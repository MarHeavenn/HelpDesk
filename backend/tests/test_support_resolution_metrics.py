"""HU-18 T3: volumen y promedio precisos (RF-181–184/188/189)."""

from dataclasses import FrozenInstanceError, asdict, dataclass, replace
from datetime import datetime, timedelta, timezone, tzinfo
from math import isfinite

import pytest

from app.modules.tickets.domain import support_metrics
from app.modules.tickets.domain.support_metrics import TicketMetricsSnapshot

CREATED = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)


def _row(identifier="ticket-1", **overrides):
    values = {
        "id": identifier,
        "company_id": "company-a",
        "status": "Resuelto",
        "priority": None,
        "created_at": CREATED,
        "resolved_at": CREATED + timedelta(minutes=60),
        "resolved_target_minutes": None,
    }
    return TicketMetricsSnapshot(**{**values, **overrides})


def _aggregate(rows):
    return support_metrics.aggregate_resolution_metrics(rows)


def _assert_invariants(result):
    assert result.total_tickets == result.resolved_tickets + result.pending_tickets
    assert result.resolved_tickets == (
        result.resolution_sample_size + result.resolution_excluded_count
    )
    assert all(isinstance(value, int) and value >= 0 for value in (
        result.total_tickets, result.resolved_tickets, result.pending_tickets,
        result.resolution_sample_size, result.resolution_excluded_count,
    ))
    assert (result.average_resolution_minutes is None) == (
        result.resolution_sample_size == 0
    )
    if result.average_resolution_minutes is not None:
        assert isfinite(result.average_resolution_minutes)
        assert result.average_resolution_minutes >= 0


def test_empty_has_zero_volume_and_no_resolution_sample():
    result = _aggregate(())

    assert asdict(result) == {
        "total_tickets": 0,
        "resolved_tickets": 0,
        "pending_tickets": 0,
        "average_resolution_minutes": None,
        "resolution_sample_size": 0,
        "resolution_excluded_count": 0,
    }
    _assert_invariants(result)


@pytest.mark.parametrize(
    "status,resolved",
    (("Abierto", 0), ("En progreso", 0), ("Resuelto", 1), ("Cerrado", 1),
     ("Otro estado", 0), ("", 0), (None, 0)),
)
def test_current_status_alone_classifies_volume_and_finalized_sample(status, resolved):
    result = _aggregate((_row(status=status),))

    assert result.total_tickets == 1
    assert result.resolved_tickets == resolved
    assert result.pending_tickets == 1 - resolved
    assert result.resolution_sample_size == resolved
    assert result.average_resolution_minutes == (60 if resolved else None)
    _assert_invariants(result)


def test_reference_example_uses_only_valid_finalized_resolution_dates():
    rows = (
        _row("open", status="Abierto"),
        _row("progress", status="En progreso"),
        _row("resolved"),
        _row("closed", status="Cerrado", resolved_at=CREATED + timedelta(minutes=120)),
        _row("invalid-closed", status="Cerrado", resolved_at=None),
    )
    result = _aggregate(rows)

    assert asdict(result) == {
        "total_tickets": 5,
        "resolved_tickets": 3,
        "pending_tickets": 2,
        "average_resolution_minutes": 90.0,
        "resolution_sample_size": 2,
        "resolution_excluded_count": 1,
    }
    _assert_invariants(result)


def test_zero_duration_is_a_real_sample_not_missing_data():
    result = _aggregate((_row(resolved_at=CREATED),))

    assert result.average_resolution_minutes == 0
    assert result.resolution_sample_size == 1
    assert result.resolution_excluded_count == 0
    _assert_invariants(result)


@pytest.mark.parametrize(
    "durations,expected",
    (
        ((timedelta(seconds=20), timedelta(seconds=40)), 0.5),
        ((timedelta(microseconds=1), timedelta(seconds=59, microseconds=999999)), 0.5),
        ((timedelta(seconds=1), timedelta(seconds=2)), 0.025),
        ((timedelta(microseconds=1),), 1 / 60_000_000),
    ),
)
def test_average_never_truncates_or_rounds_individual_durations(durations, expected):
    result = _aggregate(tuple(
        _row(f"ticket-{index}", resolved_at=CREATED + duration)
        for index, duration in enumerate(durations)
    ))

    assert result.average_resolution_minutes == pytest.approx(expected, rel=1e-12, abs=0)
    assert result.resolution_sample_size == len(durations)
    _assert_invariants(result)


