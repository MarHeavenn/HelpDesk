"""T5 (HU-03) — Caso de uso de fijacion de prioridad (RF-22, RF-26, RF-29.3).

Mapa RF -> test:
- RF-21/RF-29.3 (catalogo exacto): `test_each_catalog_priority_is_accepted`,
  `test_out_of_catalog_priority_is_rejected_without_change_or_record`,
  `test_validation_error_keeps_the_domain_message`.
- RF-29.1 (tipo estricto, en el caso de uso):
  `test_non_text_priority_is_rejected_without_change_or_record`.
- RF-22 (cambio efectivo y repeticion del valor vigente):
  `test_setting_a_new_priority_records_the_previous_value`,
  `test_repeating_the_current_priority_does_not_change_or_record`,
  `test_priority_change_mutates_the_ticket_stored_in_the_repository`,
  `test_priority_and_status_are_independent`.
- RF-26 (registro de cambios efectivos): todos los tests de registro, en
  particular `test_first_priority_has_empty_previous_value`,
  `test_default_changed_at_uses_the_system_time_in_utc`,
  `test_successive_priority_changes_accumulate_with_previous_values` y
  `test_returned_ticket_does_not_include_the_modification_record`.

La seccion HTTP (T6) verifica `PUT /api/tickets/{ticket_id}/priority` con
sesiones reales de tecnico y administrador: 200 con el ticket completo
(con `assignee: null` mientras no haya asignacion, composicion uniforme de
HU-04), cuerpo mono-campo estricto y 422, rol sin permisos / inexistente /
identificador invalido -> 404 uniforme, cerrado -> 409 y sin sesion -> 401
(RF-22, RF-29.1, RF-29.2, RF-30; RF-35.5 de HU-04).
"""

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.application.set_ticket_priority import set_ticket_priority
from app.modules.tickets.domain.entities import (
    OPEN_STATUS,
    PRIORITIES,
    PRIORITY_FIELD,
    Ticket,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
PASSWORD = "Secreta123"
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

api = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()


def _register_client(email="ana@ejemplo.com"):
    registered = api.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    return registered.json()


def _login(email):
    logged = api.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert logged.status_code == 200


def _provision_and_login(
    role="tecnico",
    email="gestion@ejemplo.com",
    name="Equipo Soporte",
):
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(email)
    return user


def _create_ticket(title="Titulo", description="Descripcion"):
    response = api.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


def _ticket(**overrides) -> Ticket:
    values = {
        "id": str(uuid.uuid4()),
        "title": "Titulo",
        "description": "Descripcion",
        "requester_id": str(uuid.uuid4()),
        "created_at": NOW,
    }
    values.update(overrides)
    return Ticket(**values)


# --- RF-21/RF-29.3: catalogo y cambio efectivo ---


@pytest.mark.parametrize("priority", list(PRIORITIES))
def test_each_catalog_priority_is_accepted(priority):
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    returned = set_ticket_priority(ticket, priority, "u-tech", log, now=NOW)

    assert returned is ticket
    assert ticket.priority == priority
    assert log.count() == 1

    [record] = log.list_by_ticket(ticket.id)
    assert record.ticket_id == ticket.id
    assert record.field == PRIORITY_FIELD
    assert record.previous_value is None
    assert record.new_value == priority
    assert record.actor_id == "u-tech"
    assert record.changed_at == NOW


def test_setting_a_new_priority_records_the_previous_value():
    ticket = _ticket(priority="Media")
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Alta", "u-admin", log, now=NOW)

    assert ticket.priority == "Alta"
    [record] = log.list_by_ticket(ticket.id)
    assert record.previous_value == "Media"
    assert record.new_value == "Alta"
    assert record.actor_id == "u-admin"


def test_first_priority_has_empty_previous_value():
    ticket = _ticket()
    assert ticket.priority is None
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Crítica", "u-tech", log, now=NOW)

    [record] = log.list_by_ticket(ticket.id)
    assert record.previous_value is None
    assert record.new_value == "Crítica"


@pytest.mark.parametrize(
    "raw", ["Urgente", "alta", "ALTA", " Alta ", "Alta ", "Alta\n", "", "   ", "Abierto"]
)
def test_out_of_catalog_priority_is_rejected_without_change_or_record(raw):
    ticket = _ticket(priority="Media")
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError):
        set_ticket_priority(ticket, raw, "u-tech", log, now=NOW)

    assert ticket.priority == "Media"
    assert log.count() == 0


