"""HU-26 B.I.6: INSERT indivisible y commit de propiedad explícita."""

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure import db
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import InMemoryTicketRepository
from hu26_sql_support import IsolatedPostgres


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.6 requiere PostgreSQL aislado opt-in")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture
def ticket(sandbox):
    company, requester, assignee = (str(uuid4()) for _ in range(3))
    with sandbox.connect() as conn:
        conn.execute(
            "INSERT INTO companies(id,name,name_normalized) "
            "VALUES (%s,'Empresa INSERT','empresa insert')", (company,),
        )
        for account, role in ((requester, "cliente"), (assignee, "tecnico")):
            conn.execute(
                "INSERT INTO users(id,company_id,name,email,password_hash,role) "
                "VALUES (%s,%s,'Cuenta sintética',%s,'hash-sintético',%s)",
                (account, company, f"{account}@example.test", role),
            )
    created = datetime(2024, 2, 3, 4, 5, 6, 123456,
                       tzinfo=timezone(timedelta(hours=-5)))
    return Ticket(
        id=str(uuid4()), company_id=company, requester_id=requester,
        title="  Título idéntico á  ", description="Descripción\nsin recortar ",
        created_at=created, priority="Alta", status="Cerrado",
        assignee_id=assignee, assignee_name="Nombre conservado",
        resolved_at=created + timedelta(minutes=73, microseconds=7),
        resolved_target_minutes=137,
    )


def _rows(sandbox):
    with sandbox.connect() as conn:
        return conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()


def _reject_insert(sandbox, deferred):
    """El error diferido ocurre en COMMIT real, no al liberar un savepoint."""
    with sandbox.connect() as conn:
        conn.execute(
            """CREATE FUNCTION reject_bi6_insert() RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'injected ticket failure' USING ERRCODE='23514';
               END $$"""
        )
        if deferred:
            conn.execute(
                "CREATE CONSTRAINT TRIGGER reject_bi6_insert AFTER INSERT ON tickets "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
                "EXECUTE FUNCTION reject_bi6_insert()"
            )
        else:
            conn.execute(
                "CREATE TRIGGER reject_bi6_insert BEFORE INSERT ON tickets "
                "FOR EACH ROW EXECUTE FUNCTION reject_bi6_insert()"
            )


@pytest.mark.parametrize("complete", [False, True])
def test_owned_insert_commits_every_field_without_cache_or_foreign_sql(
    sandbox, ticket, complete
):
    if not complete:
        ticket = replace(
            ticket, status="Abierto", priority=None, assignee_id=None,
            assignee_name=None, resolved_at=None, resolved_target_minutes=None,
        )
    # FK siguen vigentes; el adaptador no puede consultar nombres/políticas.
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
        conn.execute("ALTER TABLE ticket_sla RENAME TO unavailable_ticket_sla")
    repository = InMemoryTicketRepository()
    before = asdict(ticket)
    assert repository.add(ticket) is None
    assert len(_rows(sandbox)) == 1
    reread = InMemoryTicketRepository().find_by_id(ticket.id)
    assert reread == ticket and reread is not ticket
    assert asdict(ticket) == before and repository._by_id == {}


def test_identical_text_different_ids_are_two_new_rows(sandbox, ticket):
    first, second = InMemoryTicketRepository(), InMemoryTicketRepository()
    other = replace(ticket, id=str(uuid4()))
    first.add(ticket)
    second.add(other)
    assert InMemoryTicketRepository().count() == 2
    assert InMemoryTicketRepository().find_by_id(ticket.id) == ticket
    assert InMemoryTicketRepository().find_by_id(other.id) == other
    assert first._by_id == second._by_id == {}


@pytest.mark.parametrize("external", [False, True])
def test_duplicate_id_never_overwrites_or_resets_existing_progress(sandbox, ticket, external):
    repository = InMemoryTicketRepository()
    repository.add(ticket)
    before = _rows(sandbox)
    initial = replace(
        ticket, title="Reinicio no permitido", status="Abierto", priority=None,
        assignee_id=None, assignee_name=None, resolved_at=None,
        resolved_target_minutes=None,
    )
    if external:
        with sandbox.connect() as conn:
            with pytest.raises(psycopg.errors.UniqueViolation):
                repository.add(initial, conn)
            # La excepción capturada no inutiliza ni confirma la transacción.
            repository.add(replace(ticket, id=str(uuid4())), conn)
            assert _rows(sandbox) == before
            conn.rollback()
    else:
        with pytest.raises(psycopg.errors.UniqueViolation):
            repository.add(initial)
    assert _rows(sandbox) == before
    assert InMemoryTicketRepository().find_by_id(ticket.id) == ticket
    assert repository._by_id == {}


