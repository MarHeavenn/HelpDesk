"""Generacion perezosa de alertas de SLA (HU-16, RF-156 a RF-159).

El analisis se ejecuta antes de consultar las notificaciones y reutiliza
por completo el calculo de SLA de HU-05 (`get_ticket_sla`): no hay un
segundo umbral ni una tarea programada. Para cada ticket activo con SLA
`en_riesgo` o `incumplido` registra una notificacion por destinatario:

- todos los administradores activos de la empresa del ticket;
- el tecnico asignado vigente, si existe.

La clave de deduplicacion incluye el vencimiento (`due_at`), de modo que
repetir el analisis no duplica la alerta, pero un cambio de prioridad, de
la politica de SLA o una reapertura que mueva el vencimiento si puede
generar un evento nuevo (RF-158).

El caso de uso no importa `sla` por su dominio (usa el contrato) ni
`identity` (recibe un `Callable` que devuelve identificadores). El router
compone ambas dependencias.
"""

from collections.abc import Callable
from datetime import datetime, timezone
import uuid

from app.modules.sla.domain.entities import TicketSlaSnapshot
from app.modules.sla.interface.contract import get_ticket_sla
from app.modules.tickets.domain.entities import (
    NOTIFICATION_TYPE_SLA_BREACHED,
    NOTIFICATION_TYPE_SLA_NEAR_DUE,
    RESOLVED_STATUSES,
    SYSTEM_ACTOR_ID,
    Ticket,
    TicketNotification,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Roles cuyo analisis cubre todos los tickets de su empresa (RF-160).
SLA_ALERT_COMPANY_ROLES = frozenset({"administrador", "supervisor"})
SLA_ALERT_TECHNICIAN_ROLE = "tecnico"


def _tickets_in_scope(
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Tickets que analiza el actor segun su rol (RF-160)."""
    if actor_role in SLA_ALERT_COMPANY_ROLES:
        return [
            ticket
            for ticket in tickets.list_all()
            if ticket.company_id == actor_company_id
        ]
    if actor_role == SLA_ALERT_TECHNICIAN_ROLE:
        return tickets.list_by_assignee(actor_id)
    return []


def _alert_type(sla) -> str | None:
    """Tipo de alerta para el estado del SLA, o None si no aplica."""
    if sla.breached:
        return NOTIFICATION_TYPE_SLA_BREACHED
    if sla.near_due:
        return NOTIFICATION_TYPE_SLA_NEAR_DUE
    return None


def _recipients(
    ticket: Ticket,
    administrator_ids: Callable[[str | None], list[str]],
) -> list[str]:
    """Administradores activos de la empresa y tecnico, sin duplicados."""
    recipients: list[str] = []
    for candidate in administrator_ids(ticket.company_id):
        if candidate not in recipients:
            recipients.append(candidate)
    if ticket.assignee_id is not None and ticket.assignee_id not in recipients:
        recipients.append(ticket.assignee_id)
    return recipients


def generate_sla_alerts(
    *,
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    tickets: InMemoryTicketRepository,
    notifications: InMemoryNotificationRepository,
    administrator_ids: Callable[[str | None], list[str]],
    now: datetime | None = None,
) -> list[TicketNotification]:
    """Registra las alertas de SLA pendientes del ambito del actor.

    Un unico instante de referencia calcula el SLA de todos los tickets del
    analisis. No modifica tickets ni registros de historial. Devuelve las
    notificaciones creadas, en orden de ticket y destinatario.
    """
    reference = now if now is not None else datetime.now(timezone.utc)
    created: list[TicketNotification] = []

    for ticket in _tickets_in_scope(
        actor_id, actor_role, actor_company_id, tickets
    ):
        if ticket.status in RESOLVED_STATUSES:
            continue
        if ticket.resolved_at is not None:
            continue

        sla = get_ticket_sla(
            TicketSlaSnapshot(
                ticket.priority,
                ticket.created_at,
                ticket.resolved_at,
                ticket.resolved_target_minutes,
            ),
            reference,
        )
        if sla is None:
            continue

        alert_type = _alert_type(sla)
        if alert_type is None:
            continue

        due_at = sla.due_at.isoformat()
        for recipient_id in _recipients(ticket, administrator_ids):
            dedupe_key = (
                f"sla:{ticket.id}:{alert_type}:{recipient_id}:{due_at}"
            )
            notification = TicketNotification(
                id=str(uuid.uuid4()),
                company_id=ticket.company_id,
                recipient_id=recipient_id,
                ticket_id=ticket.id,
                ticket_title=ticket.title,
                type=alert_type,
                actor_id=SYSTEM_ACTOR_ID,
                created_at=reference,
                previous_value=None,
                new_value=due_at,
                dedupe_key=dedupe_key,
            )
            if notifications.add_if_new(notification):
                created.append(notification)

    return created
