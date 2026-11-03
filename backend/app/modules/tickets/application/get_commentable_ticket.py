"""Resolucion del ticket sobre el que se puede comentar (HU-07).

Implementa RF-64, RF-65 y RF-66 combinando la visibilidad de HU-06 con el
permiso de escritura de HU-07:

1. `get_ticket_detail` aplica el 404 uniforme de HU-02/HU-06 para ticket
   inexistente, identificador invalido o cliente sin visibilidad.
2. Solo los roles de gestion (`tecnico` y `administrador`) pueden escribir;
   un cliente recibe el mismo 404 aunque el ticket sea suyo (RF-65).
3. Un ticket `Cerrado` responde 409 con el contrato de HU-03 (RF-66).

La traduccion a codigos HTTP corresponde a la capa de comunicacion.
"""

from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
    TicketClosedError,
)
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
    get_ticket_detail,
)
from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    MANAGEMENT_ROLES,
    Ticket,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def get_commentable_ticket(
    ticket_id: str,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
) -> Ticket:
    """Devuelve el ticket sobre el que el actor puede registrar un comentario.

    Lanza `TicketNotFoundError` si el ticket no es visible para el actor o
    si el rol no es de gestion; lanza `TicketClosedError` si el ticket esta
    `Cerrado`. El orden de comprobaciones hace que la falta de sesion la
    resuelva `get_current_user` (401) antes que el recurso, y que el 404
    preceda al 409.
    """
    ticket = get_ticket_detail(
        ticket_id=ticket_id,
        actor_id=actor_id,
        actor_role=actor_role,
        tickets=tickets,
    )
    if not isinstance(actor_role, str) or actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if ticket.status == CLOSED_STATUS:
        raise TicketClosedError(TICKET_CLOSED_MESSAGE)
    return ticket
