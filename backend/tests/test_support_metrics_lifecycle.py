"""HU-18 T6: ciclo/configuración reales, solo lectura y compatibilidad."""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from importlib import import_module

import pytest

from app.modules.sla.infrastructure.sla_policy_repository import get_sla_policy_repository
from app.modules.tickets.infrastructure.assignment_log import get_assignment_log
from app.modules.tickets.infrastructure.notification_repository import get_notification_repository
from app.modules.tickets.infrastructure.ticket_comment_repository import get_ticket_comment_repository
from app.modules.tickets.infrastructure.ticket_modification_log import get_ticket_modification_log
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository
from test_support_metrics_api import (
    CREATED, URL, _ticket, clean_state, password_hash, session,
)


@pytest.fixture(autouse=True)
def clean_event_stores(clean_state):
    stores = (
        get_ticket_modification_log(), get_assignment_log(),
        get_ticket_comment_repository(), get_notification_repository(),
    )
    for store in stores:
        store.clear()
    yield
    for store in stores:
        store.clear()


@pytest.fixture
def clock(monkeypatch):
    """Inyecta solo el reloj en los casos de uso reales invocados por HTTP."""
    current = [CREATED]
    router = import_module("app.modules.tickets.interface.router")
    original_update = router.update_ticket_status
    original_reopen = router.reopen_ticket

    def update(**kwargs):
        return original_update(**kwargs, now=current[0])

    def reopen(**kwargs):
        return original_reopen(**kwargs, now=current[0])

    monkeypatch.setattr(router, "update_ticket_status", update)
    monkeypatch.setattr(router, "reopen_ticket", reopen)
    return current


def _policy(api, minutes):
    values = {
        priority: target / 60
        for priority, target in get_sla_policy_repository().get_all().items()
    }
    values["Alta"] = minutes / 60
    response = api.put("/api/sla/policies", json=values)
    assert response.status_code == 200, response.text
    assert get_sla_policy_repository().get_target_minutes("Alta") == minutes


def _state():
    tickets = get_ticket_repository().list_all()
    return {
        "tickets": {ticket.id: asdict(ticket) for ticket in tickets},
        "modifications": {
            ticket.id: [asdict(record) for record in
                        get_ticket_modification_log().list_by_ticket(ticket.id)]
            for ticket in tickets
        },
        "assignments": {
            ticket.id: [asdict(record) for record in
                        get_assignment_log().list_by_ticket(ticket.id)]
            for ticket in tickets
        },
        "comments": {
            ticket.id: [asdict(comment) for comment in
                        get_ticket_comment_repository().list_by_ticket(ticket.id)]
            for ticket in tickets
        },
        "notifications": [
            asdict(item)
            for company in ("company-a", "company-b", None)
            for item in get_notification_repository().list_by_company(company)
        ],
        "counts": (
            get_ticket_repository().count(), get_ticket_modification_log().count(),
            get_assignment_log().count(), get_ticket_comment_repository().count(),
            get_notification_repository().count(),
        ),
        "policy": get_sla_policy_repository().get_all(),
    }


