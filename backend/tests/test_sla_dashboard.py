"""HU-12 — Dashboard de cumplimiento de SLA (RF-93 a RF-101).

Mapa RF -> test:
- RF-93: `test_dashboard_without_session_returns_401`,
  `test_dashboard_without_session_and_invalid_days_returns_401`,
  `test_dashboard_as_client_returns_unified_404`.
- RF-94: `test_period_filters_old_and_future_tickets`,
  `test_dashboard_invalid_days_returns_422`,
  `test_dashboard_accepts_each_supported_period`.
- RF-95: `test_sin_sla_counts_tickets_without_priority`,
  `test_live_policy_change_affects_active_ticket`.
- RF-96: `test_admin_aggregates_all_tickets_and_states`.
- RF-97: `test_closed_without_resolved_at_counts_as_met_and_is_informed`,
  `test_resolved_ticket_keeps_the_frozen_target`.
- RF-98: `test_admin_aggregates_all_tickets_and_states`,
  `test_percentages_round_to_two_decimals`,
  `test_empty_dataset_returns_zero_contract`.
- RF-99: `test_by_priority_always_has_four_priorities_with_zeros`.
- RF-100: `test_technician_only_sees_assigned_tickets`,
  `test_contract_exposes_the_minimum_read_only_fields`.
- RF-101: `test_empty_dataset_returns_zero_contract`.

Los limites exactos del calculo de SLA se cubren en `test_sla_domain.py`
(HU-05); aqui se prueba la agregacion y la reutilizacion del modulo.
"""

import os
import sys
from dataclasses import fields
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.sla.application.dashboard import (
    SlaDashboardAccessDeniedError,
    SlaDashboardTicket,
    get_sla_dashboard,
)
from app.modules.sla.domain.entities import (
    SLA_AT_RISK,
    SLA_BREACHED,
    SLA_MET,
    SLA_ON_TIME,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.sla_contract import (
    SlaTicketView,
    list_sla_tickets,
)

PASSWORD = "Secreta123"
NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
DEFAULT_POLICIES = {
    "Crítica": 120,
    "Alta": 240,
    "Media": 720,
    "Baja": 1440,
}
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()
    client.cookies.clear()


def _ticket(
    ticket_id: str,
    *,
    created_at: datetime,
    priority: str | None = None,
    status: str = "Abierto",
    resolved_at: datetime | None = None,
    resolved_target_minutes: int | None = None,
    assignee_id: str | None = None,
) -> Ticket:
    return Ticket(
        id=ticket_id,
        title=f"Ticket {ticket_id}",
        description="descripcion confidencial",
        requester_id="requester-1",
        created_at=created_at,
        priority=priority,
        status=status,
        assignee_id=assignee_id,
        assignee_name="Ana" if assignee_id else None,
        resolved_at=resolved_at,
        resolved_target_minutes=resolved_target_minutes,
    )


def _view(
    ticket_id: str,
    *,
    created_at: datetime,
    priority: str | None = None,
    is_resolved: bool = False,
    resolved_at: datetime | None = None,
    resolved_target_minutes: int | None = None,
    assignee_id: str | None = None,
) -> SlaDashboardTicket:
    return SlaDashboardTicket(
        id=ticket_id,
        priority=priority,
        created_at=created_at,
        resolved_at=resolved_at,
        resolved_target_minutes=resolved_target_minutes,
        assignee_id=assignee_id,
        is_resolved=is_resolved,
    )


def _dashboard(tickets, *, actor_role="administrador", actor_id="admin", days=30):
    return get_sla_dashboard(
        actor_id=actor_id,
        actor_role=actor_role,
        tickets=tickets,
        now=NOW,
        days=days,
    )


def _provision(role: str, email: str, name: str = "Equipo Soporte"):
    return provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )


def _login(email: str) -> None:
    client.cookies.clear()
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200


def _register_client(email: str = "cliente@ejemplo.com") -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Cliente Uno",
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201
    _login(email)
    return response.json()


# --- Contrato de lectura (RF-100) ---


