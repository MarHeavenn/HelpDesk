import pytest
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event, local

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from app.modules.identity.application.users import (
    LastActiveAdministratorError,
    change_user_status,
)
from app.modules.identity.application.invitations import (
    InvitationNotFoundError,
    InvitationNotResendableError,
    accept_invitation,
    issue_invitation,
    resend_invitation,
)
from app.infrastructure.db import connection


def _user(user_id, email, role, company="c1", *, status="active", invitation="accepted"):
    user = User(
        id=user_id,
        name="Usuario Test",
        email=email,
        password_hash=Argon2PasswordHasher().hash("Secreta123"),
        role=role,
        company_id=company,
        status=status,
        invitation_status=invitation,
    )
    get_user_repository().add(user)
    return user


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()


def _client_for(user):
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": user.email, "password": "Secreta123"}
    )
    assert response.status_code == 200
    return client


def test_patch_is_partial_supports_null_and_is_idempotent_without_delivery_field():
    admin = _user("admin", "admin@example.com", "administrador")
    target = _user("target", "target@example.com", "cliente")
    client = _client_for(admin)

    response = client.patch(
        f"/api/users/{target.id}", json={"name": " Nuevo ", "phone": None}
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "id", "name", "email", "phone", "company_id", "role", "status", "invitation_status"
    }
    assert response.json()["name"] == "Nuevo"
    assert response.json()["phone"] is None

    before = response.json()
    repeated = client.patch(f"/api/users/{target.id}", json={"name": "Nuevo"})
    assert repeated.status_code == 200
    assert repeated.json() == before
    assert "email_status" not in repeated.json()


@pytest.mark.parametrize("body", [{}, {"password": "leak"}, {"phone": 12}, {"name": "x"}])
def test_patch_rejects_empty_extra_and_invalid_without_mutation(body):
    admin = _user("admin", "admin@example.com", "administrador")
    target = _user("target", "target@example.com", "cliente")
    client = _client_for(admin)
    before = (target.name, target.email, target.phone)
    response = client.patch(f"/api/users/{target.id}", json=body)
    assert response.status_code == 422
    assert (target.name, target.email, target.phone) == before


def test_pending_email_change_returns_email_status_and_normalizes_email():
    admin = _user("admin", "admin@example.com", "administrador")
    target = _user(
        "target", "target@example.com", "cliente", status="active", invitation="pending"
    )
    client = _client_for(admin)
    response = client.patch(
        f"/api/users/{target.id}", json={"email": " NEW@example.com "}
    )
    assert response.status_code == 200
    assert set(response.json()) == {"user", "email_status"}
    assert response.json()["email_status"] == "not-attempted"
    assert response.headers.get("Invitation-Delivery") is None
    assert response.json()["user"]["email"] == "new@example.com"


def test_role_and_status_are_separate_and_last_active_admin_is_protected():
    admin = _user("admin", "admin@example.com", "administrador")
    target = _user("target", "target@example.com", "cliente")
    client = _client_for(admin)

    role = client.put(f"/api/users/{target.id}/role", json={"role": "supervisor"})
    assert role.status_code == 200
    assert role.json()["role"] == "supervisor"
    status = client.put(f"/api/users/{target.id}/status", json={"status": "deactivated"})
    assert status.status_code == 200
    assert status.json()["status"] == "deactivated"

    blocked = client.put(f"/api/users/{admin.id}/status", json={"status": "deactivated"})
    assert blocked.status_code == 409
    assert blocked.json() == {"detail": "at least one active administrator is required"}


def test_deactivation_revokes_sessions_and_non_admin_cannot_edit():
    admin = _user("admin", "admin@example.com", "administrador")
    target = _user("target", "target@example.com", "cliente")
    admin_client = _client_for(admin)
    target_client = _client_for(target)
    response = admin_client.put(
        f"/api/users/{target.id}/status", json={"status": "deactivated"}
    )
    assert response.status_code == 200
    assert target_client.get("/api/users").status_code == 401


