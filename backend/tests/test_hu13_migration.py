"""Compatibilidad de cuentas y migracion de HU-13 (RF-123)."""

from __future__ import annotations

import os

import psycopg
import pytest

from app.infrastructure import db
from migrations.run import apply_migrations

pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DB_TESTS") == "1", reason="SKIP_DB_TESTS=1"
)


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


def test_hu13_migration_is_after_001_and_allows_nullable_company(conn):
    versions = [row["version"] for row in conn.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()]
    assert versions[:1] == ["001_init.sql"]
    assert "002_identity_accounts.sql" in versions
    assert versions[-1] == "003_identity_invitation_state.sql"

    company_nullable = conn.execute(
        """SELECT is_nullable FROM information_schema.columns
           WHERE table_name = 'users' AND column_name = 'company_id'"""
    ).fetchone()
    assert company_nullable["is_nullable"] == "YES"


def test_existing_account_is_accepted_without_changing_hash_or_role(conn):
    old = conn.execute(
        """INSERT INTO users (company_id, name, email, password_hash, role)
           VALUES (NULL, 'Cuenta previa', 'legacy@example.com',
                   '$argon2id$legacy', 'cliente')
           RETURNING id, password_hash, role, company_id"""
    ).fetchone()
    current = conn.execute(
        """SELECT password_hash, role, company_id, status, invitation_status
           FROM users WHERE id = %s""",
        (old["id"],),
    ).fetchone()
    assert current == {
        "password_hash": old["password_hash"],
        "role": old["role"],
        "company_id": old["company_id"],
        "status": "active",
        "invitation_status": "accepted",
    }


def test_hu13_roles_statuses_and_invitation_hash_invariants(conn):
    columns = {row["column_name"] for row in conn.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_name = 'users'"""
    ).fetchall()}
    assert {"phone", "status", "invitation_status", "invitation_token_hash"} <= columns

    # Cada violación se aísla en un savepoint para que la conexión pueda
    # continuar verificando la siguiente invariante tras el error esperado.
    conn.execute("SAVEPOINT pending_invariant")
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO users (name, email, password_hash, role,
                   invitation_status) VALUES ('Pendiente invalido',
                   'pending-invalid@example.com', '$argon2id$hash', 'cliente', 'pending')"""
            )
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT pending_invariant")
        conn.execute("RELEASE SAVEPOINT pending_invariant")

    conn.execute("SAVEPOINT accepted_invariant")
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO users (name, email, role, invitation_status)
                   VALUES ('Aceptada invalida', 'accepted-invalid@example.com',
                           'cliente', 'accepted')"""
            )
    finally:
        conn.execute("ROLLBACK TO SAVEPOINT accepted_invariant")
        conn.execute("RELEASE SAVEPOINT accepted_invariant")

    for role in ("cliente", "tecnico", "supervisor", "administrador"):
        conn.execute(
            """INSERT INTO users (name, email, role, password_hash)
               VALUES (%s, %s, %s, '$argon2id$hash')""",
            (f"Rol {role}", f"{role}@example.com", role),
        )


def test_failed_migration_rolls_back_its_schema_and_data(conn, tmp_path, monkeypatch):
    from migrations import run

    before = conn.execute(
        "SELECT count(*) AS count FROM users"
    ).fetchone()["count"]
    (tmp_path / "999_broken.sql").write_text(
        "ALTER TABLE users ADD COLUMN should_rollback text;\n"
        "INSERT INTO users (name, email, role, password_hash) VALUES "
        "('Temporal', 'rollback@example.com', 'cliente', '$argon2id$hash');\n"
        "THIS IS INVALID SQL;\n"
    )
    monkeypatch.setattr(run, "MIGRATIONS_DIR", tmp_path)
    with pytest.raises(psycopg.errors.SyntaxError):
        apply_migrations(conn)
    assert conn.execute(
        "SELECT count(*) AS count FROM users"
    ).fetchone()["count"] == before
    assert conn.execute(
        """SELECT 1 FROM information_schema.columns
           WHERE table_name='users' AND column_name='should_rollback'"""
    ).fetchone() is None


def test_application_startup_fails_when_migrations_fail(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.main as main

    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")

    def fail_migrations():
        raise RuntimeError("migration failed")

    monkeypatch.setattr(main, "initialize_database", fail_migrations)
    with pytest.raises(RuntimeError, match="migration failed"):
        with TestClient(app):
            pass
