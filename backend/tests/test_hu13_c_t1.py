import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository


PASSWORD = "Secreta123"
COMPANY_A = "company-a"
COMPANY_B = "company-b"


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _user(role: str, email: str, company_id: str | None, *, status="active"):
    provision_role = role if role in {"tecnico", "administrador"} else "administrador"
    user = provision_user(
        name=role.title(),
        email=email,
        password=PASSWORD,
        role=provision_role,
        users=get_user_repository(),
    )
    user.role = role
    user.company_id = company_id
    user.status = status
    return user


def _login(user) -> TestClient:
    api = TestClient(app)
    response = api.post(
        "/api/auth/login", json={"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return api


def test_technician_directory_is_scoped_to_admin_and_supervisor_tenant():
    admin_a = _user("administrador", "admin-a@example.com", COMPANY_A)
    supervisor_a = _user("supervisor", "supervisor-a@example.com", COMPANY_A)
    own = _user("tecnico", "own@example.com", COMPANY_A)
    inactive = _user(
        "tecnico", "inactive@example.com", COMPANY_A, status="deactivated"
    )
    foreign = _user("tecnico", "foreign@example.com", COMPANY_B)
    _user("cliente", "client@example.com", COMPANY_A)

    for actor in (admin_a, supervisor_a):
        response = _login(actor).get("/api/technicians")
        assert response.status_code == 200
        assert response.json() == [{"id": own.id, "name": own.name}]
        assert inactive.id not in response.text
        assert foreign.id not in response.text
        assert "@example.com" not in response.text
        assert "password" not in response.text.lower()


def test_technician_directory_returns_exactly_empty_array_for_empty_tenant():
    admin_a = _user("administrador", "admin-a@example.com", COMPANY_A)
    _user("tecnico", "foreign@example.com", COMPANY_B)

    response = _login(admin_a).get("/api/technicians")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_technician_directory_uses_uniform_denial_for_other_roles(role):
    actor = _user(role, f"{role}@example.com", COMPANY_A)

    response = _login(actor).get("/api/technicians")

    assert response.status_code == 404
    assert response.json() == {"detail": "technicians not found"}


def test_technician_directory_denies_account_without_company():
    actor = _user("administrador", "admin@example.com", None)

    response = _login(actor).get("/api/technicians")

    assert response.status_code == 404
    assert response.json() == {"detail": "technicians not found"}