def _history(api, ticket):
    response = api.get(f"/api/tickets/{ticket.id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def _metrics(api):
    before = _state()
    first = api.get(URL)
    second = api.get(URL)
    assert first.status_code == second.status_code == 200, first.text
    assert first.json() == second.json()
    assert _state() == before
    return first.json()


def _status(api, ticket, status):
    response = api.put(f"/api/tickets/{ticket.id}/status", json={"status": status})
    assert response.status_code == 200, response.text
    assert ticket.status == status
    return response.json()


def _single_result(finalized, average=None, met=None):
    sample = int(finalized)
    return {
        "total_tickets": 1, "resolved_tickets": sample,
        "pending_tickets": 1 - sample, "average_resolution_minutes": average,
        "resolution_sample_size": sample, "resolution_excluded_count": 0,
        "sla_compliance_percentage": None if met is None else 100 * int(met),
        "sla_sample_size": sample, "sla_met_count": int(bool(met)),
        "sla_excluded_count": 0,
    }


@pytest.mark.parametrize("exit_path", ("retroceso", "reapertura"))
def test_lifecycle_uses_current_resolution_once_and_keeps_original_creation(
    session, clock, exit_path,
):
    api, _ = session()
    _, requester = session("cliente")
    _, technician = session("tecnico")
    _policy(api, 60)
    ticket = _ticket(
        status="En progreso", resolved_at=None, resolved_target_minutes=None,
        requester_id=requester.id, assignee_id=technician.id,
        assignee_name=technician.name,
    )
    assert _metrics(api) == _single_result(False)

    clock[0] = CREATED + timedelta(minutes=60)
    _status(api, ticket, "Resuelto")
    assert ticket.resolved_at == clock[0]
    assert ticket.resolved_target_minutes == 60
    resolved_metrics = _metrics(api)
    assert resolved_metrics == _single_result(True, 60, True)
    assert get_notification_repository().count() > 0
    first_history = _history(api, ticket)
    assert _metrics(api) == resolved_metrics
    assert _history(api, ticket) == first_history

    clock[0] = CREATED + timedelta(minutes=120)
    if exit_path == "reapertura":
        _status(api, ticket, "Cerrado")
        assert ticket.resolved_at == CREATED + timedelta(minutes=60)
        assert ticket.resolved_target_minutes == 60
        assert _metrics(api) == resolved_metrics
        clock[0] = CREATED + timedelta(minutes=180)
        response = api.post(f"/api/tickets/{ticket.id}/reopen")
        assert response.status_code == 200, response.text
        assert ticket.status == "Abierto"
    else:
        _status(api, ticket, "En progreso")

    assert ticket.resolved_at is None
    assert ticket.resolved_target_minutes is None
    assert _metrics(api) == _single_result(False)
    pending_history = _history(api, ticket)
    assert len(pending_history) > len(first_history)
    if exit_path == "reapertura":
        clock[0] = CREATED + timedelta(minutes=210)
        _status(api, ticket, "En progreso")
        assert _metrics(api) == _single_result(False)

    minutes = 300 if exit_path == "reapertura" else 180
    clock[0] = CREATED + timedelta(minutes=minutes)
    _status(api, ticket, "Resuelto")
    assert ticket.created_at == CREATED
    assert ticket.resolved_at == clock[0]
    assert ticket.resolved_target_minutes == 60
    assert _metrics(api) == _single_result(True, minutes, False)
    final_history = _history(api, ticket)
    assert len(final_history) > len(pending_history)
    assert _metrics(api) == _single_result(True, minutes, False)
    assert _history(api, ticket) == final_history


@pytest.mark.parametrize("scenario", ("five", "three", "isolated-no-target"))
def test_policy_change_240_to_30_preserves_examples_and_missing_target_exclusion(
    session, monkeypatch, scenario,
):
    api, actor = session()
    _policy(api, 240)
    if scenario == "five":
        _ticket(status="Abierto", resolved_at=None, resolved_target_minutes=None)
        _ticket(status="En progreso", resolved_at=None, resolved_target_minutes=None)
        _ticket()
        _ticket(status="Cerrado", resolved_at=CREATED + timedelta(minutes=120))
        _ticket(status="Cerrado", resolved_at=None)
        expected = {
            "total_tickets": 5, "resolved_tickets": 3, "pending_tickets": 2,
            "average_resolution_minutes": 90.0, "resolution_sample_size": 2,
            "resolution_excluded_count": 1, "sla_compliance_percentage": 50.0,
            "sla_sample_size": 2, "sla_met_count": 1, "sla_excluded_count": 1,
        }
    else:
        if scenario == "three":
            _ticket()
            _ticket(status="Cerrado", resolved_at=CREATED + timedelta(minutes=120))
        missing = _ticket(
            status="Cerrado", resolved_at=CREATED + timedelta(minutes=180),
            resolved_target_minutes=None,
        )
        expected = {
            "total_tickets": 3 if scenario == "three" else 1,
            "resolved_tickets": 3 if scenario == "three" else 1, "pending_tickets": 0,
            "average_resolution_minutes": 120.0 if scenario == "three" else 180.0,
            "resolution_sample_size": 3 if scenario == "three" else 1,
            "resolution_excluded_count": 0,
            "sla_compliance_percentage": 50.0 if scenario == "three" else None,
            "sla_sample_size": 2 if scenario == "three" else 0,
            "sla_met_count": 1 if scenario == "three" else 0,
            "sla_excluded_count": 1,
        }
    for company in ("company-b", None):
        _ticket(
            company_id=company, requester_id=actor.id, assignee_id=actor.id,
            resolved_at=CREATED + timedelta(days=100),
        )
    http = import_module("app.modules.tickets.interface.metrics_router")
    original = http.evaluate_frozen_resolution

    def evaluate(priority, created, resolved, target):
        assert target is not None
        return original(priority, created, resolved, target)

    monkeypatch.setattr(http, "evaluate_frozen_resolution", evaluate)
    ticket_state = _state()["tickets"]
    assert _metrics(api) == expected

    _policy(api, 30)

    assert _metrics(api) == expected
    assert _state()["tickets"] == ticket_state
    if scenario != "five":
        assert missing.resolved_target_minutes is None


def test_metrics_never_use_event_writers_or_mutate_registered_history(session, clock, monkeypatch):
    api, _ = session()
    _, requester = session("cliente")
    ticket = _ticket(
        status="En progreso", resolved_at=None, resolved_target_minutes=None,
        requester_id=requester.id,
    )
    clock[0] = CREATED + timedelta(minutes=60)
    _status(api, ticket, "Resuelto")
    assert get_ticket_modification_log().count() > 0
    assert get_notification_repository().count() > 0
    history = _history(api, ticket)

    def forbidden(*args, **kwargs):
        pytest.fail("Una consulta de métricas no debe escribir ni generar eventos")

    for store in (
        get_ticket_repository(), get_ticket_modification_log(), get_assignment_log(),
        get_ticket_comment_repository(), get_notification_repository(),
    ):
        monkeypatch.setattr(store, "add", forbidden)
    monkeypatch.setattr(get_notification_repository(), "add_if_new", forbidden)

    result = _metrics(api)

    assert result["total_tickets"] == result["resolved_tickets"] == 1
    assert _history(api, ticket) == history


def test_previous_dashboards_and_general_sla_keep_their_legacy_meaning(
    session, monkeypatch,
):
    api, _ = session()
    now = CREATED + timedelta(days=1)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    for module in ("tickets", "sla"):
        monkeypatch.setattr(
            import_module(f"app.modules.{module}.application.dashboard"),
            "datetime", FixedDatetime,
        )
    _policy(api, 240)
    _ticket(status="Cerrado", resolved_at=None, resolved_target_minutes=None)
    missing_target = _ticket(
        resolved_at=CREATED + timedelta(minutes=180), resolved_target_minutes=None,
    )
    _ticket(status="Abierto", created_at=now - timedelta(minutes=30),
            resolved_at=None, resolved_target_minutes=None)
    _ticket()
    old = now - timedelta(days=45)
    _ticket(created_at=old, resolved_at=old + timedelta(minutes=120))

    def dashboards():
        result = {}
        for path in ("/api/dashboard/tickets", *(
            f"/api/dashboard/sla?days={days}" for days in (7, 30, 90)
        )):
            response = api.get(path)
            assert response.status_code == 200, response.text
            result[path] = response.json()
        return result

    before = dashboards()
    assert set(before["/api/dashboard/tickets"]) == {
        "total_tickets", "by_status", "by_priority", "by_assignee",
        "recent_tickets", "generated_at",
    }
    assert before["/api/dashboard/tickets"]["total_tickets"] == 5
    for days, evaluated, compliance in ((7, 4, 100), (30, 4, 100), (90, 5, 80)):
        dashboard = before[f"/api/dashboard/sla?days={days}"]
        assert dashboard["period_days"] == days
        assert dashboard["total_evaluated"] == evaluated
        assert dashboard["compliance_percentage"] == compliance
        assert dashboard["closed_without_resolved_at"] == 1
    detail = api.get(f"/api/tickets/{missing_target.id}").json()
    assert detail["sla"]["status"] == "cumplido"
    assert detail["sla"]["target_minutes"] == 240
    metrics = _metrics(api)
    assert metrics["total_tickets"] == 5
    assert metrics["average_resolution_minutes"] == 120
    assert metrics["resolution_sample_size"] == 3
    assert metrics["resolution_excluded_count"] == 1
    assert metrics["sla_sample_size"] == 2
    assert metrics["sla_excluded_count"] == 2
    assert metrics["sla_compliance_percentage"] == 50
    assert dashboards() == before

    _policy(api, 30)

    assert _metrics(api) == metrics
    detail_after = api.get(f"/api/tickets/{missing_target.id}").json()
    assert detail_after["sla"]["status"] == "incumplido"
    assert detail_after["sla"]["target_minutes"] == 30
    assert missing_target.resolved_target_minutes is None
    assert dashboards()["/api/dashboard/sla?days=7"]["compliance_percentage"] == 50


@pytest.mark.parametrize("role,old_status,new_status", (
    ("administrador", 200, 200), ("supervisor", 200, 404),
    ("tecnico", 200, 404), ("cliente", 404, 404),
))
def test_previous_dashboard_permissions_are_not_replaced_by_hu18(
    session, role, old_status, new_status,
):
    api, _ = session(role)
    for path in ("/api/dashboard/tickets", "/api/dashboard/sla"):
        response = api.get(path)
        assert response.status_code == old_status, response.text
    assert api.get(URL).status_code == new_status
