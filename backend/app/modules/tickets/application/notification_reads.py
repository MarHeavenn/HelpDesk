"""Contador y marcado de lectura de notificaciones (HU-15, RF-149 a RF-151).

Todas las operaciones se limitan a las notificaciones **dirigidas al
actor**. La supervision de administradores y supervisores no convierte en
propias las notificaciones de otros: su contador y sus acciones de lectura
solo afectan a las suyas. Una notificacion ajena, inexistente o con
identificador invalido produce el mismo `NotificationNotFoundError` (404
uniforme, sin revelar existencia).
"""

from datetime import datetime, timezone

from app.modules.tickets.domain.entities import (
    TicketNotification,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
)

NOTIFICATION_NOT_FOUND_MESSAGE = "notification not found"


class NotificationNotFoundError(ValueError):
    """La notificacion no existe o no esta dirigida al actor."""


def count_unread(
    actor_id: str, notifications: InMemoryNotificationRepository
) -> int:
    """Numero de notificaciones dirigidas al actor y aun no leidas."""
    return sum(
        1
        for notification in notifications.list_by_recipient(actor_id)
        if notification.read_at is None
    )


def mark_notification_read(
    notification_id: object,
    actor_id: str,
    notifications: InMemoryNotificationRepository,
    now: datetime | None = None,
) -> TicketNotification:
    """Marca como leida una notificacion propia y la devuelve.

    Es idempotente: si ya estaba leida no cambia `read_at`. Lanza
    `NotificationNotFoundError` si el identificador no es UUID, no existe
    o pertenece a otro usuario.
    """
    if not is_valid_uuid_format(notification_id):
        raise NotificationNotFoundError(NOTIFICATION_NOT_FOUND_MESSAGE)

    notification = notifications.find_by_id(notification_id)
    if notification is None or notification.recipient_id != actor_id:
        raise NotificationNotFoundError(NOTIFICATION_NOT_FOUND_MESSAGE)

    if notification.read_at is None:
        notification.read_at = now if now is not None else datetime.now(timezone.utc)
    return notification


def mark_all_notifications_read(
    actor_id: str,
    notifications: InMemoryNotificationRepository,
    now: datetime | None = None,
) -> int:
    """Marca como leidas todas las notificaciones propias pendientes.

    Devuelve cuantas actualizo; es idempotente y nunca toca las de otros
    usuarios.
    """
    read_at = now if now is not None else datetime.now(timezone.utc)
    updated = 0
    for notification in notifications.list_by_recipient(actor_id):
        if notification.read_at is None:
            notification.read_at = read_at
            updated += 1
    return updated
