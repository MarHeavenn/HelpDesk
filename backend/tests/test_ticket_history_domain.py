"""HU-09 T1 - modelo de evento y acciones del historial (RF-82, RF-83)."""

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from app.modules.tickets.domain.entities import (
    HISTORY_ACTION_ASSIGNED,
    HISTORY_ACTION_COMMENT,
    HISTORY_ACTION_CREATED,
    HISTORY_ACTION_PRIORITY,
    HISTORY_ACTION_REASSIGNED,
    HISTORY_ACTION_STATUS,
    TicketHistoryEvent,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def test_action_constants_have_the_documented_values():
    assert HISTORY_ACTION_CREATED == "ticket_created"
    assert HISTORY_ACTION_ASSIGNED == "technician_assigned"
    assert HISTORY_ACTION_REASSIGNED == "technician_reassigned"
    assert HISTORY_ACTION_PRIORITY == "priority_changed"
    assert HISTORY_ACTION_STATUS == "status_changed"
    assert HISTORY_ACTION_COMMENT == "comment_added"


def test_creation_event_has_no_previous_or_new_values():
    event = TicketHistoryEvent(
        action=HISTORY_ACTION_CREATED,
        actor_id="u-client",
        occurred_at=NOW,
    )

    assert event.action == "ticket_created"
    assert event.actor_id == "u-client"
    assert event.occurred_at == NOW
    assert event.previous_value is None
    assert event.new_value is None
    assert event.previous_assignee_id is None
    assert event.new_assignee_id is None
    assert event.comment is None


def test_assignment_event_keeps_previous_and_new_technician_ids():
    event = TicketHistoryEvent(
        action=HISTORY_ACTION_REASSIGNED,
        actor_id="u-admin",
        occurred_at=NOW,
        previous_assignee_id="u-tech-1",
        new_assignee_id="u-tech-2",
    )

    assert event.previous_assignee_id == "u-tech-1"
    assert event.new_assignee_id == "u-tech-2"


def test_comment_event_keeps_the_body():
    event = TicketHistoryEvent(
        action=HISTORY_ACTION_COMMENT,
        actor_id="u-tech",
        occurred_at=NOW,
        comment="Revisando el caso",
    )

    assert event.comment == "Revisando el caso"


def test_event_has_exactly_the_documented_fields():
    assert [field.name for field in fields(TicketHistoryEvent)] == [
        "action",
        "actor_id",
        "occurred_at",
        "previous_value",
        "new_value",
        "previous_assignee_id",
        "new_assignee_id",
        "comment",
    ]


def test_event_is_immutable():
    event = TicketHistoryEvent(
        action=HISTORY_ACTION_PRIORITY,
        actor_id="u-tech",
        occurred_at=NOW,
        new_value="Alta",
    )

    with pytest.raises(FrozenInstanceError):
        event.new_value = "Baja"  # type: ignore[misc]
