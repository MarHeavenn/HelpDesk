"""Generacion de notificaciones internas a partir de eventos del ticket.

Caso de uso de HU-15 (RF-144, RF-145, RF-146). Recibe el ticket ya mutado,
el tipo de evento y el actor, y registra una notificacion por cada
destinatario implicado:

- el solicitante del ticket;
- el tecnico asignado vigente.

El actor de la accion nunca se notifica a si mismo y los destinatarios no
se repiten; si solicitante y tecnico son la misma persona se registra una
sola notificacion. Un ticket sin tecnico solo avisa al solicitante. Los
administradores y supervisores no reciben avisos por su rol: su acceso es
de supervision y lo resuelve la capa de aplicacion al consultar.

La funcion no conoce HTTP ni consulta `identity`: solo copia
identificadores y el titulo del ticket. La resolucion de nombres ocurre en
la interfaz.
"""

import uuid
from datetime import datetime, timezone

from app.modules.tickets.domain.entities import (
    NOTIFICATION_TYPES,
    Ticket,
    TicketNotification,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
    get_notification_repository,
)


def notify_ticket_event(
    *,
    event_type: str,
    ticket: Ticket,
    actor_id: str,
    previous_value: str | None = None,
    new_value: str | None = None,
    notifications: InMemoryNotificationRepository | None = None,
    now: datetime | None = None,
) -> list[TicketNotification]:
    """Registra una notificacion por destinatario y devuelve las creadas.

    Un `event_type` fuera de `NOTIFICATION_TYPES` es un error de
    programacion (`ValueError`) y no registra nada. Los destinatarios se
    calculan en el orden solicitante y tecnico, omitiendo vacios, al actor
    y los duplicados. `created_at` es un unico instante UTC compartido por
    las notificaciones del mismo evento.
    """
    if event_type not in NOTIFICATION_TYPES:
        raise ValueError(f"unknown notification type: {event_type!r}")

    repository = notifications if notifications is not None else get_notification_repository()
    created_at = now if now is not None else datetime.now(timezone.utc)

    recipients: list[str] = []
    for candidate in (ticket.requester_id, ticket.assignee_id):
        if candidate is None or candidate == actor_id:
            continue
        if candidate in recipients:
            continue
        recipients.append(candidate)

    created: list[TicketNotification] = []
    for recipient_id in recipients:
        notification = TicketNotification(
            id=str(uuid.uuid4()),
            company_id=ticket.company_id,
            recipient_id=recipient_id,
            ticket_id=ticket.id,
            ticket_title=ticket.title,
            type=event_type,
            actor_id=actor_id,
            created_at=created_at,
            previous_value=previous_value,
            new_value=new_value,
        )
        repository.add(notification)
        created.append(notification)
    return created
