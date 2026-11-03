"""Caso de uso de listado de tickets que requieren atencion (HU-10, RF-61, RF-63, RF-65).

Deriva, en el instante de la consulta, los tickets activos (`Abierto`/
`En progreso`) cuyo SLA esta `en_riesgo` (`near_due`) o `incumplido`
(`breached`), reutilizando por completo el calculo de HU-05
(`get_ticket_sla`): no introduce un segundo calculo ni un umbral nuevo
(RF-67). Los devuelve ordenados por `sla.due_at` ascendente (RF-65).

Solo los roles de gestion (`tecnico`/`administrador`) pueden consultar el
listado; un `cliente` recibe el 404 uniforme (`TicketNotFoundError` con
`TICKET_NOT_FOUND_MESSAGE`) **antes** de leer el repositorio, sin revelar
datos (RF-63). La regla «que ticket requiere atencion» vive aqui, en la
capa de aplicacion, no en el controlador HTTP.

No muta tickets ni registros: es una consulta de solo lectura derivada en
vivo, sin estado persistido (RF-62, RF-68).
"""

from datetime import datetime, timezone

from app.modules.sla.domain.entities import TicketSlaSnapshot
from app.modules.sla.interface.contract import get_ticket_sla
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import (
    MANAGEMENT_ROLES,
    RESOLVED_STATUSES,
    Ticket,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_attention_tickets(
    actor_role: str,
    tickets: InMemoryTicketRepository,
    now: datetime | None = None,
) -> list[Ticket]:
    """Tickets que requieren atencion por SLA, mas urgentes primero (RF-61, RF-65).

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02/HU-03/HU-04) si
    el rol no es de gestion, antes de leer el repositorio. Usa un unico
    instante de referencia (`now` inyectado o el reloj UTC) para calcular el
    SLA de todo el listado. Conserva solo los activos con `near_due` o
    `breached` y los ordena por `due_at` ascendente.
    """
    if actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    reference = now if now is not None else datetime.now(timezone.utc)
    attention: list[tuple[datetime, Ticket]] = []
    for ticket in tickets.list_all():
        if ticket.status in RESOLVED_STATUSES:
            continue
        sla = get_ticket_sla(
            TicketSlaSnapshot(ticket.priority, ticket.created_at, ticket.resolved_at),
            reference,
        )
        if sla is None:
            continue
        if sla.near_due or sla.breached:
            attention.append((sla.due_at, ticket))
    attention.sort(key=lambda item: item[0])
    return [ticket for _, ticket in attention]
