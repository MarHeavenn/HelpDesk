"""HU-26 B.I.7: alta HTTP real, confirmación SQL y relectura independiente."""

import os
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.infrastructure import db
from app.modules.companies.infrastructure import company_repository
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.tickets.infrastructure import ticket_repository
from hu26_sql_support import IsolatedPostgres
from test_hu26_ticket_insert import _reject_insert


PASSWORD = "SyntheticHttpTicket123"
DETAIL_KEYS = {
    "id", "title", "description", "priority", "status", "assignee",
    "requester", "sla", "created_at", "resolved_at", "requester_id",
}
SUMMARY_KEYS = {
    "id", "title", "priority", "status", "assignee", "sla",
    "created_at", "requester",
}
VALID = {"title": "  Título á HTTP  ", "description": "\tDescripción\níntegra  "}


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.7 requiere PostgreSQL aislado opt-in")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        # Arranque y cada conexión HTTP también verifican el search_path A1.
        monkeypatch.setattr(db, "connect", isolated.connect)
        monkeypatch.setattr(
            ticket_repository, "_tickets", ticket_repository.InMemoryTicketRepository()
        )
        monkeypatch.setattr(
            user_repository, "_users", user_repository.InMemoryUserRepository()
        )
        monkeypatch.setattr(
            company_repository, "_companies", company_repository.InMemoryCompanyRepository()
        )
        monkeypatch.setattr(
            session_store, "_sessions", session_store.InMemorySessionStore()
        )
        yield isolated


@pytest.fixture
def world(sandbox, password_hash):
    company, inactive = str(uuid4()), str(uuid4())
    actors = {}
    with sandbox.connect() as conn:
        for company_id, name, status in (
            (company, "Alta HTTP", "active"),
            (inactive, "Inactiva HTTP", "inactive"),
        ):
            conn.execute(
                "INSERT INTO companies(id,name,name_normalized,status) VALUES (%s,%s,%s,%s)",
                (company_id, name, name.lower(), status),
            )
        for key, role, company_id in (
            ("client", "cliente", company),
            ("admin", "administrador", company),
            ("tech", "tecnico", company),
            ("platform", "administrador", None),
            ("unassociated", "cliente", None),
            ("inactive", "cliente", inactive),
        ):
            actor = {
                "id": str(uuid4()), "name": f"Cuenta {key}",
                "email": f"{key}@ordinary.example.com", "company_id": company_id,
            }
            conn.execute(
                "INSERT INTO users(id,company_id,name,email,password_hash,role,"
                "invitation_status) VALUES (%s,%s,%s,%s,%s,%s,'accepted')",
                (actor["id"], company_id, actor["name"], actor["email"], password_hash, role),
            )
            actors[key] = actor
    return actors


@pytest.fixture
def clients(sandbox, world):
    """Un cliente/cookie por actor; login y startup reales, sin overrides."""
    from app.main import app

    with ExitStack() as stack:
        opened = {}

        def get(key="client"):
            if key not in opened:
                client = stack.enter_context(TestClient(app, raise_server_exceptions=False))
                if key != "anonymous":
                    response = client.post("/api/auth/login", json={
                        "email": world[key]["email"], "password": PASSWORD,
                    })
                    assert response.status_code == 200
                opened[key] = client
            return opened[key]

        yield get


def _rows(sandbox):
    with sandbox.connect() as conn:
        return conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()


def _assert_confirmed(body, actor, sandbox, before, after):
    assert set(body) == DETAIL_KEYS
    assert str(UUID(body["id"])) == body["id"]
    assert body["status"] == "Abierto"
    assert body["priority"] is body["assignee"] is body["resolved_at"] is body["sla"] is None
    assert body["requester_id"] == actor["id"]
    assert body["requester"] == {
        "id": actor["id"], "name": actor["name"], "email": actor["email"],
    }
    created = datetime.fromisoformat(body["created_at"])
    assert created.utcoffset() == timedelta(0)
    assert before <= created <= after
    rows = _rows(sandbox)  # Otra conexión ve la fila antes de cualquier GET.
    row = next(row for row in rows if str(row["id"]) == body["id"])
    assert (str(row["company_id"]), str(row["requester_id"])) == (
        actor["company_id"], actor["id"],
    )
    assert (row["title"], row["description"], row["created_at"], row["status"]) == (
        body["title"], body["description"], created, "Abierto",
    )
    for field in (
        "priority", "assignee_id", "assignee_name", "resolved_at", "resolved_target_minutes",
    ):
        assert row[field] is None
    fresh = ticket_repository.InMemoryTicketRepository()
    stored = fresh.find_by_id(body["id"])
    assert (stored.id, stored.company_id, stored.requester_id, stored.created_at) == (
        body["id"], actor["company_id"], actor["id"], created,
    )
    assert stored.title == body["title"] and stored.description == body["description"]
    assert fresh._by_id == ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("actor_key", ["client", "admin"])
