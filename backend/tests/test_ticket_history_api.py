"""HU-09 T5 - contenido de eventos del historial por API (RF-82, RF-83, RF-87)."""

import os
import sys
import uuid
from datetime import datetime, timezone

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
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
HISTORY_FIELDS = {
    "action",
    "actor",
    "occurred_at",
    "previous_value",
    "new_value",
    "previous_assignee",
    "new_assignee",
    "comment",
}


@pytest.fixture(autouse=True)
def clean_history_state():
    _clear()
    yield
    _clear()


def _clear() -> None:
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    get_ticket_comment_repository().clear()


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


def _create_ticket(api: TestClient) -> dict:
    response = api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assign(api: TestClient, ticket_id: str, technician_id: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician_id},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_priority(api: TestClient, ticket_id: str, priority: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": priority}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_status(api: TestClient, ticket_id: str, status: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": status}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_comment(api: TestClient, ticket_id: str, body: str) -> dict:
    response = api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _history(api: TestClient, ticket_id: str) -> list[dict]:
    response = api.get(f"/api/tickets/{ticket_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def test_new_ticket_has_only_the_creation_event():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    events = _history(technician_api, created["id"])

    assert len(events) == 1
    event = events[0]
    assert set(event) == HISTORY_FIELDS
    assert event["action"] == "ticket_created"
    assert event["actor"] == {
        "id": requester["id"],
        "name": requester["name"],
    }
    assert event["occurred_at"] == created["created_at"]
    assert event["previous_value"] is None
    assert event["new_value"] is None
    assert event["previous_assignee"] is None
    assert event["new_assignee"] is None
    assert event["comment"] is None


def test_assignment_and_reassignment_events_keep_technician_previous_and_new():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    tech_one = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    tech_two = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    admin_api = _login(admin["email"])
    technician_api = _login(tech_one["email"])

    _assign(admin_api, created["id"], tech_one["id"])
    _assign(admin_api, created["id"], tech_two["id"])
    _assign(admin_api, created["id"], tech_two["id"])

    events = _history(technician_api, created["id"])

    assert [event["action"] for event in events] == [
        "ticket_created",
        "technician_assigned",
        "technician_reassigned",
    ]
    assert events[1]["actor"] == {"id": admin["id"], "name": admin["name"]}
    assert events[1]["previous_assignee"] is None
    assert events[1]["new_assignee"] == {
        "id": tech_one["id"],
        "name": tech_one["name"],
    }
    assert events[2]["previous_assignee"] == {
        "id": tech_one["id"],
        "name": tech_one["name"],
    }
    assert events[2]["new_assignee"] == {
        "id": tech_two["id"],
        "name": tech_two["name"],
    }


def test_priority_events_keep_previous_and_new_values():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    _set_priority(technician_api, created["id"], "Alta")
    _set_priority(technician_api, created["id"], "Media")
    _set_priority(technician_api, created["id"], "Media")

    events = _history(technician_api, created["id"])

    assert [event["action"] for event in events] == [
        "ticket_created",
        "priority_changed",
        "priority_changed",
    ]
    assert events[1]["previous_value"] is None
    assert events[1]["new_value"] == "Alta"
    assert events[2]["previous_value"] == "Alta"
    assert events[2]["new_value"] == "Media"
    assert events[1]["actor"] == {
        "id": technician["id"],
        "name": technician["name"],
    }


def test_status_events_include_the_reopen_and_ignore_rejected_changes():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin_api = _login(admin["email"])
    technician_api = _login(technician["email"])

    # Salto inválido: no debe registrar nada.
    rejected = technician_api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Resuelto"}
    )
    assert rejected.status_code == 409

    _set_status(technician_api, created["id"], "En progreso")
    _set_status(technician_api, created["id"], "Resuelto")
    _set_status(technician_api, created["id"], "Cerrado")

    # Repetir el estado o intentar cambiarlo en cerrado tampoco registra.
    repeated = technician_api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Cerrado"}
    )
    assert repeated.status_code == 409

    reopened = admin_api.post(f"/api/tickets/{created['id']}/reopen")
    assert reopened.status_code == 200, reopened.text

    events = _history(technician_api, created["id"])

    assert [event["action"] for event in events] == [
        "ticket_created",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
    ]
    assert [
        (event["previous_value"], event["new_value"])
        for event in events[1:]
    ] == [
        ("Abierto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "Cerrado"),
        ("Cerrado", "Abierto"),
    ]
    assert events[-1]["actor"] == {"id": admin["id"], "name": admin["name"]}


def test_comment_event_keeps_the_author_and_body():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    invalid = technician_api.post(
        f"/api/tickets/{created['id']}/comments", json={"body": "   "}
    )
    assert invalid.status_code == 422
    comment = _add_comment(technician_api, created["id"], "  Revisando  ")

    events = _history(technician_api, created["id"])

    assert [event["action"] for event in events] == [
        "ticket_created",
        "comment_added",
    ]
    assert events[1]["actor"] == {
        "id": technician["id"],
        "name": technician["name"],
    }
    assert events[1]["comment"] == comment["body"] == "Revisando"
    assert events[1]["occurred_at"] == comment["created_at"]


def test_history_does_not_expose_internal_record_fields():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _set_priority(technician_api, created["id"], "Alta")
    _set_status(technician_api, created["id"], "En progreso")

    response = technician_api.get(f"/api/tickets/{created['id']}/history")

    assert response.status_code == 200
    for forbidden in ("actor_id", "changed_at", "assigned_at", "ticket_id"):
        assert forbidden not in response.text


def test_history_requires_a_session_before_resolving_the_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    anonymous = TestClient(app)

    for ticket_id in (created["id"], "no-es-uuid", str(uuid.uuid4())):
        response = anonymous.get(f"/api/tickets/{ticket_id}/history")
        assert response.status_code == 401, response.text


def test_client_gets_the_uniform_404_even_for_their_own_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)

    response = requester_api.get(f"/api/tickets/{created['id']}/history")

    assert response.status_code == 404
    assert response.json() == {"detail": "ticket not found"}


def test_unknown_and_invalid_ticket_get_the_uniform_404():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    for ticket_id in (str(uuid.uuid4()), "no-es-uuid", "t-1"):
        response = technician_api.get(f"/api/tickets/{ticket_id}/history")
        assert response.status_code == 404
        assert response.json() == {"detail": "ticket not found"}


def test_closed_ticket_history_is_readable_and_not_mutated():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    _set_status(technician_api, created["id"], "En progreso")
    _set_status(technician_api, created["id"], "Resuelto")
    closed = _set_status(technician_api, created["id"], "Cerrado")
    before = requester_api.get(f"/api/tickets/{created['id']}").json()

    events = _history(technician_api, created["id"])

    assert [event["action"] for event in events] == [
        "ticket_created",
        "status_changed",
        "status_changed",
        "status_changed",
    ]
    after = requester_api.get(f"/api/tickets/{created['id']}").json()
    assert after == before
    assert after["status"] == "Cerrado"
    assert after["resolved_at"] == closed["resolved_at"]


def test_missing_actor_keeps_the_identifier_and_a_null_name():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id="u-missing",
        created_at=NOW,
    )
    get_ticket_repository().add(ticket)

    events = _history(technician_api, ticket.id)

    assert len(events) == 1
    assert events[0]["actor"] == {"id": "u-missing", "name": None}


def test_unknown_query_parameters_are_ignored():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    plain = _history(technician_api, created["id"])
    with_query = technician_api.get(
        f"/api/tickets/{created['id']}/history?limit=1&foo=bar"
    )

    assert with_query.status_code == 200
    assert with_query.json() == plain
