import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.infrastructure.assignment_log import get_assignment_log
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


PASSWORD = "Secreta123"
COMPANY_A = "company-a"
COMPANY_B = "company-b"


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_assignment_log().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_assignment_log().clear()


def _user(role, email, company):
    if role == "cliente":
        response = TestClient(app).post(
            "/api/auth/register",
            json={
                "name": "cliente user",
                "email": email,
                "password": PASSWORD,
                "role": role,
            },
        )
        assert response.status_code == 201, response.text
        user = get_user_repository().find_by_id(response.json()["id"])
        user.company_id = company
        return user
    provision_role = "administrador" if role == "supervisor" else role
    user = provision_user(
        name=f"{role} user",
        email=email,
        password=PASSWORD,
        role=provision_role,
        users=get_user_repository(),
    )
    user.role = role
    user.company_id = company
    return user


def _login(user):
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


def _ticket(client):
    response = client.post(
        "/api/tickets", json={"title": "Ticket", "description": "Description"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_and_supervisor_assign_only_active_technicians_in_ticket_tenant():
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    supervisor = _user("supervisor", "supervisor@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_A)
    own = _user("tecnico", "own@example.com", COMPANY_A)
    foreign = _user("tecnico", "foreign@example.com", COMPANY_B)
    ticket = _ticket(_login(client_user))

    for actor in (admin, supervisor):
        response = _login(actor).put(
            f"/api/tickets/{ticket['id']}/assignee",
            json={"assignee_id": own.id},
        )
        assert response.status_code == 200, response.text
        assert response.json()["assignee"]["id"] == own.id

    response = _login(admin).put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": foreign.id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "ticket not found"}


def test_assignment_rejects_malformed_uuid_as_structural_422():
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_A)
    ticket = _ticket(_login(client_user))

    response = _login(admin).put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": "not-a-uuid"},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert get_assignment_log().count() == 0


@pytest.mark.parametrize("role", ["cliente", "administrador"])
def test_unknown_or_cross_tenant_technician_is_uniform_404(role):
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_A)
    ticket = _ticket(_login(client_user))
    actor = admin if role == "administrador" else client_user

    response = _login(actor).put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": str(uuid.uuid4())},
    )

    assert response.status_code == (404 if role == "administrador" else 404)
    assert response.json() == {"detail": "ticket not found"}
    assert get_assignment_log().count() == 0


def test_inactive_or_non_technician_own_user_is_domain_422_without_mutation():
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_A)
    inactive = _user("tecnico", "inactive@example.com", COMPANY_A)
    inactive.status = "deactivated"
    non_technician = _user("supervisor", "other@example.com", COMPANY_A)
    ticket = _ticket(_login(client_user))
    actor = _login(admin)

    for candidate in (inactive, non_technician):
        before = get_ticket_repository().find_by_id(ticket["id"]).assignee_id
        response = actor.put(
            f"/api/tickets/{ticket['id']}/assignee",
            json={"assignee_id": candidate.id},
        )
        assert response.status_code == 422
        assert response.json() == {
            "detail": "assignee is not a valid technician"
        }
        assert get_ticket_repository().find_by_id(ticket["id"]).assignee_id == before
        assert get_assignment_log().count() == 0


def test_ticket_tenant_is_authoritative_even_when_requester_and_assignee_are_crossed():
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_B)
    technician = _user("tecnico", "technician@example.com", COMPANY_A)
    client = _login(client_user)
    ticket = _ticket(client)
    stored = get_ticket_repository().find_by_id(ticket["id"])
    stored.company_id = COMPANY_A

    response = _login(admin).put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )
    assert response.status_code == 200, response.text


def test_deactivating_technician_does_not_remove_existing_assignment():
    admin = _user("administrador", "admin@example.com", COMPANY_A)
    client_user = _user("cliente", "client@example.com", COMPANY_A)
    technician = _user("tecnico", "technician@example.com", COMPANY_A)
    ticket = _ticket(_login(client_user))
    actor = _login(admin)

    assigned = actor.put(
        f"/api/tickets/{ticket['id']}/assignee",
        json={"assignee_id": technician.id},
    )
    assert assigned.status_code == 200
    technician.status = "deactivated"

    stored = get_ticket_repository().find_by_id(ticket["id"])
    assert stored.assignee_id == technician.id
    assert get_assignment_log().count() == 1