@pytest.mark.parametrize("autocommit", [False, True])
@pytest.mark.parametrize("started", [False, True])
def test_external_rollback_preserves_caller_control_and_no_visibility(
    sandbox, ticket, autocommit, started
):
    repository = InMemoryTicketRepository()
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        if started:
            conn.execute("BEGIN")
            conn.execute(
                "INSERT INTO tickets(id,company_id,requester_id,title,description) "
                "VALUES (%s,%s,%s,'Trabajo previo','Pendiente')",
                (str(uuid4()), ticket.company_id, ticket.requester_id),
            )
        repository.add(ticket, conn)
        assert conn.execute("SELECT count(*) AS n FROM tickets").fetchone()["n"] == (
            2 if started else 1
        )
        assert _rows(sandbox) == []
        assert InMemoryTicketRepository().find_by_id(ticket.id) is None
        assert repository._by_id == {}
        conn.rollback()
        assert conn.execute("SELECT count(*) AS n FROM tickets").fetchone()["n"] == 0
    assert _rows(sandbox) == [] and repository._by_id == {}


@pytest.mark.parametrize("autocommit", [False, True])
def test_external_commit_publishes_only_when_caller_confirms(sandbox, ticket, autocommit):
    repository = InMemoryTicketRepository()
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        repository.add(ticket, conn)
        assert _rows(sandbox) == []
        assert repository._by_id == {}
        conn.commit()
        assert InMemoryTicketRepository().find_by_id(ticket.id) == ticket
        assert not conn.closed
    assert len(_rows(sandbox)) == 1 and repository._by_id == {}


@pytest.mark.parametrize("deferred", [False, True])
def test_owned_sql_or_real_commit_failure_leaves_no_row_or_cache(sandbox, ticket, deferred):
    _reject_insert(sandbox, deferred)
    repository = InMemoryTicketRepository()
    with pytest.raises(psycopg.errors.CheckViolation, match="injected ticket failure"):
        repository.add(ticket)
    assert _rows(sandbox) == []
    assert InMemoryTicketRepository().find_by_id(ticket.id) is None
    assert repository._by_id == {}


@pytest.mark.parametrize("autocommit", [False, True])
def test_external_immediate_error_can_be_caught_then_unrelated_work_committed(
    sandbox, ticket, autocommit
):
    _reject_insert(sandbox, deferred=False)
    repository = InMemoryTicketRepository()
    marker = str(uuid4())
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO companies(id,name,name_normalized) "
            "VALUES (%s,'Trabajo previo','trabajo previo')", (marker,),
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            repository.add(ticket, conn)
        assert conn.execute("SELECT count(*) AS n FROM tickets").fetchone()["n"] == 0
        assert _rows(sandbox) == []
        conn.commit()
    with sandbox.connect() as reader:
        assert reader.execute("SELECT id FROM companies WHERE id=%s", (marker,)).fetchone()
    assert _rows(sandbox) == [] and repository._by_id == {}


@pytest.mark.parametrize("autocommit", [False, True])
def test_external_real_commit_failure_rolls_back_all_caller_work(sandbox, ticket, autocommit):
    _reject_insert(sandbox, deferred=True)
    repository = InMemoryTicketRepository()
    marker = str(uuid4())
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO companies(id,name,name_normalized) "
            "VALUES (%s,'Trabajo pendiente','trabajo pendiente')", (marker,),
        )
        repository.add(ticket, conn)  # RELEASE SAVEPOINT no dispara el trigger.
        assert conn.execute("SELECT count(*) AS n FROM tickets").fetchone()["n"] == 1
        assert _rows(sandbox) == [] and repository._by_id == {}
        with pytest.raises(psycopg.errors.CheckViolation, match="injected ticket failure"):
            conn.commit()
        conn.rollback()
    with sandbox.connect() as reader:
        assert reader.execute("SELECT id FROM companies WHERE id=%s", (marker,)).fetchone() is None
    assert _rows(sandbox) == []
    assert InMemoryTicketRepository().find_by_id(ticket.id) is None
    assert repository._by_id == {}


