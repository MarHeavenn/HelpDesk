"""HU-04 T4 — `GET /api/technicians` (RF-31).

Verifica el endpoint del directorio de tecnicos, montado en `main.py`
junto a los routers existentes:

- 200 con la coleccion de tecnicos `{id, name}` para un administrador
  autenticado, sin correo, credenciales ni rol; una coleccion vacia es
  valida.
- 401 sin sesion valida (sin cookie o con cookie invalida).
- 404 uniforme (mismo cuerpo que el contrato, `technicians not found`)
  para cliente y tecnico, sin datos en el cuerpo.
- El rol se toma siempre de la sesion (`get_current_user`), nunca de
  parametros: los parametros de consulta desconocidos se ignoran y la
  operacion no declara parametros.

Sesiones reales: administrador y tecnico por `provision_user` + login;
cliente por el registro de HU-01 + login. Un `TestClient` por rol cuando
coexisten sesiones (un cliente guarda una sola cookie).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.dependencies import SESSION_COOKIE_NAME

client = TestClient(app)
PASSWORD = "Secreta123"
TECHNICIANS_404_BODY = {"detail": "technicians not found"}


@pytest.fixture(autouse=True)
def clean_stores():
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    client.cookies.clear()


def _provision(role: str, name: str, email: str) -> dict[str, str]:
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def _register_client(name: str, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201
    return response.json()


def _login_client(email: str) -> TestClient:
    """Cliente HTTP propio con sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    me = own.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return own


# --- 200: coleccion de tecnicos para un administrador ---


def test_get_technicians_with_admin_session_returns_only_id_and_name():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    first = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    second = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    admin_client = _login_client(admin["email"])
    response = admin_client.get("/api/technicians")

    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body} == {first["id"], second["id"]}
    assert {item["name"] for item in body} == {
        "Tecnico Uno",
        "Tecnico Dos",
    }
    for item in body:
        assert set(item) == {"id", "name"}
    assert admin["id"] not in {item["id"] for item in body}
    assert registered["id"] not in {item["id"] for item in body}
    # El cuerpo crudo no expone correo ni credenciales (RF-31, RF-35.4).
    assert "@ejemplo.com" not in response.text
    assert "$argon2" not in response.text
    assert PASSWORD not in response.text


def test_get_technicians_returns_empty_collection_when_no_technicians():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _register_client("Cliente Uno", "cliente@ejemplo.com")

    admin_client = _login_client(admin["email"])
    response = admin_client.get("/api/technicians")

    assert response.status_code == 200
    assert response.json() == []


# --- 401: sin sesion valida ---


def test_get_technicians_without_session_returns_401():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    response = client.get("/api/technicians")

    assert response.status_code == 401
    assert "detail" in response.json()
    assert "tec@ejemplo.com" not in response.text


def test_get_technicians_with_invalid_session_cookie_returns_401():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    client.cookies.set(SESSION_COOKIE_NAME, "token-invalido")

    response = client.get("/api/technicians")

    assert response.status_code == 401
    assert "detail" in response.json()


# --- 404 uniforme: cliente y tecnico ---


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_get_technicians_denied_roles_get_uniform_404(role):
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    if role == "cliente":
        actor = _register_client("Cliente Uno", "cliente@ejemplo.com")
    else:
        actor = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    assert actor["role"] == role

    actor_client = _login_client(actor["email"])
    response = actor_client.get("/api/technicians")

    assert response.status_code == 404
    assert response.json() == TECHNICIANS_404_BODY
    # Sin fuga de datos del directorio ni de la sesion.
    assert "Tecnico Uno" not in response.text
    assert "tec@ejemplo.com" not in response.text
    assert "$argon2" not in response.text


def test_get_technicians_denied_roles_receive_identical_body():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    assert admin["role"] == "administrador"
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    actor_client = _login_client(admin["email"])
    assert actor_client.get("/api/technicians").status_code == 200

    technician_client = _login_client("tec@ejemplo.com")
    technician_response = technician_client.get("/api/technicians")

    _register_client("Cliente Uno", "cliente@ejemplo.com")
    client_client = _login_client("cliente@ejemplo.com")
    client_response = client_client.get("/api/technicians")

    assert technician_response.status_code == 404
    assert client_response.status_code == 404
    assert technician_response.json() == client_response.json()
    assert technician_response.content == client_response.content


# --- El rol se toma de la sesion: parametros desconocidos ignorados ---


def test_get_technicians_ignores_unknown_query_parameters():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    admin_client = _login_client(admin["email"])
    plain = admin_client.get("/api/technicians")
    noisy = admin_client.get(
        "/api/technicians",
        params={"role": "cliente", "foo": "bar", "limit": 1, "page": 2},
    )

    assert plain.status_code == 200
    assert noisy.status_code == 200
    assert noisy.json() == plain.json()
    assert noisy.json() == [{"id": technician["id"], "name": "Tecnico Uno"}]


def test_get_technicians_denies_client_with_role_like_query_parameter():
    _register_client("Cliente Uno", "cliente@ejemplo.com")
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    client_client = _login_client("cliente@ejemplo.com")
    response = client_client.get(
        "/api/technicians", params={"role": "administrador"}
    )

    assert response.status_code == 404
    assert response.json() == TECHNICIANS_404_BODY


def test_get_technicians_operation_declares_no_parameters():
    operation = app.openapi()["paths"]["/api/technicians"]["get"]

    assert operation.get("parameters", []) == []
