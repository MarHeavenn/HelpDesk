"""A5a: transacciones reales del repositorio, sin escritores de aplicación."""

import os
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from psycopg import sql

from app.infrastructure import db
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    EmailAlreadyStoredError,
    InMemoryUserRepository,
)
from hu26_sql_support import IsolatedPostgres


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A5a SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture
def account(sandbox):
    now = datetime(2025, 2, 3, tzinfo=timezone.utc)
    with sandbox.connect() as conn:
        company_id = str(conn.execute(
            "INSERT INTO companies(name,name_normalized) "
            "VALUES ('Empresa transaccional','empresa transaccional') RETURNING id"
        ).fetchone()["id"])
    return User(
        id=str(uuid.uuid4()), name="Cuenta persistida", email="atomic@example.com",
        company_id=company_id, role="cliente", phone="+57 555 0303",
        password_hash="$argon2id$synthetic-original", status="active",
        invitation_status="accepted", invitation_used_at=now,
        created_at=now,
    )


def _rows(sandbox):
    with sandbox.connect() as conn:
        canonical = conn.execute(
            "SELECT id::text AS account_id, company_id::text AS company_id, name,"
            "email,phone,role,status,invitation_status,password_hash,"
            "invitation_token_hash,invitation_expires_at,invitation_used_at,created_at "
            "FROM users ORDER BY id"
        ).fetchall()
        projection = conn.execute(
            "SELECT * FROM identity_invitation_accounts ORDER BY account_id"
        ).fetchall()
    return canonical, projection


def _expected(user):
    values = dict(user.__dict__)
    values["account_id"] = values.pop("id")
    values.pop("invitation_token")
    return values


def _reject_write(sandbox, table, deferred):
    """Fallo SQL inmediato o durante COMMIT; solo objetos del esquema A1."""
    with sandbox.connect() as conn:
        conn.execute(
            """CREATE FUNCTION reject_a5a_write() RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN RAISE EXCEPTION 'injected identity failure' USING ERRCODE='23514';
               RETURN NEW; END $$"""
        )
        if deferred:
            statement = (
                "CREATE CONSTRAINT TRIGGER reject_a5a AFTER INSERT OR UPDATE ON {} "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_a5a_write()"
            )
        else:
            statement = (
                "CREATE TRIGGER reject_a5a BEFORE INSERT OR UPDATE ON {} "
                "FOR EACH ROW EXECUTE FUNCTION reject_a5a_write()"
            )
        conn.execute(sql.SQL(statement).format(sql.Identifier(table)))


def test_add_commits_both_stores_and_new_reader_without_publishing_cache(sandbox, account):
    repository = InMemoryUserRepository()
    repository.add(account)
    assert _rows(sandbox) == ([_expected(account)], [_expected(account)])
    assert InMemoryUserRepository().find_by_id(account.id) == account
    assert repository.count() == 0


def test_explicit_save_preserves_credentials_dates_and_every_account_field(sandbox, account):
    first, second = InMemoryUserRepository(), InMemoryUserRepository()
    first.add(account)
    changed = second.find_by_id(account.id)
    assert changed is not None
    changed.name = "Nombre confirmado"
    changed.role = "supervisor"
    changed.status = "deactivated"
    changed.phone = None
    changed.company_id = None
    second.sync_persistent(changed)
    assert first.find_by_id(account.id) == changed
    assert changed.password_hash == account.password_hash
    assert changed.created_at == account.created_at
    assert changed.invitation_used_at == account.invitation_used_at
    assert _rows(sandbox) == ([_expected(changed)], [_expected(changed)])


