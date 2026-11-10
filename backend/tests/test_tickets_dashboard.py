"""HU-11 — Dashboard de tickets (RF-81 a RF-92).

Mapa RF -> test:
- RF-81: `test_dashboard_without_session_returns_401`,
  `test_dashboard_as_client_returns_unified_404`.
- RF-82: `test_admin_dashboard_aggregates_every_ticket`.
- RF-83: `test_technician_dashboard_only_includes_assigned_tickets`.
- RF-84: `test_admin_dashboard_aggregates_every_ticket`,
  `test_generated_at_is_utc_iso8601`.
- RF-85: `test_by_status_always_has_the_four_catalog_states`.
- RF-86: `test_by_priority_always_has_the_catalog_and_sin_prioridad`.
- RF-87: `test_by_assignee_includes_technicians_with_zero_tickets`.
- RF-88: `test_recent_tickets_are_the_five_newest_without_description`.
- RF-89: `test_counts_are_invariant_across_sections`.
- RF-90: `test_empty_scope_returns_zeros_without_error`.
"""

import os
import sys
import uuid
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
from app.modules.tickets.application.dashboard import (
    DashboardAccessDeniedError,
    TechnicianRef,
    get_ticket_dashboard,
)
from app.modules.tickets.domain.entities import PRIORITIES, STATUSES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)
client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()


def _provision(role: str, name: str, email: str):
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
    return response.json()


def _ticket(
    ticket_id: str,
    *,
    created_at: datetime,
    priority: str | None = None,
    status: str = "Abierto",
    assignee: tuple[str, str] | None = None,
) -> Ticket:
    assignee_id, assignee_name = assignee if assignee else (None, None)
    return Ticket(
        id=ticket_id,
        title=f"Ticket {ticket_id}",
        description="descripcion confidencial",
        requester_id=str(uuid.uuid4()),
        created_at=created_at,
        priority=priority,
        status=status,
        assignee_id=assignee_id,
        assignee_name=assignee_name,
    )


def _seed_admin_dataset():
    tickets = [
        _ticket(
            "a",
            created_at=NOW - timedelta(minutes=1),
            priority="Crítica",
            status="Abierto",
            assignee=("tech-1", "Ana"),
        ),
        _ticket(
            "b",
            created_at=NOW - timedelta(minutes=2),
            priority="Alta",
            status="En progreso",
            assignee=("tech-1", "Ana"),
        ),
        _ticket(
            "c",
            created_at=NOW - timedelta(minutes=3),
            priority="Media",
            status="Resuelto",
            assignee=("tech-2", "Luis"),
        ),
        _ticket(
            "d",
            created_at=NOW - timedelta(minutes=4),
            priority="Baja",
            status="Cerrado",
        ),
        _ticket(
            "e",
            created_at=NOW - timedelta(minutes=5),
            priority=None,
            status="Abierto",
        ),
        _ticket(
            "f",
            created_at=NOW - timedelta(minutes=6),
            priority="Alta",
            status="En progreso",
            assignee=("tech-2", "Luis"),
        ),
    ]
    for ticket in tickets:
        get_ticket_repository().add(ticket)
    return tickets


TECHNICIANS = [
    TechnicianRef(id="tech-1", name="Ana"),
    TechnicianRef(id="tech-2", name="Luis"),
    TechnicianRef(id="tech-3", name="Zoe"),
]


# --- Agregacion (RF-82 a RF-90) ---


def test_admin_dashboard_aggregates_every_ticket():
    _seed_admin_dataset()

    dashboard = get_ticket_dashboard(
        actor_id="admin",
        actor_role="administrador",
        tickets=get_ticket_repository(),
        technicians=TECHNICIANS,
        now=NOW,
    )

    assert dashboard.total_tickets == 6
    assert [(item.status, item.count) for item in dashboard.by_status] == [
        ("Abierto", 2),
        ("En progreso", 2),
        ("Resuelto", 1),
        ("Cerrado", 1),
    ]
    assert [(item.priority, item.count) for item in dashboard.by_priority] == [
        ("Crítica", 1),
        ("Alta", 2),
        ("Media", 1),
        ("Baja", 1),
        (None, 1),
    ]
    assert [(item.label, item.count) for item in dashboard.by_assignee] == [
        ("Sin asignar", 2),
        ("Ana", 2),
        ("Luis", 2),
        ("Zoe", 0),
    ]
    assert dashboard.by_assignee[0].technician is None
    assert dashboard.by_assignee[3].technician == TechnicianRef(
        id="tech-3", name="Zoe"
    )
    assert dashboard.generated_at == NOW