@pytest.mark.parametrize("autocommit", [False, True])
def test_caught_python_failure_after_insert_cannot_be_committed(sandbox, ticket, autocommit):
    repository = InMemoryTicketRepository()
    marker = str(uuid4())
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO companies(id,name,name_normalized) "
            "VALUES (%s,'Trabajo independiente','trabajo independiente')", (marker,),
        )

        class FailureAfterInsert:
            def __getattr__(self, name):
                return getattr(conn, name)

            def execute(self, statement, *args, **kwargs):
                result = conn.execute(statement, *args, **kwargs)
                if "INSERT INTO tickets" in statement:
                    raise RuntimeError("injected Python failure")
                return result

        with pytest.raises(RuntimeError, match="injected Python failure"):
            repository.add(ticket, FailureAfterInsert())
        assert conn.execute("SELECT count(*) AS n FROM tickets").fetchone()["n"] == 0
        assert _rows(sandbox) == []
        conn.commit()
    with sandbox.connect() as reader:
        assert reader.execute("SELECT id FROM companies WHERE id=%s", (marker,)).fetchone()
    assert _rows(sandbox) == [] and repository._by_id == {}


def test_two_scoped_connections_compete_for_same_id_without_overwriting(sandbox, ticket):
    barrier = Barrier(2)
    candidates = [ticket, replace(ticket, title="Otro intento", status="En progreso")]

    def insert(candidate):
        repository = InMemoryTicketRepository()
        with sandbox.connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '8s'")
            barrier.wait(timeout=5)
            try:
                repository.add(candidate, conn)
                conn.commit()
                result = "committed"
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                result = "duplicate"
            assert repository._by_id == {}
            return result, candidate

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(insert, candidates))
    assert sorted(result for result, _ in outcomes) == ["committed", "duplicate"]
    winner = next(candidate for result, candidate in outcomes if result == "committed")
    assert len(_rows(sandbox)) == 1
    assert InMemoryTicketRepository().find_by_id(ticket.id) == winner


def test_foreign_key_error_propagates_without_fallback(sandbox, ticket):
    repository = InMemoryTicketRepository()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        repository.add(replace(ticket, requester_id=str(uuid4())))
    assert _rows(sandbox) == [] and repository._by_id == {}


def test_explicit_connection_is_used_even_without_global_database_config(sandbox, ticket, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    repository = InMemoryTicketRepository()
    with sandbox.connect() as conn:
        repository.add(ticket, conn)
        assert _rows(sandbox) == []
        conn.commit()
    assert len(_rows(sandbox)) == 1 and repository._by_id == {}


@pytest.mark.parametrize("seam", [None, "", "true", "0"])
def test_insert_requires_exact_explicit_memory_seam(monkeypatch, seam):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    if seam is not None:
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", seam)
    repository = InMemoryTicketRepository()
    ticket = Ticket("legacy", "Título", "Descripción", "actor", datetime.now(timezone.utc))
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        repository.add(ticket)
    assert repository._by_id == {}


def test_configured_unreachable_database_cannot_fall_back_on_add(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://helpdesk@127.0.0.1:1/helpdesk?connect_timeout=1",
    )
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repository = InMemoryTicketRepository()
    ticket = Ticket(str(uuid4()), "Título", "Descripción", "actor", datetime.now(timezone.utc))
    with pytest.raises(psycopg.OperationalError):
        repository.add(ticket)
    assert repository._by_id == {}


def test_memory_seam_keeps_original_references_and_replacement_semantics(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repository = InMemoryTicketRepository()
    original = Ticket("legacy", "Título", "Descripción", "actor", datetime.now(timezone.utc))
    repository.add(original)
    assert repository.find_by_id(original.id) is original
    replacement = replace(original, title="Reemplazo solo en seam")
    repository.add(replacement)
    assert repository.find_by_id(original.id) is replacement
    assert repository.count() == 1
