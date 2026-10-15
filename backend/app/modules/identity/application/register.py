"""Caso de uso de registro de usuarios (RF-1, RF-2, RF-3, RF-4, RF-9).

Orquesta validacion -> unicidad -> hash -> creacion. Toda la regla de
negocio vive aqui y en el dominio; la interfaz solo comunica.
"""

import uuid

from app.modules.identity.domain.entities import (
    User,
    validate_name,
    validate_password,
)
from app.modules.identity.infrastructure.email_validator import EmailValidator
from app.modules.identity.infrastructure.password_hasher import (
    Argon2PasswordHasher,
)
from app.modules.identity.infrastructure.user_repository import (
    EmailAlreadyStoredError,
    InMemoryUserRepository,
)

CLIENT_ROLE = "cliente"


class RegistrationValidationError(ValueError):
    """Alguna regla de validacion de RF-2 o RF-3 se incumplio."""


class EmailAlreadyExistsError(ValueError):
    """El email (case-insensitive) ya esta registrado (RF-4)."""


def register_user(
    name: str,
    email: str,
    password: str,
    role: str,
    users: InMemoryUserRepository,
    hasher: Argon2PasswordHasher | None = None,
    validator: EmailValidator | None = None,
) -> User:
    """Crea un usuario con rol cliente.

    Lanza RegistrationValidationError si el rol no es cliente (RF-2, sin
    valor por defecto) o si nombre/email/contrasena incumplen RF-3, y
    EmailAlreadyExistsError si el email ya existe (RF-4).
    """
    if role != CLIENT_ROLE:
        raise RegistrationValidationError("role must be cliente")
    try:
        clean_name = validate_name(name)
        clean_password = validate_password(password)
        clean_email = (validator or EmailValidator()).validate(email)
    except ValueError as exc:
        if isinstance(exc, RegistrationValidationError):
            raise
        raise RegistrationValidationError(str(exc)) from exc
    if users.find_by_email(clean_email) is not None:
        raise EmailAlreadyExistsError("email already registered")
    user = User(
        id=str(uuid.uuid4()),
        name=clean_name,
        email=clean_email,
        password_hash=(hasher or Argon2PasswordHasher()).hash(clean_password),
        role=CLIENT_ROLE,
    )
    try:
        users.add(user)
    except EmailAlreadyStoredError as exc:
        raise EmailAlreadyExistsError("email already registered") from exc
    return user
