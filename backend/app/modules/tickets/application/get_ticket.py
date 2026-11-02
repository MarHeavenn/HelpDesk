"""Casos de uso de detalle de un ticket (HU-02 y HU-06).

`get_my_ticket` implementa RF-16 y RF-17 de HU-02: control de propiedad para
el rol cliente, sin revelar la existencia de tickets ajenos.

`get_ticket_detail` implementa HU-06 (RF-51, RF-52, RF-56): mantiene la
regla del cliente y permite a los roles de gestion (`tecnico` y
`administrador`) consultar el detalle de cualquier ticket existente.

La traduccion de `TicketNotFoundError` a un codigo HTTP corresponde a la
capa de comunicacion (404).
"""

from app.modules.tickets.domain.entities import (
    MANAGEMENT_ROLES,
    Ticket,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Mensaje unico del 404: el mismo para ticket inexistente, identificador
# con formato invalido y ticket ajeno, de modo que los tres devuelvan un
# cuerpo de error identico y no se revele la existencia de tickets ajenos.
TICKET_NOT_FOUND_MESSAGE = "ticket not found"


class TicketNotFoundError(ValueError):
    """El ticket no existe o el actor no puede consultarlo (-> 404)."""


def get_my_ticket(
    ticket_id: str,
    requester_id: str,
    tickets: InMemoryTicketRepository,
) -> Ticket:
    """Devuelve el ticket propio indicado.

    Lanza TicketNotFoundError si el identificador no tiene formato de
    identificador valido, si el ticket no existe o si pertenece a otro
    solicitante (RF-16, RF-17). El formato se valida aqui, en la logica,
    y no en la firma de la ruta, para no devolver 422 (D5).
    """
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None or ticket.requester_id != requester_id:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return ticket


def get_ticket_detail(
    ticket_id: str,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
) -> Ticket:
    """Devuelve el ticket visible para el actor (HU-06, RF-51, RF-52).

    Un rol de gestion (`tecnico` o `administrador`) ve cualquier ticket
    existente, asignado o no. Un cliente solo ve los que creo, con el
    mismo 404 uniforme de HU-02. El formato del identificador y la
    existencia del ticket se validan antes de decidir el permiso; el 404
    es identico en todos los rechazos (RF-56).
    """
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if actor_role not in MANAGEMENT_ROLES and ticket.requester_id != actor_id:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return ticket