@pytest.mark.parametrize(
    "raw", [5, 5.5, True, False, {"value": "Alta"}, ["Alta"], None, b"Alta"]
)
def test_non_text_priority_is_rejected_without_change_or_record(raw):
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError):
        set_ticket_priority(ticket, raw, "u-tech", log, now=NOW)

    assert ticket.priority is None
    assert log.count() == 0


def test_validation_error_keeps_the_domain_message():
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError) as exc:
        set_ticket_priority(ticket, "Urgente", "u-tech", log, now=NOW)

    assert str(exc.value) == "priority must be one of Crítica, Alta, Media, Baja"

    with pytest.raises(TicketValidationError) as exc:
        set_ticket_priority(ticket, 5, "u-tech", log, now=NOW)

    assert str(exc.value) == "priority must be text"


# --- RF-22: repetir el valor vigente no cambia ni registra ---


def test_repeating_the_current_priority_does_not_change_or_record():
    ticket = _ticket(priority="Alta")
    log = InMemoryTicketModificationLog()

    returned = set_ticket_priority(ticket, "Alta", "u-tech", log, now=NOW)

    assert returned is ticket
    assert ticket.priority == "Alta"
    assert log.count() == 0
    assert log.list_by_ticket(ticket.id) == []


# --- RF-26: fecha del sistema, acumulacion y registro fuera del ticket ---


def test_default_changed_at_uses_the_system_time_in_utc():
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    before = datetime.now(timezone.utc)
    set_ticket_priority(ticket, "Baja", "u-tech", log)
    after = datetime.now(timezone.utc)

    [record] = log.list_by_ticket(ticket.id)
    assert record.changed_at.tzinfo is not None
    assert record.changed_at.utcoffset().total_seconds() == 0
    assert before <= record.changed_at <= after


def test_successive_priority_changes_accumulate_with_previous_values():
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Media", "u-tech", log, now=NOW)
    set_ticket_priority(ticket, "Alta", "u-admin", log, now=NOW)
    set_ticket_priority(ticket, "Baja", "u-tech", log, now=NOW)

    records = log.list_by_ticket(ticket.id)
    assert [(r.previous_value, r.new_value, r.actor_id) for r in records] == [
        (None, "Media", "u-tech"),
        ("Media", "Alta", "u-admin"),
        ("Alta", "Baja", "u-tech"),
    ]
    assert log.count() == 3
    assert ticket.priority == "Baja"


def test_returned_ticket_does_not_include_the_modification_record():
    ticket = _ticket()
    log = InMemoryTicketModificationLog()

    returned = set_ticket_priority(ticket, "Alta", "u-tech", log, now=NOW)

    # El registro vive solo en el log: el ticket devuelto no lo incorpora.
    assert returned is ticket
    assert not hasattr(returned, "previous_value")
    assert not hasattr(returned, "new_value")
    assert not hasattr(returned, "actor_id")
    assert not hasattr(returned, "changed_at")
    assert not hasattr(returned, "modifications")


# --- RF-22/RF-27.1: el ticket almacenado queda actualizado ---


def test_priority_change_mutates_the_ticket_stored_in_the_repository():
    ticket = _ticket()
    repo = InMemoryTicketRepository()
    repo.add(ticket)
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Crítica", "u-tech", log, now=NOW)

    stored = repo.find_by_id(ticket.id)
    assert stored is ticket
    assert stored.priority == "Crítica"


def test_priority_and_status_are_independent():
    ticket = _ticket(status="En progreso")
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Alta", "u-tech", log, now=NOW)

    assert ticket.priority == "Alta"
    assert ticket.status == "En progreso"


# --- T6 / RF-22: PUT /api/tickets/{ticket_id}/priority (200) ---


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_put_priority_by_management_role_returns_full_updated_ticket(role):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    actor = _provision_and_login(role=role)

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == created["id"]
    assert body["title"] == "Titulo"
    assert body["description"] == "Descripcion"
    assert body["priority"] == "Alta"
    assert body["status"] == OPEN_STATUS
    assert body["assignee"] is None
    assert body["created_at"] == created["created_at"]
    assert body["requester_id"] == requester["id"]
    # El registro no aparece en la respuesta (RF-26).
    assert "previous_value" not in response.text
    assert "changed_at" not in response.text

    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    assert stored.priority == "Alta"
    [record] = get_ticket_modification_log().list_by_ticket(created["id"])
    assert record.field == PRIORITY_FIELD
    assert record.previous_value is None
    assert record.new_value == "Alta"
    assert record.actor_id == actor.id


