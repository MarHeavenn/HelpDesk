"""T6 - Semilla de demostracion de HU-16 en `dev_server`."""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)
from app.infrastructure.db import postgres_configured
from app.modules.sla.domain.entities import (
    SLA_AT_RISK,
    SLA_BREACHED,
    SLA_MET,
    TicketSlaSnapshot,
)
from app.modules.sla.interface.contract import get_ticket_sla
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
    seed_demo_users,
    seed_sla_demo_client,
    seed_sla_demo_tickets,
)


@pytest.mark.skipif(not postgres_configured(), reason="requiere PostgreSQL")
def test_existing_persistent_demo_users_are_loaded_without_changing_passwords():
    users, client, _, _, _ = _seed()
    original = {user.role: user for user in users.list_all()}
    fresh = InMemoryUserRepository()
    seeded = seed_demo_users(
        fresh,
        admin_name="Otro nombre",
        admin_email=original["administrador"].email,
        admin_password="OtraClave123",
        tech_name="Otro técnico",
        tech_email=original["tecnico"].email,
        tech_password="OtraClave123",
    )
    reused_client = seed_sla_demo_client(
        fresh, name="Otro cliente", email=client.email, password="OtraClave123"
    )
    for role, user in seeded.items():
        assert user.id == original[role].id
        assert user.password_hash == original[role].password_hash
        assert fresh.find_by_id(user.id) is user
    assert reused_client.id == client.id
    assert reused_client.password_hash == client.password_hash
    assert fresh.find_by_id(client.id) is reused_client


def _seed():
    users = InMemoryUserRepository()
    seeded = seed_demo_users(
        users,
        admin_name="Administrador Local",
        admin_email="admin@helpdesk.dev",
        admin_password="DemoPassword123",
        tech_name="Tecnico Local",
        tech_email="tecnico@helpdesk.dev",
        tech_password="DemoPassword123",
    )
    client = seed_sla_demo_client(
        users,
        name="Cliente Local",
        email="cliente@helpdesk.dev",
        password="DemoPassword123",
    )
    tickets = InMemoryTicketRepository()
    assignments = InMemoryAssignmentLog()
    created = seed_sla_demo_tickets(
        requester_id=client.id,
        administrator_id=seeded["administrador"].id,
        technician_id=seeded["tecnico"].id,
        technician_name=seeded["tecnico"].name,
        tickets=tickets,
        assignments=assignments,
    )
    return users, client, tickets, assignments, created


def test_demo_seed_is_idempotent_and_builds_the_expected_tickets():
    users, client, tickets, assignments, created = _seed()

    assert len(created) == len(SLA_DEMO_TICKETS)
    assert {ticket.status for ticket in created} == {
        OPEN_STATUS,
        IN_PROGRESS_STATUS,
        RESOLVED_STATUS,
    }
    assert sum(ticket.assignee_id is not None for ticket in created) == 3
    assert assignments.count() == 3

    repeated = seed_sla_demo_tickets(
        requester_id=client.id,
        administrator_id=client.id,
        technician_id=client.id,
        technician_name=client.name,
        tickets=tickets,
        assignments=assignments,
    )
    assert repeated == []
    assert len(tickets.list_by_requester(client.id)) == len(SLA_DEMO_TICKETS)
    assert users.count() == 3


def test_demo_tickets_cover_near_due_breached_on_time_and_resolved():
    _, _, _, _, created = _seed()
    reference = datetime.now(timezone.utc)

    states = {}
    for ticket in created:
        sla = get_ticket_sla(
            TicketSlaSnapshot(
                ticket.priority,
                ticket.created_at,
                ticket.resolved_at,
                ticket.resolved_target_minutes,
            ),
            reference,
        )
        states[ticket.title] = None if sla is None else sla.status

    assert states["Correo corporativo no sincroniza"] == SLA_AT_RISK
    assert states["Factura de octubre no se genera"] == SLA_BREACHED
    assert states["Solicitud de acceso a reportes"] != SLA_AT_RISK
    assert states["Solicitud de acceso a reportes"] != SLA_BREACHED
    assert states["Impresora del piso 3 sin conexion"] == SLA_MET
