"""T5 — GET /api/tickets/{ticket_id} (detalle). (RF-16 y HU-06)

Verifica:
- RF-16 y RF-54 (HU-06): el detalle de un ticket propio responde 200 con
  **exactamente** `{id, title, description, priority, status, assignee,
  requester, sla, created_at, resolved_at, requester_id}`, con los valores
  almacenados (titulo y descripcion ya recortados al crear), `priority`
  sin fijar (`null`, contrato ampliado por HU-03), `assignee` vacio
  (`null`, contrato ampliado por HU-04), `sla` nulo sin prioridad (HU-05),
  `status` igual al valor almacenado (`Abierto`), `resolved_at` nulo y
  `created_at` en ISO 8601 con offset UTC (`+00:00`, microsegundos).
- RF-53 y RF-59 (HU-06): `requester` expone `{id, name, email}` del
  solicitante, pero nunca su rol, contrasena, hash, token ni sesion.

El camino de error (404 unificado: inexistente, ajeno o formato invalido),
la precedencia 401>404 y la visibilidad de tecnico/administrador son de
HU-06 y se cubren en `test_ticket_detail_visibility.py`.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()


def _register_and_login(email="ana@ejemplo.com"):
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": "Secreta123",
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    logged = client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert logged.status_code == 200
    return registered.json()


def _create(title, description):
    response = client.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


# --- RF-16: detalle de un ticket propio -> 200 con los ocho campos ---


def test_detail_of_own_ticket_returns_200_with_full_ticket():
    user = _register_and_login()
    created = _create("  Mi titulo  ", "  Mi descripcion  ")

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "title",
        "description",
        "priority",
        "status",
        "assignee",
        "requester",
        "sla",
        "created_at",
        "resolved_at",
        "requester_id",
    }
    assert body["id"] == created["id"]
    # Valores almacenados (recortados ya al crear).
    assert body["title"] == "Mi titulo"
    assert body["description"] == "Mi descripcion"
    assert body["priority"] is None
    assert body["status"] == "Abierto"
    assert body["assignee"] is None
    assert body["sla"] is None
    assert body["resolved_at"] is None
    assert body["requester_id"] == user["id"]
    assert body["requester"] == {
        "id": user["id"],
        "name": "Ana Perez",
        "email": "ana@ejemplo.com",
    }
    assert '"assignee":null' in response.text
    # Misma representacion de created_at que la creacion: ISO 8601 + UTC.
    assert body["created_at"] == created["created_at"]
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert body["created_at"].endswith("+00:00")


# --- HU-06 RF-59: datos del solicitante sin credenciales ni rol ---


def test_detail_exposes_requester_but_never_credentials_or_role():
    user = _register_and_login()
    created = _create("Titulo", "Descripcion")

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    # `requester` solo lleva identificador, nombre y correo.
    assert set(body["requester"]) == {"id", "name", "email"}
    assert body["requester"]["id"] == user["id"]
    assert body["requester"]["email"] == user["email"]
    # Ni claves prohibidas en el cuerpo...
    for forbidden in (
        "role",
        "password",
        "password_hash",
        "hash",
        "token",
        "session",
    ):
        assert forbidden not in body
    # ...ni valores con forma de credencial en el cuerpo crudo.
    raw = response.text
    assert "$argon2" not in raw  # ningun hash de contrasena
    assert "Secreta123" not in raw  # ningun valor de contrasena
    assert '"role"' not in raw  # ningun rol
    # El nombre y el correo solo aparecen dentro de `requester`.
    assert raw.count('"email"') == 1
    assert raw.count('"name"') == 1


# --- RF-15 (regla de consulta): parametros desconocidos ignorados ---


def test_detail_ignores_unknown_query_params():
    _register_and_login()
    created = _create("Titulo", "Descripcion")

    plain = client.get(f"/api/tickets/{created['id']}")
    with_params = client.get(f"/api/tickets/{created['id']}?status=Abierto&page=2")

    assert plain.status_code == 200
    assert with_params.status_code == 200
    assert with_params.json() == plain.json()


# --- RF-16: status y created_at son los valores almacenados ---


def test_detail_returns_stored_status_and_created_at():
    user = _register_and_login()
    instant = datetime(2026, 10, 17, 8, 30, 15, 123456, tzinfo=timezone.utc)
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo almacenado",
        description="Descripcion almacenada",
        requester_id=user["id"],
        created_at=instant,
        status="Abierto",
    )
    get_ticket_repository().add(ticket)

    body = client.get(f"/api/tickets/{ticket.id}").json()

    assert body["status"] == "Abierto"
    assert body["assignee"] is None
    assert body["created_at"] == instant.isoformat()
    assert body["created_at"] == "2026-10-17T08:30:15.123456+00:00"
    assert body["title"] == "Titulo almacenado"
    assert body["description"] == "Descripcion almacenada"
    assert body["requester_id"] == user["id"]
