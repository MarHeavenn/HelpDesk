"""T9: regresión de callers, snapshot SLA y privacidad del dato nuevo.

Cierra el mapa T1 sin ampliar lectura: cada superficie autorizada serializa
exactamente el resumen de ocho claves, el solicitante resuelto se reduce a
``{name}``, el no resoluble es ``null`` y ningún nombre de otra empresa llega
a la respuesta. El SLA se comprueba con un reloj controlado, sin segundo
cálculo por fila. Detalle, escrituras y agregados conservan sus esquemas.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from uuid import uuid4

import pytest

from test_hu17_summary_security import (
    NOT_FOUND,
    ROUTES,
    SUMMARY_FIELDS,
    clean_state,
    password_hash,
    scenario,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


SLA_FIELDS = {
    "target_minutes",
    "started_at",
    "due_at",
    "elapsed_minutes",
    "remaining_minutes",
    "status",
    "near_due",
    "breached",
}
DETAIL_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "assignee",
    "requester",
    "sla",
    "created_at",
    "resolved_at",
    "requester_id",
}
TICKET_DASHBOARD_FIELDS = {
    "total_tickets",
    "by_status",
    "by_priority",
    "by_assignee",
    "recent_tickets",
    "generated_at",
}
RECENT_TICKET_FIELDS = {
    "id",
    "title",
    "priority",
    "status",
    "assignee",
    "created_at",
}
SLA_DASHBOARD_FIELDS = {
    "total_evaluated",
    "en_tiempo",
    "en_riesgo",
    "cumplido",
    "incumplido",
    "sin_sla",
    "compliance_percentage",
    "closed_without_resolved_at",
    "threshold_percent",
    "period_days",
    "by_priority",
    "generated_at",
}
SLA_STATUSES = {"en_tiempo", "en_riesgo", "cumplido", "incumplido"}
FORBIDDEN_KEYS = (
    "email",
    "requester_id",
    "role",
    "company_id",
    "password_hash",
    "invitation_token",
    "invitation_token_hash",
)

# Solo combinaciones autorizadas: el cliente nunca recibe general ni atención;
# el supervisor no recibe atención. Asignados es una consulta de sesión.
AUTHORIZED_CALLERS = [
    ("administrador", ROUTES[0]),
    ("tecnico", ROUTES[0]),
    ("supervisor", ROUTES[0]),
    ("cliente", ROUTES[0]),
    ("administrador", ROUTES[1]),
    ("tecnico", ROUTES[1]),
    ("supervisor", ROUTES[1]),
    ("administrador", ROUTES[2]),
    ("tecnico", ROUTES[2]),
    ("administrador", ROUTES[3]),
    ("tecnico", ROUTES[3]),
]


def _expected_ids(role, route, own, other):
    if route == ROUTES[0]:
        return {own.id} if role == "cliente" else {own.id, other.id}
    if route == ROUTES[1]:
        return {own.id, other.id}
    if route == ROUTES[2]:
        return {own.id} if role == "tecnico" else set()
    return {own.id, other.id}


@pytest.mark.parametrize("role,route", AUTHORIZED_CALLERS)
def test_authorized_caller_matrix_keeps_requester_minimal_and_foreign_silent(
    scenario, role, route,
):
    api, own, other, foreign, crossed = scenario(role)
    users = get_user_repository()
    actor = users.find_by_id(own.requester_id)
    own_requester = {"name": actor.name}
    if role != "cliente":
        # El ticket propio pierde su solicitante: debe serializar ``null`` sin
        # ocultar el ticket ni romper el resto del resumen. El cliente solo ve
        # tickets propios, por lo que su solicitante siempre es resoluble.
        own = replace(own, requester_id=str(uuid4()))
        get_ticket_repository().add(own)
        own_requester = None

    response = api.get(route)

    assert response.status_code == 200, response.text
    rows = response.json()
    expected = _expected_ids(role, route, own, other)
    assert {row["id"] for row in rows} == expected
    resolved_requester = users.find_by_id(other.requester_id)
    for row in rows:
        assert set(row) == SUMMARY_FIELDS
        if row["id"] == own.id:
            assert row["requester"] == own_requester
        else:
            assert row["requester"] == {"name": resolved_requester.name}
        if row["requester"] is not None:
            assert set(row["requester"]) == {"name"}
            assert isinstance(row["requester"]["name"], str)

    foreign_user = users.find_by_id(foreign.requester_id)
    assert foreign_user.name not in response.text
    assert foreign.title not in response.text
    assert crossed.title not in response.text
    for user in users.list_all():
        assert user.email not in response.text
        assert user.password_hash not in response.text
    for forbidden in FORBIDDEN_KEYS:
        assert f'"{forbidden}"' not in response.text


def _controlled_ticket(actor, company, title, priority, created_at, **overrides):
    values = {
        "id": str(uuid4()),
        "title": title,
        "description": "Datos controlados de snapshot SLA",
        "requester_id": actor.id,
        "company_id": company,
        "assignee_id": actor.id,
        "assignee_name": actor.name,
        "created_at": created_at,
        "priority": priority,
    }
    values.update(overrides)
    return Ticket(**values)


def _build_snapshot_tickets(actor, company, reference):
    """Un ticket por cada estado de negocio, más «Sin SLA» y congelado."""
    return [
        _controlled_ticket(
            actor, company, "En tiempo", "Crítica",
            reference - timedelta(minutes=30),
        ),
        _controlled_ticket(
            actor, company, "En riesgo", "Crítica",
            reference - timedelta(minutes=110),
        ),
        _controlled_ticket(
            actor, company, "Incumplido", "Crítica",
            reference - timedelta(minutes=130),
        ),
        _controlled_ticket(
            actor, company, "Cumplido", "Crítica",
            reference - timedelta(minutes=120),
            status="Resuelto",
            resolved_at=reference - timedelta(minutes=30),
        ),
        _controlled_ticket(
            actor, company, "Incumplido resuelto", "Crítica",
            reference - timedelta(minutes=240),
            status="Resuelto",
            resolved_at=reference - timedelta(minutes=60),
            resolved_target_minutes=120,
        ),
        _controlled_ticket(
            actor, company, "Sin SLA", None,
            reference - timedelta(minutes=30),
        ),
    ]


def _freeze_clock(monkeypatch, modules, reference):
    class Clock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            return reference

    for module in modules:
        monkeypatch.setattr(module, "datetime", Clock)


SNAPSHOT_CALLERS = [
    ("tecnico", ROUTES[0], 6),
    ("administrador", ROUTES[1], 6),
    ("tecnico", ROUTES[2], 6),
    ("tecnico", ROUTES[3], 2),
]


@pytest.mark.parametrize("role,route,expected_rows", SNAPSHOT_CALLERS)
def test_each_caller_uses_one_clock_and_concrete_sla_states(
    scenario, monkeypatch, role, route, expected_rows,
):
    api, own, *_ = scenario(role)
    users = get_user_repository()
    actor = users.find_by_id(own.requester_id)
    reference = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    repo = get_ticket_repository()
    repo.clear()
    tickets = _build_snapshot_tickets(actor, own.company_id, reference)
    for ticket in tickets:
        repo.add(ticket)

    router = import_module("app.modules.tickets.interface.router")
    assignments = import_module("app.modules.tickets.interface.assignments_router")
    attention = import_module(
        "app.modules.tickets.application.list_attention_tickets"
    )
    modules = [assignments] if route == ROUTES[2] else [router]
    _freeze_clock(monkeypatch, modules, reference)

    serialized, selected = [], []
    real_router = router.get_ticket_sla
    real_attention = attention.get_ticket_sla

    def record_serialization(snapshot, now=None):
        serialized.append(now)
        return real_router(snapshot, now)

    def record_selection(snapshot, now=None):
        selected.append(now)
        return real_attention(snapshot, now)

    monkeypatch.setattr(router, "get_ticket_sla", record_serialization)
    monkeypatch.setattr(attention, "get_ticket_sla", record_selection)

    response = api.get(route)

    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == expected_rows
    assert len(serialized) == len(rows)  # Un cálculo por fila, no dos.
    assert all(now is reference for now in serialized)
    if route == ROUTES[3]:
        # Cuatro activos evaluados al seleccionar; nunca los resueltos.
        assert len(selected) == 4
        assert all(now is reference for now in selected)
        assert [row["title"] for row in rows] == ["Incumplido", "En riesgo"]
    else:
        assert selected == []

    by_title = {row["title"]: row for row in rows}
    expected_status = {
        "En tiempo": "en_tiempo",
        "En riesgo": "en_riesgo",
        "Incumplido": "incumplido",
        "Cumplido": "cumplido",
        "Incumplido resuelto": "incumplido",
        "Sin SLA": None,
    }
    for title, row in by_title.items():
        assert set(row) == SUMMARY_FIELDS
        assert row["requester"] == {"name": actor.name}
        expected = expected_status[title]
        if expected is None:
            assert row["sla"] is None
            continue
        sla = row["sla"]
        assert set(sla) == SLA_FIELDS
        assert sla["status"] == expected
        assert sla["status"] in SLA_STATUSES
        assert sla["near_due"] is (expected == "en_riesgo")
        assert sla["breached"] is (expected == "incumplido")
        if expected == "cumplido":
            assert sla["remaining_minutes"] == 0
        elif expected == "en_tiempo":
            assert sla["remaining_minutes"] > 0
        elif expected == "en_riesgo":
            assert 0 < sla["remaining_minutes"] <= 24
        else:
            assert sla["remaining_minutes"] == 0

    if route != ROUTES[3]:
        # «En tiempo» y «Cumplido» comparten presentación pero no estado.
        assert by_title["En tiempo"]["sla"]["status"] != (
            by_title["Cumplido"]["sla"]["status"]
        )


def test_resolved_summary_freezes_sla_while_active_rows_follow_the_clock(
    scenario, monkeypatch,
):
    api, own, *_ = scenario("administrador")
    users = get_user_repository()
    actor = users.find_by_id(own.requester_id)
    reference = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    repo = get_ticket_repository()
    repo.clear()
    met = _controlled_ticket(
        actor, own.company_id, "Cumplido", "Crítica",
        reference - timedelta(minutes=120),
        status="Resuelto",
        resolved_at=reference - timedelta(minutes=30),
    )
    active = _controlled_ticket(
        actor, own.company_id, "Activo", "Crítica",
        reference - timedelta(minutes=30),
    )
    repo.add(met)
    repo.add(active)
    router = import_module("app.modules.tickets.interface.router")

    _freeze_clock(monkeypatch, [router], reference)
    first = api.get(ROUTES[1]).json()
    assert {row["title"]: row["sla"]["status"] for row in first} == {
        "Cumplido": "cumplido",
        "Activo": "en_tiempo",
    }

    _freeze_clock(monkeypatch, [router], reference + timedelta(days=10))
    second = api.get(ROUTES[1]).json()
    assert {row["title"]: row["sla"]["status"] for row in second} == {
        "Cumplido": "cumplido",  # Congelado al resolver.
        "Activo": "incumplido",  # Derivado con el reloj de la consulta.
    }


def test_summary_addition_preserves_detail_writes_and_aggregates(
    scenario, password_hash,
):
    api, own, *_ = scenario("administrador")
    users = get_user_repository()
    requester = users.find_by_id(own.requester_id)

    listing = api.get(ROUTES[1])
    assert listing.status_code == 200, listing.text
    summary = next(row for row in listing.json() if row["id"] == own.id)
    assert set(summary) == SUMMARY_FIELDS
    assert summary["requester"] == {"name": requester.name}
    for absent in ("description", "resolved_at", "requester_id", "email"):
        assert absent not in summary

    detail = api.get(f"/api/tickets/{own.id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert set(body) == DETAIL_FIELDS
    assert body["requester"] == {
        "id": requester.id,
        "name": requester.name,
        "email": requester.email,
    }
    assert body["requester_id"] == requester.id

    priority = api.put(
        f"/api/tickets/{own.id}/priority", json={"priority": "Media"}
    )
    assert priority.status_code == 200, priority.text
    assert set(priority.json()) == DETAIL_FIELDS

    status = api.put(
        f"/api/tickets/{own.id}/status", json={"status": "En progreso"}
    )
    assert status.status_code == 200, status.text
    assert set(status.json()) == DETAIL_FIELDS

    technician = User(
        id=str(uuid4()),
        name="Técnica T9",
        email=f"{uuid4()}@example.com",
        password_hash=password_hash,
        role="tecnico",
        company_id=own.company_id,
    )
    users.add(technician)
    assignment = api.put(
        f"/api/tickets/{own.id}/assignee",
        json={"assignee_id": technician.id},
    )
    assert assignment.status_code == 200, assignment.text
    assert set(assignment.json()) == DETAIL_FIELDS

    ticket_dashboard = api.get("/api/dashboard/tickets")
    assert ticket_dashboard.status_code == 200, ticket_dashboard.text
    ticket_body = ticket_dashboard.json()
    assert set(ticket_body) == TICKET_DASHBOARD_FIELDS
    for item in ticket_body["recent_tickets"]:
        assert set(item) == RECENT_TICKET_FIELDS
    assert '"requester"' not in ticket_dashboard.text
    assert requester.email not in ticket_dashboard.text

    sla_dashboard = api.get("/api/dashboard/sla")
    assert sla_dashboard.status_code == 200, sla_dashboard.text
    assert set(sla_dashboard.json()) == SLA_DASHBOARD_FIELDS
    assert '"requester"' not in sla_dashboard.text
    assert requester.email not in sla_dashboard.text


@pytest.mark.parametrize("route", ROUTES)
def test_denials_keep_uniform_body_and_never_leak_requester(scenario, route):
    api, *_ = scenario("cliente")
    response = api.get(route)
    if route in (ROUTES[1], ROUTES[3]):
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    else:
        assert response.status_code == 200
    for forbidden in FORBIDDEN_KEYS:
        assert f'"{forbidden}"' not in response.text
