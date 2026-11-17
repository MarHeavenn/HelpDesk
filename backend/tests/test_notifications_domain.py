"""T1 - Dominio y repositorio de notificaciones de ticket (RF-144, RF-146).

Verifica:
- RF-144: el catalogo `NOTIFICATION_TYPES` contiene exactamente los cinco
  eventos notificables (asignacion, reasignacion, cambio de estado,
  resolucion y reapertura).
- RF-146: `TicketNotification` representa tipo, ticket, destinatario,
  actor, valores anterior/nuevo, fecha y `read_at`, que nace vacio.
- RF-147: `InMemoryNotificationRepository` devuelve las notificaciones de
  la mas reciente a la mas antigua y desempata por orden de registro
  descendente cuando `created_at` coincide.
- RF-148: `NOTIFICATION_VIEW_ALL_ROLES` fija los roles que supervisan
  todas las notificaciones de su empresa.
"""

import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.tickets.domain.entities import (
    NOTIFICATION_TYPE_ASSIGNED,
    NOTIFICATION_TYPE_REASSIGNED,
    NOTIFICATION_TYPE_REOPENED,
    NOTIFICATION_TYPE_RESOLVED,
    NOTIFICATION_TYPE_SLA_BREACHED,
    NOTIFICATION_TYPE_SLA_NEAR_DUE,
    NOTIFICATION_TYPE_STATUS_CHANGED,
    NOTIFICATION_TYPES,
    NOTIFICATION_VIEW_ALL_ROLES,
    SYSTEM_ACTOR_ID,
    TicketNotification,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
    get_notification_repository,
)

NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)


def _notification(**overrides) -> TicketNotification:
    values = {
        "id": str(uuid.uuid4()),
        "company_id": "company-1",
        "recipient_id": "u-client",
        "ticket_id": "t-1",
        "ticket_title": "No puedo entrar",
        "type": NOTIFICATION_TYPE_ASSIGNED,
        "actor_id": "u-admin",
        "created_at": NOW,
    }
    values.update(overrides)
    return TicketNotification(**values)


# --- RF-144: catalogo de tipos ---


def test_notification_types_catalog_includes_the_seven_events():
    assert NOTIFICATION_TYPES == frozenset(
        {
            "ticket_assigned",
            "ticket_reassigned",
            "ticket_status_changed",
            "ticket_resolved",
            "ticket_reopened",
            "sla_near_due",
            "sla_breached",
        }
    )
    assert NOTIFICATION_TYPE_ASSIGNED == "ticket_assigned"
    assert NOTIFICATION_TYPE_REASSIGNED == "ticket_reassigned"
    assert NOTIFICATION_TYPE_STATUS_CHANGED == "ticket_status_changed"
    assert NOTIFICATION_TYPE_RESOLVED == "ticket_resolved"
    assert NOTIFICATION_TYPE_REOPENED == "ticket_reopened"
    assert NOTIFICATION_TYPE_SLA_NEAR_DUE == "sla_near_due"
    assert NOTIFICATION_TYPE_SLA_BREACHED == "sla_breached"


def test_creation_priority_and_comment_are_not_notification_types():
    assert "ticket_created" not in NOTIFICATION_TYPES
    assert "priority_changed" not in NOTIFICATION_TYPES
    assert "comment_added" not in NOTIFICATION_TYPES


# --- RF-148: roles con supervision global ---


def test_only_administrator_and_supervisor_view_all_notifications():
    assert NOTIFICATION_VIEW_ALL_ROLES == frozenset(
        {"administrador", "supervisor"}
    )
    assert "tecnico" not in NOTIFICATION_VIEW_ALL_ROLES
    assert "cliente" not in NOTIFICATION_VIEW_ALL_ROLES


# --- RF-146: entidad ---


def test_notification_starts_unread_with_optional_values_empty():
    notification = _notification()

    assert notification.read_at is None
    assert notification.previous_value is None
    assert notification.new_value is None
    assert notification.company_id == "company-1"


def test_notification_keeps_change_values_and_recipient():
    notification = _notification(
        type=NOTIFICATION_TYPE_RESOLVED,
        previous_value="En progreso",
        new_value="Resuelto",
        recipient_id="u-tech",
        actor_id="u-tech-2",
    )

    assert notification.type == NOTIFICATION_TYPE_RESOLVED
    assert notification.previous_value == "En progreso"
    assert notification.new_value == "Resuelto"
    assert notification.recipient_id == "u-tech"
    assert notification.actor_id == "u-tech-2"
    assert notification.dedupe_key is None


def test_system_actor_constant_is_not_a_real_user_identifier():
    assert SYSTEM_ACTOR_ID == "system"


# --- RF-158: clave de deduplicacion ---


def test_repository_finds_by_dedupe_key():
    repository = InMemoryNotificationRepository()
    alert = _notification(
        type=NOTIFICATION_TYPE_SLA_BREACHED,
        actor_id=SYSTEM_ACTOR_ID,
        dedupe_key="sla:t-1:sla_breached:u-client:2026-11-17T10:00:00+00:00",
    )
    regular = _notification()
    repository.add(alert)
    repository.add(regular)

    assert (
        repository.find_by_dedupe_key(
            "sla:t-1:sla_breached:u-client:2026-11-17T10:00:00+00:00"
        )
        is alert
    )
    assert repository.find_by_dedupe_key("sla:missing") is None


def test_concurrent_alert_insertion_is_atomic():
    repository = InMemoryNotificationRepository()
    barrier = Barrier(12)

    def insert(_):
        alert = _notification(dedupe_key="sla:concurrent-event")
        barrier.wait(timeout=10)
        return repository.add_if_new(alert)

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(insert, range(12)))

    assert sum(results) == 1
    assert repository.count() == 1


# --- RF-147: repositorio ---


def test_repository_is_singleton_with_count_and_clear():
    repository = get_notification_repository()
    assert repository is get_notification_repository()

    repository.clear()
    assert repository.count() == 0

    repository.add(_notification())
    assert repository.count() == 1

    repository.clear()
    assert repository.count() == 0


def test_repository_lists_recipient_notifications_newest_first():
    repository = InMemoryNotificationRepository()
    older = _notification(created_at=NOW - timedelta(minutes=5))
    newer = _notification(created_at=NOW)
    repository.add(older)
    repository.add(newer)

    assert repository.list_by_recipient("u-client") == [newer, older]
    assert repository.list_by_recipient("u-other") == []


def test_repository_breaks_created_at_ties_by_registration_descending():
    repository = InMemoryNotificationRepository()
    first = _notification(created_at=NOW)
    second = _notification(created_at=NOW)
    repository.add(first)
    repository.add(second)

    assert repository.list_by_recipient("u-client") == [second, first]


def test_repository_filters_by_company_including_without_company():
    repository = InMemoryNotificationRepository()
    own = _notification(company_id="company-1")
    other = _notification(company_id="company-2")
    orphan = _notification(company_id=None)
    repository.add(own)
    repository.add(other)
    repository.add(orphan)

    assert repository.list_by_company("company-1") == [own]
    assert repository.list_by_company("company-2") == [other]
    assert repository.list_by_company(None) == [orphan]


def test_repository_finds_by_id_and_rejects_non_text():
    repository = InMemoryNotificationRepository()
    notification = _notification()
    repository.add(notification)

    assert repository.find_by_id(notification.id) is notification
    assert repository.find_by_id(str(uuid.uuid4())) is None
    assert repository.find_by_id(123) is None
