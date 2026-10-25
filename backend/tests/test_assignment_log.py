"""T2 — Registro de asignaciones en memoria, append-only (RF-37).

Verifica:
- RF-37: `InMemoryAssignmentLog` es un registro aparte append-only con
  singleton `get_assignment_log()`: conserva los registros en orden de
  alta sin perdidas, `list_by_ticket` devuelve solo los del ticket (los
  empates de `assigned_at` no fijan orden y las pruebas no lo afirman),
  `count`/`clear` funcionan y ninguna operacion publica expone el
  registro (no forma parte del contrato HTTP).
- RF-37: el registro es acumulativo y no sustituye ni altera el registro
  de modificaciones de HU-03 (`InMemoryTicketModificationLog`).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.main import app
from app.modules.tickets.domain.entities import AssignmentRecord
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_assignment_log():
    get_assignment_log().clear()
    yield
    get_assignment_log().clear()


def _record(**overrides) -> AssignmentRecord:
    values = {
        "ticket_id": "t-1",
        "previous_assignee_id": None,
        "new_assignee_id": "u-tech",
        "actor_id": "u-admin",
        "assigned_at": NOW,
    }
    values.update(overrides)
    return AssignmentRecord(**values)


# --- RF-37: singleton, `count` y `clear` ---


def test_assignment_log_is_singleton_with_count_and_clear():
    log = get_assignment_log()
    assert log is get_assignment_log()
    assert isinstance(log, InMemoryAssignmentLog)
    assert log.count() == 0

    log.add(_record())
    assert log.count() == 1

    log.clear()

    assert log.count() == 0
    assert log.list_by_ticket("t-1") == []


# --- RF-37: orden de alta ---


def test_log_keeps_the_records_of_a_ticket_in_registration_order():
    log = InMemoryAssignmentLog()
    first = _record(
        previous_assignee_id=None,
        new_assignee_id="u-tech-1",
        assigned_at=NOW,
    )
    second = _record(
        previous_assignee_id="u-tech-1",
        new_assignee_id="u-tech-2",
        assigned_at=NOW + timedelta(minutes=5),
    )
    third = _record(
        previous_assignee_id="u-tech-2",
        new_assignee_id="u-tech-3",
        actor_id="u-admin-2",
        assigned_at=NOW + timedelta(minutes=10),
    )
    for record in (first, second, third):
        log.add(record)

    listed = log.list_by_ticket("t-1")

    assert listed == [first, second, third]
    assert [(r.previous_assignee_id, r.new_assignee_id) for r in listed] == [
        (None, "u-tech-1"),
        ("u-tech-1", "u-tech-2"),
        ("u-tech-2", "u-tech-3"),
    ]
    assert log.count() == 3


def test_successive_assignments_accumulate_ordered_without_loss():
    """RF-37: acumulativo, sin eliminarse por asignaciones posteriores."""
    log = InMemoryAssignmentLog()
    changes = [
        _record(previous_assignee_id=None, new_assignee_id="u-tech-1", assigned_at=NOW),
        _record(
            previous_assignee_id="u-tech-1",
            new_assignee_id="u-tech-2",
            assigned_at=NOW + timedelta(minutes=1),
        ),
        _record(
            previous_assignee_id="u-tech-2",
            new_assignee_id="u-tech-3",
            actor_id="u-admin-2",
            assigned_at=NOW + timedelta(minutes=2),
        ),
        _record(
            previous_assignee_id="u-tech-3",
            new_assignee_id="u-tech-1",
            actor_id="u-admin-3",
            assigned_at=NOW + timedelta(minutes=3),
        ),
    ]
    for record in changes:
        log.add(record)

    listed = log.list_by_ticket("t-1")

    assert [
        (r.previous_assignee_id, r.new_assignee_id, r.actor_id) for r in listed
    ] == [
        (None, "u-tech-1", "u-admin"),
        ("u-tech-1", "u-tech-2", "u-admin"),
        ("u-tech-2", "u-tech-3", "u-admin-2"),
        ("u-tech-3", "u-tech-1", "u-admin-3"),
    ]
    assert log.count() == 4


def test_adding_the_same_record_twice_does_not_overwrite_it():
    """RF-37: append-only; nada se sobreescribe ni se elimina al anadir."""
    log = InMemoryAssignmentLog()
    record = _record()

    log.add(record)
    log.add(record)

    assert log.count() == 2
    assert log.list_by_ticket("t-1") == [record, record]


# --- RF-37: `list_by_ticket` ---


def test_list_by_ticket_returns_only_the_records_of_that_ticket():
    log = InMemoryAssignmentLog()
    own = _record(ticket_id="t-1", new_assignee_id="u-tech-1")
    other = _record(ticket_id="t-2", new_assignee_id="u-tech-2")
    log.add(own)
    log.add(other)

    assert log.list_by_ticket("t-1") == [own]
    assert log.list_by_ticket("t-2") == [other]
    assert log.list_by_ticket("t-3") == []
    assert log.count() == 2


def test_reading_the_log_does_not_alter_it():
    log = InMemoryAssignmentLog()
    own = _record(ticket_id="t-1", new_assignee_id="u-tech-1")
    other = _record(ticket_id="t-2", new_assignee_id="u-tech-2")
    log.add(own)
    log.add(other)

    log.list_by_ticket("t-1")
    log.list_by_ticket("t-9")

    assert log.count() == 2
    assert log.list_by_ticket("t-1") == [own]
    assert log.list_by_ticket("t-2") == [other]


# --- RF-37: empates de fecha ---


def test_tied_timestamps_keep_every_record_without_asserting_order():
    """RF-37: un empate de `assigned_at` no fija orden entre los registros."""
    log = InMemoryAssignmentLog()
    tied = [
        _record(previous_assignee_id=None, new_assignee_id="u-tech-1", assigned_at=NOW),
        _record(
            previous_assignee_id="u-tech-1",
            new_assignee_id="u-tech-2",
            actor_id="u-admin-2",
            assigned_at=NOW,
        ),
        _record(
            previous_assignee_id="u-tech-2",
            new_assignee_id="u-tech-3",
            actor_id="u-admin-3",
            assigned_at=NOW,
        ),
    ]
    for record in tied:
        log.add(record)

    listed = log.list_by_ticket("t-1")

    assert len(listed) == 3  # ninguno se pierde
    assert sorted(r.new_assignee_id for r in listed) == [
        "u-tech-1",
        "u-tech-2",
        "u-tech-3",
    ]
    assert log.count() == 3


# --- RF-37: independencia del registro de modificaciones de HU-03 ---


def test_assignment_log_is_independent_from_the_modification_log():
    """RF-37: no sustituye ni altera el registro de HU-03."""
    assignment_log = get_assignment_log()
    modification_log = get_ticket_modification_log()
    assert assignment_log is not modification_log
    assert not isinstance(assignment_log, type(modification_log))

    assignment_log.add(_record())

    assert assignment_log.count() == 1
    assert modification_log.count() == 0


# --- RF-37: el registro no se expone por ninguna operacion publica ---


def test_no_public_route_exposes_the_assignment_log():
    """RF-37: el registro no forma parte del contrato HTTP."""
    schema = app.openapi()
    paths = schema["paths"]
    assert paths, "la aplicacion expone rutas"

    for path in paths:
        assert "history" not in path.lower()
        assert "historial" not in path.lower()
        assert "record" not in path.lower()

    # Ni forma parte del contrato HTTP: ningun esquema publico lleva sus campos.
    serialized = json.dumps(schema)
    for field_name in (
        "previous_assignee_id",
        "new_assignee_id",
        "assigned_at",
        "actor_id",
    ):
        assert field_name not in serialized
