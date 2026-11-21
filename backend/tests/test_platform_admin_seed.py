"""Semilla del administrador de plataforma y entrega de correo (HU-19, RO-01/RO-02).

Cubre `backend/scripts/seed_platform_admin.py`: alta única con datos de
entorno, reejecución sin cambios, reactivación de una cuenta desactivada
conservando el hash, rechazos sin mutación para una cuenta pendiente, con
otro rol o con empresa, compensación de un alta fallida y permanencia de al
menos un administrador de plataforma activo con acceso posible.

Verifica además el requisito de operación de RO-02: la entrega de correo se
comprueba con un doble de envío (`sent`, `failed`) y sin configuración
(`not-attempted`), y ni el estado devuelto ni la salida de la semilla exponen
el token, el enlace o el hash.
"""

from __future__ import annotations

import smtplib
import uuid

import psycopg
import pytest

from app.infrastructure import db
from app.modules.identity.application.invitations import send_invitation
from app.modules.identity.application.login import login_user
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import (
    Argon2PasswordHasher,
)
from app.modules.identity.infrastructure.session_store import (
    InMemorySessionStore,
)
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)
from migrations.run import apply_migrations
from scripts.seed_platform_admin import (
    CREATED,
    ENV_EMAIL,
    ENV_NAME,
    ENV_PASSWORD,
    REACTIVATED,
    UNCHANGED,
    SeedError,
    format_result,
    main,
    seed_platform_admin,
)

TEST_DOMAIN = "@seedmail.dev"
EMAIL = f"platform.one{TEST_DOMAIN}"
LAST_EMAIL = f"platform.keep{TEST_DOMAIN}"
PASSWORD = "Platform12345"
OTHER_PASSWORD = "OtraClave9876"


class PersistenceFailure(Exception):
    """Fallo de persistencia inyectado (ni RuntimeError ni ValueError)."""


