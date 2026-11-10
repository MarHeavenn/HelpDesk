"""Caso de uso de registro de un comentario de seguimiento (HU-07).

El ticket llega ya resuelto y autorizado por `get_commentable_ticket`
(visibilidad de HU-06, rol de gestion y estado no cerrado). Aqui solo se
valida el contenido, se genera el identificador y la fecha, y se persiste
el comentario. El ticket no se muta (RF-69).
"""

import uuid
from datetime import datetime, timezone

from app.modules.tickets.application.create_ticket import (
    TicketValidationError,
)
from app.modules.tickets.domain.entities import (
    Ticket,
    TicketComment,
    validate_comment_body,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    InMemoryTicketCommentRepository,
)


def create_comment(
    ticket: Ticket,
    body: object,
    author_id: str,
    comments: InMemoryTicketCommentRepository,
    now: datetime | None = None,
) -> TicketComment:
    """Valida el cuerpo y registra el comentario del autor autenticado.

    Lanza `TicketValidationError` si el cuerpo no es texto o queda fuera de
    1-2000 code points tras el recorte (RF-62), sin crear nada. El autor
    procede de la sesion, nunca del cuerpo de la peticion (RF-61).
    """
    try:
        clean_body = validate_comment_body(body)
    except ValueError as exc:
        if isinstance(exc, TicketValidationError):
            raise
        raise TicketValidationError(str(exc)) from exc

    comment = TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        author_id=author_id,
        body=clean_body,
        created_at=now or datetime.now(timezone.utc),
    )
    comments.add(comment)
    return comment
