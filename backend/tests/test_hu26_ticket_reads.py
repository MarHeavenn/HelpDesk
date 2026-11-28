"""B.I.3–4: lecturas propias, sin caché autoritativa ni datos inventados."""

import os
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure import db
from app.modules.tickets.application.get_ticket import (
    TicketNotFoundError,
    get_ticket_detail,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import InMemoryTicketRepository
from hu26_sql_support import IsolatedPostgres


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.3–4 requiere PostgreSQL aislado opt-in")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture
def stored(sandbox):
    company, requester, assignee = (str(uuid4()) for _ in range(3))
    created = datetime(2024, 1, 2, 3, 4, 5, 123456,
                       tzinfo=timezone(timedelta(hours=-5)))
    ticket = Ticket(
        id=str(uuid4()), company_id=company, requester_id=requester,
        title="  Texto conservado á  ", description="Descripción\nsin recortar ",
        created_at=created, priority="Alta", status="Resuelto",
        assignee_id=assignee, assignee_name="Nombre conservado",
        resolved_at=created + timedelta(minutes=73, microseconds=7),
        resolved_target_minutes=137,
    )
    with sandbox.connect() as conn:
        conn.execute(
            "INSERT INTO companies (id,name,name_normalized) "
            "VALUES (%s,'Empresa sintética','empresa sintética')", (company,),
        )
        for account, role in ((requester, "cliente"), (assignee, "tecnico")):
            conn.execute(
                "INSERT INTO users (id,company_id,name,email,password_hash,role) "
                "VALUES (%s,%s,'Nombre actual diferente',%s,'hash-sintético',%s)",
                (account, company, f"{account}@example.test", role),
            )
        conn.execute(
            "INSERT INTO tickets (id,company_id,requester_id,title,description,"
            "created_at,priority,status,assignee_id,assignee_name,resolved_at,"
            "resolved_target_minutes) VALUES (%(id)s,%(company_id)s,%(requester_id)s,"
            "%(title)s,%(description)s,%(created_at)s,%(priority)s,%(status)s,"
            "%(assignee_id)s,%(assignee_name)s,%(resolved_at)s,"
            "%(resolved_target_minutes)s)", asdict(ticket),
        )
    return ticket


def test_independent_repositories_read_every_field_using_independent_connections(
    sandbox, stored, monkeypatch
):
    connections = []

    def connect():
        conn = sandbox.connect()
        connections.append(conn)
        return conn

    monkeypatch.setattr(db, "connect", connect)
    first, second = InMemoryTicketRepository(), InMemoryTicketRepository()
    a, b = first.find_by_id(stored.id), second.find_by_id(stored.id)
    assert a == b == stored
    assert a is not b
    assert len(connections) == 2 and connections[0] is not connections[1]
    assert all(conn.closed for conn in connections)
    assert first._by_id == second._by_id == {}
    assert all(isinstance(getattr(a, field), str)
               for field in ("id", "company_id", "requester_id", "assignee_id"))
    assert a.created_at.microsecond == 123456
    assert a.resolved_at.microsecond == 123463


@pytest.mark.parametrize("status,assigned,resolved,target", [
    ("Abierto", False, False, None),
    ("En progreso", True, False, None),
    ("Resuelto", True, False, None),
    ("Cerrado", True, True, None),
    ("Resuelto", True, True, 137),
])
def test_legacy_nulls_are_real_absence_not_reconstructed(
    sandbox, stored, status, assigned, resolved, target
):
    expected = replace(
        stored, status=status, priority=None, assignee_name=None,
        assignee_id=stored.assignee_id if assigned else None,
        resolved_at=stored.resolved_at if resolved else None,
        resolved_target_minutes=target,
    )
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE tickets SET status=%s,priority=NULL,assignee_id=%s,"
            "assignee_name=NULL,resolved_at=%s,resolved_target_minutes=%s WHERE id=%s",
            (status, expected.assignee_id, expected.resolved_at, target, stored.id),
        )
        # Los nombres actuales y los datos de SLA no son fuentes de este adaptador.
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
        conn.execute("ALTER TABLE ticket_sla RENAME TO unavailable_ticket_sla")
    assert InMemoryTicketRepository().find_by_id(stored.id) == expected


