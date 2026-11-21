import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.assignment_log import get_assignment_log
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


PASSWORD = "Secreta123"
COMPANY = "company-a"
OTHER_COMPANY = "company-b"


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()


def _user(role: str, email: str, company: str | None = COMPANY):
    provision_role = role if role in {"tecnico", "administrador"} else "administrador"
    user = provision_user(
        name=role.title(),
        email=email,
        password=PASSWORD,
        role=provision_role,
        users=get_user_repository(),
    )
    user.role = role
    user.company_id = company
    return user


def _client(email: str, company: str | None = COMPANY):
    user = _user("administrador", email, company)
    user.role = "cliente"
    return user


def _login(user) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


def _ticket(requester_id: str, company_id: str) -> Ticket:
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Visible",
        description="Description",
        requester_id=requester_id,
        created_at=datetime.now(timezone.utc),
        company_id=company_id,
    )
    get_ticket_repository().add(ticket)
    return ticket


def test_creation_fixes_company_and_requester_and_rejects_cross_tenant_field():
    admin = _user("administrador", "admin@example.com")
    api = _login(admin)

    response = api.post(
        "/api/tickets", json={"title": "Created", "description": "Body"}
    )
    assert response.status_code == 201, response.text
    created = get_ticket_repository().find_by_id(response.json()["id"])
    assert created is not None
    assert created.company_id == COMPANY
    assert created.requester_id == admin.id

    before = len(get_ticket_repository().list_all())
    response = api.post(
        "/api/tickets",
        json={
            "title": "Created",
            "description": "Body",
            "company_id": OTHER_COMPANY,
        },
    )
    assert response.status_code == 422
    assert len(get_ticket_repository().list_all()) == before


@pytest.mark.parametrize("role", ["supervisor", "tecnico"])
def test_supervisor_and_technician_are_denied_before_invalid_body(role):
    user = _user(role, f"{role}@example.com")
    api = _login(user)
    response = api.post("/api/tickets", json={"unexpected": 1})
    assert response.status_code == 404
    assert response.json() == {"detail": "ticket not found"}


def test_comments_and_history_use_role_and_ticket_tenant_visibility():
    admin = _user("administrador", "admin@example.com")
    supervisor = _user("supervisor", "supervisor@example.com")
    client = _client("client@example.com")
    foreign = _user("administrador", "foreign@example.com", OTHER_COMPANY)
    ticket = _ticket(client.id, COMPANY)

    supervisor_api = _login(supervisor)
    assert supervisor_api.get(f"/api/tickets/{ticket.id}/comments").status_code == 200
    assert supervisor_api.post(
        f"/api/tickets/{ticket.id}/comments", json={"body": "follow-up"}
    ).status_code == 201
    assert supervisor_api.get(f"/api/tickets/{ticket.id}/history").status_code == 200

    foreign_api = _login(foreign)
    assert foreign_api.get(f"/api/tickets/{ticket.id}/comments").status_code == 404
    assert foreign_api.get(f"/api/tickets/{ticket.id}/history").status_code == 404

    client_api = _login(client)
    assert client_api.get(f"/api/tickets/{ticket.id}/comments").status_code == 200
    assert client_api.get(f"/api/tickets/{ticket.id}/history").status_code == 404
    assert client_api.post(
        f"/api/tickets/{ticket.id}/comments", json={"body": "not allowed"}
    ).status_code == 404


def test_comment_rejection_does_not_mutate_comment_history_or_ticket():
    technician = _user("tecnico", "tech@example.com")
    client = _client("client@example.com")
    ticket = _ticket(client.id, COMPANY)
    api = _login(technician)
    before = (ticket.status, len(get_ticket_comment_repository().list_by_ticket(ticket.id)))
    response = api.post(f"/api/tickets/{ticket.id}/comments", json={"body": ""})
    assert response.status_code == 404
    assert (ticket.status, len(get_ticket_comment_repository().list_by_ticket(ticket.id))) == before