def test_created_ticket_is_committed_before_201_and_http_rereads_from_new_repository(
    sandbox, world, clients, monkeypatch, actor_key,
):
    client = clients(actor_key)
    before = datetime.now(timezone.utc)
    response = client.post("/api/tickets", json=VALID)
    after = datetime.now(timezone.utc)
    assert response.status_code == 201
    body = response.json()
    assert (body["title"], body["description"]) == ("Título á HTTP", "Descripción\níntegra")
    _assert_confirmed(body, world[actor_key], sandbox, before, after)
    assert len(_rows(sandbox)) == 1
    monkeypatch.setattr(
        ticket_repository, "_tickets", ticket_repository.InMemoryTicketRepository()
    )
    detail = client.get(f"/api/tickets/{body['id']}")
    assert detail.status_code == 200 and detail.json() == body
    summary = {key: body[key] for key in SUMMARY_KEYS}
    summary["requester"] = {"name": world[actor_key]["name"]}
    listing = client.get("/api/tickets")
    assert listing.status_code == 200 and listing.json() == [summary]
    admin_listing = clients("admin").get("/api/tickets/all")
    assert admin_listing.status_code == 200 and admin_listing.json() == [summary]
    assert ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("lengths", [(1, 1), (200, 5000)])
def test_text_boundaries_and_identical_text_keep_two_distinct_confirmed_tickets(
    sandbox, world, clients, lengths,
):
    client = clients()
    title_length, description_length = lengths
    payload = {"title": " á" + "x" * (title_length - 1) + " ",
               "description": "\tñ" + "y" * (description_length - 1) + "\n"}
    ids = []
    for _ in range(2):
        before = datetime.now(timezone.utc)
        response = client.post("/api/tickets", json=payload)
        after = datetime.now(timezone.utc)
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == payload["title"].strip()
        assert body["description"] == payload["description"].strip()
        _assert_confirmed(body, world["client"], sandbox, before, after)
        ids.append(body["id"])
    assert len(set(ids)) == len(_rows(sandbox)) == 2


@pytest.mark.parametrize("payload", [
    {}, {"title": "Título"}, {"description": "Descripción"},
    {"title": 123, "description": "Descripción"},
    {"title": "Título", "description": None},
    {"title": " \t", "description": "Descripción"},
    {"title": "Título", "description": "\n "},
    {"title": "x" * 201, "description": "Descripción"},
    {"title": "Título", "description": "x" * 5001},
    {**VALID, "requester_id": str(UUID(int=1))},
    {**VALID, "company_id": str(UUID(int=2))},
    {**VALID, "priority": "Alta"},
    {**VALID, "status": "Resuelto"},
])
def test_invalid_input_returns_422_without_any_insert(sandbox, clients, payload):
    response = clients().post("/api/tickets", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert _rows(sandbox) == []
    assert ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("key,expected", [
    ("anonymous", 401), ("tech", 404), ("platform", 404),
    ("unassociated", 404), ("inactive", 409),
])
@pytest.mark.parametrize("invalid_json", [False, True])
def test_existing_authorization_precedes_body_and_never_inserts(
    sandbox, clients, key, expected, invalid_json,
):
    client = clients(key)
    response = (
        client.post("/api/tickets", content="{", headers={"Content-Type": "application/json"})
        if invalid_json else client.post("/api/tickets", json=VALID)
    )
    assert response.status_code == expected
    if expected == 404:
        assert response.json() == {"detail": "ticket not found"}
    if expected == 409:
        assert response.json() == {"detail": "empresa no activa"}
    assert _rows(sandbox) == []
    assert ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("deferred", [False, True])
def test_real_insert_or_commit_failure_returns_500_without_row_cache_or_ghost_in_http(
    sandbox, clients, monkeypatch, deferred,
):
    client = clients()
    _reject_insert(sandbox, deferred)
    response = client.post("/api/tickets", json=VALID)
    assert response.status_code == 500
    assert _rows(sandbox) == []
    failed_repository = ticket_repository.get_ticket_repository()
    assert failed_repository._by_id == {} and failed_repository.count() == 0
    monkeypatch.setattr(
        ticket_repository, "_tickets", ticket_repository.InMemoryTicketRepository()
    )
    listing = client.get("/api/tickets")
    assert listing.status_code == 200 and listing.json() == []
    admin_listing = clients("admin").get("/api/tickets/all")
    assert admin_listing.status_code == 200 and admin_listing.json() == []
