"""HU-09 T3 - caso de uso y orden determinista del historial (RF-82, RF-86, RF-87)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.tickets.application.get_ticket import TicketNotFoundError
from app.modules.tickets.application.list_ticket_history import (
    list_ticket_history,
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
    AssignmentRecord,
    Ticket,
    TicketComment,
    TicketModification,
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

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
CLIENT_ID = "u-client"


def _ticket(*, status: str = "Abierto") -> Ticket:
    return Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id=CLIENT_ID,
        created_at=NOW,
        status=status,
    )


def _repository(ticket: Ticket) -> InMemoryTicketRepository:
    repository = InMemoryTicketRepository()
    repository.add(ticket)
    return repository


def _history(ticket, *, modifications, assignments, comments, role="tecnico"):
    return list_ticket_history(
        ticket_id=ticket.id,
        actor_id="u-tech",
        actor_role=role,
        tickets=_repository(ticket),
        modifications=modifications,
        assignments=assignments,
        comments=comments,
    )


def test_creation_is_the_first_event_of_a_new_ticket():
    ticket = _ticket()

    events = _history(
        ticket,
        modifications=InMemoryTicketModificationLog(),
        assignments=InMemoryAssignmentLog(),
        comments=InMemoryTicketCommentRepository(),
    )

    assert [(event.action, event.actor_id, event.occurred_at) for event in events] == [
        (HISTORY_ACTION_CREATED, CLIENT_ID, NOW)
    ]


def test_all_sources_are_mapped_to_their_actions_and_values():
    ticket = _ticket()
    modifications = InMemoryTicketModificationLog()
    assignments = InMemoryAssignmentLog()
    comments = InMemoryTicketCommentRepository()

    assignments.add(
        AssignmentRecord(
            ticket_id=ticket.id,
            previous_assignee_id=None,
            new_assignee_id="u-tech-1",
            actor_id="u-admin",
            assigned_at=NOW + timedelta(minutes=1),
        )
    )
    assignments.add(
        AssignmentRecord(
            ticket_id=ticket.id,
            previous_assignee_id="u-tech-1",
            new_assignee_id="u-tech-2",
            actor_id="u-admin",
            assigned_at=NOW + timedelta(minutes=2),
        )
    )
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=PRIORITY_FIELD,
            previous_value=None,
            new_value="Alta",
            actor_id="u-tech-1",
            changed_at=NOW + timedelta(minutes=3),
        )
    )
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value="Abierto",
            new_value="En progreso",
            actor_id="u-tech-1",
            changed_at=NOW + timedelta(minutes=4),
        )
    )
    comments.add(
        TicketComment(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            author_id="u-admin",
            body="Revisando el caso",
            created_at=NOW + timedelta(minutes=5),
        )
    )

    events = _history(
        ticket,
        modifications=modifications,
        assignments=assignments,
        comments=comments,
    )

    assert [event.action for event in events] == [
        HISTORY_ACTION_CREATED,
        HISTORY_ACTION_ASSIGNED,
        HISTORY_ACTION_REASSIGNED,
        HISTORY_ACTION_PRIORITY,
        HISTORY_ACTION_STATUS,
        HISTORY_ACTION_COMMENT,
    ]
    assert events[1].previous_assignee_id is None
    assert events[1].new_assignee_id == "u-tech-1"
    assert events[2].previous_assignee_id == "u-tech-1"
    assert events[2].new_assignee_id == "u-tech-2"
    assert events[3].previous_value is None
    assert events[3].new_value == "Alta"
    assert events[4].previous_value == "Abierto"
    assert events[4].new_value == "En progreso"
    assert events[5].comment == "Revisando el caso"
    assert events[0].actor_id == CLIENT_ID
    assert [event.actor_id for event in events[1:]] == [
        "u-admin",
        "u-admin",
        "u-tech-1",
        "u-tech-1",
        "u-admin",
    ]


def test_equal_timestamps_follow_the_documented_source_order():
    ticket = _ticket()
    modifications = InMemoryTicketModificationLog()
    assignments = InMemoryAssignmentLog()
    comments = InMemoryTicketCommentRepository()

    # Se registran en orden inverso al esperado para comprobar que el orden
    # no depende del orden de alta entre fuentes.
    comments.add(
        TicketComment(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            author_id="u-tech",
            body="Comentario",
            created_at=NOW,
        )
    )
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value="Abierto",
            new_value="En progreso",
            actor_id="u-tech",
            changed_at=NOW,
        )
    )
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=PRIORITY_FIELD,
            previous_value=None,
            new_value="Alta",
            actor_id="u-tech",
            changed_at=NOW,
        )
    )
    assignments.add(
        AssignmentRecord(
            ticket_id=ticket.id,
            previous_assignee_id=None,
            new_assignee_id="u-tech",
            actor_id="u-admin",
            assigned_at=NOW,
        )
    )

    events = _history(
        ticket,
        modifications=modifications,
        assignments=assignments,
        comments=comments,
    )

    assert [event.action for event in events] == [
        HISTORY_ACTION_CREATED,
        HISTORY_ACTION_ASSIGNED,
        HISTORY_ACTION_PRIORITY,
        HISTORY_ACTION_STATUS,
        HISTORY_ACTION_COMMENT,
    ]


def test_equal_timestamps_within_one_source_keep_registration_order():
    ticket = _ticket()
    modifications = InMemoryTicketModificationLog()

    for previous, new in (("Alta", "Media"), ("Media", "Baja")):
        modifications.add(
            TicketModification(
                ticket_id=ticket.id,
                field=PRIORITY_FIELD,
                previous_value=previous,
                new_value=new,
                actor_id="u-tech",
                changed_at=NOW,
            )
        )

    events = _history(
        ticket,
        modifications=modifications,
        assignments=InMemoryAssignmentLog(),
        comments=InMemoryTicketCommentRepository(),
    )

    assert [event.new_value for event in events[1:]] == ["Media", "Baja"]


def test_the_same_state_returns_the_same_order():
    ticket = _ticket()
    modifications = InMemoryTicketModificationLog()
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value="Abierto",
            new_value="En progreso",
            actor_id="u-tech",
            changed_at=NOW,
        )
    )
    deps = dict(
        modifications=modifications,
        assignments=InMemoryAssignmentLog(),
        comments=InMemoryTicketCommentRepository(),
    )

    first = _history(ticket, **deps)
    second = _history(ticket, **deps)

    assert [event.action for event in first] == [
        event.action for event in second
    ]


def test_events_of_other_tickets_are_not_included():
    ticket = _ticket()
    other = _ticket()
    modifications = InMemoryTicketModificationLog()
    modifications.add(
        TicketModification(
            ticket_id=other.id,
            field=PRIORITY_FIELD,
            previous_value=None,
            new_value="Alta",
            actor_id="u-tech",
            changed_at=NOW,
        )
    )

    events = _history(
        ticket,
        modifications=modifications,
        assignments=InMemoryAssignmentLog(),
        comments=InMemoryTicketCommentRepository(),
    )

    assert [event.action for event in events] == [HISTORY_ACTION_CREATED]


def test_unknown_ticket_raises_the_uniform_not_found():
    ticket = _ticket()

    with pytest.raises(TicketNotFoundError):
        list_ticket_history(
            ticket_id=str(uuid.uuid4()),
            actor_id="u-tech",
            actor_role="tecnico",
            tickets=_repository(ticket),
            modifications=InMemoryTicketModificationLog(),
            assignments=InMemoryAssignmentLog(),
            comments=InMemoryTicketCommentRepository(),
        )


def test_client_cannot_read_the_history():
    ticket = _ticket()

    with pytest.raises(TicketNotFoundError):
        _history(
            ticket,
            modifications=InMemoryTicketModificationLog(),
            assignments=InMemoryAssignmentLog(),
            comments=InMemoryTicketCommentRepository(),
            role="cliente",
        )
