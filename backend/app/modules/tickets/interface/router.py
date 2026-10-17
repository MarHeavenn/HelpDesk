"""Rutas HTTP de tickets (RF-11, RF-13, RF-14, RF-15, RF-16).

Solo comunican: delegan en los casos de uso y traducen sus errores a
codigos HTTP con cuerpo consistente {"detail": <mensaje>}. La identidad
proviene de la dependencia `get_current_user` de `identity` (unico
contacto entre modulos; el ticket usa solo `current["id"]`).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.tickets.application.create_ticket import (
    TicketValidationError,
    create_ticket,
)
from app.modules.tickets.application.get_ticket import (
    TicketNotFoundError,
    get_my_ticket,
)
from app.modules.tickets.application.list_tickets import list_my_tickets
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.schemas import (
    CreateTicketRequest,
    TicketResponse,
    TicketSummaryResponse,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _ticket_response(ticket: Ticket) -> TicketResponse:
    """Serializa el ticket (fecha con offset UTC y microsegundos)."""
    return TicketResponse(
        id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
        created_at=ticket.created_at.isoformat(),
        requester_id=ticket.requester_id,
    )


def _ticket_summary(ticket: Ticket) -> TicketSummaryResponse:
    """Serializa el resumen del listado (sin descripcion, RF-15)."""
    return TicketSummaryResponse(
        id=ticket.id,
        title=ticket.title,
        status=ticket.status,
        created_at=ticket.created_at.isoformat(),
    )


@router.post("", response_model=TicketResponse, status_code=201)
def create_ticket_endpoint(
    payload: CreateTicketRequest,
    current: dict = Depends(get_current_user),
) -> TicketResponse:
    """Crea un ticket del usuario autenticado (201) o rechaza con 422."""
    try:
        ticket = create_ticket(
            title=payload.title,
            description=payload.description,
            requester_id=current["id"],
            tickets=get_ticket_repository(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ticket_response(ticket)


@router.get("", response_model=list[TicketSummaryResponse])
def list_tickets_endpoint(
    current: dict = Depends(get_current_user),
) -> list[TicketSummaryResponse]:
    """Lista los tickets propios, mas recientes primero (RF-15)."""
    tickets = list_my_tickets(
        requester_id=current["id"],
        tickets=get_ticket_repository(),
    )
    return [_ticket_summary(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket_endpoint(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> TicketResponse:
    """Detalle de un ticket propio (RF-16, RF-17).

    `ticket_id` se declara como `str` (no `uuid.UUID`) para que un
    identificador mal formado no devuelva 422 de FastAPI: el formato y la
    propiedad se resuelven en la logica y se traducen aqui a 404. Sin
    sesion valida, `get_current_user` responde 401 antes del handler
    (precedencia 401 > 404, RF-18).
    """
    try:
        ticket = get_my_ticket(
            ticket_id=ticket_id,
            requester_id=current["id"],
            tickets=get_ticket_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ticket_response(ticket)
