"""T8 — Barrido de seguridad y suite final RF-1 a RF-10.

Verifica:
- RF-9: ninguna respuesta (registro, login, /me, logout ni errores
  422/409/401) expone contrasena ni hash: ni claves `password`/`hash`
  ni el valor de la contrasena en el cuerpo crudo. Lo almacenado no
  es texto plano.
- RF-1..RF-10: mapa de cobertura final (cada RF tiene su test
  asociado; ver tabla RF_MAP y memoria del informe en tasks.md T8).

Mapa RF -> archivo de test:
- RF-1  -> test_auth_register.py (201 sin contrasena ni hash)
- RF-2  -> test_auth_register_role.py (rol no-cliente u omitido -> 422)
- RF-3  -> test_auth_register.py + test_auth_hash.py (validacion 422)
- RF-4  -> test_auth_register_duplicate.py (409 case-insensitive)
- RF-5  -> test_auth_login.py (200 + sesion, normalizacion)
- RF-6  -> test_auth_login.py (422 estructural, 401 generico identico)
- RF-7  -> test_auth_me.py (me 200/401 + recurso protegido 401)
- RF-8  -> test_auth_logout.py (204 idempotente + invalidacion)
- RF-9  -> test_auth_hash.py + este archivo (barrido de respuestas)
- RF-10 -> test_auth_me.py + este archivo (identidad/rol desde sesion)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
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

client = TestClient(app)

PASSWORD = "Secreta123"
EMAIL = "ana@ejemplo.com"


@pytest.fixture(autouse=True)
def clean_stores():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _register(email=EMAIL, password=PASSWORD):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": password,
            "role": "cliente",
        },
    )
    assert response.status_code == 201
    return response


def _assert_no_secret_leak(response):
    """Ninguna respuesta expone contrasena ni hash (RF-9)."""
    body = response.json() if response.content else {}
    if isinstance(body, dict):
        lowered_keys = "".join(body.keys()).lower()
        assert "password" not in lowered_keys
        assert "hash" not in lowered_keys
        for value in body.values():
            if isinstance(value, str):
                assert value != PASSWORD
                assert "$argon2" not in value
    assert PASSWORD not in response.text
    assert "$argon2" not in response.text


# --- RF-9: barrido de respuestas de exito ---


def test_sweep_register_200_body_exposes_no_password_or_hash():
    _assert_no_secret_leak(_register())


def test_sweep_login_200_body_exposes_no_password_or_hash():
    _register()
    response = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 200
    _assert_no_secret_leak(response)


def test_sweep_me_200_body_exposes_no_password_or_hash():
    _register()
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert set(response.json().keys()) == {"id", "email", "role"}
    _assert_no_secret_leak(response)


def test_sweep_logout_204_has_empty_body():
    _register()
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert response.content in (b"", b"null")
    assert PASSWORD not in response.text


# --- RF-9: barrido de respuestas de error ---


def test_sweep_error_responses_expose_no_password_or_hash():
    _register()
    cases = [
        client.post(
            "/api/auth/register",
            json={
                "name": "Ana Perez",
                "email": "otro@ejemplo.com",
                "password": "corto",
                "role": "cliente",
            },
        ),  # 422 RF-3
        client.post(
            "/api/auth/register",
            json={
                "name": "Ana Perez",
                "email": "ANA@EJEMPLO.COM",
                "password": PASSWORD,
                "role": "cliente",
            },
        ),  # 409 RF-4
        client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD, "extra": "x"},
        ),  # 422 RF-6
        client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "OtraClave9"},
        ),  # 401 RF-6
        client.post(
            "/api/auth/login",
            json={"email": "nadie@ejemplo.com", "password": PASSWORD},
        ),  # 401 RF-6
        client.get("/api/auth/me"),  # placeholder; se limpia cookie abajo
    ]
    assert cases[0].status_code == 422
    assert cases[1].status_code == 409
    assert cases[2].status_code == 422
    assert cases[3].status_code == 401
    assert cases[3].json() == {"detail": INVALID_CREDENTIALS_MESSAGE}
    assert cases[4].status_code == 401
    assert cases[4].json() == cases[3].json()
    for response in cases[:5]:
        _assert_no_secret_leak(response)

    client.cookies.clear()
    unauthenticated = client.get("/api/auth/me")
    assert unauthenticated.status_code == 401
    _assert_no_secret_leak(unauthenticated)


# --- RF-9: lo almacenado no es texto plano ---


def test_sweep_stored_password_is_hash_not_plaintext():
    _register()

    stored = get_user_repository().find_by_email(EMAIL)

    assert stored is not None
    assert stored.password_hash != PASSWORD
    assert PASSWORD not in stored.password_hash
    assert stored.password_hash.startswith("$argon2")
    hasher = Argon2PasswordHasher()
    assert hasher.verify(stored.password_hash, PASSWORD) is True
    assert hasher.verify(stored.password_hash, "OtraClave99") is False


# --- RF-10: identidad y rol derivados de la sesion ---


def test_sweep_identity_and_role_come_from_session():
    registered = _register()
    login_response = client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )

    me_response = client.get("/api/auth/me")

    assert login_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.json()["id"] == registered.json()["id"]
    assert me_response.json()["email"] == registered.json()["email"]
    assert me_response.json()["role"] == "cliente"
    assert login_response.json()["id"] == registered.json()["id"]
