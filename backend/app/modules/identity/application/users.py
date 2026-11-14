"""Casos de uso de consulta y gestion de cuentas de un tenant."""

import uuid
from datetime import datetime, timezone

from app.modules.identity.domain.entities import User, validate_name
from app.modules.identity.infrastructure.email_validator import EmailValidator
from app.modules.identity.infrastructure.user_repository import (
    EmailAlreadyStoredError,
    InMemoryUserRepository,
    LastActiveAdministratorPersistenceError,
)
from app.modules.identity.application.invitations import issue_invitation, _invitation_lock

ALLOWED_ROLES = frozenset({"cliente", "tecnico", "supervisor", "administrador"})


class UserNotVisibleError(ValueError):
    """El usuario no pertenece al tenant visible para el actor."""


class UserManagementValidationError(ValueError):
    """Los datos de alta no cumplen las reglas de dominio."""


class UserEmailConflictError(ValueError):
    """El correo ya está registrado, sin revelar su propietario."""


class LastActiveAdministratorError(ValueError):
    """La operacion dejaria la empresa sin administrador activo."""


def visible_user(user: User, company_id: str | None) -> bool:
    return company_id is not None and user.company_id == company_id


def list_visible_users(users: InMemoryUserRepository, company_id: str | None) -> list[User]:
    if company_id is None:
        raise UserNotVisibleError("user not found")
    return [user for user in users.list_all() if visible_user(user, company_id)]


def find_visible_user(
    user_id: str, users: InMemoryUserRepository, company_id: str | None
) -> User:
    user = users.find_by_id(user_id)
    if user is None or not visible_user(user, company_id):
        raise UserNotVisibleError("user not found")
    return user


def create_user(
    *,
    name: str,
    email: str,
    role: str,
    phone: str | None,
    company_id: str | None,
    users: InMemoryUserRepository,
) -> User:
    if company_id is None:
        raise UserNotVisibleError("user not found")
    try:
        clean_name = validate_name(name)
        clean_email = EmailValidator().validate(email)
    except ValueError as exc:
        raise UserManagementValidationError(str(exc)) from exc
    if role not in ALLOWED_ROLES:
        raise UserManagementValidationError("role is invalid")
    if users.find_by_email(clean_email) is not None:
        raise UserEmailConflictError("correo no disponible")
    user = User(
        id=str(uuid.uuid4()),
        name=clean_name,
        email=clean_email,
        password_hash=None,
        role=role,
        company_id=company_id,
        phone=phone,
        status="active",
        invitation_status="pending",
    )
    try:
        users.add(user)
    except EmailAlreadyStoredError as exc:
        raise UserEmailConflictError("correo no disponible") from exc
    issue_invitation(user, users)
    return user


def update_user(
    user: User,
    changes: dict,
    users: InMemoryUserRepository,
) -> tuple[User, str | None]:
    """Aplica un PATCH validado y devuelve el estado opcional de invitacion."""
    if not changes:
        raise UserManagementValidationError("at least one field is required")
    try:
        clean_name = validate_name(changes["name"]) if "name" in changes else user.name
        clean_email = EmailValidator().validate(changes["email"]) if "email" in changes else user.email
    except ValueError as exc:
        raise UserManagementValidationError(str(exc)) from exc
    phone = changes["phone"] if "phone" in changes else user.phone
    email_changed = clean_email != user.email
    if email_changed and users.find_by_email(clean_email) not in (None, user):
        raise UserEmailConflictError("correo no disponible")
    with _invitation_lock(user.id, users) as conn:
        if conn:
            persisted = users.load_persistent_for_update(user.id, conn)
            if persisted is not None:
                users.copy_state(user, persisted)
        user.name = clean_name
        user.phone = phone
        if email_changed:
            try:
                users.update_email(user, clean_email)
            except EmailAlreadyStoredError as exc:
                raise UserEmailConflictError("correo no disponible") from exc
            if user.invitation_status == "pending":
                issue_invitation(user, users, conn)
    return user, ("not-attempted" if email_changed and user.invitation_status == "pending" else None)


def change_user_role(user: User, role: str, users: InMemoryUserRepository) -> User:
    if role not in ALLOWED_ROLES:
        raise UserManagementValidationError("role is invalid")
    with users.lock:
        if user.role == "administrador" or role == "administrador":
            try:
                users.commit_admin_mutation(user, new_role=role)
            except LastActiveAdministratorPersistenceError as exc:
                raise LastActiveAdministratorError(str(exc)) from exc
        user.role = role
    return user


def change_user_status(user: User, status: str, users: InMemoryUserRepository) -> User:
    if status not in {"active", "deactivated"}:
        raise UserManagementValidationError("status is invalid")
    before = user.__dict__.copy()
    try:
        with _invitation_lock(user.id, users) as conn:
            if conn:
                persisted = users.load_persistent_for_update(user.id, conn)
                if persisted is not None:
                    users.copy_state(user, persisted)
            if user.status == status:
                return user
            if user.role == "administrador":
                try:
                    users.commit_admin_mutation(user, new_status=status, conn=conn)
                except LastActiveAdministratorPersistenceError as exc:
                    raise LastActiveAdministratorError(str(exc)) from exc
            user.status = status
            if status == "deactivated":
                user.invitation_status = "accepted" if user.invitation_status == "accepted" else user.invitation_status
                if user.invitation_status == "pending":
                    user.invitation_token_hash = None
                    user.invitation_expires_at = None
                    user.invitation_token = None
            if conn:
                users.sync_persistent(user, conn)
    except BaseException:
        user.__dict__.clear()
        user.__dict__.update(before)
        raise
    return user


def _ensure_another_active_admin(user: User, users: InMemoryUserRepository) -> None:
    if not any(
        candidate is not user
        and candidate.company_id == user.company_id
        and candidate.role == "administrador"
        and candidate.status == "active"
        for candidate in users.list_all()
    ):
        raise LastActiveAdministratorError("at least one active administrator is required")
