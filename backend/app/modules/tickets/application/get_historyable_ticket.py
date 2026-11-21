"""Resolucion del ticket sobre el que se puede consultar el historial (HU-09).

Implementa RF-84 y RF-85 reutilizando la visibilidad de HU-06:

1. Solo los roles de gestion (`tecnico` y `administrador`) pueden consultar
   el historial; un cliente recibe el mismo 404 uniforme aunque el ticket
   sea suyo.
2. `get_ticket_detail` valida el formato UUID, la existencia y la
   visibilidad con el 404 uniforme de HU-02/HU-06.
3. No se comprueba el estado `Cerrado`: el historial se conserva y se puede
   leer en cualquier estado (RF-85).

La traduccion a codigos HTTP corresponde a la capa de comunicacion.
"""

from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
    get_ticket_detail,
)
from app.modules.tickets.domain.entities import TICKET_READ_ROLES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def get_historyable_ticket(
    ticket_id: str,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
    actor_company_id: str | None = None,
) -> Ticket:
    """Devuelve el ticket cuyo historial puede consultar el actor.

    Lanza `TicketNotFoundError` (404 uniforme) si el rol no es de gestion,
    si el identificador no tiene formato UUID valido, si el ticket no
    existe o si el cliente no puede verlo. Un ticket `Cerrado` se devuelve
    sin error: la lectura no modifica nada.
    """
    if not isinstance(actor_role, str) or actor_role not in TICKET_READ_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return get_ticket_detail(
        ticket_id=ticket_id,
        actor_id=actor_id,
        actor_role=actor_role,
        tickets=tickets,
        actor_company_id=actor_company_id,
    )