@pytest.mark.parametrize(
    "created,resolved",
    (
        (None, CREATED),
        (CREATED, None),
        ("invalid", CREATED),
        (CREATED, "invalid"),
        (123, CREATED),
        (CREATED, []),
        (CREATED.replace(tzinfo=None), CREATED),
        (CREATED, CREATED.replace(tzinfo=None)),
        (CREATED.replace(tzinfo=None), CREATED.replace(tzinfo=None)),
        (CREATED, CREATED - timedelta(microseconds=1)),
        (datetime.min.replace(tzinfo=timezone(timedelta(hours=1))), CREATED),
    ),
)
@pytest.mark.parametrize("status", ("Resuelto", "Cerrado"))
def test_invalid_dates_exclude_only_samples_never_volume(created, resolved, status):
    row = _row(created_at=created, resolved_at=resolved, status=status)
    result = _aggregate((row,))

    assert result.total_tickets == result.resolved_tickets == 1
    assert result.pending_tickets == 0
    assert result.resolution_sample_size == 0
    assert result.resolution_excluded_count == 1
    assert result.average_resolution_minutes is None
    assert support_metrics.resolution_duration(created, resolved) is None
    _assert_invariants(result)


@pytest.mark.parametrize("target", (None, 0, -1, True, "invalid", 60))
def test_valid_duration_does_not_require_priority_or_sla_target(target):
    result = _aggregate((_row(priority=None, resolved_target_minutes=target),))

    assert result.average_resolution_minutes == 60
    assert result.resolution_sample_size == 1
    assert result.resolution_excluded_count == 0
    _assert_invariants(result)


def test_same_instant_in_different_timezones_has_zero_duration():
    result = _aggregate((_row(
        created_at=CREATED.astimezone(timezone(timedelta(hours=5))),
        resolved_at=CREATED.astimezone(timezone(timedelta(hours=-3))),
    ),))

    assert result.average_resolution_minutes == 0
    _assert_invariants(result)


def test_timezone_transition_uses_elapsed_time_not_wall_clock_duration():
    class TransitionZone(tzinfo):
        def utcoffset(self, value):
            return timedelta(hours=-5 if value.day == 1 else -4)

        def dst(self, value):
            return timedelta(0)

    zone = TransitionZone()
    created = datetime(2026, 3, 1, 12, tzinfo=zone)
    resolved = datetime(2026, 3, 2, 12, tzinfo=zone)
    result = _aggregate((_row(created_at=created, resolved_at=resolved),))

    assert result.average_resolution_minutes == 23 * 60
    assert support_metrics.resolution_duration(created, resolved) == timedelta(hours=23)
    _assert_invariants(result)


@pytest.mark.parametrize("resolution_present", (True, False))
def test_closure_date_never_changes_or_replaces_resolution(resolution_present):
    @dataclass(frozen=True)
    class ClosedRow(TicketMetricsSnapshot):
        closed_at: datetime | None = None

    row = ClosedRow(**asdict(_row(
        status="Cerrado", resolved_at=CREATED + timedelta(minutes=60)
        if resolution_present else None,
    )), closed_at=CREATED + timedelta(days=1))
    first = _aggregate((row,))
    later_closure = _aggregate((replace(row, closed_at=CREATED + timedelta(days=30)),))

    assert first == later_closure
    assert first.average_resolution_minutes == (60 if resolution_present else None)
    assert first.resolution_sample_size == int(resolution_present)
    _assert_invariants(first)


def test_large_valid_durations_stay_finite_when_their_sum_exceeds_timedelta_range():
    created = datetime.min.replace(tzinfo=timezone.utc)
    resolved = datetime.max.replace(tzinfo=timezone.utc)
    rows = tuple(
        _row(f"ticket-{index}", created_at=created, resolved_at=resolved)
        for index in range(300)
    )
    result = _aggregate(rows)

    assert result.average_resolution_minutes == pytest.approx(
        (resolved - created).total_seconds() / 60
    )
    assert result.resolution_sample_size == 300
    _assert_invariants(result)


def test_consumes_one_dataset_once_without_mutating_it():
    rows = (_row("valid"), _row("invalid", resolved_at=None), _row("pending", status="Abierto"))
    before = tuple(asdict(row) for row in rows)
    visits = []

    def source():
        for row in rows:
            visits.append(row.id)
            yield row

    result = _aggregate(source())

    assert visits == ["valid", "invalid", "pending"]
    assert tuple(asdict(row) for row in rows) == before
    assert result.total_tickets == 3
    assert result.average_resolution_minutes == 60
    assert result.resolution_sample_size == 1
    assert result.resolution_excluded_count == 1
    with pytest.raises(FrozenInstanceError):
        result.total_tickets = 99
    _assert_invariants(result)


def test_source_failure_is_not_hidden_as_empty_metrics():
    def broken_source():
        yield _row()
        raise RuntimeError("technical failure")

    with pytest.raises(RuntimeError, match="technical failure"):
        _aggregate(broken_source())
