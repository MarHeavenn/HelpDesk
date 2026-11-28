"""A3: lecturas canónicas, sin sembrar ni limpiar datos de la aplicación."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.infrastructure import db
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from hu26_sql_support import IsolatedPostgres


EMAIL = "ordinary.account@example.com"
PASSWORD = "ExistingPassword123"


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A3 SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        # Toda conexión de la API se comprueba, también al aplicar migraciones.
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture
def account(sandbox):
    created = datetime(2025, 4, 3, 12, 30, tzinfo=timezone.utc)
    values = {
        "id": str(uuid.uuid4()),
        "name": "Cuenta persistente ordinaria",
        "email": EMAIL,
        "password_hash": Argon2PasswordHasher().hash(PASSWORD),
        "role": "cliente",
        "phone": "+57 555 0101",
        "status": "active",
        "invitation_status": "accepted",
        "invitation_token_hash": None,
        "invitation_expires_at": None,
        "invitation_used_at": created + timedelta(hours=1),
        "created_at": created,
    }
    with sandbox.connect() as conn:
        values["company_id"] = str(conn.execute(
            "INSERT INTO companies (name, name_normalized) "
            "VALUES ('Empresa ordinaria', 'empresa ordinaria') RETURNING id"
        ).fetchone()["id"])
        conn.execute(
            """INSERT INTO users
               (id, company_id, name, email, password_hash, role, phone, status,
                invitation_status, invitation_token_hash, invitation_expires_at,
                invitation_used_at, created_at)
               VALUES (%(id)s, %(company_id)s, %(name)s, %(email)s,
                       %(password_hash)s, %(role)s, %(phone)s, %(status)s,
                       %(invitation_status)s, %(invitation_token_hash)s,
                       %(invitation_expires_at)s, %(invitation_used_at)s,
                       %(created_at)s)""",
            values,
        )
    return values


@pytest.fixture
def client(sandbox, monkeypatch):
    from app.main import app

    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    monkeypatch.setattr(session_store, "_sessions", session_store.InMemorySessionStore())
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("lookup", ["id", "email", "email_persistent"])
def test_independent_repositories_read_all_canonical_fields(account, lookup):
    first, second = InMemoryUserRepository(), InMemoryUserRepository()
    key = account["id"] if lookup == "id" else f"  {EMAIL.upper()}  "
    for repository in (first, second):
        user = getattr(repository, f"find_by_{lookup}")(key)
        assert user is not None
        assert user.__dict__ == {**account, "invitation_token": None}
        assert repository.count() == 0  # La lectura no hidrata una autoridad local.


def test_repeated_reads_see_commits_and_ignore_cached_objects(sandbox, account):
    repository = InMemoryUserRepository()
    stale = User(**account)
    stale.name = "Nombre obsoleto"
    repository.cache_persistent_user(stale)
    assert repository.find_by_id(account["id"]).name == account["name"]
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE users SET name='Nombre confirmado', email=%s, role='tecnico', "
            "company_id=NULL, status='deactivated' WHERE id=%s",
            ("changed@example.com", account["id"]),
        )
    for reader in (repository, InMemoryUserRepository()):
        changed = reader.find_by_id(account["id"])
        assert changed.name == "Nombre confirmado"
        assert changed.email == "changed@example.com"
        assert changed.role == "tecnico"
        assert changed.company_id is None
        assert changed.status == "deactivated"
        assert reader.find_by_email(EMAIL) is None
        assert reader.find_by_email(changed.email).id == account["id"]
    assert stale.name == "Nombre obsoleto"


def test_operational_rows_are_not_an_alternative_authority(sandbox, account):
    with sandbox.connect() as conn:
        conn.execute(
            "INSERT INTO identity_invitation_accounts "
            "(account_id,name,email,role,status,invitation_status,password_hash) "
            "VALUES (%s,'Vista anterior',%s,'administrador','deactivated',"
            "'accepted','old hash')",
            (account["id"], EMAIL),
        )
        conn.execute(
            "INSERT INTO identity_invitation_accounts "
            "(account_id,name,email,role,status,invitation_status,password_hash) "
            "VALUES (%s,'Solo operativa','operational@example.com','cliente',"
            "'active','accepted','old hash')",
            (str(uuid.uuid4()),),
        )
    repository = InMemoryUserRepository()
    assert repository.find_by_email(EMAIL).role == "cliente"
    assert repository.find_by_email_persistent(EMAIL).password_hash == account["password_hash"]
    assert repository.find_by_email("operational@example.com") is None
    assert repository.find_by_email_persistent("operational@example.com") is None


@pytest.mark.parametrize("lookup", ["id", "email", "email_persistent"])
def test_sql_errors_are_not_replaced_by_cached_users(sandbox, account, lookup):
    repository = InMemoryUserRepository()
    repository.cache_persistent_user(User(**account))
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
    key = account["id"] if lookup == "id" else EMAIL
    with pytest.raises(psycopg.errors.UndefinedTable):
        getattr(repository, f"find_by_{lookup}")(key)


def test_unknown_and_invalid_identifiers_do_not_reach_other_storage(sandbox):
    repository = InMemoryUserRepository()
    assert repository.find_by_id(str(uuid.uuid4())) is None
    assert repository.find_by_id("legacy-not-a-uuid") is None
    assert repository.find_by_email("missing@example.com") is None
    assert repository.find_by_email(None) is None
    assert repository.find_by_id(None) is None


def test_login_and_me_use_existing_non_demo_credentials_from_fresh_repositories(
    client, sandbox, account, monkeypatch
):
    response = client.post("/api/auth/login", json={
        "email": f" {EMAIL.upper()} ", "password": PASSWORD,
    })
    assert response.status_code == 200
    assert response.json() == {
        "id": account["id"], "name": account["name"], "email": EMAIL, "role": "cliente",
    }
    assert response.cookies.get("session")
    # /me usa una instancia vacía distinta, pero la política de sesión no cambia.
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE users SET role='tecnico',email='fresh@example.com' WHERE id=%s",
            (account["id"],),
        )
    current = client.get("/api/auth/me")
    assert current.status_code == 200
    assert current.json() == {
        "id": account["id"], "email": "fresh@example.com", "role": "tecnico",
    }
    with sandbox.connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id=%s",
                           (account["id"],)).fetchone()
    assert row["password_hash"] == account["password_hash"]


@pytest.mark.parametrize("state", ["wrong_password", "deactivated", "pending", "missing"])
def test_login_rejects_ineligible_canonical_account_without_session(
    client, sandbox, account, state
):
    if state == "deactivated":
        statement = "UPDATE users SET status='deactivated' WHERE id=%s"
    elif state == "pending":
        statement = (
            "UPDATE users SET invitation_status='pending',password_hash=NULL,"
            "invitation_token_hash='pending hash',invitation_used_at=NULL,"
            "invitation_expires_at=now()+interval '7 days' WHERE id=%s"
        )
    else:
        statement = None
    if statement:
        with sandbox.connect() as conn:
            conn.execute(statement, (account["id"],))
    response = client.post("/api/auth/login", json={
        "email": "absent@example.com" if state == "missing" else EMAIL,
        "password": "DifferentPassword123" if state == "wrong_password" else PASSWORD,
    })
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid email or password"}
    assert not response.cookies.get("session")
    assert session_store.get_session_store().count() == 0


def test_http_sql_error_is_not_an_invalid_credentials_response(client, sandbox, account):
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
    with pytest.raises(psycopg.errors.UndefinedTable):
        client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert session_store.get_session_store().count() == 0


@pytest.mark.parametrize("lookup", ["id", "email", "email_persistent"])
def test_memory_read_requires_explicit_seam(monkeypatch, lookup):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    key = "legacy-id" if lookup == "id" else EMAIL
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        getattr(InMemoryUserRepository(), f"find_by_{lookup}")(key)


def test_explicit_memory_seam_preserves_legacy_text_ids_and_object_identity(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    user = User(id="legacy-id", name="Cuenta de prueba", email=EMAIL,
                password_hash="test hash", role="cliente")
    repository = InMemoryUserRepository()
    repository.add(user)
    assert repository.find_by_id("legacy-id") is user
    assert repository.find_by_email(EMAIL.upper()) is user
    assert repository.find_by_email_persistent(EMAIL) is user
