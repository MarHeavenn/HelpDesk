"""HU-06 T1 — contrato de `identity` para el solicitante (RF-53).

Verifica los servicios de aplicacion, sin endpoint publico propio:

- `find_user_summary` resuelve cualquier usuario existente (cliente,
  tecnico o administrador) como vista `{id, name, email}`, sin filtrar
  por rol, y refleja el valor vigente del repositorio (sin cache).
- Un identificador inexistente o no textual devuelve `None`, sin
  distinguir entre esos casos ni revelar si el usuario existe.
- La vista no expone rol, hash, contrasena ni otras credenciales.
- `get_user_summary` resuelve contra el repositorio compartido de
  `identity`, con el mismo contrato.

Usuarios preparados con `provision_user` (tecnico/administrador) y el
registro real de HU-01 (cliente).
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
from app.modules.identity.application.user_summaries import (
    UserSummary,
    find_user_summary,
)
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.users_contract import get_user_summary

PASSWORD = "Secreta123"

client = TestClient(app)


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


# --- find_user_summary: cualquier rol, vista id + nombre + correo ---


def test_find_user_summary_resolves_users_of_any_role():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    summaries = {
        user["id"]: find_user_summary(user["id"], get_user_repository())
        for user in (admin, technician, registered)
    }

    assert set(summaries) == {admin["id"], technician["id"], registered["id"]}
    for user in (admin, technician, registered):
        summary = summaries[user["id"]]
        assert type(summary) is UserSummary
        assert asdict(summary) == {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        }
        # Ni rol ni credenciales en la vista.
        assert not hasattr(summary, "role")
        assert not hasattr(summary, "password_hash")
        assert "$argon2" not in repr(summary)
        assert "password" not in repr(summary)


def test_find_user_summary_reflects_the_current_stored_value():
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")
    stored = get_user_repository().find_by_id(registered["id"])
    stored.name = "Cliente Actualizado"

    summary = find_user_summary(registered["id"], get_user_repository())

    assert summary is not None
    assert summary.name == "Cliente Actualizado"


def test_find_user_summary_returns_none_for_unknown_identifier():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    assert find_user_summary(str(uuid.uuid4()), get_user_repository()) is None


@pytest.mark.parametrize(
    "candidate",
    [None, 123, 1.5, True, ["id"], {"id": "x"}, b"id", object()],
)
def test_find_user_summary_returns_none_for_non_textual(candidate):
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    assert find_user_summary(candidate, get_user_repository()) is None


# --- get_user_summary: contrato contra el repositorio compartido ---


def test_get_user_summary_resolves_against_the_shared_repository():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    registered = _register_client("Cliente Uno", "cliente@ejemplo.com")

    technician_summary = get_user_summary(technician["id"])
    client_summary = get_user_summary(registered["id"])

    assert type(technician_summary) is UserSummary
    assert asdict(technician_summary) == {
        "id": technician["id"],
        "name": "Tecnico Uno",
        "email": "tec@ejemplo.com",
    }
    assert type(client_summary) is UserSummary
    assert asdict(client_summary) == {
        "id": registered["id"],
        "name": "Cliente Uno",
        "email": "cliente@ejemplo.com",
    }


def test_get_user_summary_returns_none_for_unknown_or_non_textual():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    for candidate in (str(uuid.uuid4()), None, 123, {"id": "x"}):
        assert get_user_summary(candidate) is None
