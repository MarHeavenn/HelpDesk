import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository


client = TestClient(app)


def _add_user(
    user_id: str,
    email: str,
    role: str,
    company_id: str | None,
    name: str = "Usuario Test",
) -> User:
    user = User(
        id=user_id,
        name=name,
        email=email,
        password_hash=Argon2PasswordHasher().hash("Secreta123"),
        role=role,
        company_id=company_id,
        status="active",
        invitation_status="accepted",
    )
    get_user_repository().add(user)
    return user


def _login(email: str) -> None:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert response.status_code == 200


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()


def test_users_list_returns_only_admin_tenant_and_exact_representation():
    admin = _add_user("admin-1", "admin@example.com", "administrador", "c1")
    own = _add_user("own-1", "own@example.com", "cliente", "c1")
    _add_user("foreign-1", "foreign@example.com", "cliente", "c2")
    _add_user("unassigned", "unassigned@example.com", "cliente", None)
    _login(admin.email)

    response = client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "phone": None,
            "company_id": "c1",
            "role": "administrador",
            "status": "active",
            "invitation_status": "accepted",
        },
        {
            "id": own.id,
            "name": own.name,
            "email": own.email,
            "phone": None,
            "company_id": "c1",
            "role": "cliente",
            "status": "active",
            "invitation_status": "accepted",
        },
    ]


def test_users_list_empty_and_detail_are_scoped_with_uniform_404():
    admin = _add_user("admin-1", "admin@example.com", "administrador", "c1")
    foreign = _add_user("foreign-1", "foreign@example.com", "cliente", "c2")
    unassigned = _add_user("unassigned", "unassigned@example.com", "cliente", None)
    _login(admin.email)

    response = client.get("/api/users/foreign-1")
    assert response.status_code == 404
    assert response.json() == {"detail": "user not found"}
    assert client.get(f"/api/users/{unassigned.id}").json() == {
        "detail": "user not found"
    }

    assert client.get("/api/users").status_code == 200
    assert len(client.get("/api/users").json()) == 1


def test_user_queries_require_admin_and_authentication():
    client_no_auth = TestClient(app)
    assert client_no_auth.get("/api/users").status_code == 401
    user = _add_user("client-1", "client@example.com", "cliente", "c1")
    _login(user.email)
    assert client.get("/api/users").status_code == 404
    assert client.get(f"/api/users/{user.id}").status_code == 404


def test_admin_create_fixes_tenant_and_returns_no_secret_fields():
    admin = _add_user("admin-1", "admin@example.com", "administrador", "c1")
    _login(admin.email)

    response = client.post(
        "/api/users",
        json={"name": " Nueva Persona ", "email": " NEW@example.com ", "role": "cliente"},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"user", "email_status"}
    assert body["email_status"] == "not-attempted"
    assert body["user"] == {
        "id": body["user"]["id"],
        "name": "Nueva Persona",
        "email": "new@example.com",
        "phone": None,
        "company_id": "c1",
        "role": "cliente",
        "status": "active",
        "invitation_status": "pending",
    }
    assert not any(
        secret in response.text.lower()
        for secret in ("password", "hash", "token", "secret")
    )


def test_create_rejects_non_admin_extra_company_invalid_fields_and_duplicate():
    client_user = _add_user("client-1", "client@example.com", "cliente", "c1")
    _login(client_user.email)
    assert client.post(
        "/api/users",
        json={"name": "Valid Name", "email": "new@example.com", "role": "cliente"},
    ).status_code == 404

    get_session_store().clear()
    client.cookies.clear()
    admin = _add_user("admin-1", "admin@example.com", "administrador", "c1")
    _login(admin.email)
    before = get_user_repository().count()

    extra = client.post(
        "/api/users",
        json={
            "name": "Valid Name",
            "email": "new@example.com",
            "role": "cliente",
            "company_id": "c2",
        },
    )
    assert extra.status_code == 422
    assert get_user_repository().count() == before

    invalid = client.post(
        "/api/users",
        json={"name": "x", "email": "not-an-email", "role": "nope"},
    )
    assert invalid.status_code == 422
    assert get_user_repository().count() == before

    _add_user("other", "taken@example.com", "cliente", "c2")
    duplicate = client.post(
        "/api/users",
        json={"name": "Valid Name", "email": " TAKEN@example.com ", "role": "cliente"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "correo no disponible"}
    assert get_user_repository().count() == before + 1
