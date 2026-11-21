"""T2 - Generacion de alertas de SLA (HU-16, RF-156 a RF-159).

Verifica:
- RF-156: solo tickets activos con prioridad; `near_due` -> `sla_near_due`
  y `breached` -> `sla_breached`, con el calculo existente de HU-05.
- RF-157: destinatarios = administradores activos de la empresa + tecnico
  asignado, sin duplicados y sin solicitante/supervisor/cliente.
- RF-158: deduplicacion por ticket, tipo, destinatario y vencimiento;
  repetir el analisis no duplica; cambiar el vencimiento si puede crear un
  evento nuevo; las alertas historicas no se borran.
- RF-159: actor del sistema y `new_value` con el vencimiento ISO.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.identity.application.administrators import (
    list_active_administrator_ids,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)
from app.modules.tickets.application.generate_sla_alerts import (
    generate_sla_alerts,
)
from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    NOTIFICATION_TYPE_SLA_BREACHED,
    NOTIFICATION_TYPE_SLA_NEAR_DUE,
    OPEN_STATUS,
    RESOLVED_STATUS,
    SYSTEM_ACTOR_ID,
    SYSTEM_ACTOR_NAME,
    Ticket,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
COMPANY = "company-1"


@pytest.fixture()
def tickets() -> InMemoryTicketRepository:
    return InMemoryTicketRepository()


@pytest.fixture()
def notifications() -> InMemoryNotificationRepository:
    return InMemoryNotificationRepository()


def _ticket(
    *,
    priority: str | None = "Crítica",
    age_minutes: int = 0,
    status: str = OPEN_STATUS,
    assignee_id: str | None = None,
    company_id: str | None = COMPANY,
    resolved_at: datetime | None = None,
) -> Ticket:
    return Ticket(
        id=str(uuid.uuid4()),
        title="No puedo entrar",
        description="Error al iniciar sesion",
        requester_id="u-client",
        created_at=NOW - timedelta(minutes=age_minutes),
        priority=priority,
        status=status,
        assignee_id=assignee_id,
        assignee_name="Tomas" if assignee_id else None,
        company_id=company_id,
        resolved_at=resolved_at,
    )


def _admins(*ids: str):
    return lambda company_id: list(ids)


def _generate(
    tickets,
    notifications,
    *,
    admins=("u-admin",),
    actor_id="u-admin",
    actor_role="administrador",
    actor_company_id=COMPANY,
    now=NOW,
):
    return generate_sla_alerts(
        actor_id=actor_id,
        actor_role=actor_role,
        actor_company_id=actor_company_id,
        tickets=tickets,
        notifications=notifications,
        administrator_ids=_admins(*admins),
        now=now,
    )


# --- RF-156: deteccion ---


def test_near_due_and_breached_create_distinct_alert_types(
    tickets, notifications
):
    near = _ticket(priority="Crítica", age_minutes=110, assignee_id="u-tech")
    breached = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    tickets.add(near)
    tickets.add(breached)

    created = _generate(
        tickets, notifications, admins=("u-admin",)
    )

    by_ticket = {}
    for notification in created:
        by_ticket.setdefault(notification.ticket_id, set()).add(
            notification.type
        )
    assert by_ticket[near.id] == {NOTIFICATION_TYPE_SLA_NEAR_DUE}
    assert by_ticket[breached.id] == {NOTIFICATION_TYPE_SLA_BREACHED}


def test_ticket_without_priority_and_on_time_ticket_do_not_alert(
    tickets, notifications
):
    tickets.add(_ticket(priority=None, age_minutes=500))
    tickets.add(_ticket(priority="Media", age_minutes=10))

    assert _generate(tickets, notifications) == []
    assert notifications.count() == 0


def test_resolved_and_closed_tickets_do_not_alert(tickets, notifications):
    tickets.add(
        _ticket(
            priority="Crítica",
            age_minutes=500,
            status=RESOLVED_STATUS,
            resolved_at=NOW,
        )
    )
    tickets.add(
        _ticket(
            priority="Crítica",
            age_minutes=500,
            status=CLOSED_STATUS,
            resolved_at=NOW,
        )
    )

    assert _generate(tickets, notifications) == []


# --- RF-157: destinatarios ---


def test_admin_and_assigned_technician_receive_the_alert(
    tickets, notifications
):
    ticket = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    tickets.add(ticket)

    created = _generate(
        tickets,
        notifications,
        admins=("u-admin-1", "u-admin-2"),
    )

    assert [notification.recipient_id for notification in created] == [
        "u-admin-1",
        "u-admin-2",
        "u-tech",
    ]
    assert all(
        notification.company_id == COMPANY for notification in created
    )
    assert all(
        notification.actor_id == SYSTEM_ACTOR_ID for notification in created
    )
    assert all(
        notification.new_value == "2026-11-17T11:50:00+00:00"
        for notification in created
    )
    assert all(
        notification.type == NOTIFICATION_TYPE_SLA_BREACHED
        for notification in created
    )


def test_requester_is_never_a_recipient(tickets, notifications):
    ticket = _ticket(priority="Alta", age_minutes=250)
    tickets.add(ticket)

    created = _generate(tickets, notifications, admins=("u-admin",))

    assert "u-client" not in {
        notification.recipient_id for notification in created
    }


def test_ticket_without_technician_only_alerts_administrators(
    tickets, notifications
):
    tickets.add(_ticket(priority="Alta", age_minutes=250))

    created = _generate(tickets, notifications, admins=("u-admin",))

    assert [notification.recipient_id for notification in created] == [
        "u-admin"
    ]


def test_company_without_administrators_only_alerts_technician(
    tickets, notifications
):
    tickets.add(_ticket(priority="Alta", age_minutes=250, assignee_id="u-tech"))

    created = _generate(tickets, notifications, admins=())

    assert [notification.recipient_id for notification in created] == [
        "u-tech"
    ]


def test_administrator_who_is_also_the_technician_gets_one_alert(
    tickets, notifications
):
    tickets.add(_ticket(priority="Alta", age_minutes=250, assignee_id="u-admin"))

    created = _generate(tickets, notifications, admins=("u-admin",))

    assert len(created) == 1
    assert created[0].recipient_id == "u-admin"


def test_no_recipients_registers_nothing(tickets, notifications):
    tickets.add(_ticket(priority="Alta", age_minutes=250))

    assert _generate(tickets, notifications, admins=()) == []
    assert notifications.count() == 0


# --- RF-158: deduplicacion ---


def test_repeated_scan_does_not_duplicate_alerts(tickets, notifications):
    tickets.add(_ticket(priority="Alta", age_minutes=250, assignee_id="u-tech"))

    first = _generate(tickets, notifications)
    second = _generate(tickets, notifications)

    assert len(first) == 2
    assert second == []
    assert notifications.count() == 2


def test_alert_evolves_from_near_due_to_breached(tickets, notifications):
    ticket = _ticket(priority="Crítica", age_minutes=110, assignee_id="u-tech")
    tickets.add(ticket)

    near = _generate(tickets, notifications, admins=("u-admin",), now=NOW)
    breached = _generate(
        tickets,
        notifications,
        admins=("u-admin",),
        now=NOW + timedelta(minutes=30),
    )

    assert {notification.type for notification in near} == {
        NOTIFICATION_TYPE_SLA_NEAR_DUE
    }
    assert {notification.type for notification in breached} == {
        NOTIFICATION_TYPE_SLA_BREACHED
    }
    assert notifications.count() == 4


def test_moving_the_due_date_creates_a_new_event(tickets, notifications):
    ticket = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    tickets.add(ticket)

    first = _generate(tickets, notifications, admins=("u-admin",))
    ticket.priority = "Crítica"
    second = _generate(tickets, notifications, admins=("u-admin",))

    assert len(first) == 2
    assert len(second) == 2
    assert {item.new_value for item in first} != {
        item.new_value for item in second
    }
    assert notifications.count() == 4


def test_existing_alerts_remain_after_the_ticket_is_resolved(
    tickets, notifications
):
    ticket = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    tickets.add(ticket)
    _generate(tickets, notifications)

    ticket.status = RESOLVED_STATUS
    ticket.resolved_at = NOW
    created = _generate(tickets, notifications)

    assert created == []
    assert notifications.count() == 2


# --- RF-160: ambito del analisis ---


def test_technician_only_scans_own_assigned_tickets(tickets, notifications):
    own = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech-1")
    other = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech-2")
    tickets.add(own)
    tickets.add(other)

    created = _generate(
        tickets,
        notifications,
        admins=("u-admin",),
        actor_id="u-tech-1",
        actor_role="tecnico",
    )

    assert {notification.ticket_id for notification in created} == {own.id}


def test_supervisor_scans_company_but_is_not_a_recipient(
    tickets, notifications
):
    ticket = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    tickets.add(ticket)

    created = _generate(
        tickets,
        notifications,
        admins=("u-admin",),
        actor_id="u-supervisor",
        actor_role="supervisor",
    )

    assert {notification.recipient_id for notification in created} == {
        "u-admin",
        "u-tech",
    }


def test_client_does_not_scan(tickets, notifications):
    tickets.add(_ticket(priority="Alta", age_minutes=250, assignee_id="u-tech"))

    assert (
        _generate(
            tickets,
            notifications,
            admins=("u-admin",),
            actor_id="u-client",
            actor_role="cliente",
        )
        == []
    )


def test_company_scope_ignores_other_companies(tickets, notifications):
    own = _ticket(priority="Alta", age_minutes=250, assignee_id="u-tech")
    other = _ticket(
        priority="Alta",
        age_minutes=250,
        assignee_id="u-tech-2",
        company_id="company-2",
    )
    tickets.add(own)
    tickets.add(other)

    created = _generate(tickets, notifications, admins=("u-admin",))

    assert {notification.ticket_id for notification in created} == {own.id}


# --- RF-157: resolucion de administradores en identity ---


def _user(
    *,
    role: str,
    status: str = "active",
    company_id: str | None = COMPANY,
) -> User:
    return User(
        id=str(uuid.uuid4()),
        name="Usuario",
        email=f"{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=role,
        company_id=company_id,
        status=status,
    )


def test_list_active_administrator_ids_filters_role_status_and_company():
    users = InMemoryUserRepository()
    active = _user(role="administrador")
    inactive = _user(role="administrador", status="deactivated")
    technician = _user(role="tecnico")
    other_company = _user(role="administrador", company_id="company-2")
    for user in (active, inactive, technician, other_company):
        users.add(user)

    assert list_active_administrator_ids(COMPANY, users) == [active.id]


def test_list_active_administrator_ids_handles_the_companyless_scope():
    users = InMemoryUserRepository()
    companyless = _user(role="administrador", company_id=None)
    with_company = _user(role="administrador", company_id=COMPANY)
    for user in (companyless, with_company):
        users.add(user)

    assert list_active_administrator_ids(None, users) == [companyless.id]


def test_system_actor_has_a_visible_name():
    assert SYSTEM_ACTOR_ID == "system"
    assert SYSTEM_ACTOR_NAME == "Sistema"
