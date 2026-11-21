"""Caso de uso de listado de los tickets propios (RF-15, RF-20).

Resuelve la propiedad del ticket en la logica de negocio (no en la
interfaz): solo se devuelven los tickets cuyo solicitante es el usuario
autenticado. El orden por `created_at` descendente lo garantiza el
repositorio. Sin paginacion ni filtros; un empate de fecha no fija orden.
"""

from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.domain.entities import TICKET_READ_ROLES
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_my_tickets(
    requester_id: str,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Tickets del solicitante autenticado, mas recientes primero (RF-15)."""
    return tickets.list_by_requester(requester_id)


def list_visible_tickets(
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Lista tickets visibles por rol y por el tenant almacenado."""
    # Tickets legacy sin tenant conservan el contrato HU-02 de listado propio.
    if actor_company_id is None:
        if any(ticket.company_id is not None for ticket in tickets.list_all()):
            return []
        return tickets.list_by_requester(actor_id)
    visible: list[Ticket] = []
    for ticket in tickets.list_all():
        same_tenant = ticket.company_id == actor_company_id
        if ticket.company_id is None and actor_company_id is None:
            same_tenant = True
        if not same_tenant:
            continue
        if actor_role in TICKET_READ_ROLES or (
            actor_role == "cliente" and ticket.requester_id == actor_id
        ):
            visible.append(ticket)
    return visible
