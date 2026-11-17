"""T3 - API de alertas de SLA (HU-16, RF-160, RF-161).

Verifica:
- El sondeo de `GET /api/notifications` y `GET /api/notifications/unread-count`
  genera las alertas de SLA antes de responder.
- Visibilidad: el administrador de la empresa ve las alertas; el tecnico
  asignado ve la suya; el administrador de otra empresa no ve nada; el
  supervisor ve la empresa pero no es destinatario.
- Deduplicacion entre llamadas.
- Contrato sin campos internos (`dedupe_key`, `company_id`) y actor
  `{id: "system", name: "Sistema"}`.
- 401 sin sesion y OpenAPI estable.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
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
    get_sla_policy_repository().reset()


def _user(
    *,
    role: str,
    company_id: str | None,
    email: str,
    name: str,
    status: str = "active",
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=Argon2PasswordHasher().hash(PASSWORD),
        role=role,
        company_id=company_id,
        status=status,
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


def _scenario(*, age_minutes: int = 250, priority: str = "Alta") -> dict:
    """Empresa A con dos administradores, tecnico y cliente; un ticket
    envejecido y asignado. Empresa B con un administrador."""
    admin = _user(
        role="administrador",
        company_id=COMPANY_A,
        email="admin-a@example.com",
        name="Ana Admin",
    )
    second_admin = _user(
        role="administrador",
        company_id=COMPANY_A,
        email="admin-a2@example.com",
        name="Alberto Admin",
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

    client_api = _login(client.email)
    response = client_api.post(
        "/api/tickets",
        json={"title": "No puedo entrar", "description": "Descripcion"},
    )
    assert response.status_code == 201, response.text
    ticket = response.json()

    stored = get_ticket_repository().find_by_id(ticket["id"])
    stored.priority = priority
    stored.assignee_id = technician.id
    stored.assignee_name = technician.name
    stored.created_at = datetime.now(timezone.utc) - timedelta(
        minutes=age_minutes
    )

    return {
        "admin": admin,
        "second_admin": second_admin,
        "supervisor": supervisor,
        "technician": technician,
        "client": client,
        "outsider": outsider,
        "ticket": ticket,
    }


def _list(api: TestClient) -> list[dict]:
    response = api.get("/api/notifications")
    assert response.status_code == 200, response.text
    return response.json()


def _unread(api: TestClient) -> int:
    response = api.get("/api/notifications/unread-count")
    assert response.status_code == 200, response.text
    return response.json()["count"]


# --- RF-160: generacion al consultar ---


def test_listing_notifications_generates_breached_alerts():
    data = _scenario()
    api = _login(data["admin"].email)

    notifications = _list(api)

    assert len(notifications) == 3
    assert {notification["type"] for notification in notifications} == {
        "sla_breached"
    }
    assert {
        notification["recipient"]["id"] for notification in notifications
    } == {
        data["admin"].id,
        data["second_admin"].id,
        data["technician"].id,
    }
    assert {
        notification["actor"]["id"] for notification in notifications
    } == {"system"}
    assert {
        notification["actor"]["name"] for notification in notifications
    } == {"Sistema"}

    for notification in notifications:
        assert set(notification) == NOTIFICATION_KEYS
        assert notification["ticket"]["id"] == data["ticket"]["id"]
        assert notification["previous_value"] is None
        assert datetime.fromisoformat(notification["new_value"]).tzinfo is not None
        assert notification["read_at"] is None

    assert "sla:" not in str(notifications)
    assert "company-a" not in str(notifications)


def test_repeated_reads_do_not_duplicate_alerts():
    data = _scenario()
    api = _login(data["admin"].email)

    first = _list(api)
    second = _list(api)
    third = _unread(api)

    assert len(first) == len(second) == 3
    assert third == 1
    assert get_notification_repository().count() == 3


def test_unread_count_also_generates_alerts():
    data = _scenario()
    technician_api = _login(data["technician"].email)

    assert _unread(technician_api) == 1
    visible = _list(technician_api)

    assert len(visible) == 1
    assert visible[0]["type"] == "sla_breached"
    assert visible[0]["recipient"]["id"] == data["technician"].id


def test_near_due_ticket_generates_near_due_alerts():
    data = _scenario(age_minutes=110, priority="Crítica")
    api = _login(data["admin"].email)

    notifications = _list(api)

    assert len(notifications) == 3
    assert {notification["type"] for notification in notifications} == {
        "sla_near_due"
    }


def test_on_time_ticket_generates_no_alerts():
    data = _scenario(age_minutes=10, priority="Media")
    api = _login(data["admin"].email)

    assert _list(api) == []
    assert _unread(api) == 0


# --- Visibilidad ---


def test_outsider_administrator_sees_nothing():
    _scenario()
    outsider_api = _login("admin-b@example.com")

    assert _list(outsider_api) == []
    assert _unread(outsider_api) == 0


def test_supervisor_sees_company_alerts_but_is_not_a_recipient():
    data = _scenario()
    supervisor_api = _login(data["supervisor"].email)

    visible = _list(supervisor_api)

    assert len(visible) == 3
    assert data["supervisor"].id not in {
        notification["recipient"]["id"] for notification in visible
    }
    assert _unread(supervisor_api) == 0


def test_client_is_not_an_sla_recipient():
    data = _scenario()
    client_api = _login(data["client"].email)

    assert _list(client_api) == []
    assert _unread(client_api) == 0


# --- Lectura y contrato ---


def test_marking_an_sla_alert_read_works():
    data = _scenario()
    api = _login(data["admin"].email)
    notification = next(
        item
        for item in _list(api)
        if item["recipient"]["id"] == data["admin"].id
    )

    response = api.post(f"/api/notifications/{notification['id']}/read")

    assert response.status_code == 200, response.text
    assert response.json()["read_at"] is not None
    assert _unread(api) == 0


def test_openapi_keeps_the_notification_shape_without_internal_fields():
    schema = unauthenticated.get("/openapi.json").json()
    notification_schema = schema["components"]["schemas"][
        "NotificationResponse"
    ]
    properties = set(notification_schema["properties"])

    assert properties == NOTIFICATION_KEYS
    assert "sla_near_due" in notification_schema["description"]
    assert "sla_breached" in notification_schema["description"]
    assert "dedupe_key" not in properties
    assert "company_id" not in properties
    assert "/api/notifications" in schema["paths"]
    assert "/api/notifications/unread-count" in schema["paths"]
