"""HU-09 T2 - resolucion autorizada del ticket para el historial (RF-84, RF-85)."""

import uuid
from datetime import datetime, timezone

import pytest

from app.modules.tickets.application.get_historyable_ticket import (
    get_historyable_ticket,
)
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import CLOSED_STATUS, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
CLIENT_ID = "u-client"


def _ticket(*, requester_id: str = CLIENT_ID, status: str = "Abierto") -> Ticket:
    return Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id=requester_id,
        created_at=NOW,
        status=status,
    )


def _repository(*tickets: Ticket) -> InMemoryTicketRepository:
    repository = InMemoryTicketRepository()
    for ticket in tickets:
        repository.add(ticket)
    return repository


def test_administrator_can_read_the_history_of_any_ticket():
    ticket = _ticket(requester_id="u-other")
    repository = _repository(ticket)

    resolved = get_historyable_ticket(
        ticket_id=ticket.id,
        actor_id="u-admin",
        actor_role="administrador",
        tickets=repository,
    )

    assert resolved is ticket


def test_technician_can_read_the_history_of_any_ticket():
    ticket = _ticket(requester_id="u-other")
    repository = _repository(ticket)

    resolved = get_historyable_ticket(
        ticket_id=ticket.id,
        actor_id="u-tech",
        actor_role="tecnico",
        tickets=repository,
    )

    assert resolved is ticket


def test_client_gets_the_uniform_404_even_for_their_own_ticket():
    ticket = _ticket(requester_id=CLIENT_ID)
    repository = _repository(ticket)

    with pytest.raises(TicketNotFoundError) as error:
        get_historyable_ticket(
            ticket_id=ticket.id,
            actor_id=CLIENT_ID,
            actor_role="cliente",
            tickets=repository,
        )

    assert str(error.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_gets_the_uniform_404_for_another_ticket():
    ticket = _ticket(requester_id="u-other")
    repository = _repository(ticket)

    with pytest.raises(TicketNotFoundError):
        get_historyable_ticket(
            ticket_id=ticket.id,
            actor_id=CLIENT_ID,
            actor_role="cliente",
            tickets=repository,
        )


@pytest.mark.parametrize("ticket_id", ["no-es-uuid", "", "t-1"])
def test_invalid_identifier_gets_the_uniform_404(ticket_id):
    repository = _repository(_ticket())

    with pytest.raises(TicketNotFoundError) as error:
        get_historyable_ticket(
            ticket_id=ticket_id,
            actor_id="u-tech",
            actor_role="tecnico",
            tickets=repository,
        )

    assert str(error.value) == TICKET_NOT_FOUND_MESSAGE


def test_unknown_ticket_gets_the_uniform_404():
    repository = _repository()

    with pytest.raises(TicketNotFoundError) as error:
        get_historyable_ticket(
            ticket_id=str(uuid.uuid4()),
            actor_id="u-tech",
            actor_role="tecnico",
            tickets=repository,
        )

    assert str(error.value) == TICKET_NOT_FOUND_MESSAGE


@pytest.mark.parametrize("role", ["cliente", "visitante", "", None])
def test_unknown_or_forbidden_role_gets_the_uniform_404(role):
    ticket = _ticket(requester_id=CLIENT_ID)
    repository = _repository(ticket)

    with pytest.raises(TicketNotFoundError):
        get_historyable_ticket(
            ticket_id=ticket.id,
            actor_id=CLIENT_ID,
            actor_role=role,
            tickets=repository,
        )


def test_closed_ticket_is_still_readable():
    ticket = _ticket(status=CLOSED_STATUS)
    repository = _repository(ticket)

    resolved = get_historyable_ticket(
        ticket_id=ticket.id,
        actor_id="u-tech",
        actor_role="tecnico",
        tickets=repository,
    )

    assert resolved is ticket
    assert resolved.status == CLOSED_STATUS
