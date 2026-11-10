"""Rutas HTTP del historial y la trazabilidad de un ticket (HU-09).

Prefijo compartido `/api/tickets`: el subrecurso `/{ticket_id}/history`
tiene un segmento mas que el detalle `/{ticket_id}`, por lo que no compite
con las rutas de HU-02/HU-06.

Solo comunica: la visibilidad, el 404 uniforme y la derivacion de eventos
viven en los casos de uso. Los nombres visibles se resuelven con el
contrato publico de `identity`, sin acceder a sus estructuras internas.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.users_contract import get_user_summary
from app.modules.tickets.application.get_ticket import TicketNotFoundError
from app.modules.tickets.application.list_ticket_history import (
    list_ticket_history,
)
from app.modules.tickets.domain.entities import TicketHistoryEvent
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.schemas import (
    HistoryEventResponse,
    HistoryUserResponse,
)

router = APIRouter(prefix="/api/tickets", tags=["history"])


def _user_response(user_id: str | None) -> HistoryUserResponse | None:
    """Resuelve el nombre visible de un usuario del evento (RF-88).

    Conserva el identificador aunque el usuario ya no exista; en ese caso
    el nombre queda vacio. La lectura no revela correo, rol ni credenciales.
    """
    if user_id is None:
        return None
    user = get_user_summary(user_id)
    return HistoryUserResponse(
        id=user_id,
        name=user.name if user is not None else None,
    )


def _event_response(event: TicketHistoryEvent) -> HistoryEventResponse:
    """Serializa un evento del historial (fecha con offset UTC)."""
    return HistoryEventResponse(
        action=event.action,
        actor=_user_response(event.actor_id),
        occurred_at=event.occurred_at.isoformat(),
        previous_value=event.previous_value,
        new_value=event.new_value,
        previous_assignee=_user_response(event.previous_assignee_id),
        new_assignee=_user_response(event.new_assignee_id),
        comment=event.comment,
    )


@router.get(
    "/{ticket_id}/history",
    response_model=list[HistoryEventResponse],
)
def list_ticket_history_endpoint(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> list[HistoryEventResponse]:
    """Lista el historial visible del ticket, del mas antiguo al mas nuevo.

    La visibilidad (solo `tecnico` y `administrador`) y el 404 uniforme se
    resuelven en el caso de uso. Un ticket cerrado conserva su historial.
    """
    try:
        events = list_ticket_history(
            ticket_id=ticket_id,
            actor_id=current["id"],
            actor_role=current["role"],
            tickets=get_ticket_repository(),
            modifications=get_ticket_modification_log(),
            assignments=get_assignment_log(),
            comments=get_ticket_comment_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_event_response(event) for event in events]
