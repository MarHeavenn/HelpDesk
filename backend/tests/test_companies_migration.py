"""Migracion de empresas de HU-19 (RF-126, RF-128, RF-139).

Comprueba que `004_companies_management.sql` se aplica despues de
`001`-`003`, que tolera empresas heredadas (duplicadas, fuera de rango o
sin correo), que las deja en `active` y que introduce la forma normalizada
con un indice NO unico (D-2). Sin PostgreSQL las pruebas se omiten.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from app.infrastructure import db
from migrations.run import MIGRATIONS_DIR, apply_migrations

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1", reason="SKIP_DB_TESTS=1"
)

ORDERED_MIGRATIONS = [
    "001_init.sql",
    "002_identity_accounts.sql",
    "003_identity_invitation_state.sql",
    "004_companies_management.sql",
    "005_identity_account_created_at.sql",
    "006_identity_invitation_email_unique.sql",
]


@pytest.fixture(scope="module")
def migrated_database() -> None:
    try:
        conn = db.connect()
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        apply_migrations(conn)
    finally:
        conn.close()


@pytest.fixture
def conn(migrated_database: None) -> psycopg.Connection:
    with db.connection() as connection:
        with connection.transaction(force_rollback=True):
            yield connection


def _migration_text(name: str) -> str:
    return (MIGRATIONS_DIR / name).read_text(encoding="utf-8")


def _use_temp_schema(conn: psycopg.Connection, name: str) -> None:
    conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    conn.execute(f'CREATE SCHEMA "{name}"')
    conn.execute(f'SET LOCAL search_path TO "{name}", public')


def test_004_is_applied_after_001_to_003(conn: psycopg.Connection) -> None:
    versions = [
        row["version"]
        for row in conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    ]
    assert versions == ORDERED_MIGRATIONS


def test_company_columns_status_default_and_normalized_form(
    conn: psycopg.Connection,
) -> None:
    columns = {
        row["column_name"]: row
        for row in conn.execute(
            """
            SELECT column_name, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'companies'
            """
        ).fetchall()
    }
    assert {"email", "phone", "contact_name", "status", "name_normalized"} <= set(
        columns
    )
    assert columns["status"]["column_default"] == "'active'::text"
    assert columns["status"]["is_nullable"] == "NO"

    inserted = conn.execute(
        "INSERT INTO companies (name) VALUES ('Empresa heredada') "
        "RETURNING id, status, name_normalized"
    ).fetchone()
    assert inserted["status"] == "active"
    assert inserted["name_normalized"] is None

    policies = conn.execute(
        "SELECT count(*) AS count FROM sla_policies WHERE company_id = %s",
        (inserted["id"],),
    ).fetchone()["count"]
    assert policies == 4


def test_status_check_accepts_only_active_and_inactive(
    conn: psycopg.Connection,
) -> None:
    conn.execute("SAVEPOINT bad_status")
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO companies (name, status) "
                "VALUES ('Estado invalido', 'disabled')"
            )
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT bad_status")
        conn.execute("RELEASE SAVEPOINT bad_status")

    for status in ("active", "inactive"):
        conn.execute(
            "INSERT INTO companies (name, status) VALUES (%s, %s)",
            (f"Empresa {status}", status),
        )


def test_backfill_normalizes_and_keeps_legacy_duplicates(
    conn: psycopg.Connection,
) -> None:
    first = conn.execute(
        "INSERT INTO companies (name) VALUES ('  Ácme  ') RETURNING id"
    ).fetchone()
    second = conn.execute(
        "INSERT INTO companies (name) VALUES ('ácme') RETURNING id"
    ).fetchone()
    long_name = "x" * 120
    legacy = conn.execute(
        "INSERT INTO companies (name) VALUES (%s) RETURNING id", (long_name,)
    ).fetchone()

    conn.execute(_migration_text("004_companies_management.sql"))

    rows = {
        row["id"]: row
        for row in conn.execute(
            """
            SELECT id, name, name_normalized, status
            FROM companies
            WHERE id = ANY(%s)
            """,
            ([first["id"], second["id"], legacy["id"]],),
        ).fetchall()
    }
    assert rows[first["id"]]["name_normalized"] == "ácme"
    assert rows[second["id"]]["name_normalized"] == "ácme"
    assert rows[legacy["id"]]["name_normalized"] == long_name
    assert {row["status"] for row in rows.values()} == {"active"}

    duplicates = conn.execute(
        "SELECT count(*) AS count FROM companies WHERE name_normalized = 'ácme'"
    ).fetchone()["count"]
    assert duplicates == 2


def test_name_normalized_index_is_not_unique(conn: psycopg.Connection) -> None:
    index = conn.execute(
        """
        SELECT i.indisunique AS is_unique, pg_get_indexdef(idx.oid) AS definition
        FROM pg_index i
        JOIN pg_class idx ON idx.oid = i.indexrelid
        WHERE idx.relname = 'companies_name_normalized_idx'
        """
    ).fetchone()
    assert index is not None
    assert index["is_unique"] is False
    assert "name_normalized" in index["definition"]
    assert "UNIQUE" not in index["definition"].upper()


def test_clean_install_applies_all_migrations_with_runner(
    conn: psycopg.Connection,
) -> None:
    _use_temp_schema(conn, "companies_clean_install")

    applied = apply_migrations(conn)

    assert applied == ORDERED_MIGRATIONS
    columns = {
        row["column_name"]
        for row in conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'companies'
            """
        ).fetchall()
    }
    assert {"email", "phone", "contact_name", "status", "name_normalized"} <= columns


def test_004_after_001_to_003_keeps_legacy_companies_active(
    conn: psycopg.Connection,
) -> None:
    _use_temp_schema(conn, "companies_legacy")

    for name in ORDERED_MIGRATIONS[:3]:
        conn.execute(_migration_text(name))

    first = conn.execute(
        "INSERT INTO companies (name) VALUES ('  Ácme  ') RETURNING id"
    ).fetchone()
    second = conn.execute(
        "INSERT INTO companies (name) VALUES ('ácme') RETURNING id"
    ).fetchone()
    long_name = "y" * 120
    legacy = conn.execute(
        "INSERT INTO companies (name) VALUES (%s) RETURNING id", (long_name,)
    ).fetchone()

    conn.execute(_migration_text("004_companies_management.sql"))

    rows = conn.execute(
        """
        SELECT id, name, name_normalized, status, email, phone, contact_name
        FROM companies
        ORDER BY id
        """
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {first["id"], second["id"], legacy["id"]}
    assert by_id[first["id"]]["name_normalized"] == "ácme"
    assert by_id[second["id"]]["name_normalized"] == "ácme"
    assert by_id[legacy["id"]]["name_normalized"] == long_name
    assert all(row["status"] == "active" for row in rows)
    assert all(row["email"] is None for row in rows)
    assert all(row["phone"] is None for row in rows)
    assert all(row["contact_name"] is None for row in rows)