def test_contract_exposes_the_minimum_read_only_fields():
    get_ticket_repository().add(
        _ticket(
            "t-1",
            created_at=NOW,
            priority="Alta",
            status="Resuelto",
            resolved_at=NOW,
            resolved_target_minutes=240,
            assignee_id="tech-1",
        )
    )

    [view] = list_sla_tickets()

    assert isinstance(view, SlaTicketView)
    assert view.id == "t-1"
    assert view.priority == "Alta"
    assert view.status == "Resuelto"
    assert view.is_resolved is True
    assert view.created_at == NOW
    assert view.resolved_at == NOW
    assert view.resolved_target_minutes == 240
    assert view.assignee_id == "tech-1"
    field_names = {field.name for field in fields(SlaTicketView)}
    assert "title" not in field_names
    assert "description" not in field_names
    assert "requester_id" not in field_names


def test_contract_marks_resolved_and_closed_as_resolved():
    for ticket_id, status in (
        ("open", "Abierto"),
        ("progress", "En progreso"),
        ("resolved", "Resuelto"),
        ("closed", "Cerrado"),
    ):
        get_ticket_repository().add(
            _ticket(ticket_id, created_at=NOW, status=status)
        )

    views = {view.id: view for view in list_sla_tickets()}

    assert views["open"].is_resolved is False
    assert views["progress"].is_resolved is False
    assert views["resolved"].is_resolved is True
    assert views["closed"].is_resolved is True


# --- Agregacion (RF-94 a RF-101) ---


def test_admin_aggregates_all_tickets_and_states():
    tickets = [
        _view("on-time", created_at=NOW - timedelta(minutes=10), priority="Crítica"),
        _view(
            "at-risk",
            created_at=NOW - timedelta(minutes=100),
            priority="Crítica",
        ),
        _view(
            "breached",
            created_at=NOW - timedelta(minutes=300),
            priority="Alta",
        ),
        _view(
            "met",
            created_at=NOW - timedelta(minutes=100),
            priority="Media",
            is_resolved=True,
            resolved_at=NOW - timedelta(minutes=50),
        ),
        _view(
            "breached-resolved",
            created_at=NOW - timedelta(minutes=2000),
            priority="Baja",
            is_resolved=True,
            resolved_at=NOW - timedelta(minutes=100),
        ),
        _view("no-sla", created_at=NOW),
    ]

    dashboard = _dashboard(tickets)

    assert dashboard.total_evaluated == 5
    assert dashboard.en_tiempo == 1
    assert dashboard.en_riesgo == 1
    assert dashboard.cumplido == 1
    assert dashboard.incumplido == 2
    assert dashboard.sin_sla == 1
    assert dashboard.compliance_percentage == 40.0
    assert dashboard.threshold_percent == 20
    assert dashboard.period_days == 30
    assert dashboard.generated_at == NOW
    assert dashboard.closed_without_resolved_at == 0
    assert [
        (
            item.priority,
            item.en_tiempo,
            item.en_riesgo,
            item.cumplido,
            item.incumplido,
            item.compliance_percentage,
        )
        for item in dashboard.by_priority
    ] == [
        ("Crítica", 1, 1, 0, 0, 50.0),
        ("Alta", 0, 0, 0, 1, 0.0),
        ("Media", 0, 0, 1, 0, 100.0),
        ("Baja", 0, 0, 0, 1, 0.0),
    ]
    assert dashboard.total_evaluated + dashboard.sin_sla == len(tickets)


def test_technician_only_sees_assigned_tickets():
    tickets = [
        _view(
            "mine",
            created_at=NOW - timedelta(minutes=10),
            priority="Alta",
            assignee_id="tech-1",
        ),
        _view(
            "other",
            created_at=NOW - timedelta(minutes=10),
            priority="Alta",
            assignee_id="tech-2",
        ),
        _view("unassigned", created_at=NOW - timedelta(minutes=10), priority="Alta"),
    ]

    dashboard = _dashboard(tickets, actor_role="tecnico", actor_id="tech-1")

    assert dashboard.total_evaluated == 1
    assert dashboard.en_tiempo == 1
    assert dashboard.sin_sla == 0
    assert dashboard.total_evaluated + dashboard.sin_sla == 1


