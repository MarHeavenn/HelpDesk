"""Caso de uso de creacion de tickets (RF-11, RF-13, RF-14).

Orquesta validacion -> generacion de identificador, estado inicial y
fecha/hora -> persistencia. Toda la regla de negocio vive aqui y en el
dominio; la interfaz solo comunica.
"""

import uuid
from datetime import datetime, timezone

from app.modules.tickets.domain.entities import (
    OPEN_STATUS,
    Ticket,
    validate_description,
    validate_title,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


class TicketValidationError(ValueError):
    """Alguna regla de validacion de RF-12 se incumplio (-> 422)."""


def create_ticket(
    title: str,
    description: str,
    requester_id: str,
    tickets: InMemoryTicketRepository,
    now: datetime | None = None,
) -> Ticket:
    """Crea un ticket del solicitante autenticado.

    Valida y recorta titulo y descripcion (RF-12; lanza
    TicketValidationError), genera un identificador UUID (RF-13), fija el
    estado inicial `Abierto` (RF-11, RF-19), sella `created_at` con zona
    UTC (RF-11) y asocia el ticket al solicitante recibido (RF-14). El
    solicitante procede de la sesion, nunca del cuerpo de la peticion.
    """
    try:
        clean_title = validate_title(title)
        clean_description = validate_description(description)
    except ValueError as exc:
        if isinstance(exc, TicketValidationError):
            raise
        raise TicketValidationError(str(exc)) from exc
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=clean_title,
        description=clean_description,
        requester_id=requester_id,
        created_at=now or datetime.now(timezone.utc),
        status=OPEN_STATUS,
    )
    tickets.add(ticket)
    return ticket