@pytest.mark.parametrize("priority", list(PRIORITIES))
def test_put_priority_accepts_each_catalog_value(priority):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": priority}
    )

    assert response.status_code == 200
    assert response.json()["priority"] == priority
    assert get_ticket_modification_log().list_by_ticket(created["id"])[
        0
    ].new_value == priority


def test_put_repeated_priority_returns_200_without_new_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    first = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Media"}
    )
    second = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Media"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["priority"] == "Media"
    assert get_ticket_modification_log().count() == 1


# --- T6 / RF-29.1 y RF-29.2: cuerpo mono-campo estricto (422) ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"priority": 5},
        {"priority": 5.5},
        {"priority": True},
        {"priority": None},
        {"priority": ["Alta"]},
        {"priority": {"value": "Alta"}},
        {"priority": "Alta", "actor_id": "00000000-0000-0000-0000-000000000000"},
        {"priority": "Alta", "changed_at": "2026-10-19T12:00:00+00:00"},
        {"priority": "Alta", "status": "Cerrado"},
        {"priority": "Alta", "requester_id": "00000000-0000-0000-0000-000000000000"},
    ],
    ids=[
        "valor_ausente",
        "entero",
        "decimal",
        "booleano",
        "nulo",
        "lista",
        "objeto",
        "campo_actor_id",
        "campo_changed_at",
        "campo_status",
        "campo_requester_id",
    ],
)
def test_put_priority_body_only_admits_the_value(payload):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(f"/api/tickets/{created['id']}/priority", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).priority is None
    assert get_ticket_modification_log().count() == 0


@pytest.mark.parametrize(
    "raw", ["Urgente", "alta", "ALTA", " Alta ", "Alta ", "Alta\n", "", "   ", "Abierto"]
)
def test_put_out_of_catalog_priority_returns_422_without_change_or_record(raw):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": raw}
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).priority is None
    assert get_ticket_modification_log().count() == 0


def test_put_priority_with_malformed_json_returns_422_without_change_or_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    # JSON sintacticamente invalido enviado crudo: ticket abierto y sesion
    # de gestion, unico supuesto que llega al 422 (RF-30).
    response = api.put(
        f"/api/tickets/{created['id']}/priority",
        content=b'{"priority": ',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).priority is None
    assert get_ticket_modification_log().count() == 0


# --- T6 / RF-24 y RF-25: 404 uniforme ---


def test_put_priority_as_client_returns_unified_404_and_changes_nothing():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    unified = api.get(f"/api/tickets/{uuid.uuid4()}")

    assert response.status_code == unified.status_code == 404
    assert response.text == unified.text
    assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
    assert get_ticket_repository().find_by_id(created["id"]).priority is None
    assert get_ticket_modification_log().count() == 0


@pytest.mark.parametrize("ticket_id", [str(uuid.uuid4()), "no-es-uuid", "123"])
def test_put_priority_for_nonexistent_or_invalid_id_returns_404(ticket_id):
    _provision_and_login()

    response = api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )

    assert response.status_code == 404
    assert response.status_code not in (400, 403, 422)
    assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}


# --- T6 / RF-28: ticket cerrado -> 409 ---


def test_put_priority_on_closed_ticket_returns_409_without_change_or_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    closed = api.put(f"/api/tickets/{created['id']}/status", json={"status": "Cerrado"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "Cerrado"
    records_before = get_ticket_modification_log().count()

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )

    assert response.status_code == 409
    assert response.status_code not in (400, 403, 422)
    assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored.status == "Cerrado"
    assert stored.priority is None
    assert get_ticket_modification_log().count() == records_before == 1


# --- T6 / RF-30: sin sesion valida -> 401 ---


def test_put_priority_without_session_returns_401():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    api.cookies.clear()

    response = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )

    assert response.status_code == 401
    assert response.status_code not in (400, 403, 404, 409, 422)
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).priority is None
    assert get_ticket_modification_log().count() == 0

