"""T4 y T6 - API del centro de notificaciones (RF-147 a RF-151, RF-154).

Verifica:
- Las cuatro rutas responden 401 sin sesion antes de un 404.
- El contrato exacto: tipos, ticket, destinatario, actor, valores, fechas y
  `read_at`, sin `company_id` ni identificadores internos.
- Visibilidad por rol y empresa (admin/supervisor todas las de su empresa;
  tecnico/cliente solo las suyas), con `[]` cuando no hay.
- Orden descendente y empates deterministas.
- Contador propio para cada rol.
- Marcar una: 200, idempotente y 404 uniforme para ajena, inexistente o
  identificador invalido.
- Marcar todas: solo propias, idempotente.
- La creacion, la prioridad y los comentarios no generan notificaciones.
- OpenAPI expone las cuatro rutas y el contrato sin campos internos.
"""

import os
import sys
import uuid
from datetime import datetime

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
COMPANY_A = "company-a"
COMPANY_B = "company-b"

NOTIFICATION_KEYS = {
    "id",
    "type",
    "ticket",
    "recipient",
    "actor",
    "previous_value",
    "new_value",
    "created_at",
    "read_at",
}

unauthenticated = TestClient(app)


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


def _user(
    *,
    role: str,
    company_id: str | None,
    email: str,
    name: str,
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=Argon2PasswordHasher().hash(PASSWORD),
        role=role,
        company_id=company_id,
    )
    get_user_repository().add(user)
    return user


def _login(email: str) -> TestClient:
    api = TestClient(app)
    response = api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return api


def _create_ticket(api: TestClient, title: str = "No puedo entrar") -> dict:
    response = api.post(
        "/api/tickets", json={"title": title, "description": "Descripcion"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assign(api: TestClient, ticket_id: str, technician_id: str) -> None:
    response = api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician_id},
    )
    assert response.status_code == 200, response.text


def _set_status(api: TestClient, ticket_id: str, status: str) -> None:
    response = api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": status}
    )
    assert response.status_code == 200, response.text


def _list(api: TestClient) -> list[dict]:
    response = api.get("/api/notifications")
    assert response.status_code == 200, response.text
    return response.json()


def _unread(api: TestClient) -> int:
    response = api.get("/api/notifications/unread-count")
    assert response.status_code == 200, response.text
    return response.json()["count"]


def _scenario() -> dict:
    """Crea empresa A con admin/supervisor/tecnico/cliente y un ticket
    asignado, mas un admin de empresa B."""
    admin = _user(
        role="administrador",
        company_id=COMPANY_A,
        email="admin-a@example.com",
        name="Ana Admin",
    )
    supervisor = _user(
        role="supervisor",
        company_id=COMPANY_A,
        email="supervisor-a@example.com",
        name="Sofia Supervisora",
    )
    technician = _user(
        role="tecnico",
        company_id=COMPANY_A,
        email="tech-a@example.com",
        name="Tomas Tecnico",
    )
    client = _user(
        role="cliente",
        company_id=COMPANY_A,
        email="client-a@example.com",
        name="Carla Cliente",
    )
    outsider = _user(
        role="administrador",
        company_id=COMPANY_B,
        email="admin-b@example.com",
        name="Beto Admin",
    )
    admin_api = _login(admin.email)
    client_api = _login(client.email)
    ticket = _create_ticket(client_api)
    _assign(admin_api, ticket["id"], technician.id)
    return {
        "admin": admin,
        "supervisor": supervisor,
        "technician": technician,
        "client": client,
        "outsider": outsider,
        "admin_api": admin_api,
        "ticket": ticket,
    }


# --- 401 primero ---


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/notifications"),
        ("get", "/api/notifications/unread-count"),
        ("post", "/api/notifications/read-all"),
        ("post", f"/api/notifications/{uuid.uuid4()}/read"),
    ],
)
def test_without_session_gets_401_before_any_404(method, path):
    response = getattr(unauthenticated, method)(path)
    assert response.status_code == 401


# --- Contrato y visibilidad ---


def test_list_returns_exact_contract_without_internal_fields():
    data = _scenario()
    notifications = _list(data["admin_api"])

    assert len(notifications) == 2
    for notification in notifications:
        assert set(notification) == NOTIFICATION_KEYS
        assert set(notification["ticket"]) == {"id", "title"}
        assert set(notification["recipient"]) == {"id", "name"}
        assert set(notification["actor"]) == {"id", "name"}
        assert notification["type"] == "ticket_assigned"
        assert notification["ticket"] == {
            "id": data["ticket"]["id"],
            "title": data["ticket"]["title"],
        }
        assert notification["actor"]["id"] == data["admin"].id
        assert notification["previous_value"] is None
        assert notification["new_value"] == data["technician"].name
        assert notification["read_at"] is None
        assert datetime.fromisoformat(notification["created_at"]).tzinfo is not None


def test_administrator_and_supervisor_see_company_notifications():
    data = _scenario()
    technician_b = _user(
        role="tecnico",
        company_id=COMPANY_B,
        email="tech-b@example.com",
        name="Teresa Tecnica",
    )
    outsider_api = _login(data["outsider"].email)
    ticket_b = _create_ticket(outsider_api)
    _assign(outsider_api, ticket_b["id"], technician_b.id)

    for email in (data["admin"].email, data["supervisor"].email):
        visible = _list(_login(email))
        assert {item["ticket"]["id"] for item in visible} == {data["ticket"]["id"]}

    assert {item["ticket"]["id"] for item in _list(outsider_api)} == {
        ticket_b["id"]
    }


