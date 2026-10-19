"""T5 (HU-03) — Caso de uso de actualizacion de estado (RF-23, RF-26, RF-29.3).

Mapa RF -> test:
- RF-21/RF-29.3 (catalogo exacto): `test_each_catalog_status_is_accepted`,
  `test_any_transition_between_open_states_is_allowed`,
  `test_out_of_catalog_status_is_rejected_without_change_or_record`,
  `test_validation_error_keeps_the_domain_message`.
- RF-29.1 (tipo estricto, en el caso de uso):
  `test_non_text_status_is_rejected_without_change_or_record`.
- RF-23 (transiciones libres, saltos y retrocesos, y repeticion del valor):
  `test_any_transition_between_open_states_is_allowed`,
  `test_jump_from_open_to_closed_is_allowed`,
  `test_regression_from_resolved_to_in_progress_is_allowed`,
  `test_repeating_the_current_status_does_not_change_or_record`,
  `test_status_change_mutates_the_ticket_stored_in_the_repository`.
- RF-26 (registro de cambios efectivos): todos los tests de registro, en
  particular `test_default_changed_at_uses_the_system_time_in_utc`,
  `test_successive_status_changes_accumulate_with_previous_values` y
  `test_returned_ticket_does_not_include_the_modification_record`.

`Cerrado` como estado de origen no llega a este caso de uso: RF-28 lo
rechaza antes en `get_modifiable_ticket` (T4). Aqui se verifican todas las
transiciones desde los estados no cerrados, con cualquier destino.
La seccion HTTP (T6) verifica `PUT /api/tickets/{ticket_id}/status` con
sesiones reales de tecnico y administrador: 200 con el ticket completo,
transiciones libres, cuerpo mono-campo estricto y 422, rol sin permisos /
inexistente / identificador invalido -> 404 uniforme, cerrado -> 409 y sin
sesion -> 401 (RF-23, RF-29.1, RF-29.2, RF-30).
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
from app.modules.tickets.application.update_ticket_status import update_ticket_status
from app.modules.tickets.domain.entities import (
    OPEN_STATUS,
    STATUSES,
    STATUS_FIELD,
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
    "created_at",
    "requester_id",
}
MODIFIABLE_SOURCE_STATUSES = [value for value in STATUSES if value != "Cerrado"]

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


# --- RF-21/RF-23/RF-29.3: catalogo y transiciones libres ---


@pytest.mark.parametrize("status", list(STATUSES))
def test_each_catalog_status_is_accepted(status):
    source = OPEN_STATUS if status != OPEN_STATUS else "En progreso"
    ticket = _ticket(status=source)
    log = InMemoryTicketModificationLog()

    returned = update_ticket_status(ticket, status, "u-tech", log, now=NOW)

    assert returned is ticket
    assert ticket.status == status
    assert log.count() == 1

    [record] = log.list_by_ticket(ticket.id)
    assert record.ticket_id == ticket.id
    assert record.field == STATUS_FIELD
    assert record.previous_value == source
    assert record.new_value == status
    assert record.actor_id == "u-tech"
    assert record.changed_at == NOW


@pytest.mark.parametrize("target", list(STATUSES))
@pytest.mark.parametrize("source", MODIFIABLE_SOURCE_STATUSES)
def test_any_transition_between_open_states_is_allowed(source, target):
    ticket = _ticket(status=source)
    log = InMemoryTicketModificationLog()

    update_ticket_status(ticket, target, "u-admin", log, now=NOW)

    assert ticket.status == target
    if source == target:
        assert log.count() == 0
    else:
        [record] = log.list_by_ticket(ticket.id)
        assert record.previous_value == source
        assert record.new_value == target


def test_jump_from_open_to_closed_is_allowed():
    """RF-23: HU-03 no impone secuencia; el salto directo es valido."""
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    update_ticket_status(ticket, "Cerrado", "u-tech", log, now=NOW)

    assert ticket.status == "Cerrado"
    [record] = log.list_by_ticket(ticket.id)
    assert record.previous_value == OPEN_STATUS
    assert record.new_value == "Cerrado"


def test_regression_from_resolved_to_in_progress_is_allowed():
    """RF-23: los retrocesos tambien son validos en HU-03."""
    ticket = _ticket(status="Resuelto")
    log = InMemoryTicketModificationLog()

    update_ticket_status(ticket, "En progreso", "u-tech", log, now=NOW)

    assert ticket.status == "En progreso"
    [record] = log.list_by_ticket(ticket.id)
    assert record.previous_value == "Resuelto"
    assert record.new_value == "En progreso"


@pytest.mark.parametrize(
    "raw",
    ["Abierta", "abierto", "ABIERTO", "En Progreso", "En progreso ", "Resuelto.", "", "   ", "Alta"],
)
def test_out_of_catalog_status_is_rejected_without_change_or_record(raw):
    ticket = _ticket(status="En progreso")
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError):
        update_ticket_status(ticket, raw, "u-tech", log, now=NOW)

    assert ticket.status == "En progreso"
    assert log.count() == 0


@pytest.mark.parametrize(
    "raw", [5, 5.5, True, False, {"value": "Resuelto"}, ["Resuelto"], None, b"Resuelto"]
)
def test_non_text_status_is_rejected_without_change_or_record(raw):
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError):
        update_ticket_status(ticket, raw, "u-tech", log, now=NOW)

    assert ticket.status == OPEN_STATUS
    assert log.count() == 0


def test_validation_error_keeps_the_domain_message():
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    with pytest.raises(TicketValidationError) as exc:
        update_ticket_status(ticket, "Abierta", "u-tech", log, now=NOW)

    assert str(exc.value) == "status must be one of Abierto, En progreso, Resuelto, Cerrado"

    with pytest.raises(TicketValidationError) as exc:
        update_ticket_status(ticket, None, "u-tech", log, now=NOW)

    assert str(exc.value) == "status must be text"


# --- RF-23: repetir el valor vigente no cambia ni registra ---


def test_repeating_the_current_status_does_not_change_or_record():
    ticket = _ticket(status="Resuelto")
    log = InMemoryTicketModificationLog()

    returned = update_ticket_status(ticket, "Resuelto", "u-tech", log, now=NOW)

    assert returned is ticket
    assert ticket.status == "Resuelto"
    assert log.count() == 0
    assert log.list_by_ticket(ticket.id) == []


# --- RF-26: fecha del sistema, acumulacion y registro fuera del ticket ---


def test_default_changed_at_uses_the_system_time_in_utc():
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    before = datetime.now(timezone.utc)
    update_ticket_status(ticket, "En progreso", "u-tech", log)
    after = datetime.now(timezone.utc)

    [record] = log.list_by_ticket(ticket.id)
    assert record.changed_at.tzinfo is not None
    assert record.changed_at.utcoffset().total_seconds() == 0
    assert before <= record.changed_at <= after


def test_successive_status_changes_accumulate_with_previous_values():
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    update_ticket_status(ticket, "En progreso", "u-tech", log, now=NOW)
    update_ticket_status(ticket, "Resuelto", "u-admin", log, now=NOW)
    update_ticket_status(ticket, "En progreso", "u-tech", log, now=NOW)
    update_ticket_status(ticket, "Cerrado", "u-admin", log, now=NOW)

    records = log.list_by_ticket(ticket.id)
    assert [(r.previous_value, r.new_value, r.actor_id) for r in records] == [
        ("Abierto", "En progreso", "u-tech"),
        ("En progreso", "Resuelto", "u-admin"),
        ("Resuelto", "En progreso", "u-tech"),
        ("En progreso", "Cerrado", "u-admin"),
    ]
    assert log.count() == 4
    assert ticket.status == "Cerrado"


def test_returned_ticket_does_not_include_the_modification_record():
    ticket = _ticket(status=OPEN_STATUS)
    log = InMemoryTicketModificationLog()

    returned = update_ticket_status(ticket, "En progreso", "u-tech", log, now=NOW)

    # El registro vive solo en el log: el ticket devuelto no lo incorpora.
    assert returned is ticket
    assert not hasattr(returned, "previous_value")
    assert not hasattr(returned, "new_value")
    assert not hasattr(returned, "actor_id")
    assert not hasattr(returned, "changed_at")
    assert not hasattr(returned, "modifications")


# --- RF-23/RF-27.1: el ticket almacenado queda actualizado ---


def test_status_change_mutates_the_ticket_stored_in_the_repository():
    ticket = _ticket(status=OPEN_STATUS)
    repo = InMemoryTicketRepository()
    repo.add(ticket)
    log = InMemoryTicketModificationLog()

    update_ticket_status(ticket, "Resuelto", "u-tech", log, now=NOW)

    stored = repo.find_by_id(ticket.id)
    assert stored is ticket
    assert stored.status == "Resuelto"
    assert stored.priority is None


# --- T6 / RF-23: PUT /api/tickets/{ticket_id}/status (200) ---


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_put_status_by_management_role_returns_full_updated_ticket(role):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    actor = _provision_and_login(role=role)

    response = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "En progreso"}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == created["id"]
    assert body["title"] == "Titulo"
    assert body["description"] == "Descripcion"
    assert body["priority"] is None
    assert body["status"] == "En progreso"
    assert body["created_at"] == created["created_at"]
    assert body["requester_id"] == requester["id"]
    assert "previous_value" not in response.text
    assert "changed_at" not in response.text

    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    assert stored.status == "En progreso"
    [record] = get_ticket_modification_log().list_by_ticket(created["id"])
    assert record.field == STATUS_FIELD
    assert record.previous_value == OPEN_STATUS
    assert record.new_value == "En progreso"
    assert record.actor_id == actor.id


@pytest.mark.parametrize("status", list(STATUSES))
def test_put_status_accepts_each_catalog_value(status):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": status}
    )

    assert response.status_code == 200
    assert response.json()["status"] == status
    if status == OPEN_STATUS:
        # Repetir el estado vigente: 200 sin registro.
        assert get_ticket_modification_log().count() == 0
    else:
        assert get_ticket_modification_log().list_by_ticket(created["id"])[
            0
        ].new_value == status


def test_put_status_allows_regression_without_sequence_rules():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    resolved = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Resuelto"}
    )
    regression = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "En progreso"}
    )

    assert resolved.status_code == 200
    assert regression.status_code == 200
    assert regression.json()["status"] == "En progreso"
    records = get_ticket_modification_log().list_by_ticket(created["id"])
    assert [(r.previous_value, r.new_value) for r in records] == [
        (OPEN_STATUS, "Resuelto"),
        ("Resuelto", "En progreso"),
    ]


def test_put_repeated_status_returns_200_without_new_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    first = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "En progreso"}
    )
    second = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "En progreso"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "En progreso"
    assert get_ticket_modification_log().count() == 1


def test_put_status_keeps_the_current_priority():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    with_priority = api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    changed = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Resuelto"}
    )

    assert with_priority.status_code == 200
    assert changed.status_code == 200
    body = changed.json()
    assert body["priority"] == "Alta"
    assert body["status"] == "Resuelto"


# --- T6 / RF-29.1 y RF-29.2: cuerpo mono-campo estricto (422) ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"status": 5},
        {"status": 5.5},
        {"status": True},
        {"status": None},
        {"status": ["Resuelto"]},
        {"status": {"value": "Resuelto"}},
        {"status": "Resuelto", "actor_id": "00000000-0000-0000-0000-000000000000"},
        {"status": "Resuelto", "changed_at": "2026-10-19T12:00:00+00:00"},
        {"status": "Resuelto", "priority": "Alta"},
        {"status": "Resuelto", "requester_id": "00000000-0000-0000-0000-000000000000"},
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
        "campo_priority",
        "campo_requester_id",
    ],
)
def test_put_status_body_only_admits_the_value(payload):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(f"/api/tickets/{created['id']}/status", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).status == OPEN_STATUS
    assert get_ticket_modification_log().count() == 0


@pytest.mark.parametrize(
    "raw",
    ["Abierta", "abierto", "ABIERTO", "En Progreso", "En progreso ", "Resuelto.", "", "   ", "Alta"],
)
def test_put_out_of_catalog_status_returns_422_without_change_or_record(raw):
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    response = api.put(f"/api/tickets/{created['id']}/status", json={"status": raw})

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).status == OPEN_STATUS
    assert get_ticket_modification_log().count() == 0


def test_put_status_with_malformed_json_returns_422_without_change_or_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    # JSON sintacticamente invalido enviado crudo: ticket abierto y sesion
    # de gestion, unico supuesto que llega al 422 (RF-30).
    response = api.put(
        f"/api/tickets/{created['id']}/status",
        content=b'{"status": ',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).status == OPEN_STATUS
    assert get_ticket_modification_log().count() == 0


# --- T6 / RF-24 y RF-25: 404 uniforme ---


def test_put_status_as_client_returns_unified_404_and_changes_nothing():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()

    response = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Resuelto"}
    )
    unified = api.get(f"/api/tickets/{uuid.uuid4()}")

    assert response.status_code == unified.status_code == 404
    assert response.text == unified.text
    assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
    assert get_ticket_repository().find_by_id(created["id"]).status == OPEN_STATUS
    assert get_ticket_modification_log().count() == 0


@pytest.mark.parametrize("ticket_id", [str(uuid.uuid4()), "no-es-uuid", "123"])
def test_put_status_for_nonexistent_or_invalid_id_returns_404(ticket_id):
    _provision_and_login()

    response = api.put(f"/api/tickets/{ticket_id}/status", json={"status": "Resuelto"})

    assert response.status_code == 404
    assert response.status_code not in (400, 403, 422)
    assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}


# --- T6 / RF-28: ticket cerrado -> 409 ---


def test_put_status_on_closed_ticket_returns_409_without_change_or_record():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    _provision_and_login()

    closed = api.put(f"/api/tickets/{created['id']}/status", json={"status": "Cerrado"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "Cerrado"
    records_before = get_ticket_modification_log().count()

    response = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Abierto"}
    )

    assert response.status_code == 409
    assert response.status_code not in (400, 403, 422)
    assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored.status == "Cerrado"
    assert get_ticket_modification_log().count() == records_before == 1


# --- T6 / RF-30: sin sesion valida -> 401 ---


def test_put_status_without_session_returns_401():
    requester = _register_client()
    _login(requester["email"])
    created = _create_ticket()
    api.cookies.clear()

    response = api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Resuelto"}
    )

    assert response.status_code == 401
    assert response.status_code not in (400, 403, 404, 409, 422)
    assert "detail" in response.json()
    assert get_ticket_repository().find_by_id(created["id"]).status == OPEN_STATUS
    assert get_ticket_modification_log().count() == 0
