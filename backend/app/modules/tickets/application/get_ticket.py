"""Caso de uso de detalle de un ticket propio (RF-16, RF-17).

El control de propiedad vive aqui, en la logica de negocio (no en la
interfaz): solo se devuelve el ticket si su solicitante es el usuario
autenticado. Un ticket inexistente o ajeno se trata como no encontrado
para no revelar la existencia de tickets de otros usuarios.

La traduccion de `TicketNotFoundError` a un codigo HTTP corresponde a la
capa de comunicacion (RF-17 -> 404, cableado en T6).
"""

from app.modules.tickets.domain.entities import Ticket, is_valid_uuid_format
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Mensaje unico del 404: el mismo para ticket inexistente, identificador
# con formato invalido y ticket ajeno, de modo que los tres devuelvan un
# cuerpo de error identico y no se revele la existencia de tickets ajenos.
TICKET_NOT_FOUND_MESSAGE = "ticket not found"


class TicketNotFoundError(ValueError):
    """El ticket no existe o no pertenece al solicitante (-> 404, RF-17)."""


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