def test_committed_changes_override_stale_cache_without_mutating_retained_objects(
    sandbox, stored
):
    repo = InMemoryTicketRepository()
    stale = replace(stored, title="Solo caché")
    memory_only = replace(stale, id=str(uuid4()))
    repo._by_id.update({stale.id: stale, memory_only.id: memory_only})
    retained = repo.find_by_id(stored.id)
    assert retained == stored and retained is not stale
    before = asdict(retained)
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE tickets SET title='Cambio confirmado',description='Otra descripción',"
            "priority='Baja',status='Cerrado',assignee_name=NULL,"
            "resolved_at=NULL,resolved_target_minutes=NULL WHERE id=%s", (stored.id,),
        )
    expected = replace(
        stored, title="Cambio confirmado", description="Otra descripción",
        priority="Baja", status="Cerrado", assignee_name=None,
        resolved_at=None, resolved_target_minutes=None,
    )
    assert repo.find_by_id(stored.id) == expected
    assert InMemoryTicketRepository().find_by_id(stored.id) == expected
    assert repo.find_by_id(memory_only.id) is None
    assert asdict(retained) == before
    assert stale.title == "Solo caché"
    assert repo._by_id == {stale.id: stale, memory_only.id: memory_only}


def test_missing_local_table_propagates_even_with_a_cached_ticket(sandbox, stored):
    repo = InMemoryTicketRepository()
    repo._by_id[stored.id] = stored
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE tickets RENAME TO unavailable_tickets")
    with pytest.raises(psycopg.errors.UndefinedTable):
        repo.find_by_id(stored.id)


def test_missing_id_keeps_application_not_found(sandbox):
    repo = InMemoryTicketRepository()
    missing = str(uuid4())
    assert repo.find_by_id(missing) is None
    with pytest.raises(TicketNotFoundError, match="^ticket not found$"):
        get_ticket_detail(missing, str(uuid4()), "administrador", repo)


@pytest.mark.parametrize("value", [None, 123, [], "", "not-a-uuid"])
def test_invalid_ids_never_connect_and_keep_application_not_found(monkeypatch, value):
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")

    def forbidden():
        pytest.fail("Un ID inválido no debe abrir conexión")

    monkeypatch.setattr(db, "connect", forbidden)
    repo = InMemoryTicketRepository()
    assert repo.find_by_id(value) is None
    with pytest.raises(TicketNotFoundError, match="^ticket not found$"):
        get_ticket_detail(value, "actor", "administrador", repo)


@pytest.mark.parametrize("seam", [None, "", "true", "0"])
def test_no_database_requires_exact_explicit_seam(monkeypatch, seam):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    if seam is not None:
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", seam)
    repo = InMemoryTicketRepository()
    for read in (
        lambda: repo.find_by_id(str(uuid4())),
        lambda: repo.list_by_requester("requester"),
        lambda: repo.list_by_assignee("technician"),
        repo.list_all, repo.count, repo.clear,
    ):
        with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
            read()