@pytest.mark.parametrize("operation", ["add", "save"])
@pytest.mark.parametrize("table", ["users", "identity_invitation_accounts"])
@pytest.mark.parametrize("deferred", [False, True], ids=["execute", "commit"])
def test_sql_failure_rolls_back_canonical_projection_and_cache(
    sandbox, account, operation, table, deferred
):
    repository = InMemoryUserRepository()
    if operation == "save":
        repository.add(account)
    before = _rows(sandbox)
    _reject_write(sandbox, table, deferred)
    changed = replace(account, name="No confirmado", role="tecnico")
    with pytest.raises(psycopg.errors.CheckViolation, match="injected identity failure"):
        if operation == "add":
            repository.add(changed)
        else:
            repository.sync_persistent(changed)
    assert _rows(sandbox) == before
    reader = InMemoryUserRepository()
    if operation == "add":
        assert reader.find_by_id(account.id) is None
    else:
        assert reader.find_by_id(account.id) == account
    assert repository.count() == 0


@pytest.mark.parametrize("autocommit", [False, True])
@pytest.mark.parametrize("operation", ["add", "save"])
def test_caller_transaction_is_not_committed_or_cached_by_repository(
    sandbox, account, autocommit, operation
):
    repository = InMemoryUserRepository()
    with sandbox.connect() as conn:
        conn.autocommit = autocommit
        getattr(repository, "add" if operation == "add" else "sync_persistent")(account, conn)
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 1
        assert _rows(sandbox) == ([], [])
        assert repository.count() == 0
        conn.rollback()
    assert _rows(sandbox) == ([], [])


def test_caller_commit_publishes_both_rows_only_after_confirmation(sandbox, account):
    repository = InMemoryUserRepository()
    with sandbox.connect() as conn:
        repository.add(account, conn)
        assert _rows(sandbox) == ([], [])
    assert _rows(sandbox) == ([_expected(account)], [_expected(account)])


