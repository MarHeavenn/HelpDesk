"""Aceptación adicional R1: contexto explícito, sin adaptar tenants legacy."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from importlib import import_module
from uuid import uuid4

import pytest

from test_hu17_summary_security import (
    NOT_FOUND, ROLES, ROUTES, SUMMARY_FIELDS,
    clean_state, password_hash, scenario,
)
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.application.get_ticket import TicketNotFoundError
from app.modules.tickets.application.list_all_tickets import list_all_tickets
from app.modules.tickets.application.list_assigned_tickets import list_assigned_tickets
from app.modules.tickets.application.list_attention_tickets import list_attention_tickets
from app.modules.tickets.application.list_tickets import list_visible_tickets
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


AUTHORIZED = [
    (role, route)
    for route in ROUTES
    for role in ROLES
    if not (route == ROUTES[1] and role == "cliente")
    and not (route == ROUTES[3] and role not in ("tecnico", "administrador"))
]


@pytest.mark.parametrize("role,route", AUTHORIZED)
def test_authorized_empty_is_200_not_denial(scenario, role, route):
    api, *_ = scenario(role)
    get_ticket_repository().clear()
    response = api.get(route)
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize("role,route", AUTHORIZED)
def test_ticket_without_company_is_never_inferred_from_links(scenario, role, route):
    api, own, *_ = scenario(role)
    repo = get_ticket_repository()
    repo.clear()
    legacy = replace(own, id=str(uuid4()), company_id=None)
    repo.add(legacy)
    before = asdict(legacy)
    response = api.get(route)
    assert response.status_code == 200, response.text
    assert response.json() == []
    assert asdict(legacy) == before


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("legacy_ticket", (False, True))
def test_no_company_denied_even_without_tenant_data_and_preserves_accounts(
    scenario, role, route, legacy_ticket,
):
    api, own, *_ = scenario(role, company=False)
    repo = get_ticket_repository()
    repo.clear()
    if legacy_ticket:
        repo.add(replace(own, company_id=None))
    accounts = [asdict(user) for user in get_user_repository().list_all()]
    tickets = [asdict(ticket) for ticket in repo.list_all()]
    response = api.get(route)
    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert [asdict(user) for user in get_user_repository().list_all()] == accounts
    assert [asdict(ticket) for ticket in repo.list_all()] == tickets


def test_supervisor_does_not_gain_attention(scenario):
    api, *_ = scenario("supervisor")
    response = api.get(ROUTES[3])
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("route", ROUTES)
def test_company_query_cannot_override_session_and_summary_stays_exact(scenario, route):
    api, own, other, foreign, crossed = scenario("tecnico")
    response = api.get(route, params={"company_id": foreign.company_id})
    assert response.status_code == 200, response.text
    expected = {own.id} if route == ROUTES[2] else {own.id, other.id}
    assert {row["id"] for row in response.json()} == expected
    for row in response.json():
        assert set(row) == SUMMARY_FIELDS
    assert foreign.title not in response.text
    assert crossed.title not in response.text


class UnreadableRepository:
    def list_all(self):
        pytest.fail("Unauthorized query read the repository")

    def list_by_assignee(self, actor_id):
        pytest.fail("Unauthorized query read the repository")


@pytest.mark.parametrize("surface", ("visible", "all", "assigned", "attention"))
def test_application_rejects_missing_company_before_repository(surface):
    repo = UnreadableRepository()
    with pytest.raises(TicketNotFoundError, match="^ticket not found$"):
        if surface == "visible":
            list_visible_tickets("actor", "tecnico", None, repo)
        elif surface == "all":
            list_all_tickets("tecnico", repo, actor_company_id=None)
        elif surface == "assigned":
            list_assigned_tickets("actor", repo, actor_company_id=None)
        else:
            list_attention_tickets("tecnico", repo, actor_company_id=None)


@pytest.mark.parametrize("role", ("cliente", "supervisor", "unknown"))
def test_attention_role_guard_is_not_widened(role):
    with pytest.raises(TicketNotFoundError, match="^ticket not found$"):
        list_attention_tickets(role, UnreadableRepository(), actor_company_id="a")


def test_attention_uses_same_clock_for_selection_and_serialization(scenario, monkeypatch):
    api, own, other, *_ = scenario("tecnico")
    reference = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
    own.created_at = reference - timedelta(hours=4)
    other.created_at = reference - timedelta(hours=3)
    router = import_module("app.modules.tickets.interface.router")
    application = import_module("app.modules.tickets.application.list_attention_tickets")
    real_sla = router.get_ticket_sla
    observed = []

    class Clock:
        @staticmethod
        def now(tz):
            assert tz is timezone.utc
            return reference

    def recording_sla(snapshot, now=None):
        observed.append(now)
        return real_sla(snapshot, now)

    monkeypatch.setattr(router, "datetime", Clock)
    monkeypatch.setattr(router, "get_ticket_sla", recording_sla)
    monkeypatch.setattr(application, "get_ticket_sla", recording_sla)
    response = api.get(ROUTES[3])
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [own.id, other.id]
    assert len(observed) == 4  # Dos selecciones + dos serializaciones; nunca ajenos.
    assert all(now is reference for now in observed)
    assert all(row["sla"]["status"] == "incumplido" for row in response.json())
