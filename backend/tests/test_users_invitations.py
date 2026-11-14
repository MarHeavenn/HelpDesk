import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
import app.modules.identity.infrastructure.user_repository as user_repository
import app.modules.identity.application.invitations as invitations


def _admin() -> User:
    user = User(
        id="admin", name="Administrador", email="admin@example.com",
        password_hash=Argon2PasswordHasher().hash("Secreta123"),
        role="administrador", company_id="c1", status="active",
        invitation_status="accepted",
    )
    get_user_repository().add(user)
    return user


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    get_user_repository().clear()
    get_session_store().clear()
    monkeypatch.delenv("SMTP_HOST", raising=False)
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _admin_client() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "Secreta123"}
    )
    assert response.status_code == 200
    return client


def test_invitation_is_168_hours_single_use_and_acceptance_preserves_password():
    _admin()
    client = _admin_client()
    created = client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    assert created.status_code == 201
    user = get_user_repository().find_by_email("invite@example.com")
    assert user is not None
    assert user.invitation_expires_at - datetime.now(timezone.utc) <= timedelta(hours=168)
    token = user.invitation_token
    assert token

    accepted = TestClient(app).post(
        f"/api/invitations/{token}/accept", json={"password": "  exact pass  "}
    )
    assert accepted.status_code == 200
    assert accepted.json()["invitation_status"] == "accepted"
    assert user.password_hash and user.password_hash != "  exact pass  "
    assert get_user_repository().find_by_id(user.id).invitation_token_hash is None
    assert TestClient(app).post(
        f"/api/invitations/{token}/accept", json={"password": "anotherpass"}
    ).status_code == 404


def test_invalid_invitation_is_404_before_password_validation_and_resend_rotates():
    _admin()
    client = _admin_client()
    created = client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    old_token = user.invitation_token
    resent = client.post(f"/api/users/{user.id}/invitation/resend")
    assert resent.status_code == 200
    assert set(resent.json()) == {"user", "email_status"}
    assert resent.json()["email_status"] == "not-attempted"
    assert TestClient(app).post(
        f"/api/invitations/{old_token}/accept", json={"password": "short"}
    ).status_code == 404


def test_acceptance_rejects_expired_token_and_pending_cannot_login():
    _admin()
    client = _admin_client()
    client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    user.invitation_expires_at = datetime.now(timezone.utc) - timedelta(microseconds=1)
    get_user_repository().sync_persistent(user)
    token = user.invitation_token
    assert TestClient(app).post(
        f"/api/invitations/{token}/accept", json={"password": "validpass"}
    ).status_code == 404
    assert TestClient(app).post(
        "/api/auth/login", json={"email": user.email, "password": "validpass"}
    ).status_code == 401


@pytest.mark.parametrize("smtp_result", ["sent", "failed"])
def test_configured_smtp_reports_delivery_state(monkeypatch, smtp_result):
    _admin()
    client = _admin_client()
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            if smtp_result == "failed":
                raise OSError("delivery failed")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def starttls(self):
            pass
        def send_message(self, message):
            pass

    monkeypatch.setattr(invitations.smtplib, "SMTP", FakeSMTP)
    response = client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    assert response.status_code == 201
    assert response.json()["email_status"] == smtp_result
    assert "Invitation-Delivery" not in response.headers
    assert "token" not in response.text.lower()


