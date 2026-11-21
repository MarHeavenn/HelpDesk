"""Agregado del dashboard de tickets (RF-82 a RF-90).

El calculo vive en el modulo `tickets`: recibe una instantanea del
repositorio y, para el tecnico, la filtra por responsable. No escribe ni
muta tickets y no consulta las tablas internas de `identity`: los
tecnicos con cero tickets llegan como `TechnicianRef` desde su contrato.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.modules.tickets.domain.entities import (
    PRIORITIES,
    STATUSES,
    Ticket,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

ADMIN_ROLE = "administrador"
SUPERVISOR_ROLE = "supervisor"
TECHNICIAN_ROLE = "tecnico"
MANAGEMENT_ROLES = frozenset({ADMIN_ROLE, SUPERVISOR_ROLE, TECHNICIAN_ROLE})
DENIED_MESSAGE = "tickets not found"
UNASSIGNED_LABEL = "Sin asignar"
NO_PRIORITY_LABEL = "Sin prioridad"
RECENT_LIMIT = 5


class DashboardAccessDeniedError(ValueError):
    """El rol del actor no puede consultar el dashboard (-> 404)."""


@dataclass(frozen=True)
class TechnicianRef:
    """Vista minima de un tecnico: identificador y nombre."""

    id: str
    name: str


@dataclass(frozen=True)
class StatusCount:
    status: str
    count: int


@dataclass(frozen=True)
class PriorityCount:
    priority: str | None
    label: str
    count: int


@dataclass(frozen=True)
class AssigneeCount:
    technician: TechnicianRef | None
    label: str
    count: int


@dataclass(frozen=True)
class RecentTicket:
    id: str
    title: str
    priority: str | None
    status: str
    assignee: TechnicianRef | None
    created_at: datetime


@dataclass(frozen=True)
class TicketDashboard:
    total_tickets: int
    by_status: list[StatusCount]
    by_priority: list[PriorityCount]
    by_assignee: list[AssigneeCount]
    recent_tickets: list[RecentTicket]
    generated_at: datetime


def _assignee_ref(ticket: Ticket) -> TechnicianRef | None:
    """Tecnico responsable o None; nunca inventa un nombre incompleto."""
    if ticket.assignee_id is None or ticket.assignee_name is None:
        return None
    return TechnicianRef(id=ticket.assignee_id, name=ticket.assignee_name)


def get_ticket_dashboard(
    *,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
    technicians: Sequence[TechnicianRef] = (),
    company_id: str | None = None,
    now: datetime | None = None,
) -> TicketDashboard:
    """Construye el resumen agregado del alcance del actor.

    Administrador: todos los tickets. Tecnico: solo los asignados a el.
    Cualquier otro rol lanza `DashboardAccessDeniedError` (RF-81). Todos
    los conteos se derivan de la misma instantanea en una sola pasada
    (RF-89) y el tecnico conserva su entrada con cero tickets (RF-87).
    """
    if actor_role not in MANAGEMENT_ROLES:
        raise DashboardAccessDeniedError(DENIED_MESSAGE)

    generated_at = now or datetime.now(timezone.utc)
    snapshot = tickets.list_all()
    if company_id is not None:
        snapshot = [
            ticket for ticket in snapshot if ticket.company_id == company_id
        ]
    if actor_role == TECHNICIAN_ROLE:
        snapshot = [
            ticket for ticket in snapshot if ticket.assignee_id == actor_id
        ]

    status_counts = {status: 0 for status in STATUSES}
    priority_counts: dict[str | None, int] = {
        priority: 0 for priority in PRIORITIES
    }
    priority_counts[None] = 0

    technician_counts: dict[str, int] = {}
    technician_names: dict[str, str] = {}
    for technician in technicians:
        technician_counts[technician.id] = 0
        technician_names[technician.id] = technician.name
    unassigned_count = 0

    for ticket in snapshot:
        status_counts[ticket.status] = status_counts.get(ticket.status, 0) + 1
        priority_counts[ticket.priority] = (
            priority_counts.get(ticket.priority, 0) + 1
        )
        if ticket.assignee_id is None:
            unassigned_count += 1
        else:
            technician_counts[ticket.assignee_id] = (
                technician_counts.get(ticket.assignee_id, 0) + 1
            )
            if ticket.assignee_id not in technician_names:
                technician_names[ticket.assignee_id] = (
                    ticket.assignee_name or ticket.assignee_id
                )

    by_status = [
        StatusCount(status=status, count=status_counts[status])
        for status in STATUSES
    ]

    by_priority = [
        PriorityCount(
            priority=priority,
            label=priority if priority is not None else NO_PRIORITY_LABEL,
            count=priority_counts[priority],
        )
        for priority in (*PRIORITIES, None)
    ]

    by_assignee = [
        AssigneeCount(
            technician=None,
            label=UNASSIGNED_LABEL,
            count=unassigned_count,
        )
    ]
    for technician_id in sorted(
        technician_counts, key=lambda item: technician_names[item]
    ):
        by_assignee.append(
            AssigneeCount(
                technician=TechnicianRef(
                    id=technician_id, name=technician_names[technician_id]
                ),
                label=technician_names[technician_id],
                count=technician_counts[technician_id],
            )
        )

    recent = sorted(
        snapshot, key=lambda ticket: ticket.created_at, reverse=True
    )[:RECENT_LIMIT]
    recent_tickets = [
        RecentTicket(
            id=ticket.id,
            title=ticket.title,
            priority=ticket.priority,
            status=ticket.status,
            assignee=_assignee_ref(ticket),
            created_at=ticket.created_at,
        )
        for ticket in recent
    ]

    return TicketDashboard(
        total_tickets=len(snapshot),
        by_status=by_status,
        by_priority=by_priority,
        by_assignee=by_assignee,
        recent_tickets=recent_tickets,
        generated_at=generated_at,
    )
