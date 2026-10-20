"""T1 y T2 — Dominio y registro en memoria de modificaciones (RF-21, RF-26, RF-27.2).

Verifica:
- RF-21: el catalogo de prioridades (`PRIORITIES`) y el de estados
  (`STATUSES`) tienen exactamente cuatro valores cada uno, y
  `validate_priority`/`validate_status` los aceptan con coincidencia
  exacta: sin recorte, sin normalizar mayusculas y sin normalizar Unicode.
- RF-29.1 (dominio): un valor de tipo JSON no textual (numero, booleano,
  objeto, lista o nulo) se rechaza sin coercion a texto.
- RF-29.3 (dominio): un valor fuera del catalogo (`Urgente`, `alta`,
  ` Alta `, vacio, o de otro catalogo) se rechaza.
- RF-27.2 y RF-27.3: `Ticket` nace sin prioridad (`priority is None`) y con
  el estado `Abierto`; admite como prioridad los cuatro valores del catalogo.
- RF-26: `TicketModification` representa un cambio efectivo con ticket,
  campo, valor anterior, valor nuevo, responsable y fecha, y admite
  `previous_value` vacio (`None`) en la primera asignacion de prioridad.
- RF-26 (T2): `InMemoryTicketModificationLog` es un registro aparte
  append-only con singleton `get_ticket_modification_log()`: conserva los
  registros en orden de alta sin perdidas, `list_by_ticket` devuelve solo
  los del ticket (los empates de `changed_at` no fijan orden y las pruebas
  no lo afirman), `count`/`clear` funcionan y ninguna ruta publica expone
  el registro (no forma parte del contrato HTTP).
- Soporte de RF-24: `MANAGEMENT_ROLES` fija los roles con permisos de
  gestion de la historia (su aplicacion vive en la capa de aplicacion, T4).
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.main import app
from app.modules.tickets.domain.entities import (
    MANAGEMENT_ROLES,
    OPEN_STATUS,
    PRIORITIES,
    PRIORITY_FIELD,
    STATUSES,
    STATUS_FIELD,
    Ticket,
    TicketModification,
    validate_priority,
    validate_status,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
    get_ticket_modification_log,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_modification_log():
    get_ticket_modification_log().clear()
    yield
    get_ticket_modification_log().clear()


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


# --- RF-21: catalogos exactos ---


def test_priority_catalog_has_exactly_four_values():
    assert PRIORITIES == ("Crítica", "Alta", "Media", "Baja")
    assert len(PRIORITIES) == 4
    assert len(set(PRIORITIES)) == 4


def test_status_catalog_has_exactly_four_values():
    assert STATUSES == ("Abierto", "En progreso", "Resuelto", "Cerrado")
    assert len(STATUSES) == 4
    assert len(set(STATUSES)) == 4


def test_open_status_is_the_initial_value_of_the_status_catalog():
    assert OPEN_STATUS == "Abierto"
    assert OPEN_STATUS == STATUSES[0]


def test_management_roles_are_exactly_technician_and_administrator():
    assert isinstance(MANAGEMENT_ROLES, frozenset)
    assert MANAGEMENT_ROLES == frozenset({"tecnico", "administrador"})
    assert "cliente" not in MANAGEMENT_ROLES


def test_modification_field_names_are_fixed_by_the_plan():
    assert PRIORITY_FIELD == "priority"
    assert STATUS_FIELD == "status"


# --- RF-21: coincidencia exacta (valores validos) ---


@pytest.mark.parametrize("value", list(PRIORITIES))
def test_validate_priority_accepts_each_catalog_value(value):
    assert validate_priority(value) == value


@pytest.mark.parametrize("value", list(STATUSES))
def test_validate_status_accepts_each_catalog_value(value):
    assert validate_status(value) == value


# --- RF-21 y RF-29.3: valores fuera del catalogo ---


@pytest.mark.parametrize(
    "raw",
    [
        "Urgente",
        "alta",
        "ALTA",
        " Alta ",
        "Alta ",
        " Alta",
        "Alta\n",
        "critica",
        "Crítica ",
        "En progreso",
        "",
        "   ",
    ],
)
def test_validate_priority_rejects_out_of_catalog_values(raw):
    with pytest.raises(ValueError):
        validate_priority(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "Abierto ",
        " abierto",
        "ABIERTO",
        "En Progreso",
        "EN PROGRESO",
        "Resuelto ",
        "Cerrado.",
        "Abierta",
        "",
        "   ",
    ],
)
def test_validate_status_rejects_out_of_catalog_values(raw):
    with pytest.raises(ValueError):
        validate_status(raw)


def test_validate_priority_does_not_normalize_unicode():
    # NFD (composed) no es el mismo texto que el valor NFC del catalogo.
    decomposed = "Cri\u0301tica"
    assert decomposed != "Crítica"
    with pytest.raises(ValueError):
        validate_priority(decomposed)


def test_validators_do_not_accept_the_other_catalog_values():
    with pytest.raises(ValueError):
        validate_priority("Abierto")
    with pytest.raises(ValueError):
        validate_status("Alta")


# --- RF-29.1: tipo estricto sin coercion ---


@pytest.mark.parametrize("raw", [5, 5.5, True, False, {"value": "Alta"}, ["Alta"], None, b"Alta"])
def test_validate_priority_rejects_non_string_values_without_coercion(raw):
    with pytest.raises(ValueError):
        validate_priority(raw)


@pytest.mark.parametrize(
    "raw", [5, 5.5, True, False, {"value": "Abierto"}, ["Abierto"], None, b"Abierto"]
)
def test_validate_status_rejects_non_string_values_without_coercion(raw):
    with pytest.raises(ValueError):
        validate_status(raw)


# --- RF-27.2 y RF-27.3: `priority` en el ticket ---


def test_new_ticket_is_born_without_priority_and_open():
    ticket = _ticket()

    assert ticket.priority is None
    assert ticket.status == OPEN_STATUS
    assert ticket.status in STATUSES


def test_new_ticket_can_omit_priority_explicitly():
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id=str(uuid.uuid4()),
        created_at=NOW,
    )

    assert ticket.priority is None


@pytest.mark.parametrize("value", list(PRIORITIES))
def test_ticket_keeps_the_priority_value_stored(value):
    assert _ticket(priority=value).priority == value


def test_ticket_priority_and_status_are_independent_values():
    ticket = _ticket(priority="Alta", status="En progreso")

    assert ticket.priority == "Alta"
    assert ticket.status == "En progreso"


# --- RF-26: entidad `TicketModification` ---


def test_priority_modification_keeps_all_change_data():
    changed_at = datetime(2026, 10, 19, 12, 30, 15, 123456, tzinfo=timezone.utc)
    modification = TicketModification(
        ticket_id="t-1",
        field=PRIORITY_FIELD,
        previous_value="Media",
        new_value="Alta",
        actor_id="u-tech",
        changed_at=changed_at,
    )

    assert modification.ticket_id == "t-1"
    assert modification.field == "priority"
    assert modification.previous_value == "Media"
    assert modification.new_value == "Alta"
    assert modification.actor_id == "u-tech"
    assert modification.changed_at == changed_at


def test_status_modification_keeps_previous_and_new_values():
    modification = TicketModification(
        ticket_id="t-1",
        field=STATUS_FIELD,
        previous_value="Abierto",
        new_value="En progreso",
        actor_id="u-admin",
        changed_at=NOW,
    )

    assert modification.field == "status"
    assert modification.previous_value == "Abierto"
    assert modification.new_value == "En progreso"


def test_first_priority_modification_has_empty_previous_value():
    modification = TicketModification(
        ticket_id="t-1",
        field=PRIORITY_FIELD,
        previous_value=None,
        new_value="Crítica",
        actor_id="u-tech",
        changed_at=NOW,
    )

    assert modification.previous_value is None
    assert modification.new_value == "Crítica"
    assert modification.new_value in PRIORITIES


# --- RF-26 (T2): registro en memoria append-only ---


def _modification(**overrides) -> TicketModification:
    values = {
        "ticket_id": "t-1",
        "field": PRIORITY_FIELD,
        "previous_value": None,
        "new_value": "Alta",
        "actor_id": "u-1",
        "changed_at": NOW,
    }
    values.update(overrides)
    return TicketModification(**values)


def test_modification_log_is_singleton_with_count_and_clear():
    log = get_ticket_modification_log()
    assert log is get_ticket_modification_log()
    assert isinstance(log, InMemoryTicketModificationLog)
    assert log.count() == 0

    log.add(_modification())
    assert log.count() == 1

    log.clear()

    assert log.count() == 0
    assert log.list_by_ticket("t-1") == []


def test_log_keeps_the_records_of_a_ticket_in_registration_order():
    log = InMemoryTicketModificationLog()
    first = _modification(
        field=PRIORITY_FIELD,
        previous_value=None,
        new_value="Media",
        changed_at=NOW,
    )
    second = _modification(
        field=STATUS_FIELD,
        previous_value="Abierto",
        new_value="En progreso",
        changed_at=NOW + timedelta(minutes=5),
    )
    third = _modification(
        field=STATUS_FIELD,
        previous_value="En progreso",
        new_value="Resuelto",
        actor_id="u-2",
        changed_at=NOW + timedelta(minutes=10),
    )
    for modification in (first, second, third):
        log.add(modification)

    listed = log.list_by_ticket("t-1")

    assert listed == [first, second, third]
    assert [(m.field, m.new_value) for m in listed] == [
        (PRIORITY_FIELD, "Media"),
        (STATUS_FIELD, "En progreso"),
        (STATUS_FIELD, "Resuelto"),
    ]
    assert log.count() == 3


def test_list_by_ticket_returns_only_the_records_of_that_ticket():
    log = InMemoryTicketModificationLog()
    own = _modification(ticket_id="t-1", new_value="Alta")
    other = _modification(ticket_id="t-2", new_value="Baja")
    log.add(own)
    log.add(other)

    assert log.list_by_ticket("t-1") == [own]
    assert log.list_by_ticket("t-2") == [other]
    assert log.list_by_ticket("t-3") == []
    assert log.count() == 2


def test_reading_the_log_does_not_alter_it():
    log = InMemoryTicketModificationLog()
    own = _modification(ticket_id="t-1", new_value="Crítica")
    other = _modification(ticket_id="t-2", new_value="Media")
    log.add(own)
    log.add(other)

    log.list_by_ticket("t-1")
    log.list_by_ticket("t-9")

    assert log.count() == 2
    assert log.list_by_ticket("t-1") == [own]
    assert log.list_by_ticket("t-2") == [other]


def test_tied_timestamps_keep_every_record_without_asserting_order():
    """RF-26: un empate de `changed_at` no fija orden entre los registros."""
    log = InMemoryTicketModificationLog()
    tied = [
        _modification(previous_value=None, new_value="Media", changed_at=NOW),
        _modification(
            previous_value="Media", new_value="Alta", actor_id="u-2", changed_at=NOW
        ),
        _modification(
            field=STATUS_FIELD,
            previous_value="Abierto",
            new_value="Resuelto",
            actor_id="u-3",
            changed_at=NOW,
        ),
    ]
    for modification in tied:
        log.add(modification)

    listed = log.list_by_ticket("t-1")

    assert len(listed) == 3  # ninguno se pierde
    assert sorted(m.new_value for m in listed) == ["Alta", "Media", "Resuelto"]
    assert log.count() == 3


def test_successive_modifications_accumulate_ordered_without_loss():
    """RF-26: acumulativo, sin eliminarse por modificaciones posteriores."""
    log = InMemoryTicketModificationLog()
    changes = [
        _modification(
            previous_value=None,
            new_value="Media",
            actor_id="u-tech",
            changed_at=NOW,
        ),
        _modification(
            field=STATUS_FIELD,
            previous_value="Abierto",
            new_value="En progreso",
            actor_id="u-tech",
            changed_at=NOW + timedelta(minutes=1),
        ),
        _modification(
            previous_value="Media",
            new_value="Baja",
            actor_id="u-admin",
            changed_at=NOW + timedelta(minutes=2),
        ),
        _modification(
            field=STATUS_FIELD,
            previous_value="En progreso",
            new_value="Cerrado",
            actor_id="u-admin",
            changed_at=NOW + timedelta(minutes=3),
        ),
    ]
    for modification in changes:
        log.add(modification)

    listed = log.list_by_ticket("t-1")

    assert [(m.field, m.previous_value, m.new_value, m.actor_id) for m in listed] == [
        (PRIORITY_FIELD, None, "Media", "u-tech"),
        (STATUS_FIELD, "Abierto", "En progreso", "u-tech"),
        (PRIORITY_FIELD, "Media", "Baja", "u-admin"),
        (STATUS_FIELD, "En progreso", "Cerrado", "u-admin"),
    ]
    assert log.count() == 4


def test_no_public_route_exposes_the_modification_log():
    """RF-26: el registro no se expone por ninguna operacion publica."""
    schema = app.openapi()
    paths = schema["paths"]
    assert paths, "la aplicacion expone rutas"

    for path in paths:
        assert "modification" not in path.lower()
        assert "historial" not in path.lower()
        assert "history" not in path.lower()

    # Ni forma parte del contrato HTTP: ningun esquema publico lleva sus campos.
    serialized = json.dumps(schema)
    for field_name in ("changed_at", "previous_value", "actor_id"):
        assert field_name not in serialized