def test_period_filters_old_and_future_tickets():
    tickets = [
        _view(
            "boundary",
            created_at=NOW - timedelta(days=7),
            priority="Alta",
        ),
        _view(
            "recent",
            created_at=NOW - timedelta(days=1),
            priority="Alta",
        ),
        _view(
            "old",
            created_at=NOW - timedelta(days=8),
            priority="Alta",
        ),
        _view(
            "future",
            created_at=NOW + timedelta(hours=1),
            priority="Alta",
        ),
    ]

    last_week = _dashboard(tickets, days=7)
    last_month = _dashboard(tickets, days=30)

    assert last_week.total_evaluated == 2
    assert last_week.incumplido == 2
    assert last_month.total_evaluated == 3
    assert last_month.incumplido == 3


def test_by_priority_always_has_four_priorities_with_zeros():
    dashboard = _dashboard(
        [_view("only", created_at=NOW, priority="Alta")]
    )

    assert [item.priority for item in dashboard.by_priority] == [
        "Crítica",
        "Alta",
        "Media",
        "Baja",
    ]
    assert dashboard.by_priority[0].en_tiempo == 0
    assert dashboard.by_priority[1].en_tiempo == 1
    assert dashboard.by_priority[2].en_tiempo == 0
    assert dashboard.by_priority[3].en_tiempo == 0
    assert sum(
        item.en_tiempo + item.en_riesgo + item.cumplido + item.incumplido
        for item in dashboard.by_priority
    ) == dashboard.total_evaluated


def test_sin_sla_counts_tickets_without_priority():
    dashboard = _dashboard(
        [
            _view("no-priority", created_at=NOW),
            _view("with-priority", created_at=NOW, priority="Alta"),
        ]
    )

    assert dashboard.sin_sla == 1
    assert dashboard.total_evaluated == 1


def test_closed_without_resolved_at_counts_as_met_and_is_informed():
    dashboard = _dashboard(
        [
            _view(
                "legacy",
                created_at=NOW - timedelta(days=1),
                priority="Alta",
                is_resolved=True,
                resolved_at=None,
            )
        ]
    )

    assert dashboard.cumplido == 1
    assert dashboard.closed_without_resolved_at == 1
    assert dashboard.total_evaluated == 1
    assert dashboard.by_priority[1].cumplido == 1


def test_empty_dataset_returns_zero_contract():
    dashboard = _dashboard([])

    assert dashboard.total_evaluated == 0
    assert dashboard.en_tiempo == 0
    assert dashboard.en_riesgo == 0
    assert dashboard.cumplido == 0
    assert dashboard.incumplido == 0
    assert dashboard.sin_sla == 0
    assert dashboard.compliance_percentage == 0.0
    assert dashboard.closed_without_resolved_at == 0
    assert [item.compliance_percentage for item in dashboard.by_priority] == [
        0.0,
        0.0,
        0.0,
        0.0,
    ]


def test_percentages_round_to_two_decimals():
    dashboard = _dashboard(
        [
            _view("one", created_at=NOW - timedelta(minutes=10), priority="Crítica"),
            _view("two", created_at=NOW - timedelta(minutes=10), priority="Crítica"),
            _view(
                "three",
                created_at=NOW - timedelta(minutes=300),
                priority="Alta",
            ),
        ]
    )

    assert dashboard.compliance_percentage == 66.67


def test_live_policy_change_affects_active_ticket():
    tickets = [
        _view(
            "active",
            created_at=NOW - timedelta(minutes=45),
            priority="Crítica",
        )
    ]

    before = _dashboard(tickets)
    get_sla_policy_repository().replace(
        {**DEFAULT_POLICIES, "Crítica": 30}
    )
    after = _dashboard(tickets)

    assert before.en_tiempo == 1
    assert after.incumplido == 1


