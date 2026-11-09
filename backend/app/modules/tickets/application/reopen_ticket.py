"""Caso de uso de reapertura de un ticket cerrado (HU-08, RF-76, RF-80).

El ticket ya viene resuelto y autorizado por `get_reopenable_ticket`
(solo administrador y solo en estado `Cerrado`). Aqui solo se muta el
estado a `Abierto`, se descarta `resolved_at` para que el SLA vuelva a
evolucionar desde la creacion y se registra la modificacion.

No toca prioridad, tecnico responsable, solicitante, titulo, descripcion
ni fecha de creacion. El registro reutiliza `TicketModification`, de modo
que el historial de HU-09 lo vera sin un formato nuevo.
"""

from datetime import datetime, timezone

from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    OPEN_STATUS,
    STATUS_FIELD,
    Ticket,
    TicketModification,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)


def reopen_ticket(
    ticket: Ticket,
    actor_id: str,
    modifications: InMemoryTicketModificationLog,
    now: datetime | None = None,
) -> Ticket:
    """Reabre el ticket cerrado y devuelve el ticket en `Abierto`.

    Muta `Ticket.status`, descarta `resolved_at` (RF-80) y anade el
    registro `Cerrado` -> `Abierto` con el responsable de la sesion y la
    fecha y hora del sistema (RF-76). El registro no forma parte del
    ticket devuelto.
    """
    changed_at = now if now is not None else datetime.now(timezone.utc)
    previous_status = ticket.status
    ticket.status = OPEN_STATUS
    ticket.resolved_at = None
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value=previous_status,
            new_value=OPEN_STATUS,
            actor_id=actor_id,
            changed_at=changed_at,
        )
    )
    return ticket
