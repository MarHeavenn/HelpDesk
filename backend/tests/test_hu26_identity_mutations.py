"""A5b: mutaciones de aplicación, HTTP y carreras en PostgreSQL aislado."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.modules.identity.application.company_accounts import (
    AccountAssociationNotAllowedError,
    associate_account,
)
from app.modules.identity.application.users import (
    LastActiveAdministratorError,
    UserEmailConflictError,
    change_user_role,
    change_user_status,
    update_user,
)
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from test_hu26_identity_atomic_storage import account, sandbox, _reject_write, _rows


PASSWORD = "ExistingMutationPassword123"


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


@pytest.fixture
def state(sandbox, account, password_hash):
    repo = InMemoryUserRepository()
    with sandbox.connect() as conn:
        other_company = str(conn.execute(
            "INSERT INTO companies(name,name_normalized) VALUES ('Otra empresa','otra empresa') RETURNING id"
        ).fetchone()["id"])
    result = {}
    for key, role, company in (
        ("admin", "administrador", account.company_id),
        ("second_admin", "administrador", account.company_id),
        ("client", "cliente", account.company_id),
        ("foreign", "cliente", other_company),
        ("loose", "cliente", None),
    ):
        user = replace(account, id=str(uuid.uuid4()), name=key,
                       email=f"{key}@ordinary.example.com", role=role,
                       company_id=company, password_hash=password_hash)
        repo.add(user)
        result[key] = user
    return result


@pytest.fixture
def client(sandbox, monkeypatch):
    from app.main import app

    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    monkeypatch.setattr(session_store, "_sessions", session_store.InMemorySessionStore())
    with TestClient(app) as client:
        yield client


def _login(client, actor):
    assert client.post("/api/auth/login", json={
        "email": actor.email, "password": PASSWORD,
    }).status_code == 200


def _mutate(kind, user, repository, company):
    if kind == "profile":
        return update_user(user, {"name": "Nombre nuevo", "phone": None}, repository)[0]
    if kind == "email":
        return update_user(user, {"email": "changed@example.com"}, repository)[0]
    if kind == "role":
        return change_user_role(user, "tecnico", repository)
    if kind == "status":
        return change_user_status(user, "deactivated", repository)
    return associate_account(
        company_id=company, account_id=user.id, users=repository, company_status="active",
    )


@pytest.mark.parametrize("kind", ["profile", "email", "role", "status", "association"])
def test_mutation_is_visible_to_independent_reader_and_preserves_other_fields(state, sandbox, kind):
    repository = InMemoryUserRepository()
    target = state["loose"] if kind == "association" else state["client"]
    before = target.__dict__.copy()
    changed = _mutate(kind, target, repository, state["admin"].company_id)
    assert InMemoryUserRepository().find_by_id(target.id) == changed
    canonical, projection = _rows(sandbox)
    assert canonical == projection
    for field in ("password_hash", "created_at", "invitation_status",
                  "invitation_token_hash", "invitation_expires_at", "invitation_used_at"):
        assert getattr(changed, field) == before[field]
    expected = {
        "profile": ("name", "Nombre nuevo"), "email": ("email", "changed@example.com"),
        "role": ("role", "tecnico"), "status": ("status", "deactivated"),
        "association": ("company_id", state["admin"].company_id),
    }[kind]
    assert getattr(changed, expected[0]) == expected[1]


def test_partial_patch_rereads_instead_of_overwriting_concurrent_commits(state, sandbox):
    repository = InMemoryUserRepository()
    stale = state["client"]
    with sandbox.connect() as conn:
        conn.execute("UPDATE users SET phone='fresh phone',role='supervisor' WHERE id=%s",
                     (stale.id,))
    update_user(stale, {"name": "Solo nombre"}, repository)
    fresh = InMemoryUserRepository().find_by_id(stale.id)
    assert (fresh.name, fresh.phone, fresh.role) == ("Solo nombre", "fresh phone", "supervisor")
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


@pytest.mark.parametrize("kind", ["profile", "email", "role", "status", "association"])
@pytest.mark.parametrize("deferred", [False, True], ids=["execute", "commit"])
def test_mutation_failure_restores_retained_object_and_both_rows(
    state, sandbox, monkeypatch, kind, deferred
):
    repository = InMemoryUserRepository()
    target = state["loose"] if kind == "association" else state["client"]
    if kind == "association":
        monkeypatch.setattr(repository, "find_by_id", lambda _: target)
    before, rows = target.__dict__.copy(), _rows(sandbox)
    _reject_write(sandbox, "identity_invitation_accounts", deferred)
    with pytest.raises(psycopg.errors.CheckViolation):
        _mutate(kind, target, repository, state["admin"].company_id)
    assert target.__dict__ == before
    assert _rows(sandbox) == rows


@pytest.mark.parametrize("kind", ["role", "status"])
def test_last_admin_ignores_obsolete_guard_projection(state, sandbox, kind):
    repository = InMemoryUserRepository()
    first = state["admin"]
    change_user_status(first, "deactivated", repository)
    with sandbox.connect() as conn:
        conn.execute("UPDATE identity_active_admin_guard SET active_admin_ids=%s WHERE company_id=%s",
                     ([state["admin"].id, state["second_admin"].id, str(uuid.uuid4())],
                      first.company_id))
    target = InMemoryUserRepository().find_by_id(state["second_admin"].id)
    with pytest.raises(LastActiveAdministratorError):
        _mutate(kind, target, repository, first.company_id)
    assert InMemoryUserRepository().find_by_id(target.id).role == "administrador"
    assert InMemoryUserRepository().find_by_id(target.id).status == "active"


@pytest.mark.parametrize("kinds", [("role", "role"), ("status", "status"), ("role", "status")])
def test_two_admin_removals_from_independent_repositories_preserve_one(state, sandbox, kinds):
    barrier = Barrier(2)

    def worker(key, kind):
        repository = InMemoryUserRepository()
        user = repository.find_by_id(state[key].id)
        barrier.wait(timeout=5)
        try:
            _mutate(kind, user, repository, user.company_id)
            return "ok"
        except LastActiveAdministratorError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, key, kind)
                   for key, kind in zip(("admin", "second_admin"), kinds)]
        assert sorted(f.result(timeout=15) for f in futures) == ["ok", "rejected"]
    admins = [user for user in InMemoryUserRepository().list_all()
              if user.company_id == state["admin"].company_id
              and user.role == "administrador" and user.status == "active"]
    assert len(admins) == 1
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


def test_two_email_updates_cannot_claim_same_address(state, sandbox):
    barrier = Barrier(2)

    def worker(key):
        repository = InMemoryUserRepository()
        user = repository.find_by_id(state[key].id)
        before = user.__dict__.copy()
        barrier.wait(timeout=5)
        try:
            update_user(user, {"email": "shared@example.com"}, repository)
            return "ok"
        except UserEmailConflictError:
            assert user.__dict__ == before
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, key) for key in ("client", "foreign")]
        assert sorted(f.result(timeout=15) for f in futures) == ["conflict", "ok"]
    assert len([u for u in InMemoryUserRepository().list_all() if u.email == "shared@example.com"]) == 1
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


def test_two_associations_cannot_reassign_an_account(state, sandbox):
    barrier = Barrier(2)
    companies = (state["admin"].company_id, state["foreign"].company_id)

    def worker(company):
        repository = InMemoryUserRepository()
        original_find = repository.find_by_id

        def read_before_lock(account_id):
            user = original_find(account_id)
            barrier.wait(timeout=5)  # Ambas instancias leyeron aún sin empresa.
            return user

        repository.find_by_id = read_before_lock
        try:
            associate_account(company_id=company, account_id=state["loose"].id,
                              users=repository, company_status="active")
            return "ok"
        except AccountAssociationNotAllowedError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, company) for company in companies]
        assert sorted(f.result(timeout=15) for f in futures) == ["conflict", "ok"]
    assert InMemoryUserRepository().find_by_id(state["loose"].id).company_id in companies
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


@pytest.mark.parametrize("kind", ["role", "status"])
@pytest.mark.parametrize("deferred", [False, True])
def test_admin_guard_and_account_rollback_together(state, sandbox, kind, deferred):
    user = state["admin"]
    before, rows = user.__dict__.copy(), _rows(sandbox)
    with sandbox.connect() as conn:
        guard_before = conn.execute("SELECT * FROM identity_active_admin_guard").fetchall()
    _reject_write(sandbox, "identity_invitation_accounts", deferred)
    with pytest.raises(psycopg.errors.CheckViolation):
        _mutate(kind, user, InMemoryUserRepository(), user.company_id)
    assert user.__dict__ == before
    assert _rows(sandbox) == rows
    with sandbox.connect() as conn:
        assert conn.execute("SELECT * FROM identity_active_admin_guard").fetchall() == guard_before


@pytest.mark.parametrize("kind", ["profile", "role", "status"])
def test_pending_invitation_is_preserved_or_invalidated_only_by_existing_status_rule(
    state, sandbox, kind
):
    from datetime import datetime, timedelta, timezone

    repository = InMemoryUserRepository()
    pending = replace(state["client"], password_hash=None, invitation_status="pending",
                      invitation_token_hash="original pending hash", invitation_used_at=None,
                      invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    repository.sync_persistent(pending)
    changed = _mutate(kind, pending, repository, pending.company_id)
    assert changed.password_hash is None
    assert changed.invitation_status == "pending"
    if kind == "status":
        assert changed.invitation_token_hash is None
        assert changed.invitation_expires_at is None
    else:
        assert changed.invitation_token_hash == "original pending hash"
        assert changed.invitation_expires_at == pending.invitation_expires_at
    assert InMemoryUserRepository().find_by_id(pending.id) == changed
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


def test_pending_email_commit_failure_restores_original_invitation_and_email(state, sandbox):
    from datetime import datetime, timedelta, timezone

    repository = InMemoryUserRepository()
    pending = replace(state["client"], password_hash=None, invitation_status="pending",
                      invitation_token_hash="original pending hash", invitation_used_at=None,
                      invitation_expires_at=datetime.now(timezone.utc) + timedelta(days=7))
    repository.sync_persistent(pending)
    before, rows = pending.__dict__.copy(), _rows(sandbox)
    _reject_write(sandbox, "identity_invitation_accounts", deferred=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        update_user(pending, {"email": "pending-changed@example.com"}, repository)
    assert pending.__dict__ == before
    assert _rows(sandbox) == rows


def test_association_respects_external_transaction_without_publishing(state, sandbox):
    repository = InMemoryUserRepository()
    with sandbox.connect() as conn:
        result = associate_account(
            company_id=state["admin"].company_id, account_id=state["loose"].id,
            company_status="active", users=repository, conn=conn,
        )
        assert result.company_id == state["admin"].company_id
        assert InMemoryUserRepository().find_by_id(result.id).company_id is None
        conn.rollback()
    assert InMemoryUserRepository().find_by_id(state["loose"].id).company_id is None
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


@pytest.mark.parametrize("kind,method,path,body", [
    ("profile", "patch", "", {"name": "Nombre HTTP", "phone": None}),
    ("email", "patch", "", {"email": "http-changed@example.com"}),
    ("role", "put", "/role", {"role": "tecnico"}),
    ("status", "put", "/status", {"status": "deactivated"}),
])
def test_http_mutations_commit_and_fresh_request_recovers_them(
    client, state, kind, method, path, body, monkeypatch
):
    _login(client, state["admin"])
    response = getattr(client, method)(f"/api/users/{state['client'].id}{path}", json=body)
    assert response.status_code == 200
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    detail = client.get(f"/api/users/{state['client'].id}")
    assert detail.status_code == 200
    for key, value in body.items():
        assert detail.json()[key] == value
    assert not ({"password_hash", "invitation_token_hash", "invitation_token"} & detail.json().keys())
    assert InMemoryUserRepository().find_by_id(state["client"].id).password_hash == state["client"].password_hash


def test_http_errors_keep_auth_tenant_validation_and_conflict_contracts(client, state):
    path = f"/api/users/{state['client'].id}"
    assert client.patch(path, json={"name": "Nuevo"}).status_code == 401
    _login(client, state["client"])
    assert client.patch(path, json={"name": "Nuevo"}).status_code == 404
    _login(client, state["admin"])
    assert client.patch(f"/api/users/{state['foreign'].id}", json={"name": "Nuevo"}).status_code == 404
    assert client.patch(path, json={"name": "x"}).status_code == 422
    assert client.patch(path, json={"email": state["foreign"].email}).status_code == 409


@pytest.mark.parametrize("kind,path,body", [
    ("profile", "", {"name": "No confirmado"}),
    ("role", "/role", {"role": "tecnico"}),
    ("status", "/status", {"status": "deactivated"}),
])
def test_http_commit_failure_never_reports_success(client, state, sandbox, kind, path, body):
    _login(client, state["admin"])
    before = _rows(sandbox)
    _reject_write(sandbox, "identity_invitation_accounts", deferred=True)
    with pytest.raises(psycopg.errors.CheckViolation):
        method = client.patch if kind == "profile" else client.put
        method(f"/api/users/{state['client'].id}{path}", json=body)
    assert _rows(sandbox) == before
