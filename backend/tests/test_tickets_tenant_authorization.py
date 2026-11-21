from datetime import datetime, timezone

import pytest

from app.modules.tickets.application.get_modifiable_ticket import (
    get_modifiable_ticket,
)
from app.modules.tickets.application.get_ticket import get_ticket_detail
from app.modules.tickets.application.list_tickets import list_visible_tickets
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


COMPANY_A = "company-a"
COMPANY_B = "company-b"
ACTOR = "actor-a"
OTHER_ACTOR = "actor-b"
ASSIGNEE = "tech-a"


def _ticket(company_id: str, *, requester_id: str = OTHER_ACTOR, assignee_id: str | None = None) -> Ticket:
    return Ticket(
        id=(
            "00000000-0000-0000-0000-000000000001"
            if company_id == COMPANY_A and assignee_id == ACTOR
            else "00000000-0000-0000-0000-000000000002"
            if company_id == COMPANY_A
            else "00000000-0000-0000-0000-000000000003"
        ),
        title="Ticket",
        description="Description",
        requester_id=requester_id,
        created_at=datetime.now(timezone.utc),
        company_id=company_id,
        assignee_id=assignee_id,
    )


def test_ticket_company_is_authoritative_for_reading_even_with_cross_tenant_requester():
    tickets = InMemoryTicketRepository()
    ticket = _ticket(COMPANY_B, requester_id=ACTOR, assignee_id=ASSIGNEE)
    tickets.add(ticket)

    with pytest.raises(ValueError, match="ticket not found"):
        get_ticket_detail(ticket.id, ACTOR, "administrador", tickets, COMPANY_A)


@pytest.mark.parametrize("role", ["administrador", "supervisor"])
def test_admin_and_supervisor_read_any_ticket_in_their_tenant(role):
    tickets = InMemoryTicketRepository()
    ticket = _ticket(COMPANY_A)
    tickets.add(ticket)

    assert get_ticket_detail(ticket.id, ACTOR, role, tickets, COMPANY_A) is ticket


def test_technician_reads_cross_tenant_ticket_but_modifies_only_assigned_ticket():
    tickets = InMemoryTicketRepository()
    assigned = _ticket(COMPANY_A, assignee_id=ACTOR)
    unassigned = _ticket(COMPANY_A, assignee_id=ASSIGNEE)
    tickets.add(assigned)
    tickets.add(unassigned)

    assert get_ticket_detail(unassigned.id, ACTOR, "tecnico", tickets, COMPANY_A)
    assert get_modifiable_ticket(
        assigned.id, "tecnico", tickets, COMPANY_A, ACTOR
    ) is assigned
    with pytest.raises(ValueError, match="ticket not found"):
        get_modifiable_ticket(unassigned.id, "tecnico", tickets, COMPANY_A, ACTOR)


def test_client_lists_only_own_tenant_tickets_and_account_without_company_is_hidden():
    tickets = InMemoryTicketRepository()
    own = _ticket(COMPANY_A, requester_id=ACTOR)
    foreign_requester = _ticket(COMPANY_B, requester_id=ACTOR)
    tickets.add(own)
    tickets.add(foreign_requester)

    assert list_visible_tickets(ACTOR, "cliente", COMPANY_A, tickets) == [own]
    assert list_visible_tickets(ACTOR, "cliente", None, tickets) == []
