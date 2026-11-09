"""Caso de uso de actualizacion de estado de un ticket (HU-03 y HU-08).

El ticket ya viene resuelto y autorizado por `get_modifiable_ticket`
(HU-03), que ademas rechaza los tickets `Cerrado` (RF-28/RF-75). Aqui se
valida el catalogo, se comprueba el flujo del ciclo de vida de HU-08, se
decide si hay cambio efectivo y, en tal caso, se muta el ticket y se
registra la modificacion.

Reglas:
- Valor fuera del catalogo o no textual -> `TicketValidationError`
  (RF-21, RF-29.1, RF-29.3), sin modificar ni registrar.
- Valor igual al estado vigente -> sin cambio y sin registro (HU-03,
  RF-74). En un ticket cerrado no se llega aqui: `get_modifiable_ticket`
  responde 409 antes (RF-75).
- Transicion fuera del flujo de `STATUS_TRANSITIONS` -> 
  `InvalidStatusTransitionError` (HU-08, RF-73), sin modificar ni
  registrar. Solo se evalua con un destino valido del catalogo.
- Cambio efectivo -> muta `Ticket.status` y anade un registro con el
  responsable de la sesion, la fecha/hora del sistema y los valores
  anterior y nuevo (RF-26, RF-72).
- Resolucion (HU-05, RF-46): al pasar a `Resuelto` o `Cerrado` se fija
  `resolved_at` con el mismo instante del registro; al volver a un estado
  no resuelto se descarta. `Resuelto` -> `Cerrado` conserva el instante
  original. Un cambio al mismo estado no toca `resolved_at`.
"""

from datetime import datetime, timezone

from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.domain.entities import (
    RESOLVED_STATUSES,
    STATUS_FIELD,
    Ticket,
    TicketModification,
    is_allowed_status_transition,
    validate_status,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)

# Mensaje unico del 409 de transicion no permitida (HU-08, RF-73): se
# distingue del 409 `ticket is closed` de HU-03.
INVALID_STATUS_TRANSITION_MESSAGE = "invalid status transition"


class InvalidStatusTransitionError(ValueError):
    """La transicion solicitada no pertenece al flujo del ciclo de vida."""


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
    registro. Si coincide con el estado vigente no hay cambio ni registro
    (RF-74). Lanza `InvalidStatusTransitionError` si el destino es valido
    pero no figura en el flujo de RF-71, sin tocar nada (RF-73). En un
    cambio efectivo muta el ticket y anade `TicketModification` con los
    valores anterior y nuevo, `actor_id` de la sesion y `changed_at` del
    sistema (RF-26, RF-72). El registro no forma parte del ticket devuelto.
    """
    try:
        new_status = validate_status(status)
    except ValueError as exc:
        if isinstance(exc, TicketValidationError):
            raise
        raise TicketValidationError(str(exc)) from exc

    if ticket.status == new_status:
        return ticket

    if not is_allowed_status_transition(ticket.status, new_status):
        raise InvalidStatusTransitionError(INVALID_STATUS_TRANSITION_MESSAGE)

    changed_at = now if now is not None else datetime.now(timezone.utc)
    previous_status = ticket.status
    ticket.status = new_status
    if new_status in RESOLVED_STATUSES:
        # `Resuelto` -> `Cerrado` conserva la resolucion original; el
        # primer paso a un estado resuelto fija el instante (RF-46).
        if ticket.resolved_at is None:
            ticket.resolved_at = changed_at
    else:
        # Reapertura antes del cierre: el SLA vuelve a evolucionar desde
        # la creacion.
        ticket.resolved_at = None
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value=previous_status,
            new_value=new_status,
            actor_id=actor_id,
            changed_at=changed_at,
        )
    )
    return ticket
