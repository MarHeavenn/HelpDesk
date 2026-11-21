"""Frontera de lectura de `tickets` hacia el dashboard de SLA (HU-12, RF-100).

El dashboard de SLA vive en el modulo `sla` y necesita una vista minima de
los tickets para agregar su cumplimiento. Este contrato evita que `sla`
importe el repositorio, el dominio o las tablas internas de `tickets`:
expone solo los campos que el calculo agregado necesita y una instantanea
de solo lectura.

Reglas:
- No expone titulo, descripcion, solicitante, correo ni credenciales.
- `is_resolved` se deriva del estado del ticket con el catalogo de
  `tickets`; el modulo `sla` no necesita conocer los nombres de estado.
- `resolved_target_minutes` es el objetivo congelado al resolver
  (HU-14, RF-76); puede ser `None` en tickets antiguos.
"""

from dataclasses import dataclass
from datetime import datetime

from app.modules.tickets.domain.entities import RESOLVED_STATUSES
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)


@dataclass(frozen=True)
class SlaTicketView:
    """Vista minima de un ticket para el dashboard de SLA."""

    id: str
    priority: str | None
    status: str
    is_resolved: bool
    created_at: datetime
    resolved_at: datetime | None
    resolved_target_minutes: int | None
    assignee_id: str | None
    company_id: str | None = None


def list_sla_tickets(
    tickets: InMemoryTicketRepository | None = None,
) -> list[SlaTicketView]:
    """Devuelve una instantanea de solo lectura de todos los tickets.

    `tickets` permite inyectar el repositorio en pruebas; si falta, se usa
    el singleton compartido. No muta ni ordena el repositorio.
    """
    repository = tickets if tickets is not None else get_ticket_repository()
    return [
        SlaTicketView(
            id=ticket.id,
            priority=ticket.priority,
            status=ticket.status,
            is_resolved=ticket.status in RESOLVED_STATUSES,
            created_at=ticket.created_at,
            resolved_at=ticket.resolved_at,
            resolved_target_minutes=ticket.resolved_target_minutes,
            assignee_id=ticket.assignee_id,
            company_id=ticket.company_id,
        )
        for ticket in repository.list_all()
    ]