def test_explicit_memory_seam_preserves_legacy_ids_and_references(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repo = InMemoryTicketRepository()
    ticket = Ticket("legacy-id", "Título", "Descripción", "requester",
                    datetime(2024, 1, 1, tzinfo=timezone.utc))
    repo.add(ticket)
    assert repo.find_by_id(ticket.id) is ticket
    assert repo.find_by_id("missing") is None
    assert repo.find_by_id(None) is None
    newer = replace(ticket, id="newer", created_at=ticket.created_at + timedelta(days=1),
                    assignee_id="technician")
    repo.add(newer)
    assert repo.list_all() == repo.list_by_requester("requester") == [newer, ticket]
    assert repo.list_by_assignee("technician") == [newer]
    assert repo.list_by_requester("missing") == repo.list_by_assignee("missing") == []
    assert repo.list_all()[0] is newer
    assert repo.count() == 2
    repo.clear()
    assert repo.count() == 0 and repo.list_all() == []


def test_configured_unreachable_database_is_not_replaced_by_memory(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://helpdesk@127.0.0.1:1/helpdesk?connect_timeout=1",
    )
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repo = InMemoryTicketRepository()
    ticket = Ticket(str(uuid4()), "Título", "Descripción", "requester",
                    datetime(2024, 1, 1, tzinfo=timezone.utc))
    repo._by_id[ticket.id] = ticket
    for read in (
        lambda: repo.find_by_id(ticket.id),
        lambda: repo.list_by_requester(str(uuid4())),
        lambda: repo.list_by_assignee(str(uuid4())),
        repo.list_all, repo.count,
    ):
        with pytest.raises(psycopg.OperationalError):
            read()


def _insert_ticket(conn, ticket):
    """Preparación sintética, solo con conexión scoped del helper A1."""
    conn.execute(
        "INSERT INTO tickets (id,company_id,requester_id,title,description,"
        "created_at,priority,status,assignee_id,assignee_name,resolved_at,"
        "resolved_target_minutes) VALUES (%(id)s,%(company_id)s,%(requester_id)s,"
        "%(title)s,%(description)s,%(created_at)s,%(priority)s,%(status)s,"
        "%(assignee_id)s,%(assignee_name)s,%(resolved_at)s,"
        "%(resolved_target_minutes)s)", asdict(ticket),
    )


@pytest.fixture
def collection(sandbox, stored):
    other_company, other_requester, other_assignee, idle_assignee = (
        str(uuid4()) for _ in range(4)
    )
    with sandbox.connect() as conn:
        conn.execute(
            "DELETE FROM tickets WHERE id=%s", (stored.id,),
        )
        conn.execute(
            "INSERT INTO companies (id,name,name_normalized) "
            "VALUES (%s,'Otra empresa','otra empresa')", (other_company,),
        )
        for account, company, role in (
            (other_requester, other_company, "cliente"),
            (other_assignee, other_company, "tecnico"),
            (idle_assignee, stored.company_id, "tecnico"),
        ):
            conn.execute(
                "INSERT INTO users (id,company_id,name,email,password_hash,role) "
                "VALUES (%s,%s,'Cuenta sintética',%s,'hash-sintético',%s)",
                (account, company, f"{account}@example.test", role),
            )
        tickets = []
        for company, requester, assignee in (
            (stored.company_id, stored.requester_id, stored.assignee_id),
            (other_company, other_requester, other_assignee),
        ):
            for index, status in enumerate(("Abierto", "En progreso", "Resuelto", "Cerrado")):
                ticket = replace(
                    stored, id=str(uuid4()), company_id=company, requester_id=requester,
                    assignee_id=assignee if index else None, status=status,
                    title="Título repetido", description="Descripción repetida",
                    created_at=stored.created_at + timedelta(days=(0, 1, 1, 3)[index]),
                    priority=None if index == 0 else stored.priority,
                    assignee_name=None if index < 2 else stored.assignee_name,
                    resolved_at=stored.resolved_at if index == 3 else None,
                    resolved_target_minutes=137 if index == 3 else None,
                )
                _insert_ticket(conn, ticket)
                tickets.append(ticket)
    return tickets, idle_assignee


def _list(repo, method, sample):
    if method == "list_by_requester":
        return repo.list_by_requester(sample.requester_id)
    if method == "list_by_assignee":
        return repo.list_by_assignee(sample.assignee_id)
    return repo.list_all()


def _assert_listing(actual, expected):
    assert {ticket.id: ticket for ticket in actual} == {
        ticket.id: ticket for ticket in expected
    }
    assert len(actual) == len(expected)  # No deduplicación por texto ni IDs repetidos.
    assert [ticket.created_at for ticket in actual] == sorted(
        (ticket.created_at for ticket in expected), reverse=True,
    )  # Un empate no demuestra orden histórico.


@pytest.mark.parametrize("method", ["list_by_requester", "list_by_assignee", "list_all"])
def test_lists_read_own_rows_in_independent_connections_without_cache(
    sandbox, collection, monkeypatch, method
):
    tickets, idle_assignee = collection
    sample = tickets[1]
    expected = [
        ticket for ticket in tickets
        if method == "list_all" or getattr(ticket, {
            "list_by_requester": "requester_id", "list_by_assignee": "assignee_id",
        }[method]) == getattr(sample, {
            "list_by_requester": "requester_id", "list_by_assignee": "assignee_id",
        }[method])
    ]
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
        conn.execute("ALTER TABLE ticket_sla RENAME TO unavailable_ticket_sla")
    connections = []

    def connect():
        conn = sandbox.connect()
        connections.append(conn)
        return conn

    monkeypatch.setattr(db, "connect", connect)
    first, second = InMemoryTicketRepository(), InMemoryTicketRepository()
    stale = replace(sample, title="Caché obsoleta")
    memory_only = replace(stale, id=str(uuid4()))
    first._by_id.update({stale.id: stale, memory_only.id: memory_only})
    a, b = _list(first, method, sample), _list(second, method, sample)
    _assert_listing(a, expected)
    _assert_listing(b, expected)
    assert all(x is not y for x, y in zip(a, b))
    assert len(connections) == 2 and connections[0] is not connections[1]
    assert all(conn.closed for conn in connections)
    assert first._by_id == {stale.id: stale, memory_only.id: memory_only}
    assert second._by_id == {}
    assert second.list_by_assignee(idle_assignee) == []
    assert second.list_by_requester(str(uuid4())) == []
    assert second.list_by_assignee(str(uuid4())) == []


@pytest.mark.parametrize("method", ["list_by_requester", "list_by_assignee", "list_all"])
def test_lists_reflect_external_commits_without_mutating_retained_rows(
    sandbox, collection, method
):
    tickets, idle_assignee = collection
    repo = InMemoryTicketRepository()
    sample = tickets[1]
    retained = _list(repo, method, sample)
    before = [asdict(ticket) for ticket in retained]
    assert retained
    moved = replace(sample, requester_id=tickets[0].requester_id,
                    assignee_id=idle_assignee, title="Cambio confirmado", status="Cerrado")
    added = replace(sample, id=str(uuid4()), created_at=sample.created_at + timedelta(days=10))
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE tickets SET assignee_id=%s,title=%s,status=%s WHERE id=%s",
            (moved.assignee_id, moved.title, moved.status, moved.id),
        )
        _insert_ticket(conn, added)
    changed = [moved if ticket.id == sample.id else ticket for ticket in tickets] + [added]
    expected = [
        ticket for ticket in changed if method == "list_all"
        or (method == "list_by_requester" and ticket.requester_id == sample.requester_id)
        or (method == "list_by_assignee" and ticket.assignee_id == sample.assignee_id)
    ]
    _assert_listing(_list(repo, method, sample), expected)
    _assert_listing(_list(InMemoryTicketRepository(), method, sample), expected)
    assert [asdict(ticket) for ticket in retained] == before
    assert repo._by_id == {}


