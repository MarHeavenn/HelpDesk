"""Caso de uso de resolucion y permiso para modificar un ticket.

Implementa la parte de RF-24, RF-25, RF-28 y RF-30 que decide *sobre que
ticket* puede actuar un usuario de gestion. Los casos de uso de
modificacion (T5) lo invocan antes de validar el valor solicitado, de modo
que el rechazo por permiso o por estado del recurso precede al 422.

Orden de comprobaciones (RF-30):
1. Permiso de gestion por rol de sesion: un cliente recibe el 404
   uniforme de HU-02 sin resolver siquiera el ticket (no se revela nada).
2. Formato del identificador y existencia del ticket: 404 con el mismo
   mensaje unificado de HU-02.
3. Estado `Cerrado`: 409 (`TicketClosedError`); en HU-03 el ticket cerrado
   es inmutable (la reapertura es de HU-08).

La traduccion a codigos HTTP corresponde a la capa de comunicacion (T6).
"""

from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import (
    CLOSED_STATUS,
    MANAGEMENT_ROLES,
    Ticket,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Mensaje unico del 409 (contrato del plan, seccion 2): el ticket esta
# cerrado y no admite modificaciones en esta historia.
TICKET_CLOSED_MESSAGE = "ticket is closed"


class TicketClosedError(ValueError):
    """El ticket esta cerrado y es inmutable en HU-03 (-> 409, RF-28)."""


def get_modifiable_ticket(
    ticket_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
) -> Ticket:
    """Devuelve el ticket sobre el que el actor puede operar.

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02) si el rol no
    tiene permisos de gestion —antes de resolver el ticket—, si el
    identificador no tiene formato UUID valido o si el ticket no existe
    (RF-24, RF-25). Lanza `TicketClosedError` si el ticket esta `Cerrado`
    (RF-28), comprobacion previa a cualquier validacion de la entrada.
    """
    if not isinstance(actor_role, str) or actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if ticket.status == CLOSED_STATUS:
        raise TicketClosedError(TICKET_CLOSED_MESSAGE)
    return ticket
