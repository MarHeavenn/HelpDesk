"""A5c: ciclo completo de invitaciones sobre esquemas SQL exclusivos."""

import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Event

import psycopg
import pytest

from app.modules.identity.application import invitations, users as user_cases
from app.modules.identity.application.invitations import (
    InvitationNotFoundError, InvitationNotResendableError,
    accept_invitation, resend_invitation,
)
from app.modules.identity.application.users import create_user, UserEmailConflictError
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from app.modules.identity.infrastructure import user_repository
from test_hu26_identity_atomic_storage import account, sandbox, _rows, _reject_write
from test_hu26_identity_mutations import state, password_hash, client, _login, PASSWORD


def _create(repository, company_id, conn=None):
    return create_user(name="Invitada ordinaria", email="invited@ordinary.example.com",
                       role="tecnico", phone="+57 555 0404", company_id=company_id,
                       users=repository, conn=conn)


@pytest.fixture
def invitation(state):
    return _create(InMemoryUserRepository(), state["admin"].company_id)


def test_create_is_durable_with_168_hour_lifetime_without_persisting_clear_token(
    state, sandbox
):
    started = datetime.now(timezone.utc)
    user = _create(InMemoryUserRepository(), state["admin"].company_id)
    confirmed = InMemoryUserRepository().find_by_id(user.id)
    assert confirmed.invitation_token is None
    assert confirmed.password_hash is None
    assert confirmed.invitation_token_hash == hashlib.sha256(user.invitation_token.encode()).hexdigest()
    assert started + timedelta(hours=168) <= confirmed.invitation_expires_at
    assert confirmed.invitation_expires_at <= datetime.now(timezone.utc) + timedelta(hours=168)
    assert confirmed.invitation_used_at is None
    canonical, projection = _rows(sandbox)
    assert canonical == projection
    assert user.invitation_token not in str(canonical)


@pytest.mark.parametrize("deferred", [False, True], ids=["execute", "commit"])
def test_failed_invitation_issuance_rolls_back_the_initial_account(
    state, sandbox, deferred
):
    with sandbox.connect() as conn:
        conn.execute(
            """CREATE FUNCTION reject_invited_state() RETURNS trigger LANGUAGE plpgsql AS $$
               BEGIN
                 IF NEW.invitation_token_hash IS NOT NULL THEN
                   RAISE EXCEPTION 'invitation write failed' USING ERRCODE='23514';
                 END IF;
                 RETURN NEW;
               END $$"""
        )
        timing = "AFTER" if deferred else "BEFORE"
        constraint = "CONSTRAINT " if deferred else ""
        mode = "DEFERRABLE INITIALLY DEFERRED " if deferred else ""
        conn.execute(
            f"CREATE {constraint}TRIGGER reject_invited {timing} INSERT OR UPDATE "
            f"ON identity_invitation_accounts {mode}FOR EACH ROW "
            "EXECUTE FUNCTION reject_invited_state()"
        )
    before = _rows(sandbox)
    repository = InMemoryUserRepository()
    with pytest.raises(psycopg.errors.CheckViolation):
        _create(repository, state["admin"].company_id)
    assert _rows(sandbox) == before
    assert repository.find_by_email("invited@ordinary.example.com") is None
    assert repository.count() == 0


def test_creation_with_external_transaction_never_confirms_it(state, sandbox):
    repository = InMemoryUserRepository()
    before = _rows(sandbox)
    with sandbox.connect() as conn:
        user = _create(repository, state["admin"].company_id, conn)
        assert conn.execute("SELECT id FROM users WHERE id=%s", (user.id,)).fetchone()
        assert InMemoryUserRepository().find_by_id(user.id) is None
        conn.rollback()
    assert _rows(sandbox) == before


def test_failed_external_issuance_cannot_leave_an_account_after_caught_error(
    state, sandbox, monkeypatch
):
    repository = InMemoryUserRepository()
    before = _rows(sandbox)

    def fail(*args, **kwargs):
        raise RuntimeError("issuance unavailable")

    monkeypatch.setattr(user_cases, "issue_invitation", fail)
    with sandbox.connect() as conn:
        with pytest.raises(RuntimeError, match="issuance unavailable"):
            _create(repository, state["admin"].company_id, conn)
        conn.execute("SELECT 1")  # El llamador conserva una transacción utilizable.
    assert _rows(sandbox) == before


def test_duplicate_does_not_reissue_or_reset_an_existing_account(invitation, sandbox):
    before = _rows(sandbox)
    with pytest.raises(UserEmailConflictError):
        _create(InMemoryUserRepository(), invitation.company_id)
    assert _rows(sandbox) == before


