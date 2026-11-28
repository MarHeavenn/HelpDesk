"""A2: reconciliación incremental, exclusivamente en PostgreSQL aislado."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from hu26_sql_support import ACCOUNT_CASES, IsolatedPostgres, seed_account_case
from migrations import run


VERSION = "007_reconcile_identity_accounts.sql"
FIELDS = (
    "name", "email", "phone", "role", "status", "invitation_status",
    "password_hash", "invitation_token_hash", "invitation_expires_at",
    "invitation_used_at", "created_at",
)


def test_reconciliation_is_a_new_incremental_migration():
    assert VERSION in [path.name for path in run.migration_files()]


@pytest.fixture
def legacy_database(monkeypatch):
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A2 SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    # Construir la versión anterior sin modificar archivos ni el runner real.
    previous = [path for path in run.migration_files() if path.name < VERSION]
    with monkeypatch.context() as setup:
        setup.setattr(run, "migration_files", lambda: previous)
        with IsolatedPostgres(dsn) as sandbox:
            setup.undo()
            yield sandbox


def snapshot(sandbox):
    with sandbox.connect() as conn:
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("users", "identity_invitation_accounts", "schema_migrations")
        }


def migrate(sandbox):
    with sandbox.connect() as conn:
        return run.apply_migrations(conn)


def test_clean_install_and_repetition_are_idempotent(legacy_database, monkeypatch):
    # Escenario histórico 006→007; las migraciones posteriores se prueban aparte.
    historical = [path for path in run.migration_files() if path.name <= VERSION]
    monkeypatch.setattr(run, "migration_files", lambda: historical)
    assert migrate(legacy_database) == [VERSION]
    before = snapshot(legacy_database)
    assert migrate(legacy_database) == []
    assert snapshot(legacy_database) == before


@pytest.mark.parametrize("case", ["identical", "operational_only"])
def test_existing_accounts_are_copied_or_reused_without_overwriting(
    legacy_database, case, monkeypatch
):
    # Acotar solo este escenario de reconciliación, no el runner global.
    historical = [path for path in run.migration_files() if path.name <= VERSION]
    monkeypatch.setattr(run, "migration_files", lambda: historical)
    original = seed_account_case(legacy_database, case)
    before = snapshot(legacy_database)
    assert migrate(legacy_database) == [VERSION]
    after = snapshot(legacy_database)
    assert after["identity_invitation_accounts"] == before["identity_invitation_accounts"]
    user = after["users"][0]
    account = before["identity_invitation_accounts"][0]
    assert str(user["id"]) == original["operational_id"]
    assert user["company_id"] is None
    assert {field: user[field] for field in FIELDS} == {
        field: account[field] for field in FIELDS
    }
    if case == "identical":
        assert after["users"] == before["users"]
    assert migrate(legacy_database) == []
    assert snapshot(legacy_database) == after


def test_canonical_only_account_is_never_changed(legacy_database):
    original = seed_account_case(legacy_database, "identical")
    with legacy_database.connect() as conn:
        conn.execute(
            "DELETE FROM identity_invitation_accounts WHERE account_id=%s",
            (original["operational_id"],),
        )
    before = snapshot(legacy_database)
    migrate(legacy_database)
    after = snapshot(legacy_database)
    assert after["users"] == before["users"]
    assert after["identity_invitation_accounts"] == []


@pytest.mark.parametrize(
    "case", [case for case in ACCOUNT_CASES if case not in {"identical", "operational_only"}]
)
def test_conflicts_abort_without_changing_either_store_or_migration_log(
    legacy_database, case
):
    seed_account_case(legacy_database, case)
    before = snapshot(legacy_database)
    with pytest.raises(psycopg.errors.CheckViolation, match="HU26 reconciliation"):
        migrate(legacy_database)
    assert snapshot(legacy_database) == before


@pytest.mark.parametrize("state", ["pending", "deactivated", "accepted"])
def test_preserves_credentials_invitation_dates_and_company(legacy_database, state):
    now = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    pending = state == "pending"
    account_id = str(uuid.uuid4())
    with legacy_database.connect() as conn:
        company_id = conn.execute(
            "INSERT INTO companies (name,name_normalized) "
            "VALUES ('Empresa A2','empresa a2') RETURNING id"
        ).fetchone()["id"]
        conn.execute(
            """INSERT INTO identity_invitation_accounts
               (account_id,company_id,name,email,phone,role,status,invitation_status,
                password_hash,invitation_token_hash,invitation_expires_at,
                invitation_used_at,created_at)
               VALUES (%s,%s,'Cuenta persistente','persist@example.test','12345',
                       'administrador',%s,%s,%s,%s,%s,%s,%s)""",
            (
                account_id, str(company_id),
                "deactivated" if state == "deactivated" else "active",
                "pending" if pending else "accepted",
                None if pending else "$argon2id$test-only-preserved",
                "test-invitation-hash", now + timedelta(hours=168),
                None if pending else now + timedelta(hours=1), now,
            ),
        )
    before = snapshot(legacy_database)
    migrate(legacy_database)
    after = snapshot(legacy_database)
    user, account = after["users"][0], before["identity_invitation_accounts"][0]
    assert str(user["id"]) == account_id
    assert user["company_id"] == company_id
    assert {field: user[field] for field in FIELDS} == {
        field: account[field] for field in FIELDS
    }
    assert after["identity_invitation_accounts"] == before["identity_invitation_accounts"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Nombre cambiado"),
        ("phone", "55555"),
        ("role", "tecnico"),
        ("status", "deactivated"),
        ("created_at", datetime(2000, 1, 1, tzinfo=timezone.utc)),
        ("invitation_token_hash", "different-test-hash"),
        ("invitation_expires_at", datetime(2030, 1, 1, tzinfo=timezone.utc)),
        ("invitation_used_at", datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_matching_id_with_different_data_is_not_silently_merged(
    legacy_database, field, value
):
    from psycopg import sql

    original = seed_account_case(legacy_database, "identical")
    with legacy_database.connect() as conn:
        conn.execute(
            sql.SQL("UPDATE identity_invitation_accounts SET {}=%s WHERE account_id=%s")
            .format(sql.Identifier(field)),
            (value, original["operational_id"]),
        )
    before = snapshot(legacy_database)
    with pytest.raises(psycopg.errors.CheckViolation, match="HU26 reconciliation"):
        migrate(legacy_database)
    assert snapshot(legacy_database) == before


def test_same_normalized_email_with_different_id_is_a_conflict(legacy_database):
    seed_account_case(legacy_database, "identical")
    with legacy_database.connect() as conn:
        conn.execute(
            "UPDATE identity_invitation_accounts SET account_id=%s, email=upper(email)",
            (str(uuid.uuid4()),),
        )
    before = snapshot(legacy_database)
    with pytest.raises(psycopg.errors.CheckViolation, match="HU26 reconciliation"):
        migrate(legacy_database)
    assert snapshot(legacy_database) == before


def test_valid_row_is_not_inserted_if_another_row_has_a_conflict(legacy_database):
    seed_account_case(legacy_database, "conflicting_hash")
    with legacy_database.connect() as conn:
        conn.execute(
            """INSERT INTO identity_invitation_accounts
               (account_id,name,email,role,status,invitation_status,password_hash)
               VALUES (%s,'Cuenta válida','valid@example.test','cliente','active',
                       'accepted','$argon2id$test-only')""",
            (str(uuid.uuid4()),),
        )
    before = snapshot(legacy_database)
    with pytest.raises(psycopg.errors.CheckViolation, match="HU26 reconciliation"):
        migrate(legacy_database)
    assert snapshot(legacy_database) == before
