"""T7 — POST /api/auth/logout idempotente con invalidación efectiva (RF-8, RF-10).

Verifica:
- RF-8: con sesión activa responde 204 y la sesión anterior deja de
  ser válida (GET /api/auth/me → 401). La invalidación es efectiva
  en el servidor (sesión revocada), no solo respuesta exitosa.
- RF-8 idempotencia: repetir logout sin sesión responde igualmente
  204 sin error (excepción explícita frente al 401 de RF-7).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.router import SESSION_COOKIE_NAME

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()


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


def _login(email="ana@ejemplo.com", password="Secreta123"):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200
    token = response.cookies.get(SESSION_COOKIE_NAME)
    assert token
    return response.json(), token


def test_logout_with_active_session_returns_204_and_invalidates():
    _register()
    _, token = _login()
    assert get_session_store().find_by_token(token) is not None

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    # La sesión anterior deja de ser válida en el servidor aunque la
    # cookie siga presente: me → 401.
    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 401
    assert "detail" in me_response.json()
    # Invalidación efectiva en el servidor: sesión revocada.
    stored = get_session_store().find_by_token(token)
    assert stored is not None
    assert stored.revoked_at is not None


def test_logout_without_session_returns_204_idempotent():
    _register()

    first = client.post("/api/auth/logout")
    second = client.post("/api/auth/logout")

    assert first.status_code == 204
    assert second.status_code == 204


def test_logout_twice_after_login_second_is_still_204():
    _register()
    _login()

    first = client.post("/api/auth/logout")
    second = client.post("/api/auth/logout")

    assert first.status_code == 204
    assert second.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
