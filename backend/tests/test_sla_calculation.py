"""HU-05 y HU-14 — Politicas y caso de uso de calculo del SLA.

Mapa RF -> test:
- RF-41: valores iniciales exactos por prioridad y uso del objetivo de la
  prioridad vigente.
- RF-42: un ticket sin prioridad no tiene SLA.
- RF-43.1 y RF-47: el vencimiento se calcula desde la creacion, tambien
  despues de un cambio de prioridad.
- RF-46: al reabrir (sin `resolved_at`) el SLA vuelve a evolucionar.
- HU-14 RF-76: el calculo usa la configuracion vigente del repositorio en
  memoria en cada llamada, sin cachearla y sin cambiar los contratos.
"""

import inspect
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.application.calculate_ticket_sla import (
    calculate_ticket_sla,
)
from app.modules.sla.application.policies import (
    DEFAULT_SLA_TARGET_MINUTES,
    target_minutes_for,
)
from app.modules.sla.domain.entities import (
    SLA_BREACHED,
    SLA_MET,
    SLA_ON_TIME,
    TicketSlaSnapshot,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.sla.interface.contract import get_ticket_sla

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
CREATED = NOW - timedelta(hours=3)


@pytest.fixture(autouse=True)
def reset_sla_policies():
    """Aisla cada prueba de la configuracion global en memoria (HU-14)."""
    get_sla_policy_repository().reset()
    yield
    get_sla_policy_repository().reset()


def _snapshot(priority: str | None, **kwargs) -> TicketSlaSnapshot:
    return TicketSlaSnapshot(
        priority=priority,
        created_at=kwargs.get("created_at", CREATED),
        resolved_at=kwargs.get("resolved_at"),
    )


# --- RF-41: valores iniciales ---


def test_default_targets_are_the_initial_values():
    assert DEFAULT_SLA_TARGET_MINUTES == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }


@pytest.mark.parametrize(
    ("priority", "expected_minutes"),
    [
        ("Crítica", 120),
        ("Alta", 240),
        ("Media", 720),
        ("Baja", 1440),
    ],
)
def test_each_priority_uses_its_target(priority, expected_minutes):
    snapshot = _snapshot(priority)

    sla = calculate_ticket_sla(snapshot, now=NOW)

    assert sla is not None
    assert sla.target_minutes == expected_minutes
    assert sla.due_at == CREATED + timedelta(minutes=expected_minutes)


def test_target_minutes_for_unknown_priority_is_none():
    assert target_minutes_for("Urgente") is None
    assert target_minutes_for(None) is None


# --- RF-42: ticket sin prioridad ---


def test_ticket_without_priority_has_no_sla():
    assert calculate_ticket_sla(_snapshot(None), now=NOW) is None


def test_contract_returns_none_without_priority():
    assert get_ticket_sla(_snapshot(None), now=NOW) is None


def test_unknown_priority_has_no_sla():
    assert calculate_ticket_sla(_snapshot("Urgente"), now=NOW) is None


# --- RF-43.1 y RF-47: el vencimiento parte de la creacion ---


def test_due_is_computed_from_creation_even_if_priority_is_set_late():
    # Ticket creado hace 3 h y prioridad Critica (2 h): ya nace incumplido.
    snapshot = _snapshot("Crítica")

    sla = calculate_ticket_sla(snapshot, now=NOW)

    assert sla is not None
    assert sla.started_at == CREATED
    assert sla.due_at == CREATED + timedelta(minutes=120)
    assert sla.status == SLA_BREACHED


def test_priority_change_recalculates_the_due_date_only():
    snapshot = _snapshot("Alta")

    alta = calculate_ticket_sla(snapshot, now=NOW)
    critica = calculate_ticket_sla(
        TicketSlaSnapshot(
            priority="Crítica",
            created_at=snapshot.created_at,
        ),
        now=NOW,
    )

    assert alta is not None and critica is not None
    assert alta.started_at == critica.started_at == CREATED
    assert alta.due_at - critica.due_at == timedelta(minutes=120)
    assert critica.target_minutes == 120


# --- RF-46: reapertura ---


