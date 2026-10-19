"""HU-04 T3 — contrato de `identity` para tecnicos (RF-31, RF-39.3).

Verifica los servicios de aplicacion, todavia sin endpoint publico:

- `list_technicians` solo admite al rol `administrador`, devuelve los
  usuarios con rol `tecnico` como vistas `{id, name}` (sin correo, hash
  ni rol), admite una coleccion vacia y lanza
  `TechniciansAccessDeniedError` para cliente y tecnico.
- `find_technician` devuelve la vista del tecnico o `None` (inexistente,
  cliente, administrador o identificador no textual), sin distinguir
  entre esos casos ni revelar si el usuario existe.
- `get_technician_summary` resuelve contra el repositorio compartido de
  `identity` y devuelve la misma vista, sin exponer `User` ni sus
  estructuras internas.

Usuarios preparados con `provision_user` (tecnico/administrador), el
registro real de HU-01 (cliente) y login real por `POST /api/auth/login`.
"""

import os
import sys
import uuid
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.application.technicians import (
    TechnicianSummary,
    TechniciansAccessDeniedError,
    find_technician,
    list_technicians,
)
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.technicians_contract import (
    get_technician_summary,
)

client = TestClient(app)
PASSWORD = "Secreta123"


@pytest.fixture(autouse=True)
def clean_stores():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


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


def _login(email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    return me.json()


# --- list_technicians: directorio solo para administradores ---


def test_list_technicians_returns_only_technicians_as_id_and_name():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    first = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    second = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    actor = _login(admin["email"])

    technicians = list_technicians(actor["role"], get_user_repository())

    assert {item.id for item in technicians} == {first["id"], second["id"]}
    assert {item.name for item in technicians} == {
        "Tecnico Uno",
        "Tecnico Dos",
    }
    for item in technicians:
        assert type(item) is TechnicianSummary
        assert set(asdict(item)) == {"id", "name"}
        assert not hasattr(item, "email")
        assert not hasattr(item, "password_hash")
        assert not hasattr(item, "role")
    rendered = str(technicians)
    assert "@ejemplo.com" not in rendered
    assert "$argon2" not in rendered
    assert registered["id"] not in {item.id for item in technicians}
    assert admin["id"] not in {item.id for item in technicians}


def test_list_technicians_returns_empty_collection_when_no_technicians():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _register_client("Cliente Uno", "cliente@ejemplo.com")

    actor = _login(admin["email"])

    assert list_technicians(actor["role"], get_user_repository()) == []


def test_list_technicians_accepts_an_empty_repository():
    assert list_technicians("administrador", get_user_repository()) == []


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_list_technicians_denies_client_and_technician(role):
    if role == "cliente":
        _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
        actor_user = _register_client("Cliente Uno", "cliente@ejemplo.com")
    else:
        actor_user = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    actor = _login(actor_user["email"])
    assert actor["role"] == role

    with pytest.raises(TechniciansAccessDeniedError):
        list_technicians(actor["role"], get_user_repository())


# --- find_technician: vista id + nombre o None uniforme ---


def test_find_technician_returns_summary_of_existing_technician():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _register_client("Cliente Uno", "cliente@ejemplo.com")

    actor = _login(technician["email"])
    assert actor["id"] == technician["id"]

    found = find_technician(actor["id"], get_user_repository())

    assert type(found) is TechnicianSummary
    assert asdict(found) == {"id": technician["id"], "name": "Tecnico Uno"}


def test_find_technician_returns_none_for_unknown_client_or_administrator():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    for candidate in (str(uuid.uuid4()), registered["id"], admin["id"]):
        assert find_technician(candidate, get_user_repository()) is None


@pytest.mark.parametrize(
    "candidate",
    [None, 123, 1.5, True, ["id"], {"id": "x"}, b"id", object()],
)
def test_find_technician_returns_none_for_non_textual_identifier(candidate):
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    assert find_technician(candidate, get_user_repository()) is None


# --- get_technician_summary: frontera contra el repositorio compartido ---


def test_get_technician_summary_resolves_against_shared_repository():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    actor = _login(technician["email"])

    summary = get_technician_summary(actor["id"])

    assert type(summary) is TechnicianSummary
    assert asdict(summary) == {"id": technician["id"], "name": "Tecnico Uno"}
    assert "@ejemplo.com" not in str(summary)
    assert "$argon2" not in str(summary)


def test_get_technician_summary_returns_none_for_unknown_client_or_admin():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    for candidate in (str(uuid.uuid4()), registered["id"], admin["id"]):
        assert get_technician_summary(candidate) is None


@pytest.mark.parametrize(
    "candidate",
    [None, 123, 1.5, True, ["id"], {"id": "x"}, b"id", object()],
)
def test_get_technician_summary_returns_none_for_non_textual(candidate):
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    assert get_technician_summary(candidate) is None
