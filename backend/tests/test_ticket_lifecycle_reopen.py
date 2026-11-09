"""HU-08 T3 — reapertura de un ticket cerrado (RF-76, RF-77, RF-80).

Verifica `POST /api/tickets/{ticket_id}/reopen`:

- Solo el administrador reabre; técnico y cliente reciben el 404 uniforme
  de HU-02 sin revelar el ticket ni su estado.
- Un ticket inexistente o un identificador inválido responde 404 uniforme.
- Un ticket no cerrado responde 409 `{"detail": "ticket is not closed"}`.
- Sin sesión válida responde 401 antes que 404/409.
- La reapertura no requiere cuerpo: cualquier cuerpo se ignora.
- El ticket vuelve a `Abierto`, `resolved_at` queda en `null`, el SLA se
  reanuda y se registra `Cerrado` -> `Abierto` con el actor de sesión.
- Prioridad, asignación y comentarios vuelven a estar disponibles.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.sla.domain.entities import (
    SLA_AT_RISK,
    SLA_BREACHED,
    SLA_MET,
    SLA_ON_TIME,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_reopenable_ticket import (
    TICKET_NOT_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": TICKET_NOT_FOUND_MESSAGE}
NOT_CLOSED_BODY = {"detail": TICKET_NOT_CLOSED_MESSAGE}
CLOSED_BODY = {"detail": TICKET_CLOSED_MESSAGE}
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

# Camino mínimo para llegar a cada estado desde un ticket nuevo.
PATH_TO = {
    "Abierto": [],
    "En progreso": ["En progreso"],
    "Resuelto": ["En progreso", "Resuelto"],
    "Cerrado": ["En progreso", "Resuelto", "Cerrado"],
}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()


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


def _put_status(api: TestClient, ticket_id: str, status: str):
    return api.put(f"/api/tickets/{ticket_id}/status", json={"status": status})


def _advance(api: TestClient, ticket_id: str, target: str) -> None:
    for status in PATH_TO[target]:
        response = _put_status(api, ticket_id, status)
        assert response.status_code == 200, response.text
    assert get_ticket_repository().find_by_id(ticket_id).status == target


def _reopen(api: TestClient, ticket_id: str):
    return api.post(f"/api/tickets/{ticket_id}/reopen")


def _closed_ticket() -> tuple[dict, dict, TestClient]:
    """Crea un cliente con un ticket cerrado y devuelve cliente, ticket y API."""
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    _advance(_login(technician["email"]), created["id"], "Cerrado")
    return requester, created, requester_api


def _status_records(ticket_id: str):
    return [
        record
        for record in get_ticket_modification_log().list_by_ticket(ticket_id)
        if record.field == "status"
    ]


# --- RF-76: reapertura por el administrador ---


def test_administrator_reopens_a_closed_ticket():
    requester, created, requester_api = _closed_ticket()
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])
    before = requester_api.get(f"/api/tickets/{created['id']}").json()
    records_before = len(_status_records(created["id"]))

    response = _reopen(admin_api, created["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["status"] == "Abierto"
    assert body["resolved_at"] is None
    assert body["id"] == before["id"]
    assert body["title"] == before["title"]
    assert body["description"] == before["description"]
    assert body["requester"] == before["requester"]
    assert body["requester_id"] == before["requester_id"]
    assert body["created_at"] == before["created_at"]
    assert get_ticket_repository().find_by_id(created["id"]).status == "Abierto"

    records = _status_records(created["id"])
    assert len(records) == records_before + 1
    record = records[-1]
    assert record.previous_value == "Cerrado"
    assert record.new_value == "Abierto"
    assert record.actor_id == admin["id"]
    assert record.changed_at.tzinfo is not None
    assert record.changed_at.utcoffset() == timedelta(0)

    # El detalle y el listado reflejan el estado vigente.
    assert requester_api.get(f"/api/tickets/{created['id']}").json()["status"] == (
        "Abierto"
    )
    listed = requester_api.get("/api/tickets").json()
    assert [item["status"] for item in listed] == ["Abierto"]


def test_reopen_resumes_the_sla():
    requester, created, requester_api = _closed_ticket()
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])
    technician = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    technician_api = _login(technician["email"])
    # Se reabre para fijar la prioridad y se vuelve a cerrar con SLA fijado.
    reopened = _reopen(admin_api, created["id"])
    assert reopened.status_code == 200, reopened.text
    priority = technician_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    assert priority.status_code == 200, priority.text
    _advance(technician_api, created["id"], "Cerrado")
    closed = requester_api.get(f"/api/tickets/{created['id']}").json()
    assert closed["resolved_at"] is not None
    assert closed["sla"]["status"] in {
        SLA_ON_TIME,
        SLA_AT_RISK,
        SLA_MET,
        SLA_BREACHED,
    }

    response = _reopen(admin_api, created["id"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resolved_at"] is None
    assert body["priority"] == "Alta"
    assert body["sla"]["started_at"] == closed["sla"]["started_at"]
    assert body["sla"]["target_minutes"] == closed["sla"]["target_minutes"]
    assert body["sla"]["status"] in {SLA_ON_TIME, SLA_AT_RISK}
    assert datetime.fromisoformat(body["sla"]["due_at"]).utcoffset() == timedelta(0)


def test_reopen_ignores_any_body():
    requester, created, requester_api = _closed_ticket()
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    for kwargs in (
        {"json": {"status": "Resuelto"}},
        {"json": {"unexpected": True}},
        {"content": b"not json", "headers": {"content-type": "application/json"}},
    ):
        response = admin_api.post(
            f"/api/tickets/{created['id']}/reopen", **kwargs
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "Abierto"
        # Se vuelve a cerrar para el siguiente intento.
        technician = _provision(
            "tecnico", "Tecnico Uno", f"tec{uuid.uuid4().hex}@ejemplo.com"
        )
        _advance(_login(technician["email"]), created["id"], "Cerrado")


def test_reopen_enables_priority_assignment_and_comments_again():
    requester, created, requester_api = _closed_ticket()
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])
    technician = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    technician_api = _login(technician["email"])
    ticket_id = created["id"]

    # Cerrado: las tres operaciones siguen bloqueadas con 409.
    blocked_priority = technician_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )
    blocked_assignment = admin_api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician["id"]},
    )
    blocked_comment = technician_api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": "Seguimiento"}
    )
    for response in (blocked_priority, blocked_assignment, blocked_comment):
        assert response.status_code == 409, response.text
        assert response.json() == CLOSED_BODY

    assert _reopen(admin_api, ticket_id).status_code == 200

    priority = technician_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )
    assignment = admin_api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician["id"]},
    )
    comment = technician_api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": "Seguimiento"}
    )

    assert priority.status_code == 200, priority.text
    assert priority.json()["priority"] == "Alta"
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()["assignee"] == {
        "id": technician["id"],
        "name": "Tecnico Dos",
    }
    assert comment.status_code == 201, comment.text
    assert comment.json()["body"] == "Seguimiento"


# --- RF-77: autorización y estado ---


def test_technician_and_client_get_uniform_404():
    requester, created, requester_api = _closed_ticket()
    technician = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    technician_api = _login(technician["email"])
    unified = requester_api.get(f"/api/tickets/{uuid.uuid4()}")
    before = requester_api.get(f"/api/tickets/{created['id']}").json()
    records_before = len(_status_records(created["id"]))

    for api in (technician_api, requester_api):
        response = _reopen(api, created["id"])
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY
        assert response.text == unified.text
        assert requester_api.get(f"/api/tickets/{created['id']}").json() == before
        assert len(_status_records(created["id"])) == records_before


def test_unknown_or_invalid_ticket_returns_uniform_404():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    for candidate in ("not-a-uuid", str(uuid.uuid4())):
        response = _reopen(admin_api, candidate)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize("status", ["Abierto", "En progreso", "Resuelto"])
def test_reopen_of_a_non_closed_ticket_returns_409(status):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _advance(_login(technician["email"]), created["id"], status)
    admin_api = _login(admin["email"])
    before = requester_api.get(f"/api/tickets/{created['id']}").json()
    records_before = len(_status_records(created["id"]))

    response = _reopen(admin_api, created["id"])

    assert response.status_code == 409, response.text
    assert response.json() == NOT_CLOSED_BODY
    assert requester_api.get(f"/api/tickets/{created['id']}").json() == before
    assert len(_status_records(created["id"])) == records_before


def test_missing_session_returns_401_before_404_and_409():
    requester, created, requester_api = _closed_ticket()
    anonymous = TestClient(app)

    for candidate in ("not-a-uuid", str(uuid.uuid4()), created["id"]):
        response = _reopen(anonymous, candidate)
        assert response.status_code == 401

    assert _reopen(requester_api, created["id"]).status_code == 404


def test_closed_ticket_cannot_be_reopened_through_put_status():
    requester, created, requester_api = _closed_ticket()
    technician = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    technician_api = _login(technician["email"])

    response = _put_status(technician_api, created["id"], "Abierto")

    assert response.status_code == 409
    assert response.json() == CLOSED_BODY
    assert get_ticket_repository().find_by_id(created["id"]).status == "Cerrado"


def test_reopen_does_not_expose_the_modification_log():
    requester, created, requester_api = _closed_ticket()
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    response = _reopen(admin_api, created["id"])

    assert response.status_code == 200
    for forbidden in (
        "previous_value",
        "new_value",
        "actor_id",
        "changed_at",
        "modifications",
        "allowed_transitions",
    ):
        assert forbidden not in response.text


def test_reopen_is_the_only_new_route_in_the_contract():
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/tickets/{ticket_id}/reopen"]
    assert "put" in paths["/api/tickets/{ticket_id}/status"]
    assert not any("reopen" in path for path in paths if path != (
        "/api/tickets/{ticket_id}/reopen"
    ))