def test_resolved_ticket_keeps_the_frozen_target():
    tickets = [
        _view(
            "resolved",
            created_at=NOW - timedelta(minutes=200),
            priority="Crítica",
            is_resolved=True,
            resolved_at=NOW - timedelta(minutes=10),
            resolved_target_minutes=120,
        )
    ]

    get_sla_policy_repository().replace(
        {**DEFAULT_POLICIES, "Crítica": 600}
    )
    dashboard = _dashboard(tickets)

    assert dashboard.incumplido == 1
    assert dashboard.by_priority[0].incumplido == 1


@pytest.mark.parametrize("role", ["cliente", "desconocido"])
def test_non_management_roles_are_denied(role):
    with pytest.raises(SlaDashboardAccessDeniedError):
        _dashboard([], actor_role=role, actor_id="u-1")


# --- API (RF-93, RF-94, RF-98, RF-101) ---


def test_dashboard_without_session_returns_401():
    response = client.get("/api/dashboard/sla")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_dashboard_without_session_and_invalid_days_returns_401():
    response = client.get("/api/dashboard/sla?days=5")

    assert response.status_code == 401


def test_dashboard_as_client_returns_unified_404():
    _register_client()

    response = client.get("/api/dashboard/sla")

    assert response.status_code == 404
    assert response.json() == {"detail": "sla not found"}


def test_dashboard_as_admin_returns_200_with_the_contract():
    admin = _provision("administrador", "admin@ejemplo.com", "Admin Uno")
    get_ticket_repository().add(
        _ticket(
            "t-1",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            priority="Crítica",
        )
    )
    _login(admin.email)

    response = client.get("/api/dashboard/sla")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
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
    assert body["total_evaluated"] == 1
    assert body["en_tiempo"] == 1
    assert body["threshold_percent"] == 20
    assert body["period_days"] == 30
    assert len(body["by_priority"]) == 4
    assert "descripcion confidencial" not in response.text
    assert "requester-1" not in response.text
    generated = datetime.fromisoformat(body["generated_at"])
    assert generated.tzinfo is not None
    assert generated.utcoffset().total_seconds() == 0


def test_dashboard_as_technician_returns_only_own_tickets():
    technician = _provision("tecnico", "ana@ejemplo.com", "Ana")
    now = datetime.now(timezone.utc)
    get_ticket_repository().add(
        _ticket(
            "mine",
            created_at=now - timedelta(minutes=10),
            priority="Alta",
            assignee_id=technician.id,
        )
    )
    get_ticket_repository().add(
        _ticket(
            "other",
            created_at=now - timedelta(minutes=10),
            priority="Alta",
            assignee_id="otro-tecnico",
        )
    )
    _login(technician.email)

    response = client.get("/api/dashboard/sla")

    assert response.status_code == 200
    body = response.json()
    assert body["total_evaluated"] == 1
    assert body["en_tiempo"] == 1


def test_dashboard_invalid_days_returns_422():
    admin = _provision("administrador", "admin@ejemplo.com", "Admin Uno")
    _login(admin.email)

    response = client.get("/api/dashboard/sla?days=5")

    assert response.status_code == 422


@pytest.mark.parametrize("days", [7, 30, 90])
def test_dashboard_accepts_each_supported_period(days):
    admin = _provision("administrador", "admin@ejemplo.com", "Admin Uno")
    _login(admin.email)

    response = client.get(f"/api/dashboard/sla?days={days}")

    assert response.status_code == 200
    assert response.json()["period_days"] == days


def test_dashboard_empty_scope_returns_zero_contract():
    admin = _provision("administrador", "admin@ejemplo.com", "Admin Uno")
    _login(admin.email)

    response = client.get("/api/dashboard/sla")

    assert response.status_code == 200
    body = response.json()
    assert body["total_evaluated"] == 0
    assert body["sin_sla"] == 0
    assert body["compliance_percentage"] == 0.0
    assert all(
        item["en_tiempo"] == 0
        and item["en_riesgo"] == 0
        and item["cumplido"] == 0
        and item["incumplido"] == 0
        for item in body["by_priority"]
    )
