"""Puerta T1 de HU-17: contratos de seguridad previos, sin ampliar lectura.

Expectativas de HU-13 RF-105/106/113-116/119. Los fallos reproducen
prerrequisitos pendientes: no son permisos nuevos ni correcciones de HU-17.
El nombre del módulo evita el adaptador de tenants legacy de conftest.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository


ROUTES = (
    "/api/tickets",
    "/api/tickets/all",
    "/api/assignments/mine",
    "/api/tickets/requiring-attention",
)
ROLES = ("administrador", "tecnico", "supervisor", "cliente")
SUMMARY_FIELDS = {
    "id", "title", "priority", "status", "assignee", "sla", "created_at", "requester",
}
NOT_FOUND = {"detail": "ticket not found"}
PASSWORD = "Hu17TestPassword123"


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


@pytest.fixture(autouse=True)
def clean_state():
    def reset():
        get_user_repository().clear()
        get_session_store().clear()
        get_ticket_repository().clear()
        get_sla_policy_repository().reset()

    reset()
    yield
    reset()


@pytest.fixture
def scenario(password_hash):
    def build(role, company=True):
        company_a, company_b = str(uuid4()), str(uuid4())

        def user(name, tenant, user_role):
            account = User(
                id=str(uuid4()),
                name=name,
                email=f"{uuid4()}@example.com",
                password_hash=password_hash,
                role=user_role,
                company_id=tenant,
            )
            get_user_repository().add(account)
            assert account.company_id == tenant  # Sin adaptación legacy oculta.
            return account

        actor = user("Actor empresa A", company_a if company else None, role)
        colleague = user("Solicitante empresa A", company_a, "cliente")
        foreign_user = user("Solicitante empresa B", company_b, "cliente")

        def ticket(title, tenant, requester, assigned=False):
            item = Ticket(
                id=str(uuid4()),
                title=title,
                description="Datos de prueba de autorización",
                requester_id=requester.id,
                company_id=tenant,
                created_at=datetime.now(timezone.utc) - timedelta(hours=4),
                priority="Crítica",
                assignee_id=actor.id if assigned else None,
                assignee_name=actor.name if assigned else None,
            )
            get_ticket_repository().add(item)
            return item

        assigned = role == "tecnico"
        own = ticket("Propio A", company_a, actor, assigned)
        other = ticket("Otro A", company_a, colleague)
        foreign = ticket("Ajeno B", company_b, foreign_user)
        crossed = ticket("Ajeno B vínculo cruzado", company_b, actor, assigned)
        api = TestClient(app)
        login = api.post(
            "/api/auth/login", json={"email": actor.email, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        return api, own, other, foreign, crossed

    return build


@pytest.mark.parametrize("route", ROUTES)
def test_summary_routes_require_real_session(route):
    response = TestClient(app).get(route)
    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


@pytest.mark.parametrize("role", ROLES)
def test_visible_list_uses_ticket_tenant_not_crossed_requester(scenario, role):
    api, own, other, foreign, crossed = scenario(role)
    response = api.get("/api/tickets")
    assert response.status_code == 200, response.text
    expected = {own.id} if role == "cliente" else {own.id, other.id}
    assert {item["id"] for item in response.json()} == expected
    assert foreign.title not in response.text
    assert crossed.title not in response.text
    for item in response.json():
        assert set(item) == SUMMARY_FIELDS


@pytest.mark.parametrize("route", (ROUTES[1], ROUTES[3]))
def test_client_cannot_receive_global_or_attention_list(scenario, route):
    api, *_ = scenario("cliente")
    response = api.get(route)
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize("role", ("administrador", "tecnico"))
@pytest.mark.parametrize("route", (ROUTES[1], ROUTES[3]))
def test_management_summary_excludes_foreign_ticket_even_with_crossed_links(
    scenario, role, route
):
    api, own, other, foreign, crossed = scenario(role)
    response = api.get(route)
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert ids == {own.id, other.id}, (
        f"{route}: foreign={foreign.id}, crossed={crossed.id}, received={ids}"
    )
    assert foreign.title not in response.text
    assert crossed.title not in response.text


def test_assigned_list_excludes_foreign_ticket_even_if_assigned_to_actor(scenario):
    api, own, _, foreign, crossed = scenario("tecnico")
    response = api.get("/api/assignments/mine")
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()} == {own.id}, (
        f"Foreign assigned ticket {crossed.id} must not be readable"
    )
    assert foreign.title not in response.text
    assert crossed.title not in response.text


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("route", ROUTES)
def test_account_without_company_gets_uniform_404(scenario, role, route):
    api, *_ = scenario(role, company=False)
    response = api.get(route)
    assert response.status_code == 404, response.text
    assert response.json() == NOT_FOUND


def test_supervisor_can_consult_tenant_tickets_via_global_view_source(scenario):
    """HU-13 RF-114/124: /tickets usa /all, no /api/tickets."""
    api, own, other, _, _ = scenario("supervisor")
    response = api.get("/api/tickets/all")
    assert response.status_code == 200, response.text
    assert {item["id"] for item in response.json()} == {own.id, other.id}
