"""Casos de uso de invitaciones y aceptacion de cuentas."""

import hashlib
import os
import secrets
import smtplib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Iterator

from app.infrastructure.db import connection
from app.modules.companies.interface.company_status_contract import (
    get_company_status,
)
from app.modules.identity.domain.entities import User, validate_password
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository

INVITATION_LIFETIME = timedelta(hours=168)


class InvitationNotFoundError(ValueError):
    pass


class InvitationValidationError(ValueError):
    pass


class InvitationNotResendableError(ValueError):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_invitation(
    user: User,
    users: InMemoryUserRepository | None = None,
    conn=None,
) -> str:
    before = user.__dict__.copy()
    token = secrets.token_urlsafe(32)
    try:
        user.invitation_token = token
        user.invitation_token_hash = _hash_token(token)
        user.invitation_expires_at = datetime.now(timezone.utc) + INVITATION_LIFETIME
        user.invitation_used_at = None
        if users is not None:
            users.sync_persistent(user, conn)
    except BaseException:
        user.__dict__.clear()
        user.__dict__.update(before)
        raise
    return token


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def _postgres_configured() -> bool:
    """Indica si se solicito explicitamente persistencia PostgreSQL."""
    return bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PASSWORD"))


def _in_memory_fallback_enabled() -> bool:
    return os.getenv("HELPDESK_ALLOW_IN_MEMORY") == "1"


def send_invitation(user: User, token: str) -> str:
    """Entrega una invitacion sin guardar secretos ni devolver el enlace."""
    if not _smtp_configured():
        return "not-attempted"
    try:
        message = EmailMessage()
        message["From"] = os.getenv("SMTP_FROM", "no-reply@helpdesk.local")
        message["To"] = user.email
        message["Subject"] = "Invitación a Help Desk"
        base_url = os.getenv("INVITATION_BASE_URL", "http://localhost:5173")
        message.set_content(f"Acepta tu invitación: {base_url}/invitations/{token}")
        with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))) as smtp:
            if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                smtp.starttls()
            username = os.getenv("SMTP_USERNAME")
            password = os.getenv("SMTP_PASSWORD")
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception:
        return "failed"
    return "sent"


@contextmanager
def _invitation_lock(account_id: str, users: InMemoryUserRepository) -> Iterator[object]:
    """Serializa todas las mutaciones de invitacion de una cuenta.

    El lock es transaccional y usa una clave estable por cuenta, por lo que
    acceptance, desactivacion y rotacion comparten la misma exclusion aunque
    se ejecuten en procesos distintos. El repositorio en memoria solo se usa
    como compatibilidad para los tests que no tienen PostgreSQL configurado;
    no aporta ninguna exclusion local.
    """
    transaction = None
    conn = None
    try:
        transaction = connection()
        conn = transaction.__enter__()
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"identity:account:{account_id}",),
        )
    except Exception as exc:
        if conn is not None:
            transaction.__exit__(type(exc), exc, exc.__traceback__)
        if _postgres_configured() or not _in_memory_fallback_enabled():
            raise
        # In-memory/unit-test installations without PostgreSQL do not require
        # the shared lock. A configured database must never use this fallback.
        with users.lock:
            yield None
        return
    try:
        yield conn
    except BaseException as exc:
        transaction.__exit__(type(exc), exc, exc.__traceback__)
        raise
    else:
        transaction.__exit__(None, None, None)


@contextmanager
def _invitation_change(user: User, users: InMemoryUserRepository):
    """Compensa bajo el lock; el commit SQL también queda dentro del memento."""
    before = None
    try:
        with _invitation_lock(user.id, users) as conn:
            before = user.__dict__.copy()
            try:
                yield conn
            except BaseException:
                users.restore_state(user, before)
                before = None
                raise
    except BaseException:
        if before is not None:
            users.restore_state(user, before)
        raise


def accept_invitation(
    token: str, password: str, users: InMemoryUserRepository
) -> User:
    """Consume exactly one current invitation and establish its hash."""
    token_hash = _hash_token(token)
    candidate = next(
        (candidate for candidate in users.list_all()
         if candidate.invitation_token_hash == token_hash),
        None,
    )
    if candidate is None:
        try:
            account_id = users.find_persistent_account_by_token(token_hash)
        except RuntimeError:
            if _postgres_configured():
                raise
            account_id = None
        if account_id is not None:
            candidate = users.find_by_id(account_id)
    if candidate is None:
        raise InvitationNotFoundError("invitation not found")
    with _invitation_change(candidate, users) as conn:
        # Sin fallback local si falta la fila canónica bajo el lock.
        user = users.load_persistent_for_update(candidate.id, conn) if conn else next(
            (current for current in users.list_all()
             if current.invitation_token_hash == token_hash), None
        )
        now = datetime.now(timezone.utc)
        if (
            user is None
            or user.status != "active"
            or user.invitation_status != "pending"
            or user.invitation_used_at is not None
            or user.invitation_expires_at is None
            or now >= user.invitation_expires_at
            or user.invitation_token_hash != token_hash
        ):
            raise InvitationNotFoundError("invitation not found")
        # Empresa inactiva/token inválido preceden a validar contraseña.
        # None conserva la compatibilidad heredada de HU-19 (RF-139).
        if get_company_status(user.company_id) == "inactive":
            raise InvitationNotFoundError("invitation not found")
        try:
            clean_password = validate_password(password)
        except ValueError as exc:
            raise InvitationValidationError(str(exc)) from exc
        user.password_hash = Argon2PasswordHasher().hash(clean_password)
        user.invitation_status = "accepted"
        user.invitation_used_at = now
        user.invitation_token_hash = None
        user.invitation_expires_at = None
        user.invitation_token = None
        users.sync_persistent(user, conn)
        users.copy_state(candidate, user)
    return candidate


def resend_invitation(user: User, users: InMemoryUserRepository) -> str:
    with _invitation_change(user, users) as conn:
        if conn:
            persisted = users.load_persistent_for_update(user.id, conn)
            if persisted is None:
                raise InvitationNotResendableError("invitation is not resendable")
            users.copy_state(user, persisted)
        if user.status != "active" or user.invitation_status != "pending":
            raise InvitationNotResendableError("invitation is not resendable")
        return issue_invitation(user, users, conn)
