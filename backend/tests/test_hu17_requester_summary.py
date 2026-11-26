"""T2: proyección mínima después de autorizar, sin ampliar detalle ni SLA."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from test_hu17_summary_security import (
    NOT_FOUND, ROLES, ROUTES, clean_state, password_hash, scenario,
)
from app.main import app
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository
from app.modules.tickets.interface import router as tickets_http


SUMMARY_FIELDS = {
    "id", "title", "priority", "status", "assignee", "sla", "created_at", "requester",
}


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("requester_kind", ("resolved", "missing", "null_name"))
def test_each_summary_serializes_only_requester_name(scenario, route, requester_kind):
    api, own, *_ = scenario("tecnico")
    users = get_user_repository()
    actor = users.find_by_id(own.requester_id)
    expected = {"name": actor.name}
    if requester_kind == "missing":
        own = replace(own, requester_id=str(uuid4()))
        get_ticket_repository().add(own)
        expected = None
    elif requester_kind == "null_name":
        unnamed = replace(actor, id=str(uuid4()), email=f"{uuid4()}@example.com", name=None)
        users.add(unnamed)
        own = replace(own, requester_id=unnamed.id)
        get_ticket_repository().add(own)
        expected = None

    response = api.get(route)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows
    for row in rows:
        assert set(row) == SUMMARY_FIELDS
        if row["requester"] is not None:
            assert set(row["requester"]) == {"name"}
            assert isinstance(row["requester"]["name"], str)
    row = next(item for item in rows if item["id"] == own.id)
    assert row["requester"] == expected
    assert row["title"] == own.title
    assert row["status"] == own.status
    assert row["priority"] == own.priority
    assert row["created_at"] == own.created_at.isoformat()
    for user in users.list_all():
        assert user.email not in response.text
        assert user.password_hash not in response.text
    for forbidden in (
        "email", "requester_id", "role", "company_id", "password_hash",
        "invitation_token", "invitation_token_hash",
    ):
        assert f'"{forbidden}"' not in response.text


@pytest.mark.parametrize("route", ROUTES)
def test_identity_resolution_only_receives_authorized_tickets(scenario, monkeypatch, route):
    api, own, other, foreign, crossed = scenario("tecnico")
    original = tickets_http.get_user_summary
    seen = []

    def resolve(user_id):
        seen.append(user_id)
        return original(user_id)

    monkeypatch.setattr(tickets_http, "get_user_summary", resolve)
    response = api.get(route, params={"company_id": foreign.company_id})
    assert response.status_code == 200
    expected = [own] if route == ROUTES[2] else [own, other]
    assert {row["id"] for row in response.json()} == {ticket.id for ticket in expected}
    assert sorted(seen) == sorted(ticket.requester_id for ticket in expected)
    assert foreign.id not in response.text
    assert crossed.id not in response.text
    foreign_user = get_user_repository().find_by_id(foreign.requester_id)
    assert foreign_user.name not in response.text


def _unexpected_resolution(_):
    pytest.fail("identity no debe consultarse antes de autorizar o sin resultados")


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("role", ROLES)
def test_no_company_rejection_never_resolves_requester(scenario, monkeypatch, route, role):
    api, *_ = scenario(role, company=False)
    monkeypatch.setattr(tickets_http, "get_user_summary", _unexpected_resolution)
    response = api.get(route)
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("route", ROUTES)
def test_no_session_never_resolves_requester(monkeypatch, route):
    monkeypatch.setattr(tickets_http, "get_user_summary", _unexpected_resolution)
    response = TestClient(app).get(route)
    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


@pytest.mark.parametrize("role,route", [
    ("cliente", ROUTES[1]), ("cliente", ROUTES[3]), ("supervisor", ROUTES[3]),
])
def test_role_denial_never_resolves_requester(scenario, monkeypatch, role, route):
    api, *_ = scenario(role)
    monkeypatch.setattr(tickets_http, "get_user_summary", _unexpected_resolution)
    response = api.get(route)
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("route", ROUTES)
def test_authorized_empty_never_resolves_requester(scenario, monkeypatch, route):
    api, *_ = scenario("tecnico")
    get_ticket_repository().clear()
    monkeypatch.setattr(tickets_http, "get_user_summary", _unexpected_resolution)
    response = api.get(route)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("route", ROUTES)
def test_summary_composition_preserves_order_sla_and_one_reference(scenario, monkeypatch, route):
    api, own, *_ = scenario("tecnico")
    repo = get_ticket_repository()
    repo.clear()
    now = datetime.now(timezone.utc)
    older = replace(own, created_at=now - timedelta(hours=4))
    newer = replace(own, id=str(uuid4()), created_at=now - timedelta(hours=3))
    repo.add(newer)
    repo.add(older)
    references = []
    expected_sla = {}
    original = tickets_http._sla_response

    def sla(ticket, reference):
        references.append(reference)
        result = original(ticket, reference)
        expected_sla[ticket.id] = result.model_dump() if result is not None else None
        return result

    monkeypatch.setattr(tickets_http, "_sla_response", sla)
    response = api.get(route)
    assert response.status_code == 200
    rows = response.json()
    expected_ids = [older.id, newer.id] if route == ROUTES[3] else [newer.id, older.id]
    assert [row["id"] for row in rows] == expected_ids
    assert len(references) == 2
    assert references[0] is references[1]
    for row in rows:
        assert set(row) == SUMMARY_FIELDS
        assert row["requester"] == {"name": own.assignee_name}
        assert row["sla"] == expected_sla[row["id"]]


def test_detail_requester_keeps_exact_original_projection(scenario):
    api, own, *_ = scenario("tecnico")
    user = get_user_repository().find_by_id(own.requester_id)
    response = api.get(f"/api/tickets/{own.id}")
    assert response.status_code == 200
    assert response.json()["requester"] == {
        "id": user.id, "name": user.name, "email": user.email,
    }
