"""Caso de uso de actualizacion de estado de un ticket (RF-23, RF-26).

El ticket ya viene resuelto y autorizado por `get_modifiable_ticket`
(T4), que ademas rechaza los tickets `Cerrado` (RF-28). Aqui solo se
valida el catalogo, se decide si hay cambio efectivo y, en tal caso, se
muta el ticket y se registra la modificacion.

Reglas:
- Valor fuera del catalogo o no textual -> `TicketValidationError`
  (RF-21, RF-29.1, RF-29.3), sin modificar ni registrar.
- HU-03 no impone secuencia: cualquier transicion entre estados no
  cerrados es valida, incluidos saltos y retrocesos (RF-23).
- Valor igual al estado vigente -> sin cambio y sin registro (RF-23).
- Cambio efectivo -> muta `Ticket.status` y anade un registro con el
  responsable de la sesion, la fecha/hora del sistema y los valores
  anterior y nuevo (RF-26).
"""

from datetime import datetime, timezone

from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.domain.entities import (
    STATUS_FIELD,
    Ticket,
    TicketModification,
    validate_status,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)


def update_ticket_status(
    ticket: Ticket,
    status: object,
    actor_id: str,
    modifications: InMemoryTicketModificationLog,
    now: datetime | None = None,
) -> Ticket:
    """Actualiza el estado del ticket resuelto y devuelve el ticket.

    Lanza `TicketValidationError` si `status` no es texto o no pertenece
    a `STATUSES` (RF-21, RF-29.1, RF-29.3), sin tocar el ticket ni el
    registro. Si coincide con el estado vigente no hay cambio ni
    registro. En un cambio efectivo muta el ticket y anade
    `TicketModification` con los valores anterior y nuevo, `actor_id` de
    la sesion y `changed_at` del sistema (RF-23, RF-26). El registro no
    forma parte del ticket devuelto.
    """
    try:
        new_status = validate_status(status)
    except ValueError as exc:
        if isinstance(exc, TicketValidationError):
            raise
        raise TicketValidationError(str(exc)) from exc

    if ticket.status == new_status:
        return ticket

    previous_status = ticket.status
    ticket.status = new_status
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value=previous_status,
            new_value=new_status,
            actor_id=actor_id,
            changed_at=now if now is not None else datetime.now(timezone.utc),
        )
    )
    return ticket
