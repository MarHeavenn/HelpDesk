"""HU-08 T1 — flujo del ciclo de vida en el dominio (RF-71, RF-74, RF-77).

Verifica sin HTTP:

- El catálogo conserva los cuatro estados y su orden de HU-03.
- `STATUS_TRANSITIONS` contiene exactamente las transiciones permitidas:
  `Abierto` -> `En progreso`, `En progreso` -> `Resuelto`,
  `Resuelto` -> `Cerrado` y `Resuelto` -> `En progreso`.
- `Cerrado` no tiene destinos por `PUT /status`; su salida es la
  reapertura, reservada a `REOPEN_ROLES` (administrador).
- Repetir el estado no es una transición (el caso de uso lo resuelve como
  no-op antes de consultar la tabla).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    IN_PROGRESS_STATUS,
    OPEN_STATUS,
    REOPEN_ROLES,
    RESOLVED_STATUS,
    STATUS_TRANSITIONS,
    STATUSES,
    is_allowed_status_transition,
)

VALID = [
    (OPEN_STATUS, IN_PROGRESS_STATUS),
    (IN_PROGRESS_STATUS, RESOLVED_STATUS),
    (RESOLVED_STATUS, CLOSED_STATUS),
    (RESOLVED_STATUS, IN_PROGRESS_STATUS),
]


def test_catalog_keeps_the_four_statuses_in_order():
    assert STATUSES == (
        "Abierto",
        "En progreso",
        "Resuelto",
        "Cerrado",
    )
    assert OPEN_STATUS == "Abierto"
    assert IN_PROGRESS_STATUS == "En progreso"
    assert RESOLVED_STATUS == "Resuelto"
    assert CLOSED_STATUS == "Cerrado"


def test_transition_table_is_exact():
    assert STATUS_TRANSITIONS == {
        OPEN_STATUS: frozenset({IN_PROGRESS_STATUS}),
        IN_PROGRESS_STATUS: frozenset({RESOLVED_STATUS}),
        RESOLVED_STATUS: frozenset({CLOSED_STATUS, IN_PROGRESS_STATUS}),
        CLOSED_STATUS: frozenset(),
    }


@pytest.mark.parametrize("current,new", VALID)
def test_valid_transitions(current, new):
    assert is_allowed_status_transition(current, new) is True


@pytest.mark.parametrize(
    "current,new",
    [
        (OPEN_STATUS, OPEN_STATUS),
        (OPEN_STATUS, RESOLVED_STATUS),
        (OPEN_STATUS, CLOSED_STATUS),
        (IN_PROGRESS_STATUS, OPEN_STATUS),
        (IN_PROGRESS_STATUS, IN_PROGRESS_STATUS),
        (IN_PROGRESS_STATUS, CLOSED_STATUS),
        (RESOLVED_STATUS, OPEN_STATUS),
        (RESOLVED_STATUS, RESOLVED_STATUS),
        (CLOSED_STATUS, OPEN_STATUS),
        (CLOSED_STATUS, IN_PROGRESS_STATUS),
        (CLOSED_STATUS, RESOLVED_STATUS),
        (CLOSED_STATUS, CLOSED_STATUS),
    ],
)
def test_invalid_or_repeated_transitions(current, new):
    assert is_allowed_status_transition(current, new) is False


def test_repeating_the_current_status_is_not_a_transition():
    for status in STATUSES:
        assert is_allowed_status_transition(status, status) is False


def test_closed_has_no_outgoing_transitions():
    assert STATUS_TRANSITIONS[CLOSED_STATUS] == frozenset()


def test_unknown_current_status_has_no_transitions():
    assert is_allowed_status_transition("Cancelado", OPEN_STATUS) is False


def test_only_administrator_can_reopen():
    assert REOPEN_ROLES == frozenset({"administrador"})
