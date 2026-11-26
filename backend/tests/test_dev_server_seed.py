"""Semilla local de desarrollo: creación e idempotencia (HU-26, RF-167)."""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)
from dev_server import (
    SLA_DEMO_TICKETS,
    seed_sla_demo_client,
    seed_sla_demo_tickets,
)


def test_demo_client_seed_creates_and_reuses_the_client():
    users = InMemoryUserRepository()

    client = seed_sla_demo_client(
        users,
        name="Cliente Demo",
        email="cliente@helpdesk.dev",
        password="DemoPassword123",
    )
    original_password_hash = client.password_hash
    reused = seed_sla_demo_client(
        users,
        name="Otro nombre",
        email="CLIENTE@HELPDESK.DEV",
        password="OtroPassword123",
    )

    assert client.id == reused.id
    assert client.role == "cliente"
    assert users.count() == 1
    assert reused.name == "Cliente Demo"
    assert reused.email == "cliente@helpdesk.dev"
    assert reused.password_hash == original_password_hash
    assert users.find_by_id(client.id) is reused


def test_demo_ticket_seed_creates_realistic_repeatable_data():
    tickets = InMemoryTicketRepository()
    assignments = InMemoryAssignmentLog()
    reference = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    seed_args = {
        "requester_id": "22222222-2222-4222-8222-222222222222",
        "administrator_id": "33333333-3333-4333-8333-333333333333",
        "technician_id": "11111111-1111-4111-8111-111111111111",
        "technician_name": "Tecnico Demo",
        "tickets": tickets,
        "assignments": assignments,
    }

    created = seed_sla_demo_tickets(**seed_args, now=reference)
    seeded = tickets.list_by_requester(seed_args["requester_id"])
    assert len(seeded) == len(SLA_DEMO_TICKETS)
    assert seeded == sorted(
        created, key=lambda ticket: ticket.created_at, reverse=True
    )
    assert {ticket.status for ticket in seeded} == {
        OPEN_STATUS,
        IN_PROGRESS_STATUS,
        RESOLVED_STATUS,
    }
    assert sum(ticket.assignee_id is not None for ticket in seeded) == 3
    assert assignments.count() == 3

    # La semilla vigente crea tickets directamente, sin modificaciones HU-03.
    # Su auditoria de asignacion debe corresponder al ticket y al actor reales.
    for ticket in seeded:
        records = assignments.list_by_ticket(ticket.id)
        if ticket.assignee_id is None:
            assert ticket.assignee_name is None
            assert records == []
        else:
            assert ticket.assignee_id == seed_args["technician_id"]
            assert ticket.assignee_name == seed_args["technician_name"]
            assert len(records) == 1
            record = records[0]
            assert record.previous_assignee_id is None
            assert record.new_assignee_id == seed_args["technician_id"]
            assert record.actor_id == seed_args["administrator_id"]
            assert record.assigned_at == ticket.created_at + timedelta(minutes=1)

    original = [
        (ticket.id, ticket.created_at, ticket.assignee_id, ticket.assignee_name)
        for ticket in seeded
    ]
    original_assignments = {
        ticket.id: [
            (r.previous_assignee_id, r.new_assignee_id, r.actor_id, r.assigned_at)
            for r in assignments.list_by_ticket(ticket.id)
        ]
        for ticket in seeded
    }
    repeated = seed_sla_demo_tickets(
        **seed_args, now=reference + timedelta(days=1)
    )
    assert repeated == []
    assert [
        (ticket.id, ticket.created_at, ticket.assignee_id, ticket.assignee_name)
        for ticket in tickets.list_by_requester(seed_args["requester_id"])
    ] == original
    assert assignments.count() == 3
    assert {
        ticket.id: [
            (r.previous_assignee_id, r.new_assignee_id, r.actor_id, r.assigned_at)
            for r in assignments.list_by_ticket(ticket.id)
        ]
        for ticket in seeded
    } == original_assignments
