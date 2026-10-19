"""Caso de uso de fijacion de prioridad de un ticket (RF-22, RF-26).

El ticket ya viene resuelto y autorizado por `get_modifiable_ticket`
(T4), de modo que aqui solo se valida el catalogo, se decide si hay
cambio efectivo y, en tal caso, se muta el ticket y se registra la
modificacion. La validacion y el registro viven en la logica de negocio,
nunca en la interfaz.

Reglas:
- Valor fuera del catalogo o no textual -> `TicketValidationError`
  (RF-21, RF-29.1, RF-29.3), sin modificar ni registrar.
- Valor igual a la prioridad vigente -> sin cambio y sin registro
  (RF-22).
- Cambio efectivo -> muta `Ticket.priority` y anade un registro con el
  responsable de la sesion, la fecha/hora del sistema y los valores
  anterior (`None` en la primera prioridad) y nuevo (RF-26).
"""

from datetime import datetime, timezone

from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.domain.entities import (
    PRIORITY_FIELD,
    Ticket,
    TicketModification,
    validate_priority,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)


def set_ticket_priority(
    ticket: Ticket,
    priority: object,
    actor_id: str,
    modifications: InMemoryTicketModificationLog,
    now: datetime | None = None,
) -> Ticket:
    """Fija la prioridad del ticket resuelto y devuelve el ticket.

    Lanza `TicketValidationError` si `priority` no es texto o no
    pertenece a `PRIORITIES` (RF-21, RF-29.1, RF-29.3), sin tocar el
    ticket ni el registro. Si coincide con la prioridad vigente no hay
    cambio ni registro (RF-22). En un cambio efectivo muta el ticket y
    anade `TicketModification` con `previous_value` vacio en la primera
    asignacion, `actor_id` de la sesion y `changed_at` del sistema
    (RF-26). El registro no forma parte del ticket devuelto.
    """
    try:
        new_priority = validate_priority(priority)
    except ValueError as exc:
        if isinstance(exc, TicketValidationError):
            raise
        raise TicketValidationError(str(exc)) from exc

    if ticket.priority == new_priority:
        return ticket

    previous_priority = ticket.priority
    ticket.priority = new_priority
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=PRIORITY_FIELD,
            previous_value=previous_priority,
            new_value=new_priority,
            actor_id=actor_id,
            changed_at=now if now is not None else datetime.now(timezone.utc),
        )
    )
    return ticket
