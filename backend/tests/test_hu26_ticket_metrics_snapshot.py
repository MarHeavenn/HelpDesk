"""B.I.5: instantánea SQL propia y compatibilidad de muestras HU-18."""

import os
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from app.infrastructure import db
from app.modules.sla.infrastructure import sla_policy_repository as policy_module
from app.modules.sla.interface.contract import evaluate_frozen_resolution
from app.modules.tickets.application.support_metrics import (
    SupportMetricsAccessDeniedError,
    get_support_metrics,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.domain.support_metrics import TicketMetricsSnapshot
from app.modules.tickets.infrastructure import ticket_repository as repository_module
from app.modules.tickets.infrastructure.ticket_repository import InMemoryTicketRepository
from hu26_sql_support import IsolatedPostgres


CREATED = datetime(2024, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
FIELDS = (
    "id", "company_id", "status", "priority", "created_at", "resolved_at",
    "resolved_target_minutes",
)


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.5 requiere PostgreSQL aislado opt-in")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture
def tenants(sandbox):
    pairs = [(str(uuid4()), str(uuid4())) for _ in range(2)]
    with sandbox.connect() as conn:
        for number, (company, requester) in enumerate(pairs):
            conn.execute(
                "INSERT INTO companies (id,name,name_normalized) VALUES (%s,%s,%s)",
                (company, f"Empresa {number}", f"empresa {number}"),
            )
            conn.execute(
                "INSERT INTO users (id,company_id,name,email,password_hash,role) "
                "VALUES (%s,%s,'Solicitante sintético',%s,'hash-sintético','cliente')",
                (requester, company, f"{requester}@example.test"),
            )
    return pairs


def _insert(conn, tenant, **overrides):
    """Solo preparación de fixtures con conexión scoped A1, no escritor del producto."""
    company, requester = tenant
    values = {
        "id": str(uuid4()), "company_id": company, "requester_id": requester,
        "status": "Resuelto", "priority": "Alta", "created_at": CREATED,
        "resolved_at": CREATED + timedelta(minutes=60),
        "resolved_target_minutes": 60,
    }
    values.update(overrides)
    conn.execute(
        "INSERT INTO tickets (id,company_id,requester_id,title,description,status,"
        "priority,created_at,resolved_at,resolved_target_minutes,updated_at) "
        "VALUES (%(id)s,%(company_id)s,%(requester_id)s,'Título privado repetido',"
        "'Descripción privada',%(status)s,%(priority)s,%(created_at)s,%(resolved_at)s,"
        "%(resolved_target_minutes)s,%(created_at)s)", values,
    )
    return TicketMetricsSnapshot(**{key: values[key] for key in FIELDS})


def _rows(sandbox):
    with sandbox.connect() as conn:
        return conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()


def _run(repo, company, evaluator=evaluate_frozen_resolution):
    return get_support_metrics(
        actor_role="administrador", actor_company_id=company,
        read_snapshot=repo.snapshot_for_metrics, evaluate_resolution=evaluator,
    )


def _forbidden(*args, **kwargs):
    pytest.fail("No debe consultar caché/listados/política ni escribir")


def test_empty_sql_is_materialized_not_a_cached_success(sandbox):
    repo = InMemoryTicketRepository()
    repo._by_id["memory-only"] = Ticket(
        "memory-only", "Privado", "Privado", "requester", CREATED,
    )
    assert repo.snapshot_for_metrics() == ()
    assert set(repo._by_id) == {"memory-only"}


def test_one_sql_query_copies_exactly_seven_immutable_fields_without_foreign_tables(
    sandbox, tenants, monkeypatch,
):
    with sandbox.connect() as conn:
        expected = [
            _insert(conn, tenants[0]),
            _insert(conn, tenants[0], status="Cerrado", resolved_at=None,
                    resolved_target_minutes=None, priority=None),
            _insert(conn, tenants[1], status="En progreso",
                    resolved_at=CREATED + timedelta(minutes=137, microseconds=7),
                    resolved_target_minutes=137),
        ]
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
        conn.execute("ALTER TABLE ticket_sla RENAME TO unavailable_ticket_sla")
        conn.execute("ALTER TABLE sla_policies RENAME TO unavailable_sla_policies")
    before = _rows(sandbox)
    queries, connections = [], []

    class TrackedConnection:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, query, *args, **kwargs):
            queries.append(" ".join(query.lower().split()))
            return self.conn.execute(query, *args, **kwargs)

    @contextmanager
    def tracked_connection():
        with sandbox.connect() as conn:
            connections.append(conn)
            yield TrackedConnection(conn)

    repo = InMemoryTicketRepository()
    monkeypatch.setattr(repository_module, "connection", tracked_connection)
    for name in ("find_by_id", "list_all", "list_by_requester", "list_by_assignee"):
        monkeypatch.setattr(repo, name, _forbidden)
    # No lectura de memoria, aunque existan objetos obsoletos en otra instancia.
    class UnreadableCache(dict):
        values = _forbidden
    repo._by_id = UnreadableCache()
    snapshot = repo.snapshot_for_metrics()
    assert isinstance(snapshot, tuple)
    assert {row.id: asdict(row) for row in snapshot} == {
        row.id: asdict(row) for row in expected
    }
    assert queries == [
        "select id::text as id, company_id::text as company_id, status, priority, "
        "created_at, resolved_at, resolved_target_minutes from tickets"
    ]
    assert len(connections) == 1 and connections[0].closed
    assert repo._by_id == {}
    for row in snapshot:
        assert tuple(asdict(row)) == FIELDS
        for field in FIELDS:
            with pytest.raises(FrozenInstanceError):
                setattr(row, field, None)
    assert _rows(sandbox) == before


def test_new_snapshot_sees_only_committed_rows_and_does_not_mutate_retained_values(
    sandbox, tenants,
):
    with sandbox.connect() as conn:
        initial = _insert(conn, tenants[0])
    repo = InMemoryTicketRepository()
    stale = Ticket(
        initial.id, "Solo caché", "Privado", tenants[0][1], CREATED,
        company_id=initial.company_id, status="Abierto",
    )
    repo._by_id[stale.id] = stale
    first = repo.snapshot_for_metrics()
    assert first == (initial,)
    with sandbox.connect() as writer:
        writer.execute(
            "UPDATE tickets SET status='Abierto',resolved_at=NULL,"
            "resolved_target_minutes=NULL WHERE id=%s", (initial.id,),
        )
        added = _insert(writer, tenants[1])
        assert repo.snapshot_for_metrics() == first
        writer.commit()
    second = repo.snapshot_for_metrics()
    expected = replace(initial, status="Abierto", resolved_at=None,
                       resolved_target_minutes=None)
    assert {row.id: row for row in second} == {initial.id: expected, added.id: added}
    assert {row.id: row for row in InMemoryTicketRepository().snapshot_for_metrics()} == {
        row.id: row for row in second
    }
    assert next(row for row in second if row.id == initial.id) is not first[0]
    assert first == (initial,) and stale.status == "Abierto"
    assert repo._by_id == {stale.id: stale}
    result = _run(repo, tenants[0][0])
    assert result.total_tickets == result.pending_tickets == 1
    assert result.resolved_tickets == result.resolution_sample_size == result.sla_sample_size == 0


@pytest.mark.parametrize("scenario", ("five", "three", "only-no-target"))
def test_existing_hu18_examples_and_independent_samples_survive_policy_change(
    sandbox, tenants, monkeypatch, scenario,
):
    with sandbox.connect() as conn:
        if scenario == "five":
            _insert(conn, tenants[0], status="Abierto", priority=None,
                    resolved_at=None, resolved_target_minutes=None)
            _insert(conn, tenants[0], status="En progreso")
        if scenario != "only-no-target":
            _insert(conn, tenants[0])
            _insert(conn, tenants[0], status="Cerrado",
                    resolved_at=CREATED + timedelta(minutes=120))
        _insert(conn, tenants[0], status="Cerrado", resolved_target_minutes=None,
                resolved_at=None if scenario == "five" else CREATED + timedelta(minutes=180))
        # Empresa ajena queda fuera de TODAS las cifras y del evaluador.
        _insert(conn, tenants[1], resolved_at=CREATED + timedelta(days=100),
                resolved_target_minutes=999)
    before = _rows(sandbox)
    policy = policy_module.InMemorySlaPolicyRepository()
    monkeypatch.setattr(policy_module, "_policies", policy)
    repo = InMemoryTicketRepository()
    expected = {
        "total_tickets": 5 if scenario == "five" else 3 if scenario == "three" else 1,
        "resolved_tickets": 1 if scenario == "only-no-target" else 3,
        "pending_tickets": 2 if scenario == "five" else 0,
        "average_resolution_minutes": {"five": 90.0, "three": 120.0,
                                       "only-no-target": 180.0}[scenario],
        "resolution_sample_size": {"five": 2, "three": 3, "only-no-target": 1}[scenario],
        "resolution_excluded_count": 1 if scenario == "five" else 0,
        "sla_compliance_percentage": None if scenario == "only-no-target" else 50.0,
        "sla_sample_size": 0 if scenario == "only-no-target" else 2,
        "sla_met_count": 0 if scenario == "only-no-target" else 1,
        "sla_excluded_count": 1,
    }
    for minutes in (240, 30):
        targets = policy.get_all()
        policy.replace({**targets, "Alta": minutes})
        assert policy.get_target_minutes("Alta") == minutes
        calls = []

        def evaluate(*args):
            calls.append(args)
            return evaluate_frozen_resolution(*args)

        with monkeypatch.context() as guarded:
            guarded.setattr(policy, "get_all", _forbidden)
            guarded.setattr(policy, "get_target_minutes", _forbidden)
            assert asdict(_run(repo, tenants[0][0], evaluate)) == expected
        assert sorted(calls, key=lambda args: args[2]) == (
            [] if scenario == "only-no-target" else [
                ("Alta", CREATED, CREATED + timedelta(minutes=60), 60),
                ("Alta", CREATED, CREATED + timedelta(minutes=120), 60),
            ]
        )
        assert _rows(sandbox) == before
    assert repo._by_id == {}


@pytest.mark.parametrize("overrides,sample,sla,average", [
    ({"status": "Abierto"}, 0, 0, None),
    ({"status": "En progreso"}, 0, 0, None),
    ({"resolved_at": None}, 0, 0, None),
    ({"resolved_at": CREATED - timedelta(microseconds=1)}, 0, 0, None),
    ({"resolved_at": CREATED}, 1, 1, 0.0),
    ({"priority": None}, 1, 0, 60.0),
    ({"resolved_target_minutes": None}, 1, 0, 60.0),
    ({"resolved_target_minutes": 0}, 1, 0, 60.0),
    ({"resolved_target_minutes": -1}, 1, 0, 60.0),
])
def test_sql_dates_status_and_targets_keep_existing_eligibility(
    sandbox, tenants, overrides, sample, sla, average,
):
    with sandbox.connect() as conn:
        row = _insert(conn, tenants[0], **overrides)
    repo = InMemoryTicketRepository()
    assert repo.snapshot_for_metrics() == (row,)
    result = _run(repo, tenants[0][0])
    final = int(row.status in ("Resuelto", "Cerrado"))
    assert result.total_tickets == 1
    assert result.resolved_tickets == final and result.pending_tickets == 1 - final
    assert result.resolution_sample_size == sample
    assert result.resolution_excluded_count == final - sample
    assert result.average_resolution_minutes == average
    assert result.sla_sample_size == result.sla_met_count == sla
    assert result.sla_excluded_count == final - sla
    assert result.sla_compliance_percentage == (100.0 if sla else None)


@pytest.mark.parametrize("role,company", [
    ("tecnico", "company"), ("cliente", "company"), ("supervisor", "company"),
    ("administrador", None), ("administrador", ""),
])
def test_existing_authorization_precedes_snapshot_and_sql(monkeypatch, role, company):
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")
    monkeypatch.setattr(db, "connect", _forbidden)
    with pytest.raises(SupportMetricsAccessDeniedError, match="^not found$"):
        get_support_metrics(
            actor_role=role, actor_company_id=company,
            read_snapshot=InMemoryTicketRepository().snapshot_for_metrics,
            evaluate_resolution=_forbidden,
        )


@pytest.mark.parametrize("seam", [None, "", "true", "0"])
def test_snapshot_requires_exact_explicit_memory_seam(monkeypatch, seam):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    if seam is not None:
        monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", seam)
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        InMemoryTicketRepository().snapshot_for_metrics()


def test_explicit_memory_seam_still_copies_without_mutable_references(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repo = InMemoryTicketRepository()
    ticket = Ticket("legacy", "Privado", "Privado", "requester", CREATED)
    repo.add(ticket)
    snapshot = repo.snapshot_for_metrics()
    ticket.status = "Cerrado"
    assert snapshot[0].status == "Abierto"
    assert repo.snapshot_for_metrics()[0].status == "Cerrado"


def test_snapshot_does_not_hide_missing_local_table_with_memory(sandbox, tenants):
    repo = InMemoryTicketRepository()
    repo._by_id["legacy"] = Ticket("legacy", "Privado", "Privado", "requester", CREATED)
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE tickets RENAME TO unavailable_tickets")
    with pytest.raises(psycopg.errors.UndefinedTable):
        _run(repo, tenants[0][0])


def test_configured_database_failure_propagates_despite_memory_seam(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    attempts = []

    def broken():
        attempts.append(1)
        raise psycopg.OperationalError("fallo SQL sintético")

    monkeypatch.setattr(db, "connect", broken)
    with pytest.raises(psycopg.OperationalError, match="fallo SQL sintético"):
        InMemoryTicketRepository().snapshot_for_metrics()
    assert attempts == [1]