def test_caller_commit_failure_leaves_no_published_rows_or_cache(sandbox, account):
    repository = InMemoryUserRepository()
    _reject_write(sandbox, "identity_invitation_accounts", deferred=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        with sandbox.connect() as conn:
            repository.add(account, conn)
            assert _rows(sandbox) == ([], [])
            assert repository.count() == 0
    assert _rows(sandbox) == ([], [])
    assert repository.count() == 0


def test_caught_projection_runtime_error_cannot_commit_half_an_operation(sandbox, account):
    """Inyección Python, pero transacción/savepoint y observación son PostgreSQL."""
    repository = InMemoryUserRepository()
    with sandbox.connect() as conn:
        class ProjectionFailure:
            def __getattr__(self, name):
                return getattr(conn, name)

            def execute(self, statement, *args, **kwargs):
                if "INSERT INTO identity_invitation_accounts" in str(statement):
                    raise RuntimeError("projection unavailable")
                return conn.execute(statement, *args, **kwargs)

        with pytest.raises(RuntimeError, match="projection unavailable"):
            repository.sync_persistent(account, ProjectionFailure())
        # El llamador captura el error y confirma otro trabajo: no debe haber
        # una mitad de identidad pendiente de commit en su transacción.
        conn.execute(
            "INSERT INTO companies(name,name_normalized) "
            "VALUES ('Trabajo independiente','trabajo independiente')"
        )
    assert _rows(sandbox) == ([], [])
    assert repository.count() == 0


@pytest.mark.parametrize("conflict_store", ["users", "identity_invitation_accounts"])
def test_duplicate_email_rolls_back_both_stores(sandbox, account, conflict_store):
    repository = InMemoryUserRepository()
    repository.add(account)
    if conflict_store == "identity_invitation_accounts":
        with sandbox.connect() as conn:
            conn.execute(
                "UPDATE users SET email='canonical-only@example.com' WHERE id=%s",
                (account.id,),
            )
    before = _rows(sandbox)
    duplicate = replace(account, id=str(uuid.uuid4()))
    with pytest.raises(EmailAlreadyStoredError):
        repository.add(duplicate)
    assert _rows(sandbox) == before
    assert repository.count() == 0


def test_locked_and_token_reads_use_canonical_not_projection(sandbox, account):
    repository = InMemoryUserRepository()
    pending = replace(
        account, password_hash=None, invitation_status="pending",
        invitation_token_hash="canonical-token", invitation_used_at=None,
        invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    repository.add(pending)
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE identity_invitation_accounts SET name='Vista anterior',"
            "invitation_token_hash='obsolete-token' WHERE account_id=%s", (account.id,),
        )
    with sandbox.connect() as first:
        assert repository.load_persistent_for_update(account.id, first) == pending
        with sandbox.connect() as second:
            with pytest.raises(psycopg.errors.LockNotAvailable):
                second.execute("SELECT id FROM users WHERE id=%s FOR UPDATE NOWAIT", (account.id,))
    assert repository.find_persistent_account_by_token("canonical-token") == account.id
    assert repository.find_persistent_account_by_token("obsolete-token") is None


def test_invalid_legacy_id_never_falls_back_to_memory(sandbox, account):
    repository = InMemoryUserRepository()
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        repository.add(replace(account, id="legacy-text-id"))
    assert _rows(sandbox) == ([], [])
    assert repository.count() == 0


@pytest.mark.parametrize("deferred", [False, True], ids=["execute", "commit"])
def test_existing_admin_guard_registration_shares_the_account_transaction(
    sandbox, account, deferred
):
    repository = InMemoryUserRepository()
    original = replace(account, role="administrador")
    repository.add(original)
    with sandbox.connect() as conn:
        conn.execute(
            "INSERT INTO identity_active_admin_guard(company_id,active_admin_ids) VALUES (%s,%s)",
            (account.company_id, [original.id]),
        )
    before = _rows(sandbox)
    _reject_write(sandbox, "identity_active_admin_guard", deferred)
    another = replace(original, id=str(uuid.uuid4()), email="another-admin@example.com")
    with pytest.raises(psycopg.errors.CheckViolation):
        repository.add(another)
    assert _rows(sandbox) == before
    with sandbox.connect() as observer:
        assert observer.execute(
            "SELECT active_admin_ids FROM identity_active_admin_guard WHERE company_id=%s",
            (account.company_id,),
        ).fetchone()["active_admin_ids"] == [original.id]
    assert repository.count() == 0


@pytest.mark.parametrize("commit_failure", [False, True])
def test_http_registration_never_reports_success_before_commit(sandbox, monkeypatch, commit_failure):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.modules.identity.infrastructure import user_repository
    from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher

    repository = InMemoryUserRepository()
    monkeypatch.setattr(user_repository, "_users", repository)
    if commit_failure:
        _reject_write(sandbox, "identity_invitation_accounts", deferred=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/auth/register", json={
            "name": "Cuenta HTTP ordinaria", "email": "http-account@example.com",
            "password": "ExistingStoragePassword123", "role": "cliente",
        })
    if commit_failure:
        assert response.status_code == 500
        assert _rows(sandbox) == ([], [])
    else:
        assert response.status_code == 201
        assert set(response.json()) == {"id", "name", "email", "role"}
        user = InMemoryUserRepository().find_by_id(response.json()["id"])
        assert user.email == "http-account@example.com"
        assert Argon2PasswordHasher().verify(user.password_hash, "ExistingStoragePassword123")
        assert _rows(sandbox) == ([_expected(user)], [_expected(user)])
    assert repository.count() == 0


def test_memory_add_failure_does_not_publish_a_partial_aggregate(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repository = InMemoryUserRepository()
    user = User(id="legacy-id", name="Cuenta prueba", email="unit@example.com",
                role="cliente", password_hash="synthetic hash")

    def fail(*args, **kwargs):
        raise OSError("storage unavailable")

    monkeypatch.setattr(repository, "sync_persistent", fail)
    with pytest.raises(OSError, match="storage unavailable"):
        repository.add(user)
    assert repository.count() == 0
    assert repository.find_by_email(user.email) is None