def test_reopened_ticket_resumes_from_creation():
    # Resuelto hace 2 h dentro de plazo; al reabrir, ahora ya paso el
    # vencimiento de Critica (2 h desde la creacion).
    snapshot = TicketSlaSnapshot(
        priority="Crítica",
        created_at=CREATED,
        resolved_at=None,
    )

    sla = calculate_ticket_sla(snapshot, now=NOW)

    assert sla is not None
    assert sla.status == SLA_BREACHED
    assert sla.elapsed_minutes == 180


def test_resolved_snapshot_uses_the_resolution_time():
    resolved_at = CREATED + timedelta(minutes=30)
    snapshot = _snapshot("Media", resolved_at=resolved_at)

    sla = calculate_ticket_sla(snapshot, now=NOW + timedelta(days=5))

    assert sla is not None
    assert sla.status == SLA_MET
    assert sla.elapsed_minutes == 30
    assert sla.remaining_minutes == 0


def test_contract_matches_the_application_result():
    snapshot = _snapshot("Media")

    assert get_ticket_sla(snapshot, now=NOW) == calculate_ticket_sla(
        snapshot, now=NOW
    )


def test_fresh_ticket_with_priority_is_on_time():
    snapshot = TicketSlaSnapshot(priority="Baja", created_at=NOW)

    sla = calculate_ticket_sla(snapshot, now=NOW)

    assert sla is not None
    assert sla.status == SLA_ON_TIME
    assert sla.elapsed_minutes == 0
    assert sla.remaining_minutes == 1440


# --- HU-14 RF-76: configuracion vigente del repositorio ---


def _replace(priority: str, minutes: int) -> None:
    """Reemplaza un unico objetivo conservando el resto de la semilla."""
    targets = dict(DEFAULT_SLA_TARGET_MINUTES)
    targets[priority] = minutes
    get_sla_policy_repository().replace(targets)


def test_target_minutes_for_reads_the_repository_on_each_call():
    assert target_minutes_for("Crítica") == 120

    _replace("Crítica", 60)
    assert target_minutes_for("Crítica") == 60

    # Un segundo cambio se refleja sin cache: se relee en cada llamada.
    _replace("Crítica", 90)
    assert target_minutes_for("Crítica") == 90


def test_calculation_uses_the_current_configuration():
    _replace("Crítica", 60)
    snapshot = TicketSlaSnapshot(priority="Crítica", created_at=NOW)

    sla = calculate_ticket_sla(snapshot, now=NOW)

    assert sla is not None
    assert sla.target_minutes == 60
    assert sla.due_at == NOW + timedelta(minutes=60)


def test_changing_the_configuration_moves_the_due_date():
    snapshot = TicketSlaSnapshot(priority="Crítica", created_at=NOW)

    before = calculate_ticket_sla(snapshot, now=NOW)
    _replace("Crítica", 60)
    after = calculate_ticket_sla(snapshot, now=NOW)

    assert before is not None and after is not None
    assert before.due_at - after.due_at == timedelta(minutes=60)
    assert after.target_minutes == 60


def test_contract_and_application_agree_with_a_custom_configuration():
    _replace("Alta", 180)
    snapshot = TicketSlaSnapshot(priority="Alta", created_at=CREATED)

    assert get_ticket_sla(snapshot, now=NOW) == calculate_ticket_sla(
        snapshot, now=NOW
    )
    assert get_ticket_sla(snapshot, now=NOW).target_minutes == 180


def test_absent_and_unknown_priorities_stay_none_with_a_custom_configuration():
    _replace("Crítica", 60)

    assert target_minutes_for(None) is None
    assert target_minutes_for("Urgente") is None
    assert calculate_ticket_sla(_snapshot(None), now=NOW) is None
    assert calculate_ticket_sla(_snapshot("Urgente"), now=NOW) is None


def test_contract_signatures_are_unchanged():
    contract = inspect.signature(get_ticket_sla)
    application = inspect.signature(calculate_ticket_sla)

    assert list(contract.parameters) == ["snapshot", "now"]
    assert list(application.parameters) == ["snapshot", "now"]
    assert contract.parameters["now"].default is None
    assert application.parameters["now"].default is None
