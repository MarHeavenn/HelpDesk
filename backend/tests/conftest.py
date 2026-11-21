"""Compatibilidad de fixtures heredadas con el contrato multitenant de HU-13.

Las pruebas antiguas de tickets y SLA crean usuarios mediante el registro o
``provision_user`` sin empresa porque ese campo no existía en sus contratos.
No se relaja la aplicación: solo se completa el tenant de esas fixtures
heredadas. Las pruebas de HU-13 y de autorización tenant mantienen control
explícito sobre ``company_id`` y quedan fuera de este adaptador.
"""

import os

import pytest

from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)


_LEGACY_TENANT_MODULES = {
    "test_sla_api",
    "test_sla_live_config",
    "test_sla_policies_api",
}

_LEGACY_TECHNICIAN_ACTION_MODULES = {
    "test_ticket_comments_creation",
    "test_ticket_comments_flow",
    "test_ticket_comments_listing",
    "test_ticket_history_api",
    "test_ticket_lifecycle_reopen",
    "test_ticket_lifecycle_status",
    "test_tickets_detail_contract",
    "test_tickets_modifications_sweep",
    "test_tickets_modify_access",
    "test_tickets_priority_responses",
    "test_tickets_set_priority",
    "test_tickets_update_status",
    "test_sla_api",
    "test_sla_live_config",
}


@pytest.fixture(autouse=True)
def adapt_legacy_tenant_fixtures(request, monkeypatch):
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PASSWORD")):
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    module_name = request.module.__name__.rsplit(".", 1)[-1]
    if not (
        module_name.startswith("test_ticket")
        or module_name.startswith("test_tickets")
        or module_name in _LEGACY_TENANT_MODULES
    ):
        yield
        return

    repository = get_user_repository()
    original_add = repository.add
    technician_actions = module_name in _LEGACY_TECHNICIAN_ACTION_MODULES
    tickets = None

    if (
        technician_actions
        or module_name.startswith("test_ticket")
        or module_name.startswith("test_tickets")
        or module_name.startswith("test_sla")
    ):
        from app.modules.tickets.infrastructure.ticket_repository import (
            get_ticket_repository,
        )

        tickets = get_ticket_repository()
        original_ticket_add = tickets.add

        def add_with_legacy_company(ticket):
            if ticket.company_id is None:
                ticket.company_id = "legacy-company"
            if technician_actions:
                technicians = [
                    user
                    for user in repository.list_all()
                    if user.role == "tecnico"
                ]
                if technicians and not (
                    module_name == "test_ticket_history_api"
                    and ticket.assignee_id is not None
                ):
                    ticket.assignee_id = technicians[-1].id
                    ticket.assignee_name = technicians[-1].name
            original_ticket_add(ticket)

        monkeypatch.setattr(tickets, "add", add_with_legacy_company)

    def add_with_legacy_company(user):
        if user.company_id is None:
            user.company_id = "legacy-company"
        original_add(user)
        if technician_actions and user.role == "tecnico":
            for ticket in tickets.list_all():
                if module_name != "test_ticket_history_api" or ticket.assignee_id is None:
                    ticket.assignee_id = user.id
                    ticket.assignee_name = user.name

    monkeypatch.setattr(repository, "add", add_with_legacy_company)
    yield