@pytest.fixture(scope="module", autouse=True)
def postgres_ready() -> None:
    """Aplica migraciones cuando hay PostgreSQL; sin él se usa el seam en memoria."""
    if not db.postgres_configured():
        return
    try:
        conn = db.connect()
    except (psycopg.OperationalError, RuntimeError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    try:
        apply_migrations(conn)
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def clean_seed_rows():
    """Deja la tabla compartida sin filas de prueba antes y después de cada caso."""
    _delete_seed_rows()
    yield
    _delete_seed_rows()


@pytest.fixture
def repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


def _delete_seed_rows() -> None:
    if not db.postgres_configured():
        return
    try:
        with db.connection() as conn:
            conn.execute(
                "DELETE FROM identity_invitation_accounts WHERE email LIKE %s",
                (f"%{TEST_DOMAIN}",),
            )
    except (psycopg.OperationalError, RuntimeError):
        pass


def _persistent_rows(email: str = EMAIL) -> list[dict]:
    """Filas del almacén compartido para un correo (vacío sin PostgreSQL)."""
    if not db.postgres_configured():
        return []
    with db.connection() as conn:
        return conn.execute(
            """
            SELECT account_id, company_id, role, status, invitation_status,
                   password_hash, created_at
            FROM identity_invitation_accounts
            WHERE lower(email) = %s
            ORDER BY created_at, account_id
            """,
            (email.lower(),),
        ).fetchall()


def _environment(
    email: str = EMAIL,
    name: str = "Admin Plataforma",
    password: str = PASSWORD,
) -> dict[str, str]:
    return {
        ENV_NAME: name,
        ENV_EMAIL: email,
        ENV_PASSWORD: password,
    }


def _account(
    email: str = EMAIL,
    *,
    role: str = "administrador",
    company_id: str | None = None,
    status: str = "active",
    invitation_status: str = "pending",
    password_hash: str | None = None,
) -> User:
    return User(
        id=str(uuid.uuid4()),
        name="Administradora Semilla",
        email=email,
        password_hash=password_hash,
        role=role,
        company_id=company_id,
        status=status,
        invitation_status=invitation_status,
    )


def _persist(repository: InMemoryUserRepository, user: User) -> None:
    """Persiste el estado del agregado en el almacén configurado."""
    repository.sync_persistent(user)


def test_seed_creates_one_platform_administrator_with_login(repository):
    result = seed_platform_admin(environ=_environment(), users=repository)

    assert result.status == CREATED
    user = result.user
    assert user.role == "administrador"
    assert user.company_id is None
    assert user.status == "active"
    assert user.invitation_status == "accepted"
    assert user.email == EMAIL
    assert user.password_hash and user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash

    assert repository.count() == 1
    assert [candidate.id for candidate in repository.list_all()] == [user.id]

    logged, token = login_user(
        EMAIL, PASSWORD, repository, InMemorySessionStore()
    )
    assert logged.id == user.id
    assert token

    if db.postgres_configured():
        rows = _persistent_rows()
        assert len(rows) == 1
        assert rows[0]["role"] == "administrador"
        assert rows[0]["company_id"] is None
        assert rows[0]["invitation_status"] == "accepted"
        assert rows[0]["password_hash"] == user.password_hash


def test_seed_is_idempotent_and_keeps_existing_data(repository):
    first = seed_platform_admin(environ=_environment(), users=repository)
    snapshot = (
        first.user.id,
        first.user.password_hash,
        first.user.created_at,
        first.user.name,
    )

    second = seed_platform_admin(
        environ=_environment(name="Otro Nombre", password=OTHER_PASSWORD),
        users=repository,
    )

    assert second.status == UNCHANGED
    assert second.user.id == snapshot[0]
    assert second.user.password_hash == snapshot[1]
    assert second.user.created_at == snapshot[2]
    assert second.user.name == snapshot[3]
    assert second.user.status == "active"
    assert repository.count() == 1
    # La contraseña original sigue siendo la válida: no se reescribió el hash.
    login_user(EMAIL, PASSWORD, repository, InMemorySessionStore())
    if db.postgres_configured():
        assert len(_persistent_rows()) == 1


def test_seed_reactivates_deactivated_account_keeping_hash(repository):
    created = seed_platform_admin(environ=_environment(), users=repository)
    account = created.user
    hash_before = account.password_hash
    account.status = "deactivated"
    _persist(repository, account)

    result = seed_platform_admin(
        environ=_environment(password=OTHER_PASSWORD), users=repository
    )

    assert result.status == REACTIVATED
    assert result.user.id == account.id
    assert result.user.status == "active"
    assert result.user.invitation_status == "accepted"
    assert result.user.password_hash == hash_before
    assert repository.count() == 1
    login_user(EMAIL, PASSWORD, repository, InMemorySessionStore())
    if db.postgres_configured():
        rows = _persistent_rows()
        assert len(rows) == 1
        assert rows[0]["status"] == "active"
        assert rows[0]["password_hash"] == hash_before


@pytest.mark.parametrize("status", ["active", "deactivated"])
def test_seed_fails_for_pending_invitation_without_changes(repository, status):
    account = _account(status=status, invitation_status="pending")
    repository.add(account)

    with pytest.raises(SeedError) as error:
        seed_platform_admin(environ=_environment(), users=repository)

    assert "pendiente" in str(error.value)
    assert account.status == status
    assert account.invitation_status == "pending"
    assert account.password_hash is None
    assert repository.count() == 1
    if db.postgres_configured():
        rows = _persistent_rows()
        assert len(rows) == 1
        assert rows[0]["status"] == status
        assert rows[0]["invitation_status"] == "pending"


def test_seed_fails_for_another_role_without_changes(repository):
    account = _account(role="tecnico", invitation_status="accepted",
                       password_hash=Argon2PasswordHasher().hash(PASSWORD))
    repository.add(account)

    with pytest.raises(SeedError):
        seed_platform_admin(environ=_environment(), users=repository)

    assert account.role == "tecnico"
    assert account.status == "active"
    assert repository.count() == 1
    if db.postgres_configured():
        assert len(_persistent_rows()) == 1


def test_seed_fails_for_account_with_company_without_changes(repository):
    account = _account(
        company_id="company-x",
        invitation_status="accepted",
        password_hash=Argon2PasswordHasher().hash(PASSWORD),
    )
    repository.add(account)

    with pytest.raises(SeedError):
        seed_platform_admin(environ=_environment(), users=repository)

    assert account.company_id == "company-x"
    assert account.role == "administrador"
    assert account.status == "active"
    assert repository.count() == 1
    if db.postgres_configured():
        rows = _persistent_rows()
        assert len(rows) == 1
        assert rows[0]["company_id"] == "company-x"


def test_seed_creation_failure_leaves_no_partial_account(
    repository, monkeypatch
):
    def fail(*args, **kwargs):
        raise PersistenceFailure("persistencia no disponible")

    monkeypatch.setattr(repository, "sync_persistent", fail)

    with pytest.raises(PersistenceFailure):
        seed_platform_admin(environ=_environment(), users=repository)

    assert repository.find_by_email(EMAIL) is None
    assert repository.count() == 0
    assert _persistent_rows() == []


def test_seed_reactivation_failure_restores_deactivated_state(
    repository, monkeypatch
):
    account = _account(
        status="deactivated",
        invitation_status="accepted",
        password_hash=Argon2PasswordHasher().hash(PASSWORD),
    )
    repository.add(account)

    def fail(*args, **kwargs):
        raise PersistenceFailure("persistencia no disponible")

    monkeypatch.setattr(repository, "sync_persistent", fail)

    with pytest.raises(PersistenceFailure):
        seed_platform_admin(environ=_environment(), users=repository)

    assert account.status == "deactivated"
    if db.postgres_configured():
        rows = _persistent_rows()
        assert len(rows) == 1
        assert rows[0]["status"] == "deactivated"


def test_seed_detects_account_created_by_another_process():
    if not db.postgres_configured():
        pytest.skip("PostgreSQL no configurado: sin almacén compartido")

    first_process = InMemoryUserRepository()
    seed_platform_admin(environ=_environment(), users=first_process)

    second_process = InMemoryUserRepository()
    result = seed_platform_admin(
        environ=_environment(), users=second_process
    )

    assert result.status == UNCHANGED
    assert result.user.email == EMAIL
    assert len(_persistent_rows()) == 1


@pytest.mark.parametrize("missing", [ENV_EMAIL, ENV_NAME, ENV_PASSWORD])
def test_seed_requires_environment_data(repository, missing):
    environ = _environment()
    environ.pop(missing)

    with pytest.raises(SeedError):
        seed_platform_admin(environ=environ, users=repository)

    assert repository.count() == 0
    assert _persistent_rows() == []


def test_seed_rejects_invalid_environment_data(repository):
    with pytest.raises(SeedError):
        seed_platform_admin(
            environ=_environment(email="no-es-un-correo"), users=repository
        )
    assert repository.count() == 0

    with pytest.raises(SeedError):
        seed_platform_admin(environ=_environment(password="corta"), users=repository)
    assert repository.count() == 0


def test_seed_needs_no_secret_when_account_is_unchanged(repository):
    seed_platform_admin(environ=_environment(), users=repository)

    result = seed_platform_admin(
        environ={ENV_EMAIL: EMAIL}, users=repository
    )

    assert result.status == UNCHANGED


def test_seed_output_exposes_no_credentials(repository, capsys):
    exit_code = main(environ=_environment(), users=repository)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert EMAIL in captured.out
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert "$argon2id$" not in captured.out
    assert "$argon2id$" not in captured.err

    result = seed_platform_admin(environ=_environment(), users=repository)
    message = format_result(result)
    assert PASSWORD not in message
    assert "$argon2id$" not in message
    assert result.user.invitation_token is None


class _SmtpDouble:
    """Doble de `smtplib.SMTP` que registra los mensajes entregados."""

    instances: list["_SmtpDouble"] = []
    fail = False

    def __init__(self, host, port) -> None:
        self.host = host
        self.port = int(port)
        self.messages = []
        _SmtpDouble.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def starttls(self) -> None:
        return None

    def login(self, user, password) -> None:
        return None

    def send_message(self, message) -> None:
        if _SmtpDouble.fail:
            raise RuntimeError("entrega rechazada")
        self.messages.append(message)


def test_email_delivery_reports_three_statuses_without_exposing_token(
    monkeypatch,
):
    account = _account(invitation_status="pending")
    token = "token-de-prueba-que-no-se-expone"

    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert send_invitation(account, token) == "not-attempted"

    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setattr(smtplib, "SMTP", _SmtpDouble)
    _SmtpDouble.fail = False
    _SmtpDouble.instances.clear()

    status = send_invitation(account, token)
    assert status == "sent"
    assert token not in status
    assert "http" not in status.lower()
    delivered = _SmtpDouble.instances[-1].messages
    assert len(delivered) == 1
    # El enlace solo viaja en el correo entregado, nunca en el estado devuelto.
    assert token in delivered[0].get_content()

    _SmtpDouble.fail = True
    failed = send_invitation(account, token)
    assert failed == "failed"
    assert token not in failed
    assert "http" not in failed.lower()


def test_platform_administrator_remains_active_after_the_suite(repository):
    result = seed_platform_admin(
        environ=_environment(email=LAST_EMAIL), users=repository
    )
    assert result.status == CREATED

    active = [
        account
        for account in repository.list_all()
        if account.role == "administrador"
        and account.company_id is None
        and account.status == "active"
        and account.invitation_status == "accepted"
        and account.password_hash
    ]
    assert len(active) == 1
    login_user(LAST_EMAIL, PASSWORD, repository, InMemorySessionStore())

    if db.postgres_configured():
        rows = _persistent_rows(LAST_EMAIL)
        assert len(rows) == 1
        assert rows[0]["role"] == "administrador"
        assert rows[0]["company_id"] is None
        assert rows[0]["status"] == "active"
