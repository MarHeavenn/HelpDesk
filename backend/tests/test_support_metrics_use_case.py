"""HU-18 T4: autorización, aislamiento y composición SLA sin fallback."""

from dataclasses import FrozenInstanceError, asdict
from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest

from app.modules.sla.interface.contract import evaluate_frozen_resolution
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.domain.support_metrics import TicketMetricsSnapshot
from app.modules.tickets.infrastructure.ticket_repository import InMemoryTicketRepository

CREATED = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)


def _application():
    return import_module("app.modules.tickets.application.support_metrics")


def _row(identifier="ticket-1", **overrides):
    return TicketMetricsSnapshot(**{
        **dict(
            id=identifier, company_id="company-a", status="Resuelto", priority="Alta",
            created_at=CREATED, resolved_at=CREATED + timedelta(minutes=60),
            resolved_target_minutes=60,
        ),
        **overrides,
    })


def _forbidden(*args, **kwargs):
    pytest.fail("No debe accederse a datos o evaluador fuera del alcance autorizado")


def _run(rows=(), evaluator=_forbidden, company="company-a", reader=None):
    return _application().get_support_metrics(
        actor_role="administrador",
        actor_company_id=company,
        read_snapshot=reader if reader is not None else lambda: rows,
        evaluate_resolution=evaluator,
    )


def _assert_invariants(result):
    assert result.total_tickets == result.resolved_tickets + result.pending_tickets
    assert result.resolved_tickets == (
        result.resolution_sample_size + result.resolution_excluded_count
    )
    assert result.resolved_tickets == result.sla_sample_size + result.sla_excluded_count
    assert 0 <= result.sla_met_count <= result.sla_sample_size <= result.resolution_sample_size
    assert (result.average_resolution_minutes is None) == (result.resolution_sample_size == 0)
    assert (result.sla_compliance_percentage is None) == (result.sla_sample_size == 0)
    if result.sla_sample_size:
        assert 0 <= result.sla_compliance_percentage <= 100


@pytest.mark.parametrize(
    "role", ("cliente", "tecnico", "supervisor", None, "", "Administrador", []),
)
def test_other_roles_are_denied_before_any_read_or_evaluation(role):
    application = _application()
    with pytest.raises(application.SupportMetricsAccessDeniedError, match="^not found$"):
        application.get_support_metrics(
            actor_role=role, actor_company_id="company-a",
            read_snapshot=_forbidden, evaluate_resolution=_forbidden,
        )


@pytest.mark.parametrize("role", ("administrador", "cliente", "tecnico", "supervisor"))
@pytest.mark.parametrize("company", (None, "", "   ", 0, []))
def test_missing_or_invalid_company_is_denied_uniformly_before_read(role, company):
    application = _application()
    with pytest.raises(application.SupportMetricsAccessDeniedError, match="^not found$"):
        application.get_support_metrics(
            actor_role=role, actor_company_id=company,
            read_snapshot=_forbidden, evaluate_resolution=_forbidden,
        )


def test_authorized_empty_scope_has_exact_contract_without_personal_data():
    reads = []

    def reader():
        reads.append(1)
        return ()

    result = _run(reader=reader)

    assert reads == [1]
    assert asdict(result) == {
        "total_tickets": 0, "resolved_tickets": 0, "pending_tickets": 0,
        "average_resolution_minutes": None, "resolution_sample_size": 0,
        "resolution_excluded_count": 0, "sla_compliance_percentage": None,
        "sla_sample_size": 0, "sla_met_count": 0, "sla_excluded_count": 0,
    }
    _assert_invariants(result)


def test_foreign_or_unscoped_data_is_excluded_before_dates_status_or_evaluator():
    class ForbiddenRow:
        def __init__(self, company_id):
            self.company_id = company_id

        def __getattr__(self, name):
            pytest.fail(f"No debe inspeccionarse {name} de un ticket ajeno/sin empresa")

    result = _run((ForbiddenRow("company-b"), ForbiddenRow(None)))

    assert result.total_tickets == result.resolved_tickets == 0
    assert result.sla_excluded_count == result.resolution_excluded_count == 0
    _assert_invariants(result)


@pytest.mark.parametrize("company,expected_total,expected_average", (
    ("company-a", 2, 90), ("company-b", 1, 300),
))
def test_company_stored_on_ticket_wins_over_crossed_requester_and_assignee_relations(
    company, expected_total, expected_average,
):
    repository = InMemoryTicketRepository()
    for identifier, tenant, requester, assignee, minutes in (
        ("a-1", "company-a", "foreign-requester", "foreign-technician", 60),
        ("a-2", "company-a", "another-requester", None, 120),
        ("b", "company-b", "admin-a", "admin-a", 300),
        ("legacy", None, "admin-a", "admin-a", 600),
    ):
        repository.add(Ticket(
            id=identifier, title="Privado", description="No divulgar",
            requester_id=requester, assignee_id=assignee, company_id=tenant,
            created_at=CREATED, status="Cerrado", priority="Alta",
            resolved_at=CREATED + timedelta(minutes=minutes), resolved_target_minutes=60,
        ))
    before = [asdict(ticket) for ticket in repository.list_all()]
    evaluations = []

    def evaluator(*args):
        evaluations.append(args)
        return evaluate_frozen_resolution(*args)

    result = _run(
        evaluator=evaluator, company=company, reader=repository.snapshot_for_metrics,
    )

    assert result.total_tickets == result.resolved_tickets == expected_total
    assert result.average_resolution_minutes == expected_average
    assert len(evaluations) == expected_total
    assert [asdict(ticket) for ticket in repository.list_all()] == before
    _assert_invariants(result)


