"""T2 — POST /api/tickets, camino feliz (RF-11, RF-13, RF-14).

Verifica:
- RF-11: con sesion valida, crear un ticket con titulo y descripcion
  validos responde 201 con el ticket creado, estado `Abierto` y la fecha
  y hora de creacion sellada por el sistema (no fijable por el cliente).
- RF-13: el identificador devuelto es un UUID opaco y dos creaciones dan
  identificadores distintos.
- RF-14: `requester_id` es el `id` de la sesion (nunca un valor del
  cuerpo), y `title`/`description` se almacenan y devuelven recortados.
- RF-18: sin sesion valida la creacion responde 401 (la dependencia de
  identidad se resuelve antes del handler).

La matriz completa de validacion de la creacion (422, RF-12) se cubre en
T3; aqui solo se verifica el camino feliz.
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
    return client.post(
        "/api/tickets", json={"title": title, "description": description}
    )


# --- RF-11: creacion valida -> 201 con el ticket creado ---


def test_create_ticket_returns_201_with_ticket_payload():
    user = _register_and_login()

    response = _create("Titulo de prueba", "Descripcion de prueba")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {
        "id",
        "title",
        "description",
        "status",
        "created_at",
        "requester_id",
    }
    assert body["title"] == "Titulo de prueba"
    assert body["description"] == "Descripcion de prueba"
    assert body["status"] == "Abierto"
    assert body["requester_id"] == user["id"]


# --- RF-13: identificador UUID opaco y unico ---


def test_create_ticket_id_is_opaque_uuid():
    _register_and_login()

    body = _create("Titulo", "Descripcion").json()

    parsed = uuid.UUID(body["id"])  # lanza si no es un UUID valido
    assert str(parsed) == body["id"]


def test_two_creations_return_distinct_ids():
    _register_and_login()

    first = _create("Titulo", "Descripcion").json()
    second = _create("Titulo", "Descripcion").json()

    assert first["id"] != second["id"]
    assert get_ticket_repository().count() == 2


# --- RF-11: fecha y hora generada por el sistema, con zona UTC ---


def test_created_at_is_current_utc_instant():
    _register_and_login()
    before = datetime.now(timezone.utc)

    body = _create("Titulo", "Descripcion").json()

    after = datetime.now(timezone.utc)
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert body["created_at"].endswith("+00:00")
    assert before - timedelta(seconds=1) <= created_at <= after + timedelta(seconds=1)


# --- RF-14: solicitante de la sesion y valores recortados ---


def test_requester_id_comes_from_session():
    user = _register_and_login()

    body = _create("Titulo", "Descripcion").json()

    assert body["requester_id"] == user["id"]
    stored = get_ticket_repository().find_by_id(body["id"])
    assert stored is not None
    assert stored.requester_id == user["id"]


def test_title_and_description_are_stored_and_returned_trimmed():
    _register_and_login()

    body = _create("  con espacios  ", "\tcon tabulador\n").json()

    assert body["title"] == "con espacios"
    assert body["description"] == "con tabulador"
    stored = get_ticket_repository().find_by_id(body["id"])
    assert stored.title == "con espacios"
    assert stored.description == "con tabulador"


# --- RF-18: sin sesion valida -> 401 (antes del handler) ---


def test_create_ticket_without_session_returns_401():
    response = _create("Titulo", "Descripcion")

    assert response.status_code == 401
    assert "detail" in response.json()
