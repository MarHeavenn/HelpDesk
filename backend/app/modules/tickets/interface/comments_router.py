"""Rutas HTTP del seguimiento y comentarios de un ticket (HU-07).

Prefijo compartido `/api/tickets`: el subrecurso `/{ticket_id}/comments`
tiene un segmento mas que el detalle `/{ticket_id}`, por lo que no compite
con las rutas de HU-02/HU-06.

Solo comunica: la visibilidad, el permiso de escritura, el estado cerrado
y la validacion del cuerpo viven en los casos de uso y el dominio. El
cuerpo se lee en una dependencia declarada al final para que 401, 404 y
409 precedan al 422 (RF-70).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.users_contract import get_user_summary
from app.modules.tickets.application.create_comment import create_comment
from app.modules.tickets.application.create_ticket import (
    TicketValidationError,
)
from app.modules.tickets.application.get_commentable_ticket import (
    get_commentable_ticket,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TicketClosedError,
)
from app.modules.tickets.application.get_ticket import TicketNotFoundError
from app.modules.tickets.application.list_comments import list_comments
from app.modules.tickets.domain.entities import Ticket, TicketComment
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.router import (
    _json_body,
    _json_body_documentation,
)
from app.modules.tickets.interface.schemas import (
    AuthorResponse,
    CommentResponse,
    CreateCommentRequest,
)

router = APIRouter(prefix="/api/tickets", tags=["comments"])

_comment_body = _json_body(CreateCommentRequest)


def _commentable_ticket(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> Ticket:
    """Resuelve el ticket sobre el que el actor puede comentar.

    Delega en `get_commentable_ticket` (visibilidad de HU-06, rol de
    gestion y estado cerrado) y traduce sus errores. Al ser una
    dependencia, FastAPI la resuelve antes del cuerpo: 401, 404 y 409
    prevalecen sobre el 422 de validacion.
    """
    try:
        return get_commentable_ticket(
            ticket_id=ticket_id,
            actor_id=current["id"],
            actor_role=current["role"],
            tickets=get_ticket_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _author_response(comment: TicketComment) -> AuthorResponse | None:
    """Compone el autor o `None` si no se puede resolver.

    Reutiliza el contrato de `identity` de HU-06 y proyecta solo `id` y
    `name`; `tickets` no accede al repositorio de usuarios ni expone el
    correo, el rol o las credenciales (RF-67).
    """
    user = get_user_summary(comment.author_id)
    if user is None:
        return None
    return AuthorResponse(id=user.id, name=user.name)


def _comment_response(comment: TicketComment) -> CommentResponse:
    """Serializa un comentario (fecha con offset UTC y microsegundos)."""
    return CommentResponse(
        id=comment.id,
        ticket_id=comment.ticket_id,
        body=comment.body,
        author=_author_response(comment),
        created_at=comment.created_at.isoformat(),
    )


@router.post(
    "/{ticket_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    openapi_extra=_json_body_documentation(CreateCommentRequest),
)
def create_comment_endpoint(
    ticket: Ticket = Depends(_commentable_ticket),
    current: dict = Depends(get_current_user),
    payload: CreateCommentRequest = Depends(_comment_body),
) -> CommentResponse:
    """Registra un comentario de seguimiento (201) o rechaza con 422.

    La visibilidad, el permiso de escritura y el estado cerrado se
    resuelven en `_commentable_ticket` antes de leer el cuerpo
    (401/404/409 > 422). El autor procede de la sesion y la fecha la
    genera el sistema (RF-61, RF-70).
    """
    try:
        comment = create_comment(
            ticket=ticket,
            body=payload.body,
            author_id=current["id"],
            comments=get_ticket_comment_repository(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _comment_response(comment)


@router.get(
    "/{ticket_id}/comments",
    response_model=list[CommentResponse],
)
def list_comments_endpoint(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> list[CommentResponse]:
    """Lista el seguimiento visible del ticket, del mas antiguo al mas nuevo.

    La visibilidad de HU-06 se resuelve en el caso de uso; un cliente solo
    lee los comentarios de sus tickets y el personal los de cualquiera. El
    ticket cerrado conserva la lectura (RF-63, RF-64, RF-66).
    """
    try:
        comments = list_comments(
            ticket_id=ticket_id,
            actor_id=current["id"],
            actor_role=current["role"],
            tickets=get_ticket_repository(),
            comments=get_ticket_comment_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_comment_response(comment) for comment in comments]
