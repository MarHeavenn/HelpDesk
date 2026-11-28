"""A4: directorios y DTO de identidad desde SQL, sin datos demo ni escritores."""

import os
import unicodedata
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.infrastructure import db
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from app.modules.identity.interface import (
    administrators_contract,
    company_account_contract as accounts_contract,
    technicians_contract,
    users_contract,
)
from hu26_sql_support import IsolatedPostgres


PASSWORD = "ExistingDirectoryPassword123"
USER_KEYS = {
    "id", "name", "email", "phone", "company_id", "role", "status", "invitation_status",
}
UNASSIGNED_KEYS = {"id", "name", "email", "role", "status"}


@pytest.fixture
def sandbox(monkeypatch):
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A4 SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    with IsolatedPostgres(dsn) as isolated:
        monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
        monkeypatch.setattr(db, "connect", isolated.connect)
        yield isolated


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


@pytest.fixture
def directory(sandbox, password_hash):
    rows = [
        ("admin_a", "administrador", "a", "active", "accepted", "Admin A", 2),
        ("admin_a_pending", "administrador", "a", "active", "pending", "Invitada A", 1),
        ("admin_a_off", "administrador", "a", "deactivated", "accepted", "Admin inactiva", 1),
        ("admin_a_off_pending", "administrador", "a", "deactivated", "pending", "Invitada inactiva", 0),
        ("supervisor_a", "supervisor", "a", "active", "accepted", "Supervisión A", 3),
        ("tech_a", "tecnico", "a", "active", "accepted", "Técnica A", 4),
        ("tech_a_pending", "tecnico", "a", "active", "pending", "Técnica invitada", 4),
        ("tech_a_off", "tecnico", "a", "deactivated", "accepted", "Técnica inactiva", 5),
        ("client_a", "cliente", "a", "active", "accepted", "Cliente A", 6),
        ("admin_b", "administrador", "b", "active", "accepted", "Admin B", 2),
        ("tech_b", "tecnico", "b", "active", "accepted", "Técnica B", 3),
        ("client_b", "cliente", "b", "active", "accepted", "Cliente B", 4),
        ("platform", "administrador", None, "active", "accepted", "Plataforma", 0),
        ("loose_tech", "tecnico", None, "active", "accepted", "  ÁLVARO ", 1),
        ("loose_client", "cliente", None, "deactivated", "accepted", "A\u0301lvaro", 1),
        ("loose_supervisor", "supervisor", None, "active", "pending", "Zeta", 2),
        ("loose_admin", "administrador", None, "active", "pending", "Otra plataforma", 3),
    ]
    created = datetime(2025, 1, 10, tzinfo=timezone.utc)
    companies = {}
    with sandbox.connect() as conn:
        for key in ("a", "b"):
            companies[key] = str(conn.execute(
                "INSERT INTO companies (name,name_normalized) VALUES (%s,%s) RETURNING id",
                (f"Empresa {key}", f"empresa {key}"),
            ).fetchone()["id"])
        result = {}
        for index, (key, role, scope, status, invitation, name, days) in enumerate(rows):
            result[key] = {
                "id": str(uuid.UUID(int=index + 1)),
                "company_id": companies.get(scope),
                "name": name,
                "email": f"{key}@ordinary.example.com",
                "password_hash": password_hash if invitation == "accepted" else None,
                "phone": "+57 555 0202",
                "role": role,
                "status": status,
                "invitation_status": invitation,
                "invitation_token_hash": f"test invitation hash {key}" if invitation == "pending" else None,
                "invitation_expires_at": created + timedelta(days=7) if invitation == "pending" else None,
                "invitation_used_at": created if invitation == "accepted" else None,
                "created_at": created + timedelta(days=days),
            }
        # Orden físico deliberadamente distinto del orden contratado.
        for row in reversed(list(result.values())):
            conn.execute(
                """INSERT INTO users
                   (id,company_id,name,email,password_hash,phone,role,status,
                    invitation_status,invitation_token_hash,invitation_expires_at,
                    invitation_used_at,created_at)
                   VALUES (%(id)s,%(company_id)s,%(name)s,%(email)s,%(password_hash)s,
                           %(phone)s,%(role)s,%(status)s,%(invitation_status)s,
                           %(invitation_token_hash)s,%(invitation_expires_at)s,
                           %(invitation_used_at)s,%(created_at)s)""",
                row,
            )
    return result


