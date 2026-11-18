"""T4 - Flujo completo de alertas de SLA (HU-16, RF-156 a RF-161).

Recorre el recorrido real: el cliente crea el ticket, el administrador lo
asigna y le fija prioridad, el ticket envejece hasta la ventana de riesgo,
el administrador consulta y recibe la alerta; al incumplirse el SLA llega
una segunda alerta distinta; al resolverlo no se generan mas avisos y las
alertas anteriores se conservan.
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
    get_sla_policy_repository().reset()


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
    response = api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return api


def _notifications(api: TestClient) -> list[dict]:
    response = api.get("/api/notifications")
    assert response.status_code == 200, response.text
    return response.json()


def _age_ticket(ticket_id: str, minutes: int) -> None:
    ticket = get_ticket_repository().find_by_id(ticket_id)
    ticket.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)


def _sla_alerts(notifications: list[dict]) -> list[dict]:
    return [
        notification
        for notification in notifications
        if notification["type"].startswith("sla_")
    ]


def test_sla_alert_flow_from_near_due_to_breached_and_resolution():
    admin = _user("administrador", "admin@example.com", "Ana Admin")
    technician = _user("tecnico", "tech@example.com", "Tomas Tecnico")
    client = _user("cliente", "client@example.com", "Carla Cliente")
    admin_api = _login(admin.email)
    client_api = _login(client.email)

    created = client_api.post(
        "/api/tickets",
        json={"title": "No puedo entrar", "description": "Descripcion"},
    )
    assert created.status_code == 201, created.text
    ticket = created.json()

    assigned = admin_api.put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )
    assert assigned.status_code == 200, assigned.text
    priority = admin_api.put(
        f"/api/tickets/{ticket['id']}/priority",
        json={"priority": "Crítica"},
    )
    assert priority.status_code == 200, priority.text

    _age_ticket(ticket["id"], 110)
    near = _sla_alerts(_notifications(admin_api))

    assert {notification["type"] for notification in near} == {
        "sla_near_due"
    }
    assert {notification["recipient"]["id"] for notification in near} == {
        admin.id,
        technician.id,
    }

    _age_ticket(ticket["id"], 130)
    after_breach = _sla_alerts(_notifications(admin_api))

    assert len(after_breach) == 4
    assert {
        notification["type"] for notification in after_breach
    } == {"sla_near_due", "sla_breached"}
    assert len({notification["new_value"] for notification in after_breach}) == 2

    in_progress = admin_api.put(
        f"/api/tickets/{ticket['id']}/status",
        json={"status": "En progreso"},
    )
    assert in_progress.status_code == 200, in_progress.text
    resolved = admin_api.put(
        f"/api/tickets/{ticket['id']}/status",
        json={"status": "Resuelto"},
    )
    assert resolved.status_code == 200, resolved.text
    after_resolution = _sla_alerts(_notifications(admin_api))

    assert after_resolution == after_breach

    technician_api = _login(technician.email)
    technician_alerts = _sla_alerts(_notifications(technician_api))

    assert len(technician_alerts) == 2
    assert {
        notification["recipient"]["id"] for notification in technician_alerts
    } == {technician.id}