def test_fresh_instance_accepts_once_preserving_identity_and_existing_dates(
    invitation, sandbox
):
    before = InMemoryUserRepository().find_by_id(invitation.id)
    result = accept_invitation(invitation.invitation_token, "  ExactPassword123  ",
                               InMemoryUserRepository())
    assert result.invitation_status == "accepted"
    assert result.invitation_token is None
    assert result.invitation_token_hash is None
    assert result.invitation_expires_at is None
    assert result.invitation_used_at is not None
    assert result.password_hash and result.password_hash != "  ExactPassword123  "
    for field in ("id", "company_id", "name", "email", "phone", "role", "status", "created_at"):
        assert getattr(result, field) == getattr(before, field)
    assert InMemoryUserRepository().find_by_id(result.id) == result
    with pytest.raises(InvitationNotFoundError):
        accept_invitation(invitation.invitation_token, "AnotherPassword123",
                          InMemoryUserRepository())
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


@pytest.mark.parametrize("operation", ["accept", "resend"])
@pytest.mark.parametrize("deferred", [False, True], ids=["execute", "commit"])
def test_failure_restores_original_invitation_and_retained_object(
    invitation, sandbox, monkeypatch, operation, deferred
):
    repository = InMemoryUserRepository()
    retained = repository.find_by_id(invitation.id)
    before, rows = retained.__dict__.copy(), _rows(sandbox)
    # Este doble conserva la referencia; relectura bloqueada y escritura son SQL reales.
    monkeypatch.setattr(repository, "list_all", lambda: [retained])
    _reject_write(sandbox, "identity_invitation_accounts", deferred)
    with pytest.raises(psycopg.errors.CheckViolation):
        if operation == "accept":
            accept_invitation(invitation.invitation_token, PASSWORD, repository)
        else:
            resend_invitation(retained, repository)
    assert retained.__dict__ == before
    assert _rows(sandbox) == rows


def test_resend_rotates_only_pending_token_and_refreshes_lifetime(invitation, sandbox):
    repository = InMemoryUserRepository()
    original = repository.find_by_id(invitation.id)
    started = datetime.now(timezone.utc)
    token = resend_invitation(original, repository)
    assert token != invitation.invitation_token
    fresh = InMemoryUserRepository().find_by_id(original.id)
    assert fresh.invitation_expires_at >= started + timedelta(hours=168)
    assert fresh.password_hash == original.password_hash is None
    assert fresh.created_at == invitation.created_at
    assert fresh.role == invitation.role
    assert fresh.company_id == invitation.company_id
    with pytest.raises(InvitationNotFoundError):
        accept_invitation(invitation.invitation_token, "short", InMemoryUserRepository())
    accept_invitation(token, PASSWORD, InMemoryUserRepository())
    with pytest.raises(InvitationNotResendableError):
        resend_invitation(InMemoryUserRepository().find_by_id(original.id),
                          InMemoryUserRepository())


@pytest.mark.parametrize("invalid", ["expired", "deactivated", "used", "inactive_company"])
def test_unusable_token_is_404_before_password_validation_and_remains_unchanged(
    invitation, sandbox, monkeypatch, invalid
):
    repository = InMemoryUserRepository()
    user = repository.find_by_id(invitation.id)
    if invalid == "expired":
        user.invitation_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif invalid == "deactivated":
        user.status = "deactivated"
    elif invalid == "used":
        user.invitation_used_at = datetime.now(timezone.utc)
    else:
        # Frontera del propietario de empresas; sus lecturas SQL son A6.
        monkeypatch.setattr(invitations, "get_company_status", lambda _: "inactive")
    repository.sync_persistent(user)
    before = _rows(sandbox)
    with pytest.raises(InvitationNotFoundError):
        accept_invitation(invitation.invitation_token, "short", InMemoryUserRepository())
    assert _rows(sandbox) == before


def test_accept_does_not_fall_back_when_locked_canonical_row_is_missing(
    invitation, sandbox, monkeypatch
):
    repository = InMemoryUserRepository()
    retained = repository.find_by_id(invitation.id)
    before = _rows(sandbox)
    monkeypatch.setattr(repository, "list_all", lambda: [retained])
    monkeypatch.setattr(repository, "load_persistent_for_update", lambda *_: None)
    with pytest.raises(InvitationNotFoundError):
        accept_invitation(invitation.invitation_token, PASSWORD, repository)
    assert _rows(sandbox) == before


