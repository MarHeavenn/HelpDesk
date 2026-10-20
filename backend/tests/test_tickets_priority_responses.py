"""T8 (HU-03) — Prioridad en las respuestas (listado, detalle y creacion).

Mapa RF -> test:
- RF-27.2 (resumen del listado y detalle con `priority`):
  `test_list_summary_shows_priority_null_before_it_is_set`,
  `test_detail_shows_priority_null_before_it_is_set`,
  `test_list_and_detail_show_current_priority_after_it_is_set`,
  `test_list_summary_keeps_each_ticket_priority` y
  `test_list_and_detail_show_the_latest_priority`.
- RF-27.2 (prioridad no fijada como `null`, distinguible del catalogo):
  las pruebas anteriores afirman `priority is None`, `not in PRIORITIES` y
  el token crudo `"priority":null`.
- RF-27.1 (las consultas devuelven el valor vigente tras la modificacion):
  `test_list_and_detail_show_current_priority_after_it_is_set` y
  `test_list_and_detail_show_the_latest_priority` fijan la prioridad con
  `PUT /api/tickets/{ticket_id}/priority` usando una sesion real de
  tecnico y vuelven a consultar como el cliente solicitante.
- RF-27.3 (la creacion no cambia):
  `test_creation_returns_priority_null_and_keeps_initial_status` (201 con
  `priority: null`, estado `Abierto` y ticket almacenado sin prioridad) y
  `test_creation_with_priority_in_body_returns_422_without_creating_ticket`
  (la prioridad en el cuerpo se sigue rechazando con 422 sin crear nada).

La composicion exacta de los cuerpos se comprueba con igualdad de claves
(`set(body) == ...`), no solo con pertenencia, para no perder los campos de
HU-02 ni el `assignee` de HU-04. Las respuestas crudas se revisan con
`response.text` (token `null`) para no depender solo de `.json()`.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.domain.entities import OPEN_STATUS, PRIORITIES
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
SUMMARY_FIELDS = {"id", "title", "priority", "status", "assignee", "created_at"}
DETAIL_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "assignee",
    "created_at",
    "requester_id",
}

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    client.cookies.clear()


def _register_client(email="ana@ejemplo.com"):
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    _login(email)
    return registered.json()


def _login(email):
    logged = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert logged.status_code == 200


def _provision_and_login(role="tecnico", email="gestion@ejemplo.com"):
    user = provision_user(
        name="Equipo Soporte",
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(email)
    return user


def _create(title="Titulo", description="Descripcion"):
    response = client.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


# --- RF-27.3: la creacion no cambia (201 con priority null y Abierto) ---


def test_creation_returns_priority_null_and_keeps_initial_status():
    user = _register_client()

    response = client.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["title"] == "Titulo"
    assert body["description"] == "Descripcion"
    assert body["priority"] is None
    assert body["priority"] not in PRIORITIES
    assert body["status"] == OPEN_STATUS
    assert body["assignee"] is None
    assert body["requester_id"] == user["id"]
    assert '"priority":null' in response.text
    assert '"assignee":null' in response.text

    stored = get_ticket_repository().find_by_id(body["id"])
    assert stored is not None
    assert stored.priority is None
    assert stored.status == OPEN_STATUS


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Titulo", "description": "Descripcion", "priority": "Alta"},
        {"title": "Titulo", "description": "Descripcion", "priority": "Urgente"},
        {"title": "Titulo", "description": "Descripcion", "priority": None},
    ],
    ids=["catalogo", "fuera_catalogo", "nulo"],
)
def test_creation_with_priority_in_body_returns_422_without_creating_ticket(payload):
    _register_client()

    response = client.post("/api/tickets", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().count() == 0


# --- RF-27.2: prioridad no fijada -> null en listado y detalle ---


def test_list_summary_shows_priority_null_before_it_is_set():
    _register_client()
    created = _create()

    response = client.get("/api/tickets")

    assert response.status_code == 200
    [item] = response.json()
    assert set(item) == SUMMARY_FIELDS
    assert item["id"] == created["id"]
    assert item["title"] == "Titulo"
    assert item["priority"] is None
    assert item["priority"] not in PRIORITIES
    assert item["status"] == OPEN_STATUS
    assert item["assignee"] is None
    assert item["created_at"] == created["created_at"]
    assert '"priority":null' in response.text


def test_detail_shows_priority_null_before_it_is_set():
    user = _register_client()
    created = _create()

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == created["id"]
    assert body["title"] == "Titulo"
    assert body["description"] == "Descripcion"
    assert body["priority"] is None
    assert body["priority"] not in PRIORITIES
    assert body["status"] == OPEN_STATUS
    assert body["assignee"] is None
    assert body["created_at"] == created["created_at"]
    assert body["requester_id"] == user["id"]
    assert '"priority":null' in response.text


# --- RF-27.1/RF-27.2: valor vigente tras fijar la prioridad ---


@pytest.mark.parametrize("priority", list(PRIORITIES))
def test_list_and_detail_show_current_priority_after_it_is_set(priority):
    requester = _register_client()
    created = _create()
    _provision_and_login()

    updated = client.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": priority}
    )
    assert updated.status_code == 200
    assert updated.json()["priority"] == priority

    # Vuelve a consultar como el cliente solicitante del ticket.
    client.cookies.clear()
    _login(requester["email"])

    list_response = client.get("/api/tickets")
    assert list_response.status_code == 200
    [item] = list_response.json()
    assert set(item) == SUMMARY_FIELDS
    assert item["id"] == created["id"]
    assert item["title"] == "Titulo"
    assert item["priority"] == priority
    assert item["status"] == OPEN_STATUS
    assert item["assignee"] is None
    assert item["created_at"] == created["created_at"]

    detail_response = client.get(f"/api/tickets/{created['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert set(detail) == DETAIL_FIELDS
    assert detail["id"] == created["id"]
    assert detail["title"] == "Titulo"
    assert detail["description"] == "Descripcion"
    assert detail["priority"] == priority
    assert detail["status"] == OPEN_STATUS
    assert detail["assignee"] is None
    assert detail["created_at"] == created["created_at"]
    assert detail["requester_id"] == requester["id"]


def test_list_and_detail_show_the_latest_priority():
    requester = _register_client()
    created = _create()
    _provision_and_login()

    first = client.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Media"}
    )
    second = client.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    assert first.status_code == second.status_code == 200

    client.cookies.clear()
    _login(requester["email"])

    [item] = client.get("/api/tickets").json()
    assert item["priority"] == "Alta"
    assert client.get(f"/api/tickets/{created['id']}").json()["priority"] == "Alta"


def test_list_summary_keeps_each_ticket_priority():
    requester = _register_client()
    first = _create(title="Primero", description="Descripcion uno")
    second = _create(title="Segundo", description="Descripcion dos")
    _provision_and_login()

    assert (
        client.put(
            f"/api/tickets/{first['id']}/priority", json={"priority": "Baja"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/tickets/{second['id']}/priority", json={"priority": "Crítica"}
        ).status_code
        == 200
    )

    client.cookies.clear()
    _login(requester["email"])

    items = client.get("/api/tickets").json()
    assert len(items) == 2
    by_id = {item["id"]: item for item in items}
    assert set(by_id) == {first["id"], second["id"]}
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert item["status"] == OPEN_STATUS
        assert item["assignee"] is None
    assert by_id[first["id"]]["priority"] == "Baja"
    assert by_id[first["id"]]["title"] == "Primero"
    assert by_id[second["id"]]["priority"] == "Crítica"
    assert by_id[second["id"]]["title"] == "Segundo"
