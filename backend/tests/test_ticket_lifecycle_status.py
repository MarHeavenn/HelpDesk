"""HU-08 T2 — transiciones de estado por API (RF-71 a RF-75, RF-78, RF-79).

Verifica `PUT /api/tickets/{ticket_id}/status`:

- Las cuatro transiciones del flujo responden 200, mutan el ticket y
  registran el cambio con el actor de la sesión.
- Las transiciones fuera del flujo responden 409
  `{"detail": "invalid status transition"}` sin cambiar nada.
- Repetir el estado vigente responde 200 sin registro.
- Un ticket `Cerrado` responde 409 `{"detail": "ticket is closed"}` con
  cualquier cuerpo, antes de validarlo.
- El catálogo y los cuerpos inválidos responden 422; el cliente recibe
  404 uniforme; sin sesión, 401.
- `resolved_at` y el SLA siguen la semántica de HU-05.
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
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.sla.domain.entities import SLA_AT_RISK, SLA_MET, SLA_ON_TIME
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
)
from app.modules.tickets.application.update_ticket_status import (
    INVALID_STATUS_TRANSITION_MESSAGE,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": TICKET_NOT_FOUND_MESSAGE}
CLOSED_BODY = {"detail": TICKET_CLOSED_MESSAGE}
INVALID_TRANSITION_BODY = {"detail": INVALID_STATUS_TRANSITION_MESSAGE}
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

# Camino mínimo para llegar a cada estado de origen desde un ticket nuevo.
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
    return api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": status}
    )


def _advance(api: TestClient, ticket_id: str, target: str) -> None:
    for status in PATH_TO[target]:
        response = _put_status(api, ticket_id, status)
        assert response.status_code == 200, response.text
    assert get_ticket_repository().find_by_id(ticket_id).status == target


def _record_count(ticket_id: str) -> int:
    return len(get_ticket_modification_log().list_by_ticket(ticket_id))


# --- RF-71/RF-72: transiciones válidas ---


@pytest.mark.parametrize(
    "source,target",
    [
        ("Abierto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "Cerrado"),
        ("Resuelto", "En progreso"),
    ],
)
def test_valid_transition_returns_200_changes_and_records(source, target):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _advance(technician_api, created["id"], source)
    records_before = _record_count(created["id"])

    response = _put_status(technician_api, created["id"], target)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["status"] == target
    assert get_ticket_repository().find_by_id(created["id"]).status == target
    records = get_ticket_modification_log().list_by_ticket(created["id"])
    assert len(records) == records_before + 1
    record = records[-1]
    assert record.previous_value == source
    assert record.new_value == target
    assert record.actor_id == technician["id"]


def test_resolved_at_is_set_and_preserved_on_close():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    priority = technician_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Media"}
    )
    assert priority.status_code == 200
    _advance(technician_api, created["id"], "En progreso")

    resolved = _put_status(technician_api, created["id"], "Resuelto")

    assert resolved.status_code == 200, resolved.text
    resolved_body = resolved.json()
    assert resolved_body["resolved_at"] is not None
    assert datetime.fromisoformat(resolved_body["resolved_at"]).utcoffset() == timedelta(0)
    assert resolved_body["sla"]["status"] in {SLA_MET, "incumplido"}
    resolved_at = resolved_body["resolved_at"]
    sla = resolved_body["sla"]

    closed = _put_status(technician_api, created["id"], "Cerrado")

    assert closed.status_code == 200, closed.text
    assert closed.json()["resolved_at"] == resolved_at
    assert closed.json()["sla"] == sla


def test_resolved_to_in_progress_clears_resolved_at_and_resumes_sla():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    technician_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Media"}
    )
    _advance(technician_api, created["id"], "Resuelto")
    assert _put_status(
        technician_api, created["id"], "En progreso"
    ).json()["resolved_at"] is None

    resumed = _put_status(technician_api, created["id"], "Resuelto")

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["resolved_at"] is not None
    # El SLA resuelto se congela; al reanudar vuelve a estar en curso.
    records = [
        record
        for record in get_ticket_modification_log().list_by_ticket(created["id"])
        if record.field == "status"
    ]
    assert [(r.previous_value, r.new_value) for r in records] == [
        ("Abierto", "En progreso"),
        ("En progreso", "Resuelto"),
        ("Resuelto", "En progreso"),
        ("En progreso", "Resuelto"),
    ]


# --- RF-73: transiciones inválidas ---


@pytest.mark.parametrize(
    "source,target",
    [
        ("Abierto", "Resuelto"),
        ("Abierto", "Cerrado"),
        ("En progreso", "Abierto"),
        ("En progreso", "Cerrado"),
        ("Resuelto", "Abierto"),
    ],
)
def test_invalid_transition_returns_409_without_change_or_record(source, target):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _advance(technician_api, created["id"], source)
    before = requester_api.get(f"/api/tickets/{created['id']}").json()
    records_before = _record_count(created["id"])

    response = _put_status(technician_api, created["id"], target)

    assert response.status_code == 409, response.text
    assert response.json() == INVALID_TRANSITION_BODY
    after = requester_api.get(f"/api/tickets/{created['id']}").json()
    assert after == before
    assert _record_count(created["id"]) == records_before


# --- RF-74: repetir el estado ---


@pytest.mark.parametrize("status", ["Abierto", "En progreso", "Resuelto"])
def test_repeating_status_returns_200_without_record(status):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _advance(technician_api, created["id"], status)
    records_before = _record_count(created["id"])
    before = requester_api.get(f"/api/tickets/{created['id']}").json()

    response = _put_status(technician_api, created["id"], status)

    assert response.status_code == 200, response.text
    assert response.json() == before
    assert _record_count(created["id"]) == records_before


# --- RF-75: ticket cerrado ---


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "Cerrado"},
        {"status": "Abierto"},
        {"status": "En progreso"},
        {"status": "Resuelto"},
        {"status": "Abierta"},
        {},
    ],
)
def test_closed_ticket_returns_ticket_is_closed_before_body_validation(payload):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _advance(technician_api, created["id"], "Cerrado")
    before = requester_api.get(f"/api/tickets/{created['id']}").json()
    records_before = _record_count(created["id"])

    response = technician_api.put(
        f"/api/tickets/{created['id']}/status", json=payload
    )

    assert response.status_code == 409, response.text
    assert response.json() == CLOSED_BODY
    assert requester_api.get(f"/api/tickets/{created['id']}").json() == before
    assert _record_count(created["id"]) == records_before


# --- RF-78: validación y precedencia ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": 5},
        {"status": None},
        {"status": ["Resuelto"]},
        {"status": "Abierta"},
        {"status": "abierto"},
        {"status": "En Progreso"},
        {"status": "En progreso", "actor_id": str(uuid.uuid4())},
        {"status": "En progreso", "changed_at": "2026-11-02T00:00:00+00:00"},
    ],
)
def test_invalid_body_or_catalog_on_open_ticket_returns_422(payload):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    records_before = _record_count(created["id"])

    response = technician_api.put(
        f"/api/tickets/{created['id']}/status", json=payload
    )

    assert response.status_code == 422, response.text
    assert get_ticket_repository().find_by_id(created["id"]).status == "Abierto"
    assert _record_count(created["id"]) == records_before


def test_client_gets_uniform_404_for_any_status_attempt():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    unified = requester_api.get(f"/api/tickets/{uuid.uuid4()}")

    for payload in ({"status": "En progreso"}, {"status": "Cerrado"}, {}):
        response = requester_api.put(
            f"/api/tickets/{created['id']}/status", json=payload
        )
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY
        assert response.text == unified.text


def test_missing_session_returns_401_before_ticket_or_body():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    anonymous = TestClient(app)

    for ticket_id, payload in (
        ("not-a-uuid", {"status": "Abierta"}),
        (str(uuid.uuid4()), {"status": "En progreso"}),
        (created["id"], {}),
    ):
        response = anonymous.put(
            f"/api/tickets/{ticket_id}/status", json=payload
        )
        assert response.status_code == 401


def test_staff_gets_uniform_404_for_unknown_or_invalid_ticket():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    for candidate in ("not-a-uuid", str(uuid.uuid4())):
        response = _put_status(technician_api, candidate, "En progreso")
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


def test_transition_does_not_change_other_ticket_fields():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician_api = _login(technician["email"])
    admin_api = _login(admin["email"])
    technician_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    admin_api.put(
        f"/api/tickets/{created['id']}/assignee",
        json={"assignee_id": technician["id"]},
    )
    before = requester_api.get(f"/api/tickets/{created['id']}").json()

    response = _put_status(technician_api, created["id"], "En progreso")

    assert response.status_code == 200, response.text
    after = requester_api.get(f"/api/tickets/{created['id']}").json()
    for key in (
        "id",
        "title",
        "description",
        "priority",
        "assignee",
        "requester",
        "created_at",
        "requester_id",
    ):
        assert after[key] == before[key]
    assert after["sla"]["target_minutes"] == before["sla"]["target_minutes"]
    assert after["sla"]["started_at"] == before["sla"]["started_at"]


def test_status_response_does_not_expose_the_modification_log():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = _put_status(technician_api, created["id"], "En progreso")

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
