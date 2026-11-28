"""HU-18 T1: evaluación conservada sin política vigente (RF-185/186/191)."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.sla.domain.entities import SLA_MET, TicketSlaSnapshot
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.sla.interface import contract

CREATED = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("priority", ("Crítica", "Alta", "Media", "Baja"))
@pytest.mark.parametrize(
    "elapsed,expected",
    (
        (timedelta(0), True),
        (timedelta(minutes=59, seconds=59), True),
        (timedelta(minutes=60), True),
        (timedelta(minutes=60, microseconds=1), False),
        (timedelta(minutes=120), False),
    ),
)
def test_evaluates_exact_resolution_deadline(priority, elapsed, expected):
    assert contract.evaluate_frozen_resolution(
        priority, CREATED, CREATED + elapsed, 60
    ) is expected


@pytest.mark.parametrize(
    "target",
    (None, 0, -1, True, False, 60.0, 0.5, "60", Decimal(60),
     float("inf"), float("nan"), [], {}),
)
def test_missing_or_invalid_frozen_target_is_not_evaluable(target):
    assert contract.evaluate_frozen_resolution(
        "Alta", CREATED, CREATED + timedelta(minutes=30), target
    ) is None


@pytest.mark.parametrize("priority", (None, "", "Urgente", "alta", 1, [], {}))
def test_priority_must_belong_to_the_existing_catalog(priority):
    assert contract.evaluate_frozen_resolution(
        priority, CREATED, CREATED + timedelta(minutes=30), 60
    ) is None


@pytest.mark.parametrize(
    "created,resolved",
    (
        (None, CREATED),
        (CREATED, None),
        ("2026-11-25T12:00:00Z", CREATED),
        (CREATED, "invalid"),
        (123, CREATED),
        (CREATED, CREATED - timedelta(microseconds=1)),
        (CREATED.replace(tzinfo=None), CREATED),
        (CREATED, CREATED.replace(tzinfo=None)),
        (CREATED.replace(tzinfo=None), CREATED.replace(tzinfo=None)),
    ),
)
def test_invalid_or_ambiguous_instants_are_not_evaluable(created, resolved):
    assert contract.evaluate_frozen_resolution(
        "Alta", created, resolved, 60
    ) is None


def test_compares_absolute_instants_in_different_timezones():
    created = CREATED.astimezone(timezone(timedelta(hours=5)))
    resolved = (CREATED + timedelta(minutes=60)).astimezone(
        timezone(timedelta(hours=-3))
    )
    assert contract.evaluate_frozen_resolution(
        "Alta", created, resolved, 60
    ) is True


@pytest.mark.parametrize(
    "created,target",
    (
        (datetime.max.replace(tzinfo=timezone.utc), 60),
        (CREATED, 10**100),
    ),
)
def test_unrepresentable_deadline_is_not_evaluable(created, target):
    assert contract.evaluate_frozen_resolution(
        "Alta", created, created, target
    ) is None


def test_delegates_to_existing_pure_sla_calculation(monkeypatch):
    from app.modules.sla.application import frozen_resolution

    calls = []
    original = frozen_resolution.calculate_sla
    resolved = CREATED + timedelta(minutes=60)

    def calculate(snapshot, target_minutes, now):
        calls.append((snapshot, target_minutes, now))
        result = original(snapshot, target_minutes, now)
        assert result.status == SLA_MET
        return result

    monkeypatch.setattr(frozen_resolution, "calculate_sla", calculate)
    assert contract.evaluate_frozen_resolution(
        "Alta", CREATED, resolved, 60
    ) is True
    assert calls == [(TicketSlaSnapshot("Alta", CREATED, resolved, 60), 60, resolved)]


def test_evaluator_never_reads_current_policy_or_uses_general_fallback(monkeypatch):
    from app.modules.sla.application import calculate_ticket_sla, policies

    repository = get_sla_policy_repository()

    def forbidden(*args, **kwargs):
        pytest.fail("HU-18 no debe leer la política ni usar el cálculo con fallback")

    monkeypatch.setattr(repository, "get_target_minutes", forbidden)
    monkeypatch.setattr(repository, "get_all", forbidden)
    monkeypatch.setattr(policies, "target_minutes_for", forbidden)
    monkeypatch.setattr(calculate_ticket_sla, "target_minutes_for", forbidden)
    monkeypatch.setattr(contract, "calculate_ticket_sla", forbidden)
    for target, expected in ((None, None), (0, None), (60, False), (240, True)):
        assert contract.evaluate_frozen_resolution(
            "Alta", CREATED, CREATED + timedelta(minutes=120), target
        ) is expected


def test_current_configuration_changes_do_not_change_frozen_results():
    repository = get_sla_policy_repository()
    original = repository.get_all()
    try:
        for current_target in (240, 30):
            repository.replace({**original, "Alta": current_target})
            results = [
                contract.evaluate_frozen_resolution(
                    "Alta", CREATED, CREATED + timedelta(minutes=elapsed), target
                )
                for elapsed, target in ((60, 60), (120, 60), (180, None))
            ]
            assert results == [True, False, None]
    finally:
        repository.replace(original)


def test_calculation_errors_are_not_masked_as_missing_data(monkeypatch):
    from app.modules.sla.application import frozen_resolution

    def broken(*args, **kwargs):
        raise RuntimeError("technical failure")

    monkeypatch.setattr(frozen_resolution, "calculate_sla", broken)
    with pytest.raises(RuntimeError, match="technical failure"):
        contract.evaluate_frozen_resolution("Alta", CREATED, CREATED, 60)
