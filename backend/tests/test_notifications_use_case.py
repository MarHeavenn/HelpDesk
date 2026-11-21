"""T2 y T3 - Casos de uso de notificaciones (RF-144 a RF-151).

Verifica:
- RF-144/RF-145: la generacion crea una notificacion por destinatario
  (solicitante y tecnico asignado), omite al actor, deduplica, respeta el
  ticket sin tecnico y copia tipo, ticket, actor, valores y fecha.
- RF-144: un tipo desconocido es un error de programacion y no registra.
- RF-147/RF-148: la consulta aplica la visibilidad por rol y empresa.
- RF-149: el contador de no leidas solo cuenta las propias.
- RF-150: marcar una es idempotente y devuelve 404 uniforme para ajena,
  inexistente o identificador invalido.
- RF-151: marcar todas solo afecta a las propias y es idempotente.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.application.list_notifications import list_notifications
from app.modules.tickets.application.notification_reads import (
    NotificationNotFoundError,
    count_unread,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.modules.tickets.application.notify_ticket_event import notify_ticket_event
from app.modules.tickets.domain.entities import (
    NOTIFICATION_TYPE_ASSIGNED,
    NOTIFICATION_TYPE_REASSIGNED,
    NOTIFICATION_TYPE_RESOLVED,
    Ticket,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
)

NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)


def _ticket(**overrides) -> Ticket:
    values = {
        "id": str(uuid.uuid4()),
        "title": "No puedo entrar",
        "description": "Error al iniciar sesion",
        "requester_id": "u-client",
        "created_at": NOW,
        "company_id": "company-1",
    }
    values.update(overrides)
    return Ticket(**values)


@pytest.fixture()
def notifications() -> InMemoryNotificationRepository:
    return InMemoryNotificationRepository()


# --- RF-144/RF-145: generacion y destinatarios ---


def test_assignment_notifies_requester_and_new_technician(notifications):
    ticket = _ticket(assignee_id="u-tech", assignee_name="Tomas")

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-admin",
        new_value="Tomas",
        notifications=notifications,
        now=NOW,
    )

    assert {notification.recipient_id for notification in created} == {
        "u-client",
        "u-tech",
    }
    assert notifications.count() == 2
    assert all(notification.company_id == "company-1" for notification in created)
    assert all(notification.ticket_title == "No puedo entrar" for notification in created)
    assert all(notification.created_at == NOW for notification in created)
    assert all(notification.new_value == "Tomas" for notification in created)
    assert all(notification.read_at is None for notification in created)


def test_reassignment_notifies_requester_and_current_technician(notifications):
    ticket = _ticket(assignee_id="u-tech-2", assignee_name="Nuevo")

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_REASSIGNED,
        ticket=ticket,
        actor_id="u-admin",
        previous_value="Anterior",
        new_value="Nuevo",
        notifications=notifications,
        now=NOW,
    )

    assert {notification.recipient_id for notification in created} == {
        "u-client",
        "u-tech-2",
    }
    assert all(
        notification.previous_value == "Anterior" for notification in created
    )
    assert all(notification.new_value == "Nuevo" for notification in created)


def test_requester_and_technician_same_user_gets_one_notification(notifications):
    ticket = _ticket(requester_id="u-same", assignee_id="u-same")

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_RESOLVED,
        ticket=ticket,
        actor_id="u-admin",
        notifications=notifications,
        now=NOW,
    )

    assert [notification.recipient_id for notification in created] == ["u-same"]
    assert notifications.count() == 1


def test_ticket_without_technician_only_notifies_requester(notifications):
    ticket = _ticket()

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_RESOLVED,
        ticket=ticket,
        actor_id="u-admin",
        notifications=notifications,
        now=NOW,
    )

    assert [notification.recipient_id for notification in created] == ["u-client"]


def test_actor_is_never_notified_of_own_action(notifications):
    ticket = _ticket(requester_id="u-client", assignee_id="u-tech")

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-client",
        notifications=notifications,
        now=NOW,
    )

    assert [notification.recipient_id for notification in created] == ["u-tech"]

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-tech",
        notifications=notifications,
        now=NOW,
    )

    assert [notification.recipient_id for notification in created] == ["u-client"]


def test_actor_who_is_the_only_recipient_registers_nothing(notifications):
    ticket = _ticket(requester_id="u-same", assignee_id="u-same")

    created = notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-same",
        notifications=notifications,
        now=NOW,
    )

    assert created == []
    assert notifications.count() == 0


def test_unknown_event_type_raises_and_registers_nothing(notifications):
    ticket = _ticket(assignee_id="u-tech")

    with pytest.raises(ValueError):
        notify_ticket_event(
            event_type="ticket_created",
            ticket=ticket,
            actor_id="u-admin",
            notifications=notifications,
            now=NOW,
        )

    assert notifications.count() == 0


# --- RF-147/RF-148: visibilidad ---


def _seed(notifications: InMemoryNotificationRepository, ticket: Ticket) -> None:
    notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-admin",
        notifications=notifications,
        now=NOW,
    )


def test_administrator_and_supervisor_see_company_notifications(notifications):
    own = _ticket(company_id="company-1", assignee_id="u-tech")
    other = _ticket(company_id="company-2", assignee_id="u-tech-2")
    orphan = _ticket(company_id=None, assignee_id="u-tech-3")
    _seed(notifications, own)
    _seed(notifications, other)
    _seed(notifications, orphan)

    for role in ("administrador", "supervisor"):
        visible = list_notifications("u-boss", role, "company-1", notifications)
        assert {notification.ticket_id for notification in visible} == {own.id}

    visible = list_notifications("u-boss", "administrador", None, notifications)
    assert {notification.ticket_id for notification in visible} == {orphan.id}


def test_technician_and_client_only_see_their_own_notifications(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)

    technician = list_notifications("u-tech", "tecnico", "company-1", notifications)
    client = list_notifications("u-client", "cliente", "company-1", notifications)
    outsider = list_notifications("u-other", "tecnico", "company-1", notifications)

    assert {notification.recipient_id for notification in technician} == {"u-tech"}
    assert {notification.recipient_id for notification in client} == {"u-client"}
    assert outsider == []


def test_list_is_newest_first(notifications):
    ticket = _ticket(assignee_id="u-tech")
    notify_ticket_event(
        event_type=NOTIFICATION_TYPE_ASSIGNED,
        ticket=ticket,
        actor_id="u-admin",
        notifications=notifications,
        now=NOW,
    )
    later = NOW.replace(minute=30)
    notify_ticket_event(
        event_type=NOTIFICATION_TYPE_RESOLVED,
        ticket=ticket,
        actor_id="u-admin",
        notifications=notifications,
        now=later,
    )

    visible = list_notifications("u-client", "cliente", "company-1", notifications)

    assert [notification.created_at for notification in visible] == [later, NOW]


# --- RF-149: contador ---


def test_unread_count_only_counts_own_notifications(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)

    assert count_unread("u-client", notifications) == 1
    assert count_unread("u-tech", notifications) == 1
    assert count_unread("u-boss", notifications) == 0


# --- RF-150: marcar una ---


def test_mark_own_notification_read_is_idempotent(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)
    notification = notifications.list_by_recipient("u-client")[0]

    first = mark_notification_read(notification.id, "u-client", notifications, now=NOW)
    assert first.read_at == NOW
    assert count_unread("u-client", notifications) == 0

    second = mark_notification_read(
        notification.id, "u-client", notifications, now=NOW.replace(minute=59)
    )
    assert second.read_at == NOW


def test_mark_read_rejects_foreign_missing_and_invalid_identifiers(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)
    foreign = notifications.list_by_recipient("u-tech")[0]

    for candidate in (foreign.id, str(uuid.uuid4()), "not-a-uuid", 123):
        with pytest.raises(NotificationNotFoundError) as error:
            mark_notification_read(candidate, "u-client", notifications, now=NOW)
        assert str(error.value) == "notification not found"

    assert foreign.read_at is None


def test_administrator_cannot_mark_other_users_notification(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)
    client_notification = notifications.list_by_recipient("u-client")[0]

    with pytest.raises(NotificationNotFoundError):
        mark_notification_read(
            client_notification.id, "u-admin", notifications, now=NOW
        )

    assert client_notification.read_at is None


# --- RF-151: marcar todas ---


def test_mark_all_only_affects_own_and_is_idempotent(notifications):
    ticket = _ticket(assignee_id="u-tech")
    _seed(notifications, ticket)

    assert mark_all_notifications_read("u-client", notifications, now=NOW) == 1
    assert count_unread("u-client", notifications) == 0
    assert count_unread("u-tech", notifications) == 1
    assert mark_all_notifications_read("u-client", notifications, now=NOW) == 0
    assert mark_all_notifications_read("u-boss", notifications, now=NOW) == 0
