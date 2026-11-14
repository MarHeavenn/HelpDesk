"""Caso de uso del historial cronologico de un ticket (HU-09).

El historial es una vista de lectura derivada: no crea ni persiste eventos
nuevos. Reune la creacion del ticket (HU-02), las asignaciones (HU-04), las
modificaciones de prioridad y estado (HU-03 y HU-08) y los comentarios de
seguimiento (HU-07), y los devuelve en orden ascendente y determinista.

Reglas:
- La visibilidad y el 404 uniforme se resuelven en `get_historyable_ticket`
  (solo `tecnico` y `administrador`; ticket cerrado legible).
- Solo se incluyen eventos efectivos: los registros de origen ya excluyen
  no-ops y operaciones rechazadas, y este caso de uso no inventa eventos.
- El orden es `(occurred_at, source_rank, insertion_index)`, con creacion=0,
  asignacion=1, prioridad=2, estado=3 y comentario=4. Dentro de una fuente
  se conserva el orden de alta (RF-86).
- La consulta no muta el ticket ni ninguno de los registros.
"""

from datetime import datetime

from app.modules.tickets.application.get_historyable_ticket import (
    get_historyable_ticket,
)
from app.modules.tickets.domain.entities import (
    HISTORY_ACTION_ASSIGNED,
    HISTORY_ACTION_COMMENT,
    HISTORY_ACTION_CREATED,
    HISTORY_ACTION_PRIORITY,
    HISTORY_ACTION_REASSIGNED,
    HISTORY_ACTION_STATUS,
    PRIORITY_FIELD,
    STATUS_FIELD,
    TicketHistoryEvent,
)
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    InMemoryTicketCommentRepository,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

# Rango de cada fuente para desempatar eventos con la misma fecha y hora.
_SOURCE_CREATED = 0
_SOURCE_ASSIGNMENT = 1
_SOURCE_PRIORITY = 2
_SOURCE_STATUS = 3
_SOURCE_COMMENT = 4


def list_ticket_history(
    ticket_id: str,
    actor_id: str,
    actor_role: str,
    tickets: InMemoryTicketRepository,
    modifications: InMemoryTicketModificationLog,
    assignments: InMemoryAssignmentLog,
    comments: InMemoryTicketCommentRepository,
    actor_company_id: str | None = None,
) -> list[TicketHistoryEvent]:
    """Devuelve el historial visible del ticket, del mas antiguo al mas nuevo.

    Lanza `TicketNotFoundError` (404 uniforme) si el rol no es de gestion,
    el identificador no tiene formato valido o el ticket no existe. No
    comprueba el estado: un ticket cerrado conserva su historial (RF-85).
    """
    ticket = get_historyable_ticket(
        ticket_id=ticket_id,
        actor_id=actor_id,
        actor_role=actor_role,
        tickets=tickets,
        actor_company_id=actor_company_id,
    )

    # (fecha, rango de fuente, indice de alta, evento)
    ordered: list[tuple[datetime, int, int, TicketHistoryEvent]] = []

    ordered.append(
        (
            ticket.created_at,
            _SOURCE_CREATED,
            0,
            TicketHistoryEvent(
                action=HISTORY_ACTION_CREATED,
                actor_id=ticket.requester_id,
                occurred_at=ticket.created_at,
            ),
        )
    )

    for index, assignment in enumerate(assignments.list_by_ticket(ticket.id)):
        action = (
            HISTORY_ACTION_ASSIGNED
            if assignment.previous_assignee_id is None
            else HISTORY_ACTION_REASSIGNED
        )
        ordered.append(
            (
                assignment.assigned_at,
                _SOURCE_ASSIGNMENT,
                index,
                TicketHistoryEvent(
                    action=action,
                    actor_id=assignment.actor_id,
                    occurred_at=assignment.assigned_at,
                    previous_assignee_id=assignment.previous_assignee_id,
                    new_assignee_id=assignment.new_assignee_id,
                ),
            )
        )

    for index, modification in enumerate(modifications.list_by_ticket(ticket.id)):
        if modification.field == PRIORITY_FIELD:
            action = HISTORY_ACTION_PRIORITY
            rank = _SOURCE_PRIORITY
        elif modification.field == STATUS_FIELD:
            action = HISTORY_ACTION_STATUS
            rank = _SOURCE_STATUS
        else:
            # El registro solo admite prioridad y estado (HU-03). Un valor
            # desconocido no se proyecta para no inventar acciones.
            continue
        ordered.append(
            (
                modification.changed_at,
                rank,
                index,
                TicketHistoryEvent(
                    action=action,
                    actor_id=modification.actor_id,
                    occurred_at=modification.changed_at,
                    previous_value=modification.previous_value,
                    new_value=modification.new_value,
                ),
            )
        )

    for index, comment in enumerate(comments.list_by_ticket(ticket.id)):
        ordered.append(
            (
                comment.created_at,
                _SOURCE_COMMENT,
                index,
                TicketHistoryEvent(
                    action=HISTORY_ACTION_COMMENT,
                    actor_id=comment.author_id,
                    occurred_at=comment.created_at,
                    comment=comment.body,
                ),
            )
        )

    ordered.sort(key=lambda item: (item[0], item[1], item[2]))
    return [event for _, _, _, event in ordered]