@pytest.mark.parametrize("overrides", (
    {"status": "Abierto"}, {"status": "En progreso"},
    {"created_at": None}, {"resolved_at": None}, {"resolved_at": "invalid"},
    {"created_at": CREATED.replace(tzinfo=None)},
    {"resolved_at": CREATED - timedelta(microseconds=1)},
    {"resolved_target_minutes": None}, {"resolved_target_minutes": 0},
    {"resolved_target_minutes": -1}, {"resolved_target_minutes": True},
    {"resolved_target_minutes": 60.0}, {"resolved_target_minutes": "60"},
    {"priority": None}, {"priority": "Urgente"},
))
def test_ineligible_rows_never_reach_injected_evaluator(overrides):
    result = _run((_row(**overrides),))

    assert result.total_tickets == 1
    assert result.sla_sample_size == result.sla_met_count == 0
    assert result.sla_compliance_percentage is None
    _assert_invariants(result)


def test_reference_120_minutes_50_percent_has_independent_samples_and_exclusions():
    rows = (
        _row("on-time"),
        _row("late", status="Cerrado", resolved_at=CREATED + timedelta(minutes=120)),
        _row("no-target", resolved_at=CREATED + timedelta(minutes=180),
             resolved_target_minutes=None),
    )
    calls = []

    def evaluator(*args):
        calls.append(args)
        return evaluate_frozen_resolution(*args)

    result = _run(rows, evaluator=evaluator)

    assert calls == [
        ("Alta", CREATED, CREATED + timedelta(minutes=60), 60),
        ("Alta", CREATED, CREATED + timedelta(minutes=120), 60),
    ]
    assert asdict(result) == {
        "total_tickets": 3, "resolved_tickets": 3, "pending_tickets": 0,
        "average_resolution_minutes": 120.0, "resolution_sample_size": 3,
        "resolution_excluded_count": 0, "sla_compliance_percentage": 50.0,
        "sla_sample_size": 2, "sla_met_count": 1, "sla_excluded_count": 1,
    }
    _assert_invariants(result)


def test_all_frozen_targets_absent_keeps_valid_average_without_evaluation():
    result = _run((_row(
        resolved_at=CREATED + timedelta(minutes=180), resolved_target_minutes=None,
    ),))

    assert result.average_resolution_minutes == 180
    assert result.resolution_sample_size == 1
    assert result.sla_sample_size == result.sla_met_count == 0
    assert result.sla_excluded_count == 1
    assert result.sla_compliance_percentage is None
    _assert_invariants(result)


@pytest.mark.parametrize("evaluation,sample,met,percentage", (
    (True, 1, 1, 100), (False, 1, 0, 0), (None, 0, 0, None),
))
def test_true_false_and_none_are_distinct_evaluator_results(evaluation, sample, met, percentage):
    result = _run((_row(),), evaluator=lambda *args: evaluation)

    assert result.resolution_sample_size == 1
    assert result.sla_sample_size == sample
    assert result.sla_met_count == met
    assert result.sla_compliance_percentage == percentage
    assert result.sla_excluded_count == 1 - sample
    _assert_invariants(result)


@pytest.mark.parametrize("evaluations,expected", (
    ((True, False, False), 33.33), ((True, True, False), 66.67),
    ((False, False, False), 0), ((True, True, True), 100),
))
def test_percentage_uses_only_evaluable_sample_and_rounds_to_two_decimals(evaluations, expected):
    values = iter((*evaluations, None))
    result = _run(
        tuple(_row(f"ticket-{index}") for index in range(4)),
        evaluator=lambda *args: next(values),
    )

    assert result.sla_compliance_percentage == expected
    assert result.sla_sample_size == 3
    assert result.sla_met_count == sum(evaluations)
    assert result.sla_excluded_count == 1
    _assert_invariants(result)


def test_one_read_of_one_shot_snapshot_feeds_every_indicator_without_pagination():
    reads = []
    visits = []
    created = datetime(1980, 1, 1, tzinfo=timezone.utc)
    rows = tuple(
        _row(f"ticket-{index}", created_at=created,
             resolved_at=created + timedelta(minutes=60))
        for index in range(125)
    )

    def reader():
        reads.append(1)
        assert len(reads) == 1
        return source()

    def source():
        for row in rows:
            visits.append(row.id)
            yield row

    result = _run(reader=reader, evaluator=evaluate_frozen_resolution)

    assert reads == [1]
    assert visits == [row.id for row in rows]
    assert result.total_tickets == result.resolution_sample_size == result.sla_sample_size == 125
    assert result.average_resolution_minutes == 60
    assert result.sla_compliance_percentage == 100
    with pytest.raises(FrozenInstanceError):
        result.sla_sample_size = 0
    _assert_invariants(result)


@pytest.mark.parametrize("failure_source", ("reader", "evaluator"))
def test_technical_failure_propagates_instead_of_becoming_empty_metrics(failure_source):
    def broken(*args):
        raise RuntimeError("technical failure")

    with pytest.raises(RuntimeError, match="technical failure"):
        _run(
            (_row(),), evaluator=broken if failure_source == "evaluator" else _forbidden,
            reader=broken if failure_source == "reader" else None,
        )
