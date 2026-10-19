"""T7 — Aislamiento entre usuarios y estado en el alcance de HU-02. (RF-14, RF-19, RF-20)

Verifica de extremo a extremo (por HTTP, sin insertar en el repositorio):
- RF-20 y RF-14: con **dos usuarios y dos sesiones simultaneas**, el
  listado y el detalle de cada uno solo alcanzan sus propios tickets y
  ninguno aparece en los del otro; el detalle ajeno devuelve 404 en ambos
  sentidos y sin filtrar contenido ajeno.
- RF-14 y RF-12.4: enviar `requester_id` (y los demas campos reservados)
  en el cuerpo de la creacion da 422 **sin crear ticket** (el repositorio
  no crece).
- RF-19: en el alcance de HU-02, tras crear, listar y consultar
  repetidamente, el `status` de un ticket existente sigue siendo
  `Abierto`: las operaciones de esta historia no lo modifican. HU-03
  hace el estado modificable para tecnicos y administradores, asi que la
  inmutabilidad ya no es global; aqui solo se afirma el alcance de HU-02.

El barrido final RF-11 a RF-20 y el mapa RF->test son de T8.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.domain.entities import OPEN_STATUS
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

# Dos clientes independientes: cada uno con su propia sesion (cookies).
client_a = TestClient(app)
client_b = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client_a.cookies.clear()
    client_b.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client_a.cookies.clear()
    client_b.cookies.clear()


def _register_and_login(client, email):
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Usuario de prueba",
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


def _create(client, title, description):
    response = client.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


# --- RF-14, RF-20: aislamiento con dos sesiones simultaneas ---


def test_two_simultaneous_sessions_are_isolated_both_directions():
    user_a = _register_and_login(client_a, "ana@ejemplo.com")
    user_b = _register_and_login(client_b, "bruno@ejemplo.com")
    assert user_a["id"] != user_b["id"]

    ticket_a = _create(client_a, "Ticket de Ana", "contenido exclusivo de Ana")
    ticket_b = _create(client_b, "Ticket de Bruno", "contenido exclusivo de Bruno")

    # Listado: cada uno ve unicamente su ticket.
    list_a = client_a.get("/api/tickets").json()
    list_b = client_b.get("/api/tickets").json()
    assert [item["id"] for item in list_a] == [ticket_a["id"]]
    assert [item["id"] for item in list_b] == [ticket_b["id"]]
    assert ticket_b["id"] not in {item["id"] for item in list_a}
    assert ticket_a["id"] not in {item["id"] for item in list_b}

    # Detalle propio: 200 con el solicitante de la sesion correcta.
    own_a = client_a.get(f"/api/tickets/{ticket_a['id']}")
    own_b = client_b.get(f"/api/tickets/{ticket_b['id']}")
    assert own_a.status_code == 200
    assert own_b.status_code == 200
    assert own_a.json()["requester_id"] == user_a["id"]
    assert own_b.json()["requester_id"] == user_b["id"]

    # Detalle ajeno: 404 en ambos sentidos y sin filtrar contenido ajeno.
    cross_a = client_a.get(f"/api/tickets/{ticket_b['id']}")
    cross_b = client_b.get(f"/api/tickets/{ticket_a['id']}")
    assert cross_a.status_code == 404
    assert cross_b.status_code == 404
    assert "contenido exclusivo de Bruno" not in cross_a.text
    assert "Ticket de Bruno" not in cross_a.text
    assert "contenido exclusivo de Ana" not in cross_b.text
    assert "Ticket de Ana" not in cross_b.text


# --- RF-14 y RF-12.4: campos reservados en el cuerpo -> 422 sin crear ---


@pytest.mark.parametrize(
    "reserved",
    [
        {"requester_id": "00000000-0000-0000-0000-000000000000"},
        {"status": "Cerrado"},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2026-10-17T12:00:00+00:00"},
        {"priority": "alta"},
        {"assignee": "tecnico-1"},
    ],
    ids=["requester_id", "status", "id", "created_at", "priority", "assignee"],
)
def test_reserved_fields_are_rejected_without_growing_the_repository(reserved):
    _register_and_login(client_a, "ana@ejemplo.com")
    _create(client_a, "Ticket base", "descripcion base")
    assert get_ticket_repository().count() == 1

    response = client_a.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion", **reserved},
    )

    assert response.status_code == 422
    assert get_ticket_repository().count() == 1  # no crecio: no se creo ticket


def test_requester_id_from_body_never_becomes_the_owner():
    user_a = _register_and_login(client_a, "ana@ejemplo.com")
    user_b = _register_and_login(client_b, "bruno@ejemplo.com")

    response = client_a.post(
        "/api/tickets",
        json={
            "title": "Titulo",
            "description": "Descripcion",
            "requester_id": user_b["id"],
        },
    )

    assert response.status_code == 422
    assert get_ticket_repository().count() == 0
    assert get_ticket_repository().list_by_requester(user_b["id"]) == []


# --- RF-19: el estado permanece Abierto con las operaciones de HU-02 ---


def test_status_stays_open_after_repeated_hu02_operations():
    _register_and_login(client_a, "ana@ejemplo.com")
    created = _create(client_a, "Titulo", "Descripcion")
    assert created["status"] == "Abierto"

    for _ in range(3):
        assert client_a.get("/api/tickets").status_code == 200
        detail = client_a.get(f"/api/tickets/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "Abierto"
        # Nuevas creaciones no alteran el estado del ticket existente.
        _create(client_a, "Otro titulo", "Otra descripcion")

    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    assert stored.status == "Abierto"
    assert stored.status == OPEN_STATUS
    assert client_a.get(f"/api/tickets/{created['id']}").json()["status"] == "Abierto"


def test_hu02_paths_keep_only_creation_and_consultation():
    paths = app.openapi()["paths"]

    # Las rutas de HU-02 solo definen creacion y consulta. HU-03 anade la
    # modificacion como subrecursos aparte (/priority y /status), fuera de
    # estas dos entradas de OpenAPI.
    assert set(paths["/api/tickets"]) == {"get", "post"}
    assert set(paths["/api/tickets/{ticket_id}"]) == {"get"}
