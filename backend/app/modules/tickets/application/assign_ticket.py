"""Caso de uso de asignacion y reasignacion de un ticket (RF-32, RF-33, RF-37).

El ticket ya viene resuelto y autorizado por `get_assignable_ticket`
(T5), que ademas rechaza los tickets `Cerrado` con 409 (RF-39.4). Aqui
solo se valida el tecnico solicitado, se decide si hay cambio efectivo y,
en tal caso, se muta el ticket y se registra la asignacion.

Reglas:
- El identificador del tecnico debe tener formato UUID y corresponder a
  un usuario existente con rol `tecnico`, resuelto por el colaborador
  inyectado (`resolve_technician`), nunca por las estructuras internas de
  `identity` (D10, RF-39.3). Cualquier fallo produce el mismo
  `TicketValidationError` (`assignee is not a valid technician`): no se
  distingue entre no UUID, inexistente, cliente o administrador, ni se
  revela si el usuario existe (RF-39.3).
- Repetir el tecnico vigente en un ticket no cerrado no cambia nada ni
  registra (RF-33, RF-37); solo los cambios efectivos se registran.
- Cambio efectivo: fija `assignee_id` y `assignee_name` con la vista
  resuelta (proyeccion del nombre, D8) y anade un `AssignmentRecord` con
  el tecnico anterior (`None` en la primera), el nuevo, el `actor_id` de
  la sesion y la fecha/hora del sistema (RF-37). El registro no forma
  parte del ticket devuelto.
- No modifica prioridad, estado, fecha de creacion ni solicitante
  (RF-32, RF-33).
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.domain.entities import (
    AssignmentRecord,
    Ticket,
    is_valid_uuid_format,
)
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
)

# Mensaje unico del 422 de tecnico invalido (contrato del plan, seccion 2):
# no distingue entre no UUID, inexistente, cliente o administrador.
INVALID_TECHNICIAN_MESSAGE = "assignee is not a valid technician"


class _TechnicianView(Protocol):
    """Vista minima del tecnico resuelto por el contrato de `identity`."""

    id: str
    name: str


def assign_ticket(
    ticket: Ticket,
    technician_id: object,
    actor_id: str,
    resolve_technician: Callable[[object], _TechnicianView | None],
    assignments: InMemoryAssignmentLog,
    now: datetime | None = None,
) -> Ticket:
    """Asigna o reasigna el tecnico del ticket resuelto y lo devuelve.

    Lanza `TicketValidationError` con `INVALID_TECHNICIAN_MESSAGE` si el
    identificador no tiene formato UUID o el contrato de `identity` no lo
    resuelve como tecnico existente (RF-39.3), sin tocar el ticket ni el
    registro. Si coincide con el tecnico vigente no hay cambio ni registro
    (RF-33). En un cambio efectivo muta `assignee_id`/`assignee_name` y
    anade `AssignmentRecord` con el anterior, el nuevo, `actor_id` de la
    sesion y `assigned_at` del sistema (RF-32, RF-33, RF-37). El registro
    no forma parte del ticket devuelto.
    """
    if not is_valid_uuid_format(technician_id):
        raise TicketValidationError(INVALID_TECHNICIAN_MESSAGE)

    technician = resolve_technician(technician_id)
    if technician is None:
        raise TicketValidationError(INVALID_TECHNICIAN_MESSAGE)

    if ticket.assignee_id == technician.id:
        return ticket

    previous_assignee_id = ticket.assignee_id
    ticket.assignee_id = technician.id
    ticket.assignee_name = technician.name
    assignments.add(
        AssignmentRecord(
            ticket_id=ticket.id,
            previous_assignee_id=previous_assignee_id,
            new_assignee_id=technician.id,
            actor_id=actor_id,
            assigned_at=now if now is not None else datetime.now(timezone.utc),
        )
    )
    return ticket