def test_status_restores_memory_when_persistence_sync_fails(monkeypatch):
    user = _user("target", "target@example.com", "cliente")
    before = user.__dict__.copy()

    @contextmanager
    def configured_lock(account_id, repository):
        yield object()

    monkeypatch.setattr(
        "app.modules.identity.application.users._invitation_lock",
        configured_lock,
    )
    monkeypatch.setattr(
        get_user_repository(),
        "load_persistent_for_update",
        lambda account_id, conn: None,
    )
    monkeypatch.setattr(
        get_user_repository(),
        "sync_persistent",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("persist failed")),
    )

    with pytest.raises(OSError, match="persist failed"):
        change_user_status(user, "deactivated", get_user_repository())
    assert user.__dict__ == before


def test_last_active_admin_is_serialized_across_independent_repositories():
    """La garantía no puede depender del singleton ni de un lock de proceso."""
    company = "concurrent-company"
    first = InMemoryUserRepository()
    second = InMemoryUserRepository()
    admins = [
        User(
            id=f"admin-{index}",
            name="Administrador",
            email=f"admin-{index}@example.com",
            password_hash="hash",
            role="administrador",
            company_id=company,
            status="active",
            invitation_status="accepted",
        )
        for index in (1, 2)
    ]
    for admin in admins:
        first.add(admin)
        second.add(User(**admin.__dict__))

    def deactivate(repository, user):
        try:
            change_user_status(user, "deactivated", repository)
            return "ok"
        except LastActiveAdministratorError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                deactivate,
                (first, second),
                (admins[0], second.find_by_id(admins[1].id)),
            )
        )

    assert sorted(results) == ["ok", "rejected"]


@pytest.mark.skipif(not __import__("os").environ.get("DATABASE_URL"), reason="requires PostgreSQL")
def test_invitation_acceptance_and_deactivation_reread_shared_state():
    first = InMemoryUserRepository()
    second = InMemoryUserRepository()
    user = User(
        id="00000000-0000-0000-0000-000000000131",
        name="Invitado",
        email="invite-131@example.com",
        password_hash=None,
        role="cliente",
        company_id="company-131",
        status="active",
        invitation_status="pending",
    )
    first.add(user)
    second.add(User(**user.__dict__))
    token = issue_invitation(user)
    first.sync_persistent(user)

    accepted = accept_invitation(token, "Secreta123", first)
    assert accepted.invitation_status == "accepted"

    stale = second.find_by_id(user.id)
    assert stale is not None
    changed = change_user_status(stale, "deactivated", second)
    assert changed.status == "deactivated"

    with pytest.raises(InvitationNotFoundError):
        accept_invitation(token, "OtraClave123", second)


@pytest.mark.skipif(not __import__("os").environ.get("DATABASE_URL"), reason="requires PostgreSQL")
def test_invitation_rotation_and_acceptance_use_independent_shared_state():
    first = InMemoryUserRepository()
    second = InMemoryUserRepository()
    user = User(
        id="00000000-0000-0000-0000-000000000132",
        name="Invitado",
        email="invite-132@example.com",
        password_hash=None,
        role="cliente",
        company_id="company-132",
        status="active",
        invitation_status="pending",
    )
    first.add(user)
    second.add(User(**user.__dict__))
    old_token = issue_invitation(user)
    first.sync_persistent(user)

    rotated = __import__(
        "app.modules.identity.application.invitations", fromlist=["resend_invitation"]
    ).resend_invitation(second.find_by_id(user.id), second)
    assert rotated != old_token

    with pytest.raises(InvitationNotFoundError):
        accept_invitation(old_token, "Secreta123", first)

    accepted = accept_invitation(rotated, "Secreta123", first)
    assert accepted.invitation_status == "accepted"


def _persistent_invitation_user(account_id: str) -> tuple[
    InMemoryUserRepository, InMemoryUserRepository, User, str
]:
    first = InMemoryUserRepository()
    second = InMemoryUserRepository()
    user = User(
        id=account_id,
        name="Invitado",
        email=f"{account_id}@example.com",
        password_hash=None,
        role="cliente",
        company_id=f"company-{account_id}",
        status="active",
        invitation_status="pending",
    )
    first.add(user)
    token = issue_invitation(user, first)
    second.add(User(**user.__dict__))
    return first, second, user, token


def _read_invitation_state(account_id: str) -> User:
    """Lee el estado final usando un repositorio y conexión distintos."""
    third = InMemoryUserRepository()
    with connection() as conn:
        state = third.load_persistent_for_update(account_id, conn)
    assert state is not None
    return state


