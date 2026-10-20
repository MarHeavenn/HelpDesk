"""Rutas HTTP de los tickets a cargo (RF-36).

Prefijo propio `/api/assignments` (D6): no compite con
`GET /api/tickets/{ticket_id}` ni depende del orden de declaracion de
rutas. Solo comunica: delega en el caso de uso y compone el resumen. La
sesion (`get_current_user`, 401) es el unico requisito; no hay permiso
adicional (RF-40), y el rol no se toma de la peticion. Los parametros de
consulta desconocidos se ignoran en silencio (sin declarar parametros).
No muta tickets ni registros.
"""

from fastapi import APIRouter, Depends

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.tickets.application.list_assigned_tickets import (
    list_assigned_tickets,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.router import ticket_summary
from app.modules.tickets.interface.schemas import TicketSummaryResponse

router = APIRouter(prefix="/api/assignments", tags=["assignments"])


@router.get("/mine", response_model=list[TicketSummaryResponse])
def list_my_assigned_tickets_endpoint(
    current: dict = Depends(get_current_user),
) -> list[TicketSummaryResponse]:
    """Lista los tickets a cargo del usuario, mas recientes primero."""
    tickets = list_assigned_tickets(
        assignee_id=current["id"],
        tickets=get_ticket_repository(),
    )
    return [ticket_summary(ticket) for ticket in tickets]
