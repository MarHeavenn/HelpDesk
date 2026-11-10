"""Caso de uso del listado cronologico de comentarios (HU-07).

Reutiliza la visibilidad de HU-06 (`get_ticket_detail`) para que cliente,
tecnico y administrador lean exactamente el seguimiento de los tickets que
pueden ver. La lectura no exige rol de gestion ni comprueba el estado
cerrado: un ticket cerrado conserva su historial (RF-63, RF-66).
"""

from app.modules.tickets.application.get_ticket import get_ticket_detail
from app.modules.tickets.domain.entities import TicketComment
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    InMemoryTicketCommentRepository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_comments(
    ticket_id: str,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
    comments: InMemoryTicketCommentRepository,
) -> list[TicketComment]:
    """Devuelve el seguimiento visible del ticket, del mas antiguo al mas nuevo.

    Lanza `TicketNotFoundError` (404 uniforme) si el ticket no existe, el
    identificador no tiene formato valido o el cliente no es el
    solicitante, con la misma regla de HU-06.
    """
    get_ticket_detail(
        ticket_id=ticket_id,
        actor_id=actor_id,
        actor_role=actor_role,
        tickets=tickets,
    )
    return comments.list_by_ticket(ticket_id)
