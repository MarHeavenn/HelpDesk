"""HU-05 — Reglas de dominio del SLA (RF-43, RF-45, RF-50).

Mapa RF -> test:
- RF-43: inicio en la creacion, vencimiento y tiempos transcurrido y
  restante (`test_*_remaining`, `test_elapsed_and_remaining_truncate`).
- RF-45.1/RF-45.2: umbral exacto del 20 % y limite del vencimiento.
- RF-45.3/RF-46: resolucion antes, en y despues del vencimiento.
- RF-45.4: `near_due` y `breached` derivados del estado.
- RF-50: minutos enteros truncados y tiempo restante no negativo.

Todas las pruebas inyectan `now`, de modo que los limites son exactos y
no dependen del reloj real.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.domain.entities import (
    SLA_AT_RISK,
    SLA_BREACHED,
    SLA_MET,
    SLA_ON_TIME,
    TicketSlaSnapshot,
    calculate_sla,
)

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
TARGET = 120


def _snapshot(
    created_minutes_ago: int,
    *,
    resolved_minutes_ago: int | None = None,
) -> TicketSlaSnapshot:
    created_at = NOW - timedelta(minutes=created_minutes_ago)
    resolved_at = (
        None
        if resolved_minutes_ago is None
        else NOW - timedelta(minutes=resolved_minutes_ago)
    )
    return TicketSlaSnapshot(
        priority="Media",
        created_at=created_at,
        resolved_at=resolved_at,
    )


# --- RF-43: inicio, vencimiento, transcurrido y restante ---


def test_started_at_is_the_ticket_creation():
    snapshot = _snapshot(created_minutes_ago=30)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.started_at == snapshot.created_at


def test_due_at_is_start_plus_target_minutes():
    snapshot = _snapshot(created_minutes_ago=30)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.due_at == snapshot.created_at + timedelta(minutes=TARGET)


def test_elapsed_and_remaining_while_on_time():
    snapshot = _snapshot(created_minutes_ago=90)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.elapsed_minutes == 90
    assert sla.remaining_minutes == 30
    assert sla.status == SLA_ON_TIME


# --- RF-45.1: umbral del 20 % ---


def test_exactly_twenty_percent_remaining_is_at_risk():
    # 24 minutos restantes de 120: 24 <= 20 % de 120 y > 0.
    snapshot = _snapshot(created_minutes_ago=96)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.remaining_minutes == 24
    assert sla.status == SLA_AT_RISK
    assert sla.near_due is True


def test_just_above_twenty_percent_is_on_time():
    snapshot = _snapshot(created_minutes_ago=95)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.remaining_minutes == 25
    assert sla.status == SLA_ON_TIME
    assert sla.near_due is False


def test_inside_the_risk_window_is_at_risk():
    snapshot = _snapshot(created_minutes_ago=100)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.remaining_minutes == 20
    assert sla.status == SLA_AT_RISK


# --- RF-45.2: vencimiento ---


def test_exactly_at_due_is_breached():
    snapshot = _snapshot(created_minutes_ago=TARGET)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == SLA_BREACHED
    assert sla.breached is True
    assert sla.remaining_minutes == 0


def test_after_due_is_breached_and_remaining_is_zero():
    snapshot = _snapshot(created_minutes_ago=TARGET + 45)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == SLA_BREACHED
    assert sla.elapsed_minutes == TARGET + 45
    assert sla.remaining_minutes == 0


# --- RF-45.3 y RF-46: resolucion ---


def test_resolved_before_due_is_met():
    snapshot = _snapshot(
        created_minutes_ago=60, resolved_minutes_ago=30
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == SLA_MET
    assert sla.breached is False
    assert sla.remaining_minutes == 0
    assert sla.elapsed_minutes == 30


def test_resolved_exactly_at_due_is_met():
    snapshot = _snapshot(
        created_minutes_ago=TARGET, resolved_minutes_ago=0
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == SLA_MET
    assert sla.elapsed_minutes == TARGET


def test_resolved_after_due_is_breached():
    snapshot = _snapshot(
        created_minutes_ago=TARGET + 10, resolved_minutes_ago=0
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == SLA_BREACHED
    assert sla.breached is True
    assert sla.near_due is False


def test_resolved_ticket_ignores_the_current_time():
    snapshot = _snapshot(
        created_minutes_ago=60, resolved_minutes_ago=30
    )
    much_later = NOW + timedelta(days=30)

    sla = calculate_sla(snapshot, TARGET, much_later)

    assert sla.status == SLA_MET
    assert sla.elapsed_minutes == 30
    assert sla.remaining_minutes == 0


# --- RF-45.4: indicadores coherentes con el estado ---


@pytest.mark.parametrize(
    ("created_minutes_ago", "resolved_minutes_ago", "expected_status"),
    [
        (10, None, SLA_ON_TIME),
        (96, None, SLA_AT_RISK),
        (TARGET + 1, None, SLA_BREACHED),
        (30, 10, SLA_MET),
        (TARGET + 10, 0, SLA_BREACHED),
    ],
)
def test_indicators_match_the_status(
    created_minutes_ago: int,
    resolved_minutes_ago: int | None,
    expected_status: str,
):
    snapshot = _snapshot(
        created_minutes_ago, resolved_minutes_ago=resolved_minutes_ago
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.status == expected_status
    assert sla.near_due is (expected_status == SLA_AT_RISK)
    assert sla.breached is (expected_status == SLA_BREACHED)


# --- RF-50: precision ---


def test_elapsed_and_remaining_truncate_partial_minutes():
    snapshot = TicketSlaSnapshot(
        priority="Media",
        created_at=NOW - timedelta(minutes=30, seconds=30),
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.elapsed_minutes == 30
    assert sla.remaining_minutes == 89


def test_remaining_is_never_negative():
    snapshot = _snapshot(created_minutes_ago=TARGET * 10)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.remaining_minutes == 0
    assert sla.elapsed_minutes == TARGET * 10


def test_elapsed_is_never_negative_with_clock_skew():
    snapshot = TicketSlaSnapshot(
        priority="Media",
        created_at=NOW + timedelta(minutes=5),
    )

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.elapsed_minutes == 0


def test_target_minutes_is_preserved_in_the_result():
    snapshot = _snapshot(created_minutes_ago=1)

    sla = calculate_sla(snapshot, TARGET, NOW)

    assert sla.target_minutes == TARGET
