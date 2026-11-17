"""T6 - Flujo completo de notificaciones de ticket (RF-144, RF-145, RF-155).

Recorre creacion -> asignacion -> estado -> resolucion -> cierre ->
reapertura con la API real y verifica el tipo, los destinatarios y los
valores anterior/nuevo de cada aviso. Comprueba ademas que la creacion, la
prioridad, los comentarios, las repeticiones y las transiciones rechazadas
no generan notificaciones, y que consultar el centro no muta el ticket ni
su historial.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.infrastructure.assignment_log import get_assignment_log
from app.modules.tickets.infrastructure.notification_repository import (
    get_notification_repository,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

PASSWORD = "Secreta123"
COMPANY = "company-a"


@pytest.fixture(autouse=True)
def clean_state():
    _clear()
    yield
    _clear()


def _clear() -> None:
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    get_ticket_comment_repository().clear()
    get_notification_repository().clear()


def _user(role: str, email: str, name: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=Argon2PasswordHasher().hash(PASSWORD),
        role=role,
        company_id=COMPANY,
    )
    get_user_repository().add(user)
    return user


def _login(email: str) -> TestClient:
    api = TestClient(app)
    assert api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).status_code == 200
    return api


def _notifications(api: TestClient) -> list[dict]:
    response = api.get("/api/notifications")
    assert response.status_code == 200, response.text
    return response.json()


def _history(api: TestClient, ticket_id: str) -> list[dict]:
    response = api.get(f"/api/tickets/{ticket_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def test_full_lifecycle_notifies_the_requester_and_assignee_with_typed_events():
    admin = _user("administrador", "admin@example.com", "Ana Admin")
    technician = _user("tecnico", "tech@example.com", "Tomas Tecnico")
    client = _user("cliente", "client@example.com", "Carla Cliente")

    admin_api = _login(admin.email)
    technician_api = _login(technician.email)
    client_api = _login(client.email)

    created = client_api.post(
        "/api/tickets",
        json={"title": "No puedo entrar", "description": "Error al iniciar"},
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert _notifications(client_api) == []

    assigned = admin_api.put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )
    assert assigned.status_code == 200, assigned.text

    in_progress = admin_api.put(
        f"/api/tickets/{ticket['id']}/status", json={"status": "En progreso"}
    )
    assert in_progress.status_code == 200, in_progress.text

    resolved = admin_api.put(
        f"/api/tickets/{ticket['id']}/status", json={"status": "Resuelto"}
    )
    assert resolved.status_code == 200, resolved.text

    closed = admin_api.put(
        f"/api/tickets/{ticket['id']}/status", json={"status": "Cerrado"}
    )
    assert closed.status_code == 200, closed.text

    reopened = admin_api.post(f"/api/tickets/{ticket['id']}/reopen")
    assert reopened.status_code == 200, reopened.text

    for api, recipient in (
        (client_api, client.id),
        (technician_api, technician.id),
    ):
        notifications = _notifications(api)
        # Mas reciente primero: reapertura, cierre, resolucion, estado y
        # asignacion.
        assert [item["type"] for item in notifications] == [
            "ticket_reopened",
            "ticket_status_changed",
            "ticket_resolved",
            "ticket_status_changed",
            "ticket_assigned",
        ]
        assert all(item["recipient"]["id"] == recipient for item in notifications)
        assert all(item["actor"]["id"] == admin.id for item in notifications)

        values = [
            (item["previous_value"], item["new_value"]) for item in notifications
        ]
        assert values == [
            ("Cerrado", "Abierto"),
            ("Resuelto", "Cerrado"),
            ("En progreso", "Resuelto"),
            ("Abierto", "En progreso"),
            (None, technician.name),
        ]


def test_priority_comment_no_op_and_rejected_transition_do_not_notify():
    admin = _user("administrador", "admin@example.com", "Ana Admin")
    technician = _user("tecnico", "tech@example.com", "Tomas Tecnico")
    client = _user("cliente", "client@example.com", "Carla Cliente")

    admin_api = _login(admin.email)
    client_api = _login(client.email)

    ticket = client_api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    ).json()
    admin_api.put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )
    before = _notifications(client_api)
    assert len(before) == 1

    # Prioridad y comentario: sin aviso.
    assert (
        admin_api.put(
            f"/api/tickets/{ticket['id']}/priority", json={"priority": "Alta"}
        ).status_code
        == 200
    )
    assert (
        admin_api.post(
            f"/api/tickets/{ticket['id']}/comments",
            json={"body": "Comentario de seguimiento"},
        ).status_code
        == 201
    )

    # Repeticion del mismo tecnico: sin aviso.
    assert (
        admin_api.put(
            f"/api/tickets/{ticket['id']}/assignee",
            json={"assignee_id": technician.id},
        ).status_code
        == 200
    )

    # Transicion fuera del flujo: 409 y sin aviso.
    rejected = admin_api.put(
        f"/api/tickets/{ticket['id']}/status", json={"status": "Resuelto"}
    )
    assert rejected.status_code == 409

    # Mismo estado: 200 y sin aviso.
    assert (
        admin_api.put(
            f"/api/tickets/{ticket['id']}/status", json={"status": "Abierto"}
        ).status_code
        == 200
    )

    assert _notifications(client_api) == before


def test_reading_notifications_does_not_mutate_ticket_or_history():
    admin = _user("administrador", "admin@example.com", "Ana Admin")
    technician = _user("tecnico", "tech@example.com", "Tomas Tecnico")
    client = _user("cliente", "client@example.com", "Carla Cliente")

    admin_api = _login(admin.email)
    client_api = _login(client.email)

    ticket = client_api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    ).json()
    admin_api.put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )

    detail_before = client_api.get(f"/api/tickets/{ticket['id']}").json()
    history_before = _history(admin_api, ticket["id"])

    _notifications(admin_api)
    client_api.get("/api/notifications/unread-count")
    client_api.post("/api/notifications/read-all")

    assert client_api.get(f"/api/tickets/{ticket['id']}").json() == detail_before
    assert _history(admin_api, ticket["id"]) == history_before
