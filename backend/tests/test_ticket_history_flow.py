"""HU-09 T7 - flujo completo del historial entre historias (RF-82, RF-86, RF-87).

Recorre HU-02 (creacion), HU-04 (asignacion y reasignacion), HU-03/HU-05
(prioridad), HU-07 (comentario) y HU-08 (estados, cierre y reapertura), y
comprueba que el historial refleja exactamente las acciones efectivas, sin
duplicados ni eventos de operaciones rechazadas.
"""

import os
import sys

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
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"


@pytest.fixture(autouse=True)
def clean_flow_state():
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
    return {"id": user.id, "name": user.name, "email": user.email}


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


def _history(api: TestClient, ticket_id: str) -> list[dict]:
    response = api.get(f"/api/tickets/{ticket_id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def test_history_follows_the_complete_ticket_lifecycle():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    tech_one = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    tech_two = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    admin_api = _login(admin["email"])
    tech_one_api = _login(tech_one["email"])
    tech_two_api = _login(tech_two["email"])

    created = _create_ticket(requester_api)
    ticket_id = created["id"]

    assert (
        admin_api.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": tech_one["id"]},
        ).status_code
        == 200
    )
    assert (
        admin_api.put(
            f"/api/tickets/{ticket_id}/assignee",
            json={"assignee_id": tech_two["id"]},
        ).status_code
        == 200
    )
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
        ).status_code
        == 200
    )
    # Repeticion: no debe generar un evento nuevo.
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
        ).status_code
        == 200
    )
    assert (
        tech_two_api.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"body": "Revisando el caso"},
        ).status_code
        == 201
    )
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "En progreso"}
        ).status_code
        == 200
    )
    # Salto invalido: no debe generar un evento nuevo.
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "Cerrado"}
        ).status_code
        == 409
    )
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "Resuelto"}
        ).status_code
        == 200
    )
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "Cerrado"}
        ).status_code
        == 200
    )
    # Un ticket cerrado no admite nuevas acciones.
    assert (
        tech_two_api.post(
            f"/api/tickets/{ticket_id}/comments",
            json={"body": "Comentario tardio"},
        ).status_code
        == 409
    )
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/priority", json={"priority": "Baja"}
        ).status_code
        == 409
    )
    assert admin_api.post(f"/api/tickets/{ticket_id}/reopen").status_code == 200
    assert (
        tech_two_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "En progreso"}
        ).status_code
        == 200
    )

    events = _history(tech_one_api, ticket_id)

    assert [event["action"] for event in events] == [
        "ticket_created",
        "technician_assigned",
        "technician_reassigned",
        "priority_changed",
        "comment_added",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
        "status_changed",
    ]
    assert [event["actor"]["id"] for event in events] == [
        requester["id"],
        admin["id"],
        admin["id"],
        tech_two["id"],
        tech_two["id"],
        tech_two["id"],
        tech_two["id"],
        tech_two["id"],
        admin["id"],
        tech_two["id"],
    ]
    assert [
        (event["previous_value"], event["new_value"])
        for event in events[5:]
    ] == [
        ("Abierto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "Cerrado"),
        ("Cerrado", "Abierto"),
        ("Abierto", "En progreso"),
    ]
    assert events[3]["previous_value"] is None
    assert events[3]["new_value"] == "Alta"
    assert events[4]["comment"] == "Revisando el caso"
    assert events[1]["new_assignee"] == {
        "id": tech_one["id"],
        "name": tech_one["name"],
    }
    assert events[2]["new_assignee"] == {
        "id": tech_two["id"],
        "name": tech_two["name"],
    }

    # No hay duplicados ni eventos de operaciones rechazadas.
    assert len(events) == 10
    assert get_ticket_modification_log().count() == 6
    assert get_assignment_log().count() == 2
    assert get_ticket_comment_repository().count() == 1

    # La consulta es de solo lectura: el ticket y el seguimiento no cambian.
    detail = requester_api.get(f"/api/tickets/{ticket_id}").json()
    assert detail["status"] == "En progreso"
    assert detail["priority"] == "Alta"
    comments = requester_api.get(f"/api/tickets/{ticket_id}/comments").json()
    assert [comment["body"] for comment in comments] == ["Revisando el caso"]
