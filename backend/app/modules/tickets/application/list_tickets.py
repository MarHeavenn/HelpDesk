"""Caso de uso de listado de los tickets propios (RF-15, RF-20).

Resuelve la propiedad del ticket en la logica de negocio (no en la
interfaz): solo se devuelven los tickets cuyo solicitante es el usuario
autenticado. El orden por `created_at` descendente lo garantiza el
repositorio. Sin paginacion ni filtros; un empate de fecha no fija orden.
"""

from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_my_tickets(
    requester_id: str,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Tickets del solicitante autenticado, mas recientes primero (RF-15)."""
    return tickets.list_by_requester(requester_id)
