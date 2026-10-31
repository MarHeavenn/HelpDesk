"""Pruebas de integracion de PostgreSQL y multitenancy (TSK-025).

Requieren un PostgreSQL accesible por `DATABASE_URL` o `POSTGRES_*`.
Si no esta disponible, se saltan. Los datos de prueba se revierten al
terminar cada test (transaccion con force_rollback).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from app.infrastructure import db
from migrations.run import apply_migrations

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1",
    reason="SKIP_DB_TESTS=1",
)

EXPECTED_TABLES = {
    "companies",
    "users",
    "tickets",
    "priorities",
    "statuses",
    "sla_policies",
    "ticket_sla",
    "ticket_comments",
}


@pytest.fixture(scope="session")
def migrated_database() -> bool:
    """Aplica las migraciones una vez; salta si no hay PostgreSQL."""
    try:
        conn = db.connect()
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        apply_migrations(conn)
    finally:
        conn.close()
    return True


@pytest.fixture
def conn(migrated_database: bool) -> psycopg.Connection:
    """Conexion con transaccion revertida al final del test."""
    with db.connection() as connection:
        with connection.transaction(force_rollback=True):
            yield connection


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _company(conn: psycopg.Connection, name: str) -> str:
    return conn.execute(
        "INSERT INTO companies (name) VALUES (%s) RETURNING id",
        (name,),
    ).fetchone()["id"]


def _user(
    conn: psycopg.Connection,
    company_id: str,
    *,
    role: str = "cliente",
    email: str | None = None,
) -> str:
    return db.create_company_user(
        conn,
        company_id=company_id,
        name=f"Usuario {role}",
        email=email or f"{_new_uuid()}@example.com",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$fake",
        role=role,
    )["id"]


def _ticket(
    conn: psycopg.Connection,
    company_id: str,
    requester_id: str,
    **overrides: object,
) -> dict:
    values = {
        "title": "No puedo acceder",
        "description": "La aplicacion rechaza mi contrasena",
        **overrides,
    }
    return db.create_company_ticket(
        conn,
        company_id=company_id,
        requester_id=requester_id,
        **values,
    )


# ---------------------------------------------------------------------------
# Esquema y catalogos
# ---------------------------------------------------------------------------
def test_migrations_create_the_eight_tables(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
    ).fetchall()
    tables = {row["table_name"] for row in rows}
    assert EXPECTED_TABLES <= tables
    assert "schema_migrations" in tables


def test_shared_catalogs_are_seeded_in_order(conn: psycopg.Connection) -> None:
    priorities = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM priorities ORDER BY sort_order"
        ).fetchall()
    ]
    statuses = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM statuses ORDER BY sort_order"
        ).fetchall()
    ]
    assert priorities == ["Crítica", "Alta", "Media", "Baja"]
    assert statuses == ["Abierto", "En progreso", "Resuelto", "Cerrado"]


def test_new_company_gets_default_sla_policies(conn: psycopg.Connection) -> None:
    company_id = _company(conn, "Empresa SLA")
    policies = {
        row["priority"]: row["target_minutes"]
        for row in db.list_sla_policies(conn, company_id)
    }
    assert policies == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }


def test_sla_policies_are_unique_per_company_and_priority(
    conn: psycopg.Connection,
) -> None:
    company_id = _company(conn, "Empresa duplicada")
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO sla_policies (company_id, priority, target_minutes)
                VALUES (%s, 'Crítica', 60)
                """,
                (company_id,),
            )


def test_migrations_are_idempotent(conn: psycopg.Connection) -> None:
    with db.connection() as fresh:
        assert apply_migrations(fresh) == []


# ---------------------------------------------------------------------------
# Aislamiento por empresa
# ---------------------------------------------------------------------------
def test_ticket_reads_are_isolated_by_company(conn: psycopg.Connection) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_a = _user(conn, company_a)
    user_b = _user(conn, company_b)
    ticket_a = _ticket(conn, company_a, user_a)
    ticket_b = _ticket(conn, company_b, user_b)

    assert [row["id"] for row in db.list_company_tickets(conn, company_a)] == [
        ticket_a["id"]
    ]
    assert db.get_company_ticket(conn, company_a, ticket_b["id"]) is None
    assert db.get_company_ticket(conn, company_b, ticket_b["id"])["id"] == ticket_b["id"]


