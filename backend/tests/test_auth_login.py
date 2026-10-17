"""T5 — POST /api/auth/login (RF-5, RF-6).

Verifica:
- RF-5: login con email con espacios/mayusculas y contrasena correcta
  responde 200 con {id, name, email, role} (sin contrasena ni hash)
  e inicia sesion (cookie + sesion almacenada); la contrasena se
  respeta intacta (sin trim, sensible a mayusculas).
- RF-6: solicitudes estructuralmente invalidas o con campos extra
  responden 422 sin comprobar credenciales; email no registrado y
  contrasena incorrecta responden 401 con el mismo mensaje generico
  identico (sin revelar si el correo existe).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.login import INVALID_CREDENTIALS_MESSAGE
from app.modules.identity.infrastructure.password_hasher import (
    Argon2PasswordHasher,
)
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.router import SESSION_COOKIE_NAME
import pytest

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_stores():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _register(
    name="Ana Perez", email="ana@ejemplo.com", password="Secreta123"
):
    response = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": "cliente",
        },
    )
    assert response.status_code == 201
    return response.json()


# --- RF-5: camino feliz con normalizacion ---


def test_login_with_spaces_and_uppercase_email_returns_200_with_session():
    registered = _register()

    response = client.post(
        "/api/auth/login",
        json={"email": "  ANA@Ejemplo.COM  ", "password": "Secreta123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == registered["id"]
    assert body["name"] == "Ana Perez"
    assert body["email"] == "ana@ejemplo.com"
    assert body["role"] == "cliente"
    assert set(body.keys()) == {"id", "name", "email", "role"}
    assert "password" not in body
    assert "password_hash" not in body
    assert "hash" not in "".join(body.keys()).lower()
    # Sesion iniciada: cookie de sesion + sesion almacenada.
    set_cookie = response.headers.get("set-cookie", "")
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie
    assert get_session_store().count() == 1


def test_login_password_is_used_intact_without_trim_nor_case_folding():
    _register(password="  Secreta123  ")

    ok = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": "  Secreta123  "},
    )
    assert ok.status_code == 200

    get_session_store().clear()
    trimmed = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": "Secreta123"},
    )
    assert trimmed.status_code == 401
    assert trimmed.json() == {"detail": INVALID_CREDENTIALS_MESSAGE}

    altered_case = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": "  secreta123  "},
    )
    assert altered_case.status_code == 401
    assert altered_case.json() == {"detail": INVALID_CREDENTIALS_MESSAGE}


# --- RF-6: 422 estructural sin comprobar credenciales ---


@pytest.mark.parametrize(
    "payload",
    [
        # Campos ausentes.
        {"password": "Secreta123"},
        {"email": "ana@ejemplo.com"},
        {},
        # Email malformado o fuera de limites.
        {"email": "no-es-email", "password": "Secreta123"},
        {"email": "", "password": "Secreta123"},
        {"email": "a" * 243 + "@ejemplo.com", "password": "Secreta123"},
        # Contrasena fuera de 8-128.
        {"email": "ana@ejemplo.com", "password": "1234567"},
        {"email": "ana@ejemplo.com", "password": "p" * 129},
        {"email": "ana@ejemplo.com", "password": ""},
        # Campos adicionales no documentados.
        {
            "email": "ana@ejemplo.com",
            "password": "Secreta123",
            "role": "cliente",
        },
        {
            "email": "ana@ejemplo.com",
            "password": "Secreta123",
            "extra": "x",
        },
    ],
)
def test_login_structurally_invalid_returns_422_without_checking_credentials(
    monkeypatch, payload
):
    _register()
    calls = []
    original_verify = Argon2PasswordHasher.verify

    def spy(self, password_hash, password):
        calls.append((password_hash, password))
        return original_verify(self, password_hash, password)

    monkeypatch.setattr(Argon2PasswordHasher, "verify", spy)

    response = client.post("/api/auth/login", json=payload)

    assert response.status_code == 422
    assert calls == []
    assert get_session_store().count() == 0


# --- RF-6: 401 con mensaje generico identico ---


def test_login_unknown_email_and_wrong_password_return_identical_401():
    _register()

    unknown = client.post(
        "/api/auth/login",
        json={"email": "nadie@ejemplo.com", "password": "Secreta123"},
    )
    wrong_password = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": "OtraClave9"},
    )

    assert unknown.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown.json() == {"detail": INVALID_CREDENTIALS_MESSAGE}
    assert wrong_password.json() == {"detail": INVALID_CREDENTIALS_MESSAGE}
    assert (
        unknown.json()["detail"] == wrong_password.json()["detail"]
    )
    # Ningun intento fallido crea sesion ni usuarios nuevos.
    assert get_session_store().count() == 0
    assert get_user_repository().count() == 1
