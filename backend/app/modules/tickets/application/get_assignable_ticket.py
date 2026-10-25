"""Caso de uso de resolucion y permiso para asignar un ticket (RF-38, RF-39.4).

Decide *sobre que ticket* puede actuar un administrador que asigna o
reasigna. El caso de uso `assign_ticket` (T6) lo invoca antes de validar
el tecnico solicitado, de modo que el rechazo por permiso y por estado del
recurso precede al 422 (RF-40).

Orden de comprobaciones:
1. Permiso de asignacion por rol de sesion (RF-38): solo los roles de
   `ASSIGNMENT_ROLES` (administrador) resuelven el ticket; un cliente o un
   tecnico reciben el 404 uniforme de HU-02 sin resolver siquiera el
   ticket (no se revela nada, tampoco si esta cerrado).
2. Formato del identificador y existencia del ticket: 404 con el mismo
   mensaje unificado de HU-02 (RF-39.4).
3. Estado `Cerrado`: 409 (`TicketClosedError`, mensaje de HU-03 `ticket is
   closed`); un ticket cerrado no admite asignacion ni reasignacion,
   incluida la repeticion del tecnico vigente (RF-39.4).

Es independiente de `get_modifiable_ticket` de HU-03 (D9): la autorizacion
de asignacion es distinta —solo administrador— y aquel codigo no se toca.
La traduccion a codigos HTTP corresponde a la capa de comunicacion (T8).
"""

from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
    TicketClosedError,
)
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import (
    ASSIGNMENT_ROLES,
    CLOSED_STATUS,
    Ticket,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def get_assignable_ticket(
    ticket_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
) -> Ticket:
    """Devuelve el ticket que el actor puede asignar o reasignar.

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02) si el rol no
    tiene permiso de asignacion —antes de resolver el ticket—, si el
    identificador no tiene formato UUID valido o si el ticket no existe
    (RF-38, RF-39.4). Lanza `TicketClosedError` si el ticket esta
    `Cerrado` (RF-39.4), comprobacion previa a cualquier validacion de la
    solicitud y del tecnico (RF-40).
    """
    if not isinstance(actor_role, str) or actor_role not in ASSIGNMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if ticket.status == CLOSED_STATUS:
        raise TicketClosedError(TICKET_CLOSED_MESSAGE)
    return ticket