def test_technician_and_client_only_see_their_own_notifications():
    data = _scenario()

    technician_notifications = _list(_login(data["technician"].email))
    client_notifications = _list(_login(data["client"].email))

    assert [item["recipient"]["id"] for item in technician_notifications] == [
        data["technician"].id
    ]
    assert [item["recipient"]["id"] for item in client_notifications] == [
        data["client"].id
    ]


def test_list_is_newest_first():
    data = _scenario()
    _set_status(data["admin_api"], data["ticket"]["id"], "En progreso")

    visible = _list(data["admin_api"])

    created = [item["created_at"] for item in visible]
    assert created == sorted(created, reverse=True)
    assert visible[0]["type"] == "ticket_status_changed"


def test_empty_list_returns_200_and_no_notifications():
    client = _user(
        role="cliente",
        company_id=COMPANY_A,
        email="lonely@example.com",
        name="Sin Avisos",
    )
    response = _login(client.email).get("/api/notifications")

    assert response.status_code == 200
    assert response.json() == []


def test_unknown_query_parameters_are_ignored():
    data = _scenario()
    admin_api = data["admin_api"]
    client_api = _login(data["client"].email)

    plain = admin_api.get("/api/notifications").json()
    assert admin_api.get("/api/notifications?foo=bar&page=2").json() == plain
    assert admin_api.get("/api/notifications/unread-count?foo=bar").json() == {
        "count": 0
    }

    notification = _list(client_api)[0]
    read = client_api.post(f"/api/notifications/{notification['id']}/read?foo=1")
    assert read.status_code == 200
    assert client_api.post("/api/notifications/read-all?foo=1").json() == {
        "updated": 0
    }


# --- Contador ---


def test_unread_count_is_personal_for_every_role():
    data = _scenario()

    assert _unread(_login(data["client"].email)) == 1
    assert _unread(_login(data["technician"].email)) == 1
    assert _unread(_login(data["admin"].email)) == 0
    assert _unread(_login(data["supervisor"].email)) == 0


# --- Marcar una ---


def test_mark_own_notification_read_is_idempotent():
    data = _scenario()
    client_api = _login(data["client"].email)
    notification = _list(client_api)[0]

    first = client_api.post(f"/api/notifications/{notification['id']}/read")
    assert first.status_code == 200, first.text
    assert first.json()["read_at"] is not None
    assert _unread(client_api) == 0

    read_at = first.json()["read_at"]
    second = client_api.post(f"/api/notifications/{notification['id']}/read")
    assert second.status_code == 200, second.text
    assert second.json()["read_at"] == read_at
    assert _unread(_login(data["technician"].email)) == 1


def test_mark_read_returns_uniform_404_for_foreign_missing_or_invalid():
    data = _scenario()
    client_api = _login(data["client"].email)
    own = _list(client_api)[0]

    admin_api = _login(data["admin"].email)
    for candidate in (own["id"], str(uuid.uuid4()), "not-a-uuid"):
        response = admin_api.post(f"/api/notifications/{candidate}/read")
        assert response.status_code == 404
        assert response.json() == {"detail": "notification not found"}

    assert _unread(client_api) == 1


# --- Marcar todas ---


def test_mark_all_read_only_affects_own_notifications():
    data = _scenario()
    client_api = _login(data["client"].email)

    response = client_api.post("/api/notifications/read-all")
    assert response.status_code == 200, response.text
    assert response.json() == {"updated": 1}

    assert _unread(client_api) == 0
    assert client_api.post("/api/notifications/read-all").json() == {"updated": 0}
    assert _unread(_login(data["technician"].email)) == 1


# --- Eventos que no notifican ---


def test_creation_priority_and_comments_do_not_notify():
    data = _scenario()
    client_api = _login(data["client"].email)
    ticket = _create_ticket(client_api, "Otro ticket")

    assert _unread(client_api) == 1  # solo el aviso de asignacion previo

    priority = data["admin_api"].put(
        f"/api/tickets/{ticket['id']}/priority", json={"priority": "Alta"}
    )
    assert priority.status_code == 200, priority.text

    comment = data["admin_api"].post(
        f"/api/tickets/{ticket['id']}/comments", json={"body": "Sigo esperando"}
    )
    assert comment.status_code == 201, comment.text

    assert _unread(client_api) == 1
    assert _unread(_login(data["admin"].email)) == 0


def test_no_op_status_change_does_not_notify():
    data = _scenario()
    before = _list(data["admin_api"])

    _set_status(data["admin_api"], data["ticket"]["id"], "Abierto")

    assert _list(data["admin_api"]) == before
    assert _unread(_login(data["client"].email)) == 1


# --- OpenAPI ---


def test_openapi_exposes_the_four_routes_and_no_internal_fields():
    schema = app.openapi()
    paths = schema["paths"]

    assert "/api/notifications" in paths
    assert "/api/notifications/unread-count" in paths
    assert "/api/notifications/read-all" in paths
    assert "/api/notifications/{notification_id}/read" in paths

    response_schema = schema["components"]["schemas"]["NotificationResponse"]
    properties = response_schema["properties"]
    assert set(properties) == NOTIFICATION_KEYS
    assert "company_id" not in properties
    assert "recipient_id" not in properties
    assert "actor_id" not in properties