def _run_controlled_interleaving(
    monkeypatch,
    *,
    holder: str,
    operations: dict[str, callable],
) -> dict[str, object]:
    """Arranca ambos workers y pausa al que obtiene primero el advisory lock."""
    import app.modules.identity.application.invitations as invitation_module
    import app.modules.identity.application.users as users_module

    start = Barrier(2)
    holder_acquired = Event()
    contender_attempted = Event()
    release_holder = Event()
    worker_context = local()
    real_lock = invitation_module._invitation_lock

    @contextmanager
    def controlled_lock(account_id, users):
        role = worker_context.role
        if role != holder:
            contender_attempted.set()
        with real_lock(account_id, users) as conn:
            if role == holder:
                holder_acquired.set()
                assert release_holder.wait(timeout=5)
            yield conn

    monkeypatch.setattr(invitation_module, "_invitation_lock", controlled_lock)
    monkeypatch.setattr(users_module, "_invitation_lock", controlled_lock)

    def worker(role: str):
        worker_context.role = role
        start.wait(timeout=5)
        if role != holder:
            assert holder_acquired.wait(timeout=5)
        try:
            return operations[role]()
        except Exception as exc:  # return outcomes without hiding the interleaving
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(worker, role)
            for role in ("acceptance", "other")
        }
        assert holder_acquired.wait(timeout=5)
        assert contender_attempted.wait(timeout=5)
        release_holder.set()
        return {role: futures[role].result(timeout=10) for role in futures}


@pytest.mark.skipif(not __import__("os").environ.get("DATABASE_URL"), reason="requires PostgreSQL")
@pytest.mark.parametrize("holder", ["acceptance", "other"])
def test_real_concurrent_acceptance_and_deactivation_are_serialized(
    monkeypatch, holder
):
    first, second, user, token = _persistent_invitation_user(
        f"00000000-0000-0000-0000-0000000002{1 if holder == 'acceptance' else '2'}"
    )

    outcomes = _run_controlled_interleaving(
        monkeypatch,
        holder=holder,
        operations={
            "acceptance": lambda: accept_invitation(token, "Secreta123", first),
            "other": lambda: change_user_status(
                second.find_by_id(user.id), "deactivated", second
            ),
        },
    )

    accepted = outcomes["acceptance"]
    deactivated = outcomes["other"]
    assert sum(isinstance(value, User) for value in outcomes.values()) <= 2
    assert isinstance(deactivated, User)
    assert deactivated.status == "deactivated"
    final = _read_invitation_state(user.id)
    assert final.status == "deactivated"
    if isinstance(accepted, User):
        assert accepted.invitation_status == "accepted"
        assert final.invitation_status == "accepted"
        assert final.invitation_used_at is not None
    else:
        assert isinstance(accepted, InvitationNotFoundError)
        assert final.invitation_status == "pending"
        assert final.invitation_used_at is None
    assert final.invitation_token_hash is None


@pytest.mark.skipif(not __import__("os").environ.get("DATABASE_URL"), reason="requires PostgreSQL")
@pytest.mark.parametrize("holder", ["acceptance", "other"])
def test_real_concurrent_acceptance_and_resend_rotate_or_consume_once(
    monkeypatch, holder
):
    first, second, user, old_token = _persistent_invitation_user(
        f"00000000-0000-0000-0000-0000000003{1 if holder == 'acceptance' else '2'}"
    )

    outcomes = _run_controlled_interleaving(
        monkeypatch,
        holder=holder,
        operations={
            "acceptance": lambda: accept_invitation(old_token, "Secreta123", first),
            "other": lambda: resend_invitation(
                second.find_by_id(user.id), second
            ),
        },
    )

    if isinstance(outcomes["acceptance"], User):
        assert isinstance(outcomes["other"], (InvitationNotResendableError, str))
        final = _read_invitation_state(user.id)
        assert final.invitation_status == "accepted"
        assert final.invitation_token_hash is None
    else:
        assert isinstance(outcomes["acceptance"], InvitationNotFoundError)
        assert isinstance(outcomes["other"], str)
        final = _read_invitation_state(user.id)
        assert final.invitation_status == "pending"
        assert final.invitation_token_hash is not None
        assert final.invitation_token_hash != __import__(
            "hashlib"
        ).sha256(old_token.encode("utf-8")).hexdigest()
    with pytest.raises(InvitationNotFoundError):
        accept_invitation(old_token, "Secreta123", InMemoryUserRepository())
