"""Casos de uso de consulta y gestion de cuentas de un tenant."""

import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from app.modules.companies.interface.company_status_contract import (
    get_company_status,
)
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


class InactiveCompanyError(ValueError):
    """La empresa esta inactiva: no admite altas nuevas de cuentas (RF-136)."""


class LastActiveAdministratorError(ValueError):
    """La operacion dejaria la empresa sin administrador activo."""


@contextmanager
def _account_change(user: User, users: InMemoryUserRepository, conn=None):
    """Relee bajo lock y compensa también fallos al confirmar el contexto."""
    before = user.__dict__.copy()
    transaction = (
        _invitation_lock(user.id, users) if conn is None
        else users.locked_account(user.id, conn)
    )
    try:
        with transaction as active:
            if active:
                persisted = users.load_persistent_for_update(user.id, active)
                if persisted is not None:
                    users.copy_state(user, persisted)
            yield active
    except BaseException:
        users.restore_state(user, before)
        raise


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
    conn=None,
) -> User:
    """Crea una cuenta pendiente con invitacion de 168 h.

    `conn` permite que el alta participe en la transaccion del llamador
    (HU-19 RF-135: empresa y administrador inicial atomicos).
    """
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
    # RF-136: una empresa inactiva solo bloquea las altas nuevas y se evalúa
    # en el escalón de conflictos, después del 422 estructural y de dominio.
    # RF-139: solo bloquea el estado persistido exactamente `inactive`; un
    # estado `None` (empresa heredada sin fila en `companies`, como
    # `company_id="c1"` en fixtures de HU-13) NO bloquea.
    if get_company_status(company_id) == "inactive":
        raise InactiveCompanyError("empresa no activa")
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
        transaction = (
            _invitation_lock(user.id, users) if conn is None
            else users.locked_account(user.id, conn)
        )
        with transaction as active:
            users.add(user, active)
            issue_invitation(user, users, active)
    except EmailAlreadyStoredError as exc:
        users.remove(user.id)
        raise UserEmailConflictError("correo no disponible") from exc
    except BaseException:
        # SQL revierte por el contexto; el seam no debe retener un alta a medias.
        users.remove(user.id)
        raise
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
        clean_name = validate_name(changes["name"]) if "name" in changes else None
        clean_email = EmailValidator().validate(changes["email"]) if "email" in changes else None
    except ValueError as exc:
        raise UserManagementValidationError(str(exc)) from exc
    try:
        with _account_change(user, users) as conn:
            email_changed = clean_email is not None and clean_email != user.email
            if email_changed:
                existing = users.find_by_email(clean_email)
                if existing is not None and existing.id != user.id:
                    raise UserEmailConflictError("correo no disponible")
            if "name" in changes:
                user.name = clean_name
            if "phone" in changes:
                user.phone = changes["phone"]
            if email_changed:
                users.update_email(user, clean_email)
                if user.invitation_status == "pending":
                    issue_invitation(user, users, conn)
            users.sync_persistent(user, conn)
    except EmailAlreadyStoredError as exc:
        raise UserEmailConflictError("correo no disponible") from exc
    return user, ("not-attempted" if email_changed and user.invitation_status == "pending" else None)


def change_user_role(user: User, role: str, users: InMemoryUserRepository) -> User:
    if role not in ALLOWED_ROLES:
        raise UserManagementValidationError("role is invalid")
    with _account_change(user, users) as conn:
        if user.role == "administrador" or role == "administrador":
            try:
                users.commit_admin_mutation(user, new_role=role, conn=conn)
            except LastActiveAdministratorPersistenceError as exc:
                raise LastActiveAdministratorError(str(exc)) from exc
        user.role = role
        users.sync_persistent(user, conn)
    return user


def change_user_status(user: User, status: str, users: InMemoryUserRepository) -> User:
    if status not in {"active", "deactivated"}:
        raise UserManagementValidationError("status is invalid")
    with _account_change(user, users) as conn:
        if user.status == status:
            return user
        if user.role == "administrador":
            try:
                users.commit_admin_mutation(user, new_status=status, conn=conn)
            except LastActiveAdministratorPersistenceError as exc:
                raise LastActiveAdministratorError(str(exc)) from exc
        user.status = status
        if status == "deactivated" and user.invitation_status == "pending":
            user.invitation_token_hash = None
            user.invitation_expires_at = None
            user.invitation_token = None
        users.sync_persistent(user, conn)
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
