import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.identity.application.technicians import TechnicianSummary
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)
from app.modules.tickets.domain.entities import (
    IN_PROGRESS_STATUS,
    OPEN_STATUS,
    RESOLVED_STATUS,
)
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)
from dev_server import (
    DEMO_TICKETS,
    seed_demo_client,
    seed_demo_tickets,
)


def test_demo_client_seed_creates_and_reuses_the_client():
    users = InMemoryUserRepository()

    client = seed_demo_client(
        users,
        name="Cliente Demo",
        email="cliente@helpdesk.dev",
        password="DemoPassword123",
    )
    reused = seed_demo_client(
        users,
        name="Otro nombre",
        email="CLIENTE@HELPDESK.DEV",
        password="OtroPassword123",
    )

    assert client.id == reused.id
    assert client.role == "cliente"
    assert users.count() == 1


def test_demo_ticket_seed_creates_realistic_repeatable_data():
    tickets = InMemoryTicketRepository()
    modifications = InMemoryTicketModificationLog()
    assignments = InMemoryAssignmentLog()
    technician = TechnicianSummary(
        id="11111111-1111-4111-8111-111111111111",
        name="Tecnico Demo",
    )
    resolve_technician = (
        lambda candidate: technician if candidate == technician.id else None
    )
    seed_args = {
        "requester_id": "22222222-2222-4222-8222-222222222222",
        "administrator_id": "33333333-3333-4333-8333-333333333333",
        "technician_id": technician.id,
        "tickets": tickets,
        "modifications": modifications,
        "assignments": assignments,
        "resolve_technician": resolve_technician,
    }

    seed_demo_tickets(**seed_args)
    seed_demo_tickets(**seed_args)

    seeded = tickets.list_by_requester(seed_args["requester_id"])
    assert len(seeded) == len(DEMO_TICKETS)
    assert {ticket.status for ticket in seeded} == {
        OPEN_STATUS,
        IN_PROGRESS_STATUS,
        RESOLVED_STATUS,
    }
    assert sum(ticket.assignee_id is not None for ticket in seeded) == 3
    assert modifications.count() == 7
    assert assignments.count() == 3