@pytest.fixture
def client(sandbox, monkeypatch):
    from app.main import app

    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    monkeypatch.setattr(session_store, "_sessions", session_store.InMemorySessionStore())
    with TestClient(app) as test_client:
        yield test_client


def _scope(directory, company):
    return directory[f"admin_{company}"]["company_id"] if company else None


def _members(directory, company_id):
    return [row for row in directory.values() if row["company_id"] == company_id]


def _login(client, row):
    response = client.post("/api/auth/login", json={
        "email": row["email"], "password": PASSWORD,
    })
    assert response.status_code == 200


def test_independent_list_readers_recover_every_canonical_field(directory):
    expected = {row["id"]: {**row, "invitation_token": None} for row in directory.values()}
    for reader in (InMemoryUserRepository(), InMemoryUserRepository()):
        actual = reader.list_all()
        assert {user.id: user.__dict__ for user in actual} == expected
        assert reader.count() == 0  # No hidratar el caché al consultar.


def test_list_rereads_commits_without_cache_or_operational_fallback(
    sandbox, directory, monkeypatch
):
    reader = InMemoryUserRepository()
    stale = User(**directory["tech_a"])
    reader.cache_persistent_user(stale)
    assert len(reader.list_all()) == len(directory)
    with sandbox.connect() as conn:
        conn.execute("UPDATE users SET name='Cambio confirmado',company_id=NULL WHERE id=%s",
                     (stale.id,))
        conn.execute(
            "INSERT INTO identity_invitation_accounts "
            "(account_id,name,email,role,status,invitation_status,password_hash) "
            "VALUES ('operational-only','No canónica','operational@example.com',"
            "'tecnico','active','accepted','test hash')"
        )
    for repository in (reader, InMemoryUserRepository()):
        monkeypatch.setattr(user_repository, "_users", repository)
        users = {user.id: user for user in repository.list_all()}
        assert len(users) == len(directory)
        assert users[stale.id].name == "Cambio confirmado"
        assert users[stale.id].company_id is None
        assert {item.id for item in technicians_contract.get_technician_directory(
            directory["admin_a"]["company_id"]
        )} == {directory["tech_a_pending"]["id"]}
    assert stale.company_id == directory["tech_a"]["company_id"]
    assert stale.name == directory["tech_a"]["name"]


@pytest.mark.parametrize("company", ["a", "b", None])
def test_company_stats_and_administrator_views_preserve_states_and_order(
    directory, company, monkeypatch
):
    company_id = _scope(directory, company)
    for repository in (InMemoryUserRepository(), InMemoryUserRepository()):
        monkeypatch.setattr(user_repository, "_users", repository)
        members = _members(directory, company_id) if company else []
        assert asdict(accounts_contract.get_company_account_stats(company_id)) == {
            "users_total": len(members),
            "has_administrator": bool(company),
            "administrator_invitation_pending": company == "a",
        }
        administrators = sorted(
            (row for row in members if row["role"] == "administrador"),
            key=lambda row: (row["created_at"], row["id"]),
        )
        assert [asdict(item) for item in accounts_contract.list_company_administrators(
            company_id
        )] == [{
            key: row[key] for key in ("id", "created_at", "status", "invitation_status")
        } for row in administrators]
        assert set(administrators_contract.list_company_administrator_ids(company_id)) == {
            row["id"] for row in _members(directory, company_id)
            if row["role"] == "administrador" and row["status"] == "active"
        }