@pytest.mark.parametrize("smtp_result", ["sent", "failed", "not-attempted"])
def test_email_status_contract_covers_pending_patch_and_explicit_resend(
    monkeypatch, smtp_result
):
    _admin()
    client = _admin_client()
    if smtp_result == "not-attempted":
        monkeypatch.delenv("SMTP_HOST", raising=False)
    else:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.test")

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                if smtp_result == "failed":
                    raise OSError("delivery failed")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self):
                pass

            def send_message(self, message):
                pass

        monkeypatch.setattr(invitations.smtplib, "SMTP", FakeSMTP)

    created = client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    patched = client.patch(
        f"/api/users/{user.id}", json={"email": "changed@example.com"}
    )
    resent = client.post(f"/api/users/{user.id}/invitation/resend")

    assert created.status_code == 201
    assert patched.status_code == 200
    assert resent.status_code == 200
    assert created.json()["email_status"] == smtp_result
    assert patched.json()["email_status"] == smtp_result
    assert resent.json()["email_status"] == smtp_result
    assert "Invitation-Delivery" not in patched.headers
    assert "Invitation-Delivery" not in resent.headers


def test_email_status_is_absent_from_non_invitation_user_responses():
    _admin()
    client = _admin_client()
    created = client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")

    assert "email_status" not in client.get("/api/users").json()[0]
    assert "email_status" not in client.get(f"/api/users/{user.id}").json()
    assert "email_status" not in client.patch(
        f"/api/users/{user.id}", json={"name": "Otro nombre"}
    ).json()
    assert "email_status" not in client.put(
        f"/api/users/{user.id}/status", json={"status": "deactivated"}
    ).json()
    assert "email_status" not in TestClient(app).post(
        f"/api/invitations/{user.invitation_token}/accept",
        json={"password": "validpass"},
    ).json()
    assert "email_status" in created.json()


def test_configured_postgres_lock_failure_aborts_acceptance_without_memory_mutation(
    monkeypatch,
):
    _admin()
    client = _admin_client()
    client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    before = user.__dict__.copy()
    token = user.invitation_token
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")

    class BrokenConnection:
        def execute(self, *args, **kwargs):
            raise RuntimeError("lock failed")

    class Transaction:
        def __enter__(self):
            return BrokenConnection()

        def __exit__(self, exc_type, exc, traceback):
            self.exit_args = (exc_type, exc)
            return False

    transaction = Transaction()
    monkeypatch.setattr(invitations, "connection", lambda: transaction)

    with pytest.raises(RuntimeError, match="lock failed"):
        invitations.accept_invitation(token, "validpass", get_user_repository())

    assert user.__dict__ == before
    assert transaction.exit_args[0] is RuntimeError


def test_configured_postgres_connection_failure_aborts_resend_without_memory_mutation(
    monkeypatch,
):
    _admin()
    client = _admin_client()
    client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    before = user.__dict__.copy()
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")

    def broken_connection():
        raise OSError("connection failed")

    monkeypatch.setattr(invitations, "connection", broken_connection)
    monkeypatch.setattr(user_repository, "connection", broken_connection)

    with pytest.raises(OSError, match="connection failed"):
        invitations.resend_invitation(user, get_user_repository())

    assert user.__dict__ == before


def test_issue_invitation_restores_memory_when_persistence_fails(monkeypatch):
    user = User(
        id="unit-user", name="Invitado", email="unit@example.com",
        password_hash=None, role="cliente", company_id="c1",
        status="active", invitation_status="pending",
    )
    before = user.__dict__.copy()
    repository = get_user_repository()

    def fail(*args, **kwargs):
        raise OSError("persist failed")

    monkeypatch.setattr(repository, "sync_persistent", fail)
    with pytest.raises(OSError, match="persist failed"):
        invitations.issue_invitation(user, repository, object())
    assert user.__dict__ == before


def test_concurrent_acceptance_has_at_most_one_success():
    _admin()
    admin_client = _admin_client()
    admin_client.post(
        "/api/users",
        json={"name": "Invitado", "email": "invite@example.com", "role": "cliente"},
    )
    user = get_user_repository().find_by_email("invite@example.com")
    from concurrent.futures import ThreadPoolExecutor

    def accept():
        return TestClient(app).post(
            f"/api/invitations/{user.invitation_token}/accept",
            json={"password": "validpass"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: accept(), range(2)))
    assert sorted(statuses) == [200, 404]
