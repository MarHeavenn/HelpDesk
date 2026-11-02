"""HU-06 T3 — contrato consolidado del detalle (RF-54, RF-55, RF-60).

Verifica sobre las respuestas completas de ticket (creacion, detalle,
prioridad, estado y asignacion):

- RF-54: el detalle reune el ticket con `requester`, `resolved_at` y el
  SLA calculado en el momento de la consulta; sin prioridad `sla` es
  `null`; sin resolver `resolved_at` es `null`; al resolver se fija y al
  reabrir se descarta; `Resuelto` -> `Cerrado` conserva el instante.
- RF-55: la misma composicion exacta en todas las operaciones completas;
  los resumenes (`GET /api/tickets` y `GET /api/assignments/mine`) no
  incluyen `requester` ni `resolved_at`.
- RF-60: `resolved_at` usa ISO 8601 con offset UTC y microsegundos, y la
  consulta de detalle no muta el ticket.

Cada usuario usa su propio `TestClient` con sesion real.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

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
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
DETAIL_FIELDS = {
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
SUMMARY_FIELDS = {
    "id",
    "title",
    "priority",
    "status",
    "assignee",
    "sla",
    "created_at",
}
SLA_FIELDS = {
    "target_minutes",
    "started_at",
    "due_at",
    "elapsed_minutes",
    "remaining_minutes",
    "status",
    "near_due",
    "breached",
}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()


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
    response = TestClient(app).post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(email: str) -> TestClient:
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _create_ticket(api: TestClient):
    response = api.post(
        "/api/tickets",
        json={"title": "Titulo de contrato", "description": "Descripcion"},
    )
    assert response.status_code == 201, response.text
    return response


def _put(api: TestClient, ticket_id: str, resource: str, payload: dict):
    return api.put(f"/api/tickets/{ticket_id}/{resource}", json=payload)


# --- RF-54: sla nulo sin prioridad y resolved_at nulo sin resolver ---


def test_new_ticket_has_no_resolved_at_and_no_sla_without_priority():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    api = _login(requester["email"])
    creation = _create_ticket(api)
    created = creation.json()

    assert set(created) == DETAIL_FIELDS
    assert created["priority"] is None
    assert created["sla"] is None
    assert created["resolved_at"] is None
    assert created["requester"] == {
        "id": requester["id"],
        "name": "Cliente Uno",
        "email": "cliente@ejemplo.com",
    }

    detail = api.get(f"/api/tickets/{created['id']}")

    assert detail.status_code == 200
    body = detail.json()
    assert set(body) == DETAIL_FIELDS
    assert body["priority"] is None
    assert body["sla"] is None
    assert body["resolved_at"] is None


# --- RF-54 y RF-60: valores vigentes, sin cache, con SLA calculado ---


def test_priority_and_status_changes_are_reflected_in_the_detail():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    priority = _put(
        technician_api, created["id"], "priority", {"priority": "Alta"}
    )
    assert priority.status_code == 200, priority.text
    priority_body = priority.json()
    assert set(priority_body) == DETAIL_FIELDS
    assert priority_body["priority"] == "Alta"
    assert priority_body["status"] == "Abierto"
    assert priority_body["resolved_at"] is None
    assert set(priority_body["sla"]) == SLA_FIELDS
    assert priority_body["sla"]["target_minutes"] > 0
    started = datetime.fromisoformat(priority_body["sla"]["started_at"])
    due = datetime.fromisoformat(priority_body["sla"]["due_at"])
    assert started.utcoffset() == timedelta(0)
    assert due.utcoffset() == timedelta(0)

    status = _put(
        technician_api, created["id"], "status", {"status": "En progreso"}
    )
    assert status.status_code == 200, status.text
    status_body = status.json()
    assert set(status_body) == DETAIL_FIELDS
    assert status_body["priority"] == "Alta"
    assert status_body["status"] == "En progreso"
    assert status_body["resolved_at"] is None
    assert status_body["sla"] is not None

    detail = requester_api.get(f"/api/tickets/{created['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["priority"] == "Alta"
    assert body["status"] == "En progreso"
    assert body["resolved_at"] is None
    assert body["sla"] is not None


# --- RF-54 y RF-60: resolved_at se fija al resolver y se conserva ---


def test_resolved_at_is_set_on_resolution_and_preserved_on_close():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    resolved = _put(
        technician_api, created["id"], "status", {"status": "Resuelto"}
    )
    assert resolved.status_code == 200, resolved.text
    resolved_body = resolved.json()
    assert set(resolved_body) == DETAIL_FIELDS
    assert resolved_body["status"] == "Resuelto"
    resolved_at = resolved_body["resolved_at"]
    assert resolved_at is not None
    assert resolved_at.endswith("+00:00")
    parsed = datetime.fromisoformat(resolved_at)
    assert parsed.utcoffset() == timedelta(0)
    assert parsed.microsecond >= 0
    assert parsed >= datetime.fromisoformat(resolved_body["created_at"])

    detail = requester_api.get(f"/api/tickets/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["resolved_at"] == resolved_at

    closed = _put(
        technician_api, created["id"], "status", {"status": "Cerrado"}
    )
    assert closed.status_code == 200, closed.text
    closed_body = closed.json()
    assert closed_body["status"] == "Cerrado"
    # `Resuelto` -> `Cerrado` conserva el instante de resolucion y el SLA.
    assert closed_body["resolved_at"] == resolved_at
    assert closed_body["sla"] == resolved_body["sla"]


def test_resolved_at_is_cleared_when_the_ticket_is_reopened():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _put(technician_api, created["id"], "priority", {"priority": "Media"})
    resolved = _put(
        technician_api, created["id"], "status", {"status": "Resuelto"}
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved_at"] is not None

    reopened = _put(
        technician_api, created["id"], "status", {"status": "Abierto"}
    )

    assert reopened.status_code == 200, reopened.text
    reopened_body = reopened.json()
    assert reopened_body["status"] == "Abierto"
    assert reopened_body["resolved_at"] is None
    assert reopened_body["sla"] is not None
    detail = requester_api.get(f"/api/tickets/{created['id']}")
    assert detail.json()["resolved_at"] is None


# --- RF-55: misma composicion en todas las respuestas completas ---


def test_full_ticket_composition_is_identical_across_operations():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    priority = _put(
        technician_api, created["id"], "priority", {"priority": "Baja"}
    )
    status = _put(
        technician_api, created["id"], "status", {"status": "En progreso"}
    )
    assignment = _put(
        admin_api,
        created["id"],
        "assignee",
        {"assignee_id": technician["id"]},
    )
    detail = requester_api.get(f"/api/tickets/{created['id']}")

    responses = [priority, status, assignment, detail]
    for response in responses:
        assert response.status_code == 200, response.text
        assert set(response.json()) == DETAIL_FIELDS

    for response in responses:
        body = response.json()
        assert body["requester"] == {
            "id": requester["id"],
            "name": "Cliente Uno",
            "email": "cliente@ejemplo.com",
        }
        assert body["resolved_at"] is None
        assert body["priority"] == "Baja"

    # Cada respuesta refleja el estado vigente en el momento en que se
    # produjo: la asignacion es posterior al cambio de estado.
    assert priority.json()["status"] == "Abierto"
    assert priority.json()["assignee"] is None
    assert status.json()["status"] == "En progreso"
    assert status.json()["assignee"] is None
    for response in (assignment, detail):
        assert response.json()["status"] == "En progreso"
        assert response.json()["assignee"] == {
            "id": technician["id"],
            "name": "Tecnico Uno",
        }


# --- RF-55: los resumenes no cambian ---


def test_summaries_do_not_include_requester_or_resolved_at():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])
    _put(technician_api, created["id"], "priority", {"priority": "Alta"})
    _put(
        admin_api,
        created["id"],
        "assignee",
        {"assignee_id": technician["id"]},
    )

    own = requester_api.get("/api/tickets")
    assigned = technician_api.get("/api/assignments/mine")

    assert own.status_code == 200
    assert assigned.status_code == 200
    for listing in (own.json(), assigned.json()):
        assert len(listing) == 1
        for item in listing:
            assert set(item) == SUMMARY_FIELDS
            assert "requester" not in item
            assert "resolved_at" not in item
