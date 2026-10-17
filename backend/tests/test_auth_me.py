"""T6 — Sesiones de servidor en cookie + GET /api/auth/me (RF-7, RF-10).

Verifica:
- RF-7: GET /api/auth/me con sesion valida responde 200 con
  {id, email, role}; sin autenticacion o con sesion invalida
  responde 401. Un recurso protegido distinto de /me (montado
  sobre la dependencia `get_current_user`, contrato hacia otros
  modulos) responde 401 sin auth.
- Expiracion: una sesion con `expires_at` pasado responde 401 en
  GET /api/auth/me y en el recurso protegido, aunque la cookie
  exista y la sesion no este revocada.
- CORS/cookie (verificable sin frontend): la app expone el
  middleware CORS con allow_credentials=True y sin comodin "*"
  con credenciales; la cookie de sesion sale con HttpOnly y la
  regla SameSite/Secure del despliegue (mismo sitio: Lax).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from app.main import ALLOWED_ORIGINS, app
from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.router import SESSION_COOKIE_NAME, router
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
    hash_token,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)

client = TestClient(app)

# Recurso protegido distinto de /me: usa la misma dependencia que
# consumiran los demas modulos (contrato del plan, seccion 2).
protected_app = FastAPI()
protected_app.include_router(router)


@protected_app.get("/api/protected")
def protected_resource(current=Depends(get_current_user)) -> dict:
    return {"ok": True, "user_id": current["id"]}


protected_client = TestClient(protected_app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    protected_client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    protected_client.cookies.clear()


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


def _expire_session(token: str) -> None:
    session = get_session_store().find_by_token(token)
    assert session is not None
    assert session.revoked_at is None
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)


# --- RF-7: GET /api/auth/me ---


def test_me_with_valid_session_returns_200_with_identity_and_role():
    registered = _register()
    _login()

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": registered["id"],
        "email": "ana@ejemplo.com",
        "role": "cliente",
    }


def test_me_without_authentication_returns_401():
    _register()

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_me_with_invalid_session_token_returns_401():
    _register()
    client.cookies.set(SESSION_COOKIE_NAME, "token-invalido")

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert "detail" in response.json()


# --- RF-7: recurso protegido distinto de /me ---


def test_protected_resource_without_auth_returns_401():
    _register()

    response = protected_client.get("/api/protected")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_protected_resource_with_valid_session_returns_200():
    registered = _register()
    _, token = _login()
    protected_client.cookies.set(SESSION_COOKIE_NAME, token)

    response = protected_client.get("/api/protected")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "user_id": registered["id"]}


# --- Expiracion: expires_at pasado -> 401 aunque haya cookie y no revoque ---


def test_expired_session_returns_401_on_me_and_protected():
    _register()
    _, token = _login()
    protected_client.cookies.set(SESSION_COOKIE_NAME, token)
    _expire_session(token)

    me_response = client.get("/api/auth/me")
    protected_response = protected_client.get("/api/protected")

    assert me_response.status_code == 401
    assert "detail" in me_response.json()
    assert protected_response.status_code == 401
    assert "detail" in protected_response.json()


# --- CORS con credenciales + atributos de la cookie ---


def _cors_options() -> dict:
    for middleware in app.user_middleware:
        if getattr(middleware, "cls", None) is CORSMiddleware:
            kwargs = getattr(middleware, "kwargs", None)
            if kwargs:
                return dict(kwargs)
            options = getattr(middleware, "options", None)
            if isinstance(options, dict):
                return dict(options)
    return {}


def test_cors_middleware_allows_credentials_without_wildcard():
    options = _cors_options()

    assert options, "la app debe exponer el middleware CORSMiddleware"
    assert options.get("allow_credentials") is True
    allow_origins = options.get("allow_origins", [])
    assert allow_origins, "CORS debe declarar origenes explicitos"
    assert "*" not in allow_origins
    assert set(ALLOWED_ORIGINS) == set(allow_origins)


def test_cors_preflight_allows_explicit_origin_with_credentials():
    response = client.options(
        "/api/auth/me",
        headers={
            "Origin": ALLOWED_ORIGINS[0],
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == ALLOWED_ORIGINS[0]
    )
    assert (
        response.headers.get("access-control-allow-credentials") == "true"
    )


def test_session_cookie_has_httponly_and_samesite_attributes():
    _register()
    response = client.post(
        "/api/auth/login",
        json={"email": "ana@ejemplo.com", "password": "Secreta123"},
    )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    # La huella almacenada sigue sin exponer el token en claro.
    stored_hashes = list(get_session_store()._by_token_hash.keys())
    assert len(stored_hashes) == 1
    assert stored_hashes[0] == hash_token(response.cookies.get("session"))
