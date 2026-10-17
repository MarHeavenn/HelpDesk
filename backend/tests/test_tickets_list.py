"""T4 — GET /api/tickets (listado). (RF-15, RF-18, RF-20)

Verifica:
- RF-15: el listado responde 200 con **solo** los tickets del usuario
  autenticado, ordenados por `created_at` descendente, con un resumen por
  ticket de exactamente `{id, title, status, created_at}` (sin
  `description` ni `requester_id`).
- RF-15: sin tickets devuelve `[]`; los parametros de consulta
  desconocidos (`?status=Abierto&page=2`) se ignoran en silencio (mismo
  resultado y sin error).
- RF-18: sin sesion valida la respuesta es 401.

Los empates de `created_at` no fijan orden: la prueba de orden fija
instantes distintos. El aislamiento completo con dos sesiones simultaneas
es de T7 y no se adelanta aqui.
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


# --- RF-15: sin tickets -> 200 con lista vacia ---


def test_list_without_tickets_returns_200_with_empty_list():
    _register_and_login()

    response = client.get("/api/tickets")

    assert response.status_code == 200
    assert response.json() == []


# --- RF-15 y RF-20: solo los propios, con resumen sin description ---


def test_list_returns_only_own_tickets_with_summary_fields():
    user = _register_and_login()
    first = _create("Primero", "descripcion uno")
    second = _create("Segundo", "descripcion dos")

    # Ticket de otro solicitante, insertado por el contrato publico del
    # repositorio: no debe aparecer en el listado.
    ajeno = Ticket(
        id=str(uuid.uuid4()),
        title="Ajeno",
        description="no debe aparecer",
        requester_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
    )
    get_ticket_repository().add(ajeno)

    response = client.get("/api/tickets")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    ids = {item["id"] for item in items}
    assert ids == {first["id"], second["id"]}
    assert ajeno.id not in ids
    for item in items:
        assert set(item) == {"id", "title", "status", "created_at"}
        assert "description" not in item
        assert "requester_id" not in item
        assert item["status"] == "Abierto"


# --- RF-15: orden por created_at descendente (instantes distintos) ---


def test_list_is_ordered_by_created_at_descending():
    user = _register_and_login()
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
    repo = get_ticket_repository()
    for minutes in (0, 5, 10):
        repo.add(
            Ticket(
                id=f"t-{minutes}",
                title=f"Titulo {minutes}",
                description="descripcion",
                requester_id=user["id"],
                created_at=base + timedelta(minutes=minutes),
            )
        )

    items = client.get("/api/tickets").json()

    assert [item["id"] for item in items] == ["t-10", "t-5", "t-0"]
    assert [item["created_at"] for item in items] == [
        (base + timedelta(minutes=10)).isoformat(),
        (base + timedelta(minutes=5)).isoformat(),
        base.isoformat(),
    ]


# --- RF-15: parametros de consulta desconocidos ignorados ---


def test_unknown_query_parameters_are_ignored():
    _register_and_login()
    created = _create("Titulo", "Descripcion")

    plain = client.get("/api/tickets")
    with_params = client.get("/api/tickets?status=Abierto&page=2")

    assert with_params.status_code == 200
    assert with_params.json() == plain.json()
    assert [item["id"] for item in with_params.json()] == [created["id"]]


# --- RF-18: sin sesion valida -> 401 ---


def test_list_without_session_returns_401():
    response = client.get("/api/tickets")

    assert response.status_code == 401
    assert "detail" in response.json()
