"""Caso de uso de listado de los tickets a cargo (RF-36).

Devuelve los tickets cuyo tecnico responsable es el usuario autenticado,
en cualquier estado (incluido `Cerrado`). El rol no filtra aqui: solo los
tecnicos pueden ser asignados, de modo que un cliente o un administrador
reciben una coleccion vacia de forma natural. El orden por `created_at`
descendente lo garantiza el repositorio. Sin paginacion ni filtros; un
empate de fecha no fija orden. No muta tickets ni registros.
"""

from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_assigned_tickets(
    assignee_id: str,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Tickets a cargo del tecnico autenticado, mas recientes primero."""
    return tickets.list_by_assignee(assignee_id)