def test_ticket_rejects_requester_from_another_company(
    conn: psycopg.Connection,
) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_b = _user(conn, company_b)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():
            _ticket(conn, company_a, user_b)


def test_ticket_rejects_assignee_from_another_company(
    conn: psycopg.Connection,
) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_a = _user(conn, company_a)
    user_b = _user(conn, company_b)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with conn.transaction():
            _ticket(conn, company_a, user_a, assignee_id=user_b)


def test_assign_does_not_update_a_foreign_ticket(
    conn: psycopg.Connection,
) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_a = _user(conn, company_a)
    user_b = _user(conn, company_b)
    ticket_b = _ticket(conn, company_b, user_b)

    assert (
        db.assign_company_ticket(
            conn,
            company_id=company_a,
            ticket_id=ticket_b["id"],
            assignee_id=user_a,
        )
        is None
    )
    assert db.get_company_ticket(conn, company_b, ticket_b["id"])["assignee_id"] is None


def test_email_is_unique_globally(conn: psycopg.Connection) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    shared_email = f"{_new_uuid()}@example.com"
    _user(conn, company_a, email=shared_email)

    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            _user(conn, company_b, email=shared_email)


# ---------------------------------------------------------------------------
# Comentarios y SLA
# ---------------------------------------------------------------------------
def test_comment_from_another_company_is_rejected(
    conn: psycopg.Connection,
) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_a = _user(conn, company_a)
    user_b = _user(conn, company_b)
    ticket_a = _ticket(conn, company_a, user_a)

    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            db.create_ticket_comment(
                conn,
                company_id=company_a,
                ticket_id=ticket_a["id"],
                author_id=user_b,
                body="Comentario ajeno",
            )


def test_same_company_comment_is_visible_only_in_its_company(
    conn: psycopg.Connection,
) -> None:
    company_a = _company(conn, "Empresa A")
    company_b = _company(conn, "Empresa B")
    user_a = _user(conn, company_a)
    user_b = _user(conn, company_b)
    ticket_a = _ticket(conn, company_a, user_a)

    comment = db.create_ticket_comment(
        conn,
        company_id=company_a,
        ticket_id=ticket_a["id"],
        author_id=user_a,
        body="Estamos revisando el caso",
    )

    assert comment is not None
    assert db.list_ticket_comments(conn, company_a, ticket_a["id"]) == [comment]
    assert db.list_ticket_comments(conn, company_b, ticket_a["id"]) == []
    assert db.create_ticket_comment(
        conn,
        company_id=company_b,
        ticket_id=ticket_a["id"],
        author_id=user_b,
        body="No deberia crearse",
    ) is None


def test_ticket_sla_due_at_is_computed_from_target(
    conn: psycopg.Connection,
) -> None:
    company_id = _company(conn, "Empresa SLA")
    user_id = _user(conn, company_id)
    ticket = _ticket(conn, company_id, user_id)
    started_at = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    row = conn.execute(
        """
        INSERT INTO ticket_sla (ticket_id, target_minutes, started_at)
        VALUES (%s, %s, %s)
        RETURNING due_at
        """,
        (ticket["id"], 120, started_at),
    ).fetchone()

    assert row["due_at"] == started_at + timedelta(hours=2)


def test_ticket_sla_is_unique_per_ticket(conn: psycopg.Connection) -> None:
    company_id = _company(conn, "Empresa SLA")
    user_id = _user(conn, company_id)
    ticket = _ticket(conn, company_id, user_id)
    conn.execute(
        """
        INSERT INTO ticket_sla (ticket_id, target_minutes)
        VALUES (%s, 240)
        """,
        (ticket["id"],),
    )

    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO ticket_sla (ticket_id, target_minutes)
                VALUES (%s, 720)
                """,
                (ticket["id"],),
            )