@pytest.mark.parametrize("other", ["accept", "resend", "deactivate"])
@pytest.mark.parametrize("holder", ["accept", "other"])
def test_controlled_invitation_races_use_one_account_lock(
    invitation, sandbox, monkeypatch, other, holder
):
    acquired, attempted, release = Event(), Event(), Event()
    real_lock = invitations._invitation_lock
    repositories = {"accept": InMemoryUserRepository(), "other": InMemoryUserRepository()}

    @contextmanager
    def controlled_lock(account_id, repository):
        key = "accept" if repository is repositories["accept"] else "other"
        if key != holder:
            attempted.set()
        with real_lock(account_id, repository) as conn:
            if key == holder:
                acquired.set()
                assert release.wait(timeout=10)
            yield conn

    monkeypatch.setattr(invitations, "_invitation_lock", controlled_lock)
    monkeypatch.setattr(user_cases, "_invitation_lock", controlled_lock)

    def worker(key):
        repository = repositories[key]
        try:
            if key == "accept" or other == "accept":
                return accept_invitation(invitation.invitation_token, PASSWORD, repository)
            user = repository.find_by_id(invitation.id)
            if other == "resend":
                return resend_invitation(user, repository)
            return user_cases.change_user_status(user, "deactivated", repository)
        except (InvitationNotFoundError, InvitationNotResendableError) as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, holder)
        assert acquired.wait(timeout=10)
        second = pool.submit(worker, "other" if holder == "accept" else "accept")
        try:
            assert attempted.wait(timeout=10)
        finally:
            release.set()
        outcomes = {holder: first.result(timeout=15),
                    ("other" if holder == "accept" else "accept"): second.result(timeout=15)}
    fresh = InMemoryUserRepository().find_by_id(invitation.id)
    if other == "accept":
        assert sum(not isinstance(value, Exception) for value in outcomes.values()) == 1
        assert fresh.invitation_status == "accepted"
    elif other == "resend":
        if holder == "accept":
            assert isinstance(outcomes["other"], InvitationNotResendableError)
            assert fresh.invitation_status == "accepted"
        else:
            assert isinstance(outcomes["accept"], InvitationNotFoundError)
            assert fresh.invitation_status == "pending"
    else:
        assert fresh.status == "deactivated"
        assert fresh.invitation_status == ("accepted" if holder == "accept" else "pending")
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


def test_http_create_resend_accept_and_login_do_not_expose_secrets(
    client, state, monkeypatch, sandbox
):
    # Captura de entrega interna: nunca extraer token de una representación HTTP.
    import app.modules.identity.interface.users_router as users_router
    deliveries = []
    monkeypatch.setattr(users_router, "send_invitation",
                        lambda user, token: deliveries.append(token) or "not-attempted")
    _login(client, state["admin"])
    created = client.post("/api/users", json={
        "name": "Invitada HTTP", "email": "http-invite@ordinary.example.com", "role": "tecnico",
    })
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]
    duplicate = client.post("/api/users", json={
        "name": "Invitada HTTP", "email": "http-invite@ordinary.example.com", "role": "tecnico",
    })
    assert duplicate.status_code == 409
    assert len(deliveries) == 1
    old = deliveries[-1]
    resent = client.post(f"/api/users/{user_id}/invitation/resend")
    assert resent.status_code == 200
    current = deliveries[-1]
    assert old != current
    assert old not in created.text and current not in resent.text
    assert "password_hash" not in resent.text and "invitation_token" not in resent.text
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    assert client.post(f"/api/invitations/{old}/accept", json={"password": "short"}).status_code == 404
    invalid = client.post(f"/api/invitations/{current}/accept", json={"password": "short"})
    assert invalid.status_code == 422
    accepted = client.post(f"/api/invitations/{current}/accept", json={"password": PASSWORD})
    assert accepted.status_code == 200
    assert "password_hash" not in accepted.text and "invitation_token" not in accepted.text
    assert client.post("/api/auth/login", json={
        "email": "http-invite@ordinary.example.com", "password": PASSWORD,
    }).status_code == 200
    assert _rows(sandbox)[0] == _rows(sandbox)[1]


def test_new_process_resolves_pending_invitation_from_sql_without_seed(invitation, sandbox):
    program = """
import json, sys
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
data = json.load(sys.stdin)
repo = InMemoryUserRepository()
user = repo.find_by_id(data["id"])
assert user and user.invitation_status == "pending"
assert repo.find_persistent_account_by_token(data["hash"]) == user.id
assert repo.count() == 0
print("canonical invitation recovered")
"""
    env = dict(os.environ)
    env["DATABASE_URL"] = sandbox.scoped_dsn
    env.pop("POSTGRES_PASSWORD", None)
    env.pop("HU26_TEST_DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-c", program], env=env,
        input=json.dumps({"id": invitation.id, "hash": invitation.invitation_token_hash}),
        text=True, capture_output=True, timeout=15,
    )
    assert result.returncode == 0, "El proceso aislado no recuperó la invitación"
    assert result.stdout.strip() == "canonical invitation recovered"