def test_by_status_always_has_the_four_catalog_states():
    get_ticket_repository().add(
        _ticket("only", created_at=NOW - timedelta(minutes=1))
    )

    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        now=NOW,
    )

    assert [item.status for item in dashboard.by_status] == list(STATUSES)
    assert sum(item.count for item in dashboard.by_status) == 1
    assert all(
        item.count == 0
        for item in dashboard.by_status
        if item.status != "Abierto"
    )


def test_by_priority_always_has_the_catalog_and_sin_prioridad():
    get_ticket_repository().add(
        _ticket("only", created_at=NOW, priority="Alta")
    )

    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        now=NOW,
    )

    assert [item.priority for item in dashboard.by_priority] == [
        *PRIORITIES,
        None,
    ]
    assert [item.label for item in dashboard.by_priority] == [
        *PRIORITIES,
        "Sin prioridad",
    ]
    assert dashboard.by_priority[-1].count == 0
    assert sum(item.count for item in dashboard.by_priority) == 1


def test_by_assignee_includes_technicians_with_zero_tickets():
    get_ticket_repository().add(_ticket("only", created_at=NOW))

    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        technicians=TECHNICIANS,
        now=NOW,
    )

    assert dashboard.by_assignee[0].label == "Sin asignar"
    assert dashboard.by_assignee[0].count == 1
    assert {item.label: item.count for item in dashboard.by_assignee[1:]} == {
        "Ana": 0,
        "Luis": 0,
        "Zoe": 0,
    }
    assert sum(item.count for item in dashboard.by_assignee) == 1


def test_recent_tickets_are_the_five_newest_without_description():
    _seed_admin_dataset()

    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        technicians=TECHNICIANS,
        now=NOW,
    )

    assert [item.id for item in dashboard.recent_tickets] == [
        "a",
        "b",
        "c",
        "d",
        "e",
    ]
    assert [item.created_at for item in dashboard.recent_tickets] == [
        NOW - timedelta(minutes=offset) for offset in range(1, 6)
    ]
    first = dashboard.recent_tickets[0]
    assert first.title == "Ticket a"
    assert first.priority == "Crítica"
    assert first.status == "Abierto"
    assert first.assignee == TechnicianRef(id="tech-1", name="Ana")
    assert not hasattr(first, "description")


def test_technician_dashboard_only_includes_assigned_tickets():
    _seed_admin_dataset()

    dashboard = get_ticket_dashboard(
        actor_id="tech-1",
        actor_role="tecnico",
        tickets=get_ticket_repository(),
        technicians=[TechnicianRef(id="tech-1", name="Ana")],
        now=NOW,
    )

    assert dashboard.total_tickets == 2
    assert [(item.status, item.count) for item in dashboard.by_status] == [
        ("Abierto", 1),
        ("En progreso", 1),
        ("Resuelto", 0),
        ("Cerrado", 0),
    ]
    assert [(item.label, item.count) for item in dashboard.by_assignee] == [
        ("Sin asignar", 0),
        ("Ana", 2),
    ]
    assert [item.id for item in dashboard.recent_tickets] == ["a", "b"]


def test_counts_are_invariant_across_sections():
    _seed_admin_dataset()

    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        technicians=TECHNICIANS,
        now=NOW,
    )

    assert sum(item.count for item in dashboard.by_status) == dashboard.total_tickets
    assert (
        sum(item.count for item in dashboard.by_priority)
        == dashboard.total_tickets
    )
    assert (
        sum(item.count for item in dashboard.by_assignee)
        == dashboard.total_tickets
    )


