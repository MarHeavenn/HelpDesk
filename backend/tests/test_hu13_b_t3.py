from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


PASSWORD = "Secreta123"


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()


def _user(role: str, email: str, company: str):
    user = provision_user(
        name=role.title(),
        email=email,
        password=PASSWORD,
        role="administrador",
        users=get_user_repository(),
    )
    user.role = role
    user.company_id = company
    return user


def _login(user) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


def _ticket(ticket_id: str, company: str, assignee: str | None = None):
    get_ticket_repository().add(
        Ticket(
            id=ticket_id,
            title=ticket_id,
            description="description",
            requester_id="requester",
            created_at=datetime.now(timezone.utc),
            priority="Alta",
            assignee_id=assignee,
            assignee_name=assignee,
            company_id=company,
        )
    )


def test_ticket_dashboard_is_tenant_scoped_and_supervisor_includes_zero_technicians():
    supervisor = _user("supervisor", "supervisor@example.com", "company-a")
    own_technician = _user("tecnico", "own-tech@example.com", "company-a")
    zero_technician = _user("tecnico", "zero-tech@example.com", "company-a")
    foreign_technician = _user("tecnico", "foreign-tech@example.com", "company-b")
    _ticket("own", "company-a", own_technician.id)
    _ticket("foreign", "company-b", foreign_technician.id)

    response = _login(supervisor).get("/api/dashboard/tickets")

    assert response.status_code == 200
    body = response.json()
    assert body["total_tickets"] == 1
    assert {
        item["technician"]["id"]
        for item in body["by_assignee"]
        if item["technician"] is not None
    } == {own_technician.id, zero_technician.id}
    assert foreign_technician.id not in response.text


def test_sla_dashboard_is_tenant_scoped_and_supervisor_is_allowed():
    supervisor = _user("supervisor", "supervisor@example.com", "company-a")
    own_technician = _user("tecnico", "own-tech@example.com", "company-a")
    foreign_technician = _user("tecnico", "foreign-tech@example.com", "company-b")
    _ticket("own", "company-a", own_technician.id)
    _ticket("foreign", "company-b", foreign_technician.id)

    response = _login(supervisor).get("/api/dashboard/sla?days=7")

    assert response.status_code == 200
    assert response.json()["total_evaluated"] == 1


@pytest.mark.parametrize("path", ["/api/dashboard/tickets", "/api/dashboard/sla"])
def test_dashboard_remains_hidden_from_client(path):
    client = _user("cliente", "client@example.com", "company-a")

    response = _login(client).get(path)

    assert response.status_code == 404
