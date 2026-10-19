"""Alta controlada de usuarios con rol (soporte de verificacion de RF-24).

Via interna de `identity`, sin operacion publica (el router no cambia).
Reutiliza las validaciones de nombre y contrasena, el validador de email,
el hash Argon2id y la unicidad de email de HU-01. Solo admite los roles
de gestion `tecnico` y `administrador`, con coincidencia exacta (sin
acentos, mayusculas ni espacios).
"""

import uuid

from app.modules.identity.application.register import (
    EmailAlreadyExistsError,
    RegistrationValidationError,
)
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

PROVISIONABLE_ROLES = frozenset({"tecnico", "administrador"})


def provision_user(
    name: str,
    email: str,
    password: str,
    role: str,
    users: InMemoryUserRepository,
    hasher: Argon2PasswordHasher | None = None,
    validator: EmailValidator | None = None,
) -> User:
    """Crea un usuario con rol `tecnico` o `administrador`.

    Lanza RegistrationValidationError si el rol no es uno de los
    admitidos o si nombre/email/contrasena incumplen las reglas de
    HU-01, y EmailAlreadyExistsError si el email ya existe
    (case-insensitive).
    """
    if not isinstance(role, str) or role not in PROVISIONABLE_ROLES:
        raise RegistrationValidationError(
            "role must be tecnico or administrador"
        )
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
        role=role,
    )
    try:
        users.add(user)
    except EmailAlreadyStoredError as exc:
        raise EmailAlreadyExistsError("email already registered") from exc
    return user