def test_empty_scope_returns_zeros_without_error():
    dashboard = get_ticket_dashboard(
        actor_role="administrador",
        actor_id="admin",
        tickets=get_ticket_repository(),
        technicians=TECHNICIANS,
        now=NOW,
    )

    assert dashboard.total_tickets == 0
    assert all(item.count == 0 for item in dashboard.by_status)
    assert all(item.count == 0 for item in dashboard.by_priority)
    assert all(item.count == 0 for item in dashboard.by_assignee)
    assert dashboard.recent_tickets == []
    assert dashboard.generated_at == NOW


@pytest.mark.parametrize("role", ["cliente", "desconocido"])
def test_non_management_roles_are_denied(role):
    with pytest.raises(DashboardAccessDeniedError):
        get_ticket_dashboard(
            actor_role=role,
            actor_id="u-1",
            tickets=get_ticket_repository(),
            now=NOW,
        )


# --- API (RF-81) ---


def test_dashboard_without_session_returns_401():
    response = client.get("/api/dashboard/tickets")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_dashboard_as_client_returns_unified_404():
    registered = _register_client()
    _login(registered["email"])

    response = client.get("/api/dashboard/tickets")

    assert response.status_code == 404
    assert response.json() == {"detail": "tickets not found"}


def test_dashboard_as_admin_returns_200_with_the_contract():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _provision("tecnico", "Ana", "ana@ejemplo.com")
    _provision("tecnico", "Luis", "luis@ejemplo.com")
    _seed_admin_dataset()
    _login(admin.email)

    response = client.get("/api/dashboard/tickets")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "total_tickets",
        "by_status",
        "by_priority",
        "by_assignee",
        "recent_tickets",
        "generated_at",
    }
    assert body["total_tickets"] == 6
    assert body["by_status"] == [
        {"status": "Abierto", "count": 2},
        {"status": "En progreso", "count": 2},
        {"status": "Resuelto", "count": 1},
        {"status": "Cerrado", "count": 1},
    ]
    assert body["by_priority"][-1] == {
        "priority": None,
        "label": "Sin prioridad",
        "count": 1,
    }
    assert body["by_assignee"][0] == {
        "technician": None,
        "label": "Sin asignar",
        "count": 2,
    }
    assert len(body["recent_tickets"]) == 5
    for item in body["recent_tickets"]:
        assert set(item) == {
            "id",
            "title",
            "priority",
            "status",
            "assignee",
            "created_at",
        }
    assert "descripcion confidencial" not in response.text
    assert "requester_id" not in response.text


def test_dashboard_as_technician_returns_only_own_tickets():
    technician = _provision("tecnico", "Ana", "ana@ejemplo.com")
    tickets = _seed_admin_dataset()
    for ticket in tickets:
        if ticket.assignee_id == "tech-1":
            ticket.assignee_id = technician.id
            ticket.assignee_name = technician.name
    _login(technician.email)

    response = client.get("/api/dashboard/tickets")

    assert response.status_code == 200
    body = response.json()
    assert body["total_tickets"] == 2
    assert [item["id"] for item in body["recent_tickets"]] == ["a", "b"]
    assert [(item["label"], item["count"]) for item in body["by_assignee"]] == [
        ("Sin asignar", 0),
        ("Ana", 2),
    ]


def test_dashboard_empty_scope_returns_zero_contract():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _login(admin.email)

    response = client.get("/api/dashboard/tickets")

    assert response.status_code == 200
    body = response.json()
    assert body["total_tickets"] == 0
    assert all(item["count"] == 0 for item in body["by_status"])
    assert all(item["count"] == 0 for item in body["by_priority"])
    assert all(item["count"] == 0 for item in body["by_assignee"])
    assert body["recent_tickets"] == []


def test_generated_at_is_utc_iso8601():
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    _login(admin.email)

    body = client.get("/api/dashboard/tickets").json()
    generated = datetime.fromisoformat(body["generated_at"])

    assert generated.tzinfo is not None
    assert generated.utcoffset().total_seconds() == 0