def test_company_stats_reread_confirmed_invitation_and_status(sandbox, directory, monkeypatch):
    repository = InMemoryUserRepository()
    monkeypatch.setattr(user_repository, "_users", repository)
    company_id = _scope(directory, "a")
    assert accounts_contract.get_company_account_stats(company_id).administrator_invitation_pending
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE users SET status='deactivated' WHERE company_id=%s AND role='administrador'",
            (company_id,),
        )
    assert asdict(accounts_contract.get_company_account_stats(company_id)) == {
        "users_total": 9, "has_administrator": False, "administrator_invitation_pending": False,
    }
    assert administrators_contract.list_company_administrator_ids(company_id) == []


def test_unassigned_contract_preserves_normalized_order_and_minimal_fields(directory, monkeypatch):
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    expected = sorted(
        (row for row in directory.values()
         if row["company_id"] is None and row["role"] != "administrador"),
        key=lambda row: (unicodedata.normalize("NFC", row["name"].strip()).lower(), row["id"]),
    )
    assert [asdict(item) for item in accounts_contract.list_unassigned_accounts()] == [
        {key: row[key] for key in UNASSIGNED_KEYS} for row in expected
    ]


@pytest.mark.parametrize("company", ["a", "b", None])
def test_technician_and_user_contracts_use_canonical_minimal_views(
    directory, company, monkeypatch
):
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    company_id = _scope(directory, company)
    expected = [
        row for row in directory.values()
        if row["role"] == "tecnico" and row["status"] == "active"
        and (company_id is None or row["company_id"] == company_id)
    ]
    assert {item.id: asdict(item) for item in technicians_contract.get_technician_directory(
        company_id
    )} == {row["id"]: {"id": row["id"], "name": row["name"]} for row in expected}
    tech = directory["tech_a"]
    assert asdict(technicians_contract.get_technician_summary(tech["id"])) == {
        "id": tech["id"], "name": tech["name"],
    }
    assert asdict(users_contract.get_user_summary(tech["id"])) == {
        key: tech[key] for key in ("id", "name", "email")
    }
    candidate = technicians_contract.get_technician_assignment_candidate(tech["id"], company_id)
    if company_id == tech["company_id"]:
        assert asdict(candidate) == {"id": tech["id"], "name": tech["name"], "eligible": True}
    else:
        assert candidate is None
    inactive = directory["tech_a_off"]
    assert not technicians_contract.get_technician_assignment_candidate(
        inactive["id"], inactive["company_id"]
    ).eligible
    assert technicians_contract.get_technician_summary(directory["client_a"]["id"]) is None
    assert users_contract.get_user_summary(str(uuid.uuid4())) is None


@pytest.mark.parametrize("actor", [
    "admin_a", "admin_b", "supervisor_a", "tech_a", "client_a", "platform", "loose_tech",
])
def test_http_directories_keep_existing_permissions_and_tenant_boundaries(
    client, directory, actor, monkeypatch
):
    row = directory[actor]
    _login(client, row)
    # Instancia vacía tras el login: ningún permiso/directorio depende del proceso previo.
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    users = client.get("/api/users")
    technicians = client.get("/api/technicians")
    unassigned = client.get("/api/users/unassigned")
    if row["role"] == "administrador" and row["company_id"] is not None:
        assert users.status_code == 200
        expected = _members(directory, row["company_id"])
        assert {item["id"] for item in users.json()} == {item["id"] for item in expected}
        assert all(set(item) == USER_KEYS for item in users.json())
    else:
        assert users.status_code == 404
        assert users.json() == {"detail": "user not found"}
    if row["role"] in {"administrador", "supervisor"} and row["company_id"] is not None:
        assert technicians.status_code == 200
        expected = [item for item in _members(directory, row["company_id"])
                    if item["role"] == "tecnico" and item["status"] == "active"]
        assert {item["id"]: item for item in technicians.json()} == {
            item["id"]: {"id": item["id"], "name": item["name"]} for item in expected
        }
    else:
        assert technicians.status_code == 404
        assert technicians.json() == {"detail": "technicians not found"}
    if actor == "platform":
        assert unassigned.status_code == 200
        expected = sorted(
            (item for item in directory.values()
             if item["company_id"] is None and item["role"] != "administrador"),
            key=lambda item: (
                unicodedata.normalize("NFC", item["name"].strip()).lower(), item["id"]
            ),
        )
        assert unassigned.json() == [
            {key: item[key] for key in UNASSIGNED_KEYS} for item in expected
        ]
        assert all(set(item) == UNASSIGNED_KEYS for item in unassigned.json())
    else:
        assert unassigned.status_code == 404
        assert unassigned.json() == {"detail": "user not found"}


