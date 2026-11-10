"""HU-08 T4 — flujo completo del ciclo de vida (RF-71 a RF-80).

Recorre de principio a fin la atención de un ticket, integrando HU-02,
HU-03, HU-04, HU-05, HU-06, HU-07 y HU-08:

creación -> asignación -> prioridad -> `En progreso` -> comentario ->
`Resuelto` -> `En progreso` -> `Resuelto` -> `Cerrado` -> reapertura por
el administrador -> `Abierto` con las operaciones habilitadas de nuevo.

En cada punto se intercalan intentos inválidos (saltos, retrocesos no
permitidos, repetición, ticket cerrado y reapertura no autorizada) para
comprobar que el flujo no solo avanza por el camino feliz.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_reopenable_ticket import (
    TICKET_NOT_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.application.update_ticket_status import (
    INVALID_STATUS_TRANSITION_MESSAGE,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
INVALID_TRANSITION_BODY = {"detail": INVALID_STATUS_TRANSITION_MESSAGE}
CLOSED_BODY = {"detail": TICKET_CLOSED_MESSAGE}
NOT_CLOSED_BODY = {"detail": TICKET_NOT_CLOSED_MESSAGE}
NOT_FOUND_BODY = {"detail": TICKET_NOT_FOUND_MESSAGE}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()


def _provision(role: str, name: str, email: str) -> dict[str, str]:
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def _register_client(name: str, email: str) -> dict[str, str]:
    response = TestClient(app).post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(email: str) -> TestClient:
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _put_status(api: TestClient, ticket_id: str, status: str):
    return api.put(f"/api/tickets/{ticket_id}/status", json={"status": status})


def _status_records(ticket_id: str):
    return [
        (record.previous_value, record.new_value)
        for record in get_ticket_modification_log().list_by_ticket(ticket_id)
        if record.field == "status"
    ]


def test_full_lifecycle_with_reopen():
    # --- HU-02: el cliente crea el ticket ---
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = requester_api.post(
        "/api/tickets",
        json={"title": "No puedo acceder", "description": "Error al entrar"},
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]
    assert created.json()["status"] == "Abierto"
    assert created.json()["priority"] is None
    assert created.json()["sla"] is None

    # --- HU-04: el administrador asigna al técnico ---
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician_api = _login(technician["email"])
    admin_api = _login(admin["email"])
    assignment = admin_api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician["id"]},
    )
    assert assignment.status_code == 200, assignment.text

    # --- HU-03/HU-05: prioridad fija el SLA ---
    priority = technician_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Media"}
    )
    assert priority.status_code == 200, priority.text
    assert priority.json()["sla"] is not None

    # --- HU-08: saltos inválidos desde `Abierto` ---
    for target in ("Resuelto", "Cerrado"):
        invalid = _put_status(technician_api, ticket_id, target)
        assert invalid.status_code == 409, invalid.text
        assert invalid.json() == INVALID_TRANSITION_BODY
    assert get_ticket_repository().find_by_id(ticket_id).status == "Abierto"

    # --- HU-08: `Abierto` -> `En progreso` ---
    started = _put_status(technician_api, ticket_id, "En progreso")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "En progreso"
    assert started.json()["resolved_at"] is None

    # Repetir el estado no cambia ni registra.
    records_before = len(_status_records(ticket_id))
    repeated = _put_status(technician_api, ticket_id, "En progreso")
    assert repeated.status_code == 200, repeated.text
    assert len(_status_records(ticket_id)) == records_before

    # --- HU-07: seguimiento durante la atención ---
    comment = technician_api.post(
        f"/api/tickets/{ticket_id}/comments",
        json={"body": "Se revisó el acceso"},
    )
    assert comment.status_code == 201, comment.text

    # Retroceso no permitido y salto a `Cerrado`.
    for target in ("Abierto", "Cerrado"):
        invalid = _put_status(technician_api, ticket_id, target)
        assert invalid.status_code == 409, invalid.text
        assert invalid.json() == INVALID_TRANSITION_BODY

    # --- `En progreso` -> `Resuelto` ---
    resolved = _put_status(technician_api, ticket_id, "Resuelto")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved_at"] is not None

    # --- `Resuelto` -> `En progreso` (retroceso permitido) ---
    resumed = _put_status(technician_api, ticket_id, "En progreso")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["resolved_at"] is None
    assert resumed.json()["sla"]["status"] in {"en_tiempo", "en_riesgo"}

    # `Resuelto` -> `Abierto` sigue prohibido.
    resolved_again = _put_status(technician_api, ticket_id, "Resuelto")
    assert resolved_again.status_code == 200, resolved_again.text
    skipped_back = _put_status(technician_api, ticket_id, "Abierto")
    assert skipped_back.status_code == 409
    assert skipped_back.json() == INVALID_TRANSITION_BODY

    # --- `Resuelto` -> `Cerrado` conserva la resolución ---
    resolved_at = resolved_again.json()["resolved_at"]
    closed = _put_status(technician_api, ticket_id, "Cerrado")
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "Cerrado"
    assert closed.json()["resolved_at"] == resolved_at

    # --- Cerrado: inmutable para estado, comentarios y reapertura no autorizada ---
    blocked_status = _put_status(technician_api, ticket_id, "Abierto")
    assert blocked_status.status_code == 409
    assert blocked_status.json() == CLOSED_BODY
    blocked_comment = technician_api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": "Tarde"}
    )
    assert blocked_comment.status_code == 409
    assert blocked_comment.json() == CLOSED_BODY
    for api in (technician_api, requester_api):
        unauthorized = api.post(f"/api/tickets/{ticket_id}/reopen")
        assert unauthorized.status_code == 404
        assert unauthorized.json() == NOT_FOUND_BODY
    assert _put_status(technician_api, ticket_id, "Cerrado").json() == CLOSED_BODY

    # --- HU-08: el administrador reabre ---
    reopened = admin_api.post(f"/api/tickets/{ticket_id}/reopen")
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["status"] == "Abierto"
    assert body["resolved_at"] is None
    assert body["assignee"] == {"id": technician["id"], "name": "Tecnico Uno"}
    assert body["priority"] == "Media"
    assert body["requester_id"] == requester["id"]
    assert body["sla"]["started_at"] == closed.json()["sla"]["started_at"]
    assert body["sla"]["status"] in {"en_tiempo", "en_riesgo"}

    # Reabrir un ticket ya abierto responde 409.
    not_closed = admin_api.post(f"/api/tickets/{ticket_id}/reopen")
    assert not_closed.status_code == 409
    assert not_closed.json() == NOT_CLOSED_BODY

    # --- Tras reabrir: todo vuelve a estar disponible ---
    new_priority = technician_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )
    new_assignment = admin_api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician["id"]},
    )
    new_comment = technician_api.post(
        f"/api/tickets/{ticket_id}/comments",
        json={"body": "Reabierto para corregir"},
    )
    assert new_priority.status_code == 200, new_priority.text
    assert new_assignment.status_code == 200, new_assignment.text
    assert new_comment.status_code == 201, new_comment.text

    # Y el ciclo puede volver a avanzar.
    restarted = _put_status(technician_api, ticket_id, "En progreso")
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["status"] == "En progreso"

    # --- Registro acumulativo de estados ---
    assert _status_records(ticket_id) == [
        ("Abierto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "Cerrado"),
        ("Cerrado", "Abierto"),
        ("Abierto", "En progreso"),
    ]

    # --- El detalle y el historial visible reflejan el flujo ---
    detail = requester_api.get(f"/api/tickets/{ticket_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "En progreso"
    comments = requester_api.get(f"/api/tickets/{ticket_id}/comments")
    assert comments.status_code == 200
    assert [item["body"] for item in comments.json()] == [
        "Se revisó el acceso",
        "Reabierto para corregir",
    ]
