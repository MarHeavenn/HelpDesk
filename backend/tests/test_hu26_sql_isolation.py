"""A1: aislamiento SQL antes de reconciliar cuentas o tocar datos reales."""

import os
import uuid

import psycopg
import pytest

from app.infrastructure import db
from hu26_sql_support import ACCOUNT_CASES, IsolatedPostgres, seed_account_case


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:password@example.com:55432/helpdesk",
        "postgresql://user:password@localhost:5432/helpdesk",
        "postgresql://user:password@localhost/helpdesk",
        "host=/var/run/postgresql port=55432 dbname=helpdesk",
        "host=localhost,example.com port=55432 dbname=helpdesk",
    ],
)
def test_sandbox_rejects_non_authorized_database_before_connecting(dsn, monkeypatch):
    def unexpected_connection(*args, **kwargs):
        pytest.fail("No debe abrir conexiones para destinos no autorizados")

    monkeypatch.setattr(psycopg, "connect", unexpected_connection)
    with pytest.raises(ValueError, match="127.0.0.1:55432"):
        with IsolatedPostgres(dsn):
            pass


def test_sandbox_never_accepts_an_existing_schema_name():
    with pytest.raises(TypeError):
        IsolatedPostgres("host=127.0.0.1 port=55432", schema="public")


@pytest.fixture
def sandbox():
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A1 SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    # Con opt-in explícito, un error SQL es un fallo, no un skip.
    with IsolatedPostgres(dsn) as isolated:
        yield isolated


def test_independent_connections_share_only_the_fresh_schema(sandbox):
    with sandbox.connect() as first:
        schema = first.execute("SELECT current_schema() AS name").fetchone()["name"]
        assert schema == sandbox.schema
        assert first.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0
        first.execute(
            "INSERT INTO users (name,email,role,password_hash) VALUES "
            "('Prueba A1','a1@example.test','cliente','$argon2id$test-only')"
        )
    with sandbox.connect() as second:
        assert second.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1
        path = second.execute("SHOW search_path").fetchone()["search_path"]
        assert [item.strip() for item in path.split(",")] == [
            sandbox.schema, "pg_catalog"
        ]
        assert second.execute(
            "SELECT to_regclass('users')::text AS name"
        ).fetchone()["name"] == "users"


def test_missing_local_table_does_not_fall_back_to_public(sandbox):
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO a1_private_users")
    with sandbox.connect() as conn:
        with pytest.raises(psycopg.errors.UndefinedTable):
            conn.execute("SELECT * FROM users")


def test_application_connections_are_scoped_including_startup(sandbox, monkeypatch):
    from app.main import initialize_database

    monkeypatch.setenv("DATABASE_URL", sandbox.scoped_dsn)
    monkeypatch.setattr(db, "connect", sandbox.connect)
    initialize_database()
    for _ in range(2):
        with db.connection() as conn:
            assert conn.execute(
                "SELECT current_schema() AS name"
            ).fetchone()["name"] == sandbox.schema


def test_cleanup_removes_only_its_owned_schema(sandbox):
    schema = sandbox.schema
    sandbox.close()
    sandbox.close()  # El cierre repetido no hace una segunda operación destructiva.
    with psycopg.connect(sandbox.base_dsn) as observer:
        assert observer.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,)
        ).fetchone() is None
        assert observer.execute("SELECT to_regclass('public.users')").fetchone()[0]


@pytest.mark.parametrize("case", ACCOUNT_CASES)
def test_account_characterization_preserves_both_original_records(sandbox, case):
    original = seed_account_case(sandbox, case)
    with sandbox.connect() as fresh:
        canonical = fresh.execute(
            "SELECT id::text AS id,email,password_hash,role,status,company_id::text "
            "AS company_id FROM users WHERE id=%s",
            (original["canonical_id"],),
        ).fetchone()
        operational = fresh.execute(
            "SELECT account_id AS id,email,password_hash,role,status,company_id "
            "FROM identity_invitation_accounts WHERE account_id=%s",
            (original["operational_id"],),
        ).fetchone()
    assert canonical == original["canonical"]
    assert operational == original["operational"]
    if case == "identical":
        assert canonical == operational
    elif case == "operational_only":
        assert canonical is None
    elif case == "conflicting_hash":
        assert canonical["password_hash"] != operational["password_hash"]
    elif case == "conflicting_email":
        assert canonical["email"] != operational["email"]
    elif case == "conflicting_company":
        assert canonical["company_id"] != operational["company_id"]
    elif case == "invalid_id":
        with pytest.raises(ValueError):
            uuid.UUID(operational["id"])
    elif case == "missing_company":
        with sandbox.connect() as conn:
            assert conn.execute(
                "SELECT 1 FROM companies WHERE id=%s",
                (operational["company_id"],),
            ).fetchone() is None


def test_sandbox_rollback_does_not_leak_rows_across_connections(sandbox):
    with pytest.raises(RuntimeError, match="fallo simulado"):
        with sandbox.connect() as conn:
            conn.execute(
                "INSERT INTO users (name,email,role,password_hash) VALUES "
                "('Rollback','rollback@example.test','cliente','$argon2id$test-only')"
            )
            raise RuntimeError("fallo simulado")
    with sandbox.connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0
