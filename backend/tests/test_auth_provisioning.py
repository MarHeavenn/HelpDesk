"""T3 (HU-03) — Alta controlada de usuarios con rol en `identity`.

Soporte de verificacion de RF-24. Verifica:

- `provision_user` crea usuarios con rol `tecnico` y `administrador`
  reutilizando las validaciones, el validador de email, el hash Argon2 y
  la unicidad de email de HU-01, sin cambiar el autorregistro ni el
  router de `identity`.
- Cualquier rol distinto de `tecnico`/`administrador` (incluidos
  `cliente`, mayusculas, acentos, espacios o valores no textuales) se
  rechaza sin crear usuario.
- El usuario creado inicia sesion real por `POST /api/auth/login` y su
  rol aparece en la sesion (`GET /api/auth/me`).
- No existe ninguna operacion publica de alta (`POST /api/auth/provision`
  responde 404).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.router import SESSION_COOKIE_NAME

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_stores():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _provision(**overrides):
    params = {
        "name": "Equipo Soporte",
        "email": "gestion@ejemplo.com",
        "password": "Secreta123",
        "role": "tecnico",
        "users": get_user_repository(),
    }
    params.update(overrides)
    return provision_user(**params)


# --- Roles admitidos: tecnico y administrador (login real) ---


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_provision_management_role_creates_user_with_real_login(role):
    user = _provision(
        name="  Equipo Soporte  ",
        email="  Gestion@Ejemplo.COM  ",
        role=role,
    )

    assert user.id
    assert user.name == "Equipo Soporte"
    assert user.email == "gestion@ejemplo.com"
    assert user.role == role
    assert user.password_hash != "Secreta123"
    assert "Secreta123" not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")

    response = client.post(
        "/api/auth/login",
        json={"email": "  GESTION@Ejemplo.COM  ", "password": "Secreta123"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "name": "Equipo Soporte",
        "email": "gestion@ejemplo.com",
        "role": role,
    }
    assert f"{SESSION_COOKIE_NAME}=" in response.headers.get("set-cookie", "")
    assert get_session_store().count() == 1

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {
        "id": user.id,
        "email": "gestion@ejemplo.com",
        "role": role,
    }


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_provision_management_role_is_visible_in_me(role):
    user = _provision(role=role)

    login = client.post(
        "/api/auth/login",
        json={"email": "gestion@ejemplo.com", "password": "Secreta123"},
    )
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    assert me.json()["role"] == role


def test_provision_password_is_hashed_intact_without_trim():
    _provision(password="  Secreta123  ")

    exact = client.post(
        "/api/auth/login",
        json={"email": "gestion@ejemplo.com", "password": "  Secreta123  "},
    )
    assert exact.status_code == 200

    get_session_store().clear()
    trimmed = client.post(
        "/api/auth/login",
        json={"email": "gestion@ejemplo.com", "password": "Secreta123"},
    )
    assert trimmed.status_code == 401


def test_provision_uses_injected_hasher_and_validator():
    class _SpyHasher:
        def __init__(self):
            self.passwords = []

        def hash(self, password):
            self.passwords.append(password)
            return "hashed-by-spy"

    class _SpyValidator:
        def __init__(self):
            self.raw_emails = []

        def validate(self, raw):
            self.raw_emails.append(raw)
            return "normalizado@ejemplo.com"

    hasher = _SpyHasher()
    validator = _SpyValidator()

    user = _provision(
        email="  CRUDO@Ejemplo.COM  ",
        hasher=hasher,
        validator=validator,
    )

    assert validator.raw_emails == ["  CRUDO@Ejemplo.COM  "]
    assert hasher.passwords == ["Secreta123"]
    assert user.email == "normalizado@ejemplo.com"
    assert user.password_hash == "hashed-by-spy"


# --- Cualquier otro rol se rechaza sin crear usuario ---


@pytest.mark.parametrize(
    "role",
    [
        "cliente",
        "Tecnico",
        "TECNICO",
        "técnico",
        "TÉCNICO",
        "administrador ",
        " Administrador",
        "admin",
        "soporte",
        "",
        None,
        123,
        ["tecnico"],
    ],
)
def test_provision_rejects_any_other_role_without_creating_user(role):
    with pytest.raises(ValueError):
        _provision(role=role)

    assert get_user_repository().count() == 0


# --- Reutilizacion de las validaciones de HU-01 ---


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "A"),
        ("name", "   "),
        ("name", ""),
        ("name", "n" * 101),
        ("email", ""),
        ("email", "no-es-email"),
        ("email", "a@b"),
        ("email", "a" * 243 + "@ejemplo.com"),
        ("password", "1234567"),
        ("password", "p" * 129),
        ("password", ""),
    ],
)
def test_provision_reuses_registration_validations(field, value):
    with pytest.raises(ValueError):
        _provision(**{field: value})

    assert get_user_repository().count() == 0


# --- Unicidad de email de HU-01 (case-insensitive) ---


@pytest.mark.parametrize("duplicate", ["GESTION@EJEMPLO.COM", "Gestion@Ejemplo.Com"])
def test_provision_rejects_duplicate_email_case_insensitive(duplicate):
    first = _provision()
    assert first.email == "gestion@ejemplo.com"

    with pytest.raises(ValueError):
        _provision(email=duplicate)

    assert get_user_repository().count() == 1


def test_provision_shares_uniqueness_with_hu01_registration():
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": "compartido@ejemplo.com",
            "password": "Secreta123",
            "role": "cliente",
        },
    )
    assert registered.status_code == 201

    with pytest.raises(ValueError):
        _provision(email="  COMPARTIDO@Ejemplo.COM  ")

    assert get_user_repository().count() == 1


def test_hu01_registration_still_rejects_provisioned_email_with_409():
    _provision(email="compartido@ejemplo.com")

    response = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": "COMPARTIDO@Ejemplo.COM",
            "password": "Secreta123",
            "role": "cliente",
        },
    )

    assert response.status_code == 409
    assert "detail" in response.json()
    assert get_user_repository().count() == 1


# --- Sin operacion publica de alta ---


def test_provision_has_no_public_endpoint():
    response = client.post(
        "/api/auth/provision",
        json={
            "name": "Equipo Soporte",
            "email": "gestion@ejemplo.com",
            "password": "Secreta123",
            "role": "tecnico",
        },
    )

    assert response.status_code == 404
    assert get_user_repository().count() == 0

    paths = {getattr(route, "path", "") for route in app.routes}
    assert not [path for path in paths if "provision" in path]


def test_public_registration_still_only_accepts_cliente():
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Equipo Soporte",
            "email": "gestion@ejemplo.com",
            "password": "Secreta123",
            "role": "tecnico",
        },
    )

    assert response.status_code == 422
    assert get_user_repository().count() == 0
