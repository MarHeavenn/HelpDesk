"""T5 — GET /api/tickets/{ticket_id} (detalle). (RF-16)

Verifica:
- RF-16: el detalle de un ticket propio responde 200 con **exactamente**
  `{id, title, description, status, created_at, requester_id}`, con los
  valores almacenados (titulo y descripcion ya recortados al crear),
  `status` igual al valor almacenado (`Abierto`) y `created_at` en ISO
  8601 con offset UTC (`+00:00`, microsegundos).
- RF-16: la respuesta no expone nombre, correo, rol, contrasena, hash ni
  ningun otro dato personal del solicitante; solo su identificador opaco
  (`requester_id`).

El camino de error (404 unificado: inexistente, ajeno o formato invalido)
y la precedencia 401>404 son de T6 y no se cubren aqui.
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


# --- RF-16: detalle de un ticket propio -> 200 con los seis campos ---


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
        "status",
        "created_at",
        "requester_id",
    }
    assert body["id"] == created["id"]
    # Valores almacenados (recortados ya al crear).
    assert body["title"] == "Mi titulo"
    assert body["description"] == "Mi descripcion"
    assert body["status"] == "Abierto"
    assert body["requester_id"] == user["id"]
    # Misma representacion de created_at que la creacion: ISO 8601 + UTC.
    assert body["created_at"] == created["created_at"]
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert body["created_at"].endswith("+00:00")


# --- RF-16: sin datos personales ni hash ---


def test_detail_does_not_expose_personal_data_or_hash():
    _register_and_login()
    created = _create("Titulo", "Descripcion")

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    # Ni las claves prohibidas...
    for forbidden in (
        "name",
        "email",
        "role",
        "password",
        "password_hash",
        "hash",
        "token",
        "session",
        "requester",  # solo el identificador opaco, no un objeto anidado
    ):
        assert forbidden not in body
    assert "requester_id" in body

    # ...ni ningun valor con forma de dato personal o de hash en el cuerpo
    # crudo: un dato colado por su valor tambien debe fallar.
    raw = response.text
    assert "@" not in raw  # ningun valor con forma de correo
    assert "$argon2" not in raw  # ningun hash de contrasena
    assert "Ana Perez" not in raw  # ningun nombre
    assert "cliente" not in raw  # ningun rol
    assert "Secreta123" not in raw  # ningun valor de contrasena


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
    assert body["created_at"] == instant.isoformat()
    assert body["created_at"] == "2026-10-17T08:30:15.123456+00:00"
    assert body["title"] == "Titulo almacenado"
    assert body["description"] == "Descripcion almacenada"
    assert body["requester_id"] == user["id"]
