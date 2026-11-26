"""Caso de uso de listado de los tickets a cargo (RF-36).

Devuelve los tickets de la empresa de sesión cuyo técnico es el usuario autenticado,
en cualquier estado (incluido `Cerrado`). El rol no filtra aqui: solo los
tecnicos pueden ser asignados, de modo que un cliente o un administrador
reciben una coleccion vacia de forma natural. El orden por `created_at`
descendente lo garantiza el repositorio. Sin paginacion ni filtros; un
empate de fecha no fija orden. No muta tickets ni registros.
"""

from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_assigned_tickets(
    assignee_id: str,
    tickets: InMemoryTicketRepository,
    actor_company_id: str | None,
) -> list[Ticket]:
    """Tickets a cargo del tecnico autenticado, mas recientes primero."""
    if actor_company_id is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return [
        ticket for ticket in tickets.list_by_assignee(assignee_id)
        if ticket.company_id == actor_company_id
    ]