@pytest.mark.parametrize("company,other", [("a", "b"), ("b", "a")])
def test_http_user_detail_retains_own_and_foreign_not_found_contract(
    client, directory, company, other
):
    _login(client, directory[f"admin_{company}"])
    own = directory[f"client_{company}"]
    detail = client.get(f"/api/users/{own['id']}")
    assert detail.status_code == 200
    assert detail.json() == {key: own[key] for key in USER_KEYS}
    for user_id in (directory[f"client_{other}"]["id"], str(uuid.uuid4())):
        response = client.get(f"/api/users/{user_id}")
        assert response.status_code == 404
        assert response.json() == {"detail": "user not found"}


@pytest.mark.parametrize("path", ["/api/users", "/api/technicians", "/api/users/unassigned"])
def test_http_directory_requires_valid_session_before_listing(client, path, monkeypatch):
    def forbidden_list():
        pytest.fail("No se debe listar sin una sesión válida")

    monkeypatch.setattr(user_repository.get_user_repository(), "list_all", forbidden_list)
    assert client.get(path).status_code == 401
    client.cookies.set("session", "invalid-session")
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("query", [
    "list", "stats", "administrators", "active_administrators", "unassigned",
    "technicians", "email_exists",
])
def test_directory_contracts_propagate_sql_errors(sandbox, directory, monkeypatch, query):
    repository = InMemoryUserRepository()
    repository.cache_persistent_user(User(**directory["admin_a"]))
    monkeypatch.setattr(user_repository, "_users", repository)
    company_id = _scope(directory, "a")
    calls = {
        "list": repository.list_all,
        "stats": lambda: accounts_contract.get_company_account_stats(company_id),
        "administrators": lambda: accounts_contract.list_company_administrators(company_id),
        "active_administrators": lambda: administrators_contract.list_company_administrator_ids(company_id),
        "unassigned": accounts_contract.list_unassigned_accounts,
        "technicians": lambda: technicians_contract.get_technician_directory(company_id),
        "email_exists": lambda: accounts_contract.account_email_exists(directory["admin_a"]["email"]),
    }
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE users RENAME TO unavailable_users")
    with pytest.raises(psycopg.errors.UndefinedTable):
        calls[query]()


def test_email_existence_contract_keeps_malformed_and_missing_results(directory, monkeypatch):
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    assert accounts_contract.account_email_exists(directory["admin_a"]["email"])
    assert not accounts_contract.account_email_exists("absent@example.com")
    assert not accounts_contract.account_email_exists(None)


def test_listing_requires_explicit_memory_seam(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        InMemoryUserRepository().list_all()


def test_explicit_memory_listing_keeps_legacy_order_and_references(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    repository = InMemoryUserRepository()
    second = User(id="legacy-z", name="Segunda", email="second@example.com",
                  role="cliente", password_hash="test hash")
    first = User(id="legacy-a", name="Primera", email="first@example.com",
                 role="tecnico", password_hash="test hash")
    repository.add(second)
    repository.add(first)
    result = repository.list_all()
    assert result == [second, first]
    assert result[0] is second
    result.pop()
    assert len(repository.list_all()) == 2
