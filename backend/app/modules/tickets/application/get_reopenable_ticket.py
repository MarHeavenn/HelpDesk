"""Resolucion y permiso para reabrir un ticket cerrado (HU-08, RF-76, RF-77).

Sigue el patron de `get_assignable_ticket`: decide *sobre que ticket* puede
actuar un administrador antes de ejecutar la reapertura. El caso de uso
`reopen_ticket` lo invoca, de modo que el rechazo por permiso o por estado
del recurso precede a cualquier efecto.

Orden de comprobaciones:
1. Permiso de reapertura por rol de sesion (`REOPEN_ROLES`): solo el
   administrador resuelve el ticket; un tecnico o un cliente reciben el
   404 uniforme de HU-02 sin resolver siquiera el ticket (no se revela
   nada).
2. Formato del identificador y existencia del ticket: 404 con el mismo
   mensaje unificado de HU-02.
3. Estado distinto de `Cerrado`: 409 (`TicketNotClosedError`); solo se
   reabre un ticket cerrado.

La traduccion a codigos HTTP corresponde a la capa de comunicacion.
"""

from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    REOPEN_ROLES,
    Ticket,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Mensaje unico del 409 de reapertura: el ticket no esta cerrado.
TICKET_NOT_CLOSED_MESSAGE = "ticket is not closed"


class TicketNotClosedError(ValueError):
    """El ticket no esta cerrado y no se puede reabrir (-> 409, RF-77)."""


def get_reopenable_ticket(
    ticket_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
    actor_company_id: str | None = None,
) -> Ticket:
    """Devuelve el ticket que el actor puede reabrir.

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02) si el rol no
    tiene permiso de reapertura —antes de resolver el ticket—, si el
    identificador no tiene formato UUID valido o si el ticket no existe
    (RF-77). Lanza `TicketNotClosedError` si el ticket no esta `Cerrado`.
    """
    if not isinstance(actor_role, str) or actor_role not in REOPEN_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    same_tenant = ticket.company_id == actor_company_id
    if ticket.company_id is None and actor_company_id is None:
        same_tenant = True
    if not same_tenant:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if ticket.status != CLOSED_STATUS:
        raise TicketNotClosedError(TICKET_NOT_CLOSED_MESSAGE)
    return ticket