def test_count_reads_only_committed_sql_and_never_populates_cache(sandbox, collection):
    tickets, _ = collection
    repo = InMemoryTicketRepository()
    repo._by_id[tickets[0].id] = tickets[0]
    assert repo.count() == InMemoryTicketRepository().count() == 8
    with sandbox.connect() as writer:
        _insert_ticket(writer, replace(tickets[0], id=str(uuid4())))
        assert repo.count() == 8
        writer.commit()
        assert repo.count() == InMemoryTicketRepository().count() == 9
    with sandbox.connect() as writer:
        writer.execute("DELETE FROM tickets WHERE id=%s", (tickets[0].id,))
    assert repo.count() == 8
    assert repo._by_id == {tickets[0].id: tickets[0]}


def test_clear_rejects_sql_without_connecting_or_touching_cache(sandbox, stored, monkeypatch):
    repo = InMemoryTicketRepository()
    repo._by_id[stored.id] = stored

    def forbidden():
        pytest.fail("clear no debe abrir una conexión SQL")

    with monkeypatch.context() as scoped:
        scoped.setattr(db, "connect", forbidden)
        with pytest.raises(RuntimeError):
            repo.clear()
    assert repo._by_id == {stored.id: stored}
    assert InMemoryTicketRepository().find_by_id(stored.id) == stored


@pytest.mark.parametrize("method", ["list_by_requester", "list_by_assignee", "list_all", "count"])
def test_lists_and_count_propagate_missing_local_table(sandbox, stored, method):
    repo = InMemoryTicketRepository()
    repo._by_id[stored.id] = stored
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE tickets RENAME TO unavailable_tickets")
    with pytest.raises(psycopg.errors.UndefinedTable):
        if method == "count":
            repo.count()
        else:
            _list(repo, method, stored)
