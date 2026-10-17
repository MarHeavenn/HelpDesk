"""Caso de uso de inicio de sesion (RF-5, RF-6, RF-9, RF-10).

Orquesta validacion estructural -> normalizacion -> busqueda ->
verificacion -> creacion de sesion. Toda la regla de negocio vive aqui
y en el dominio; la interfaz solo comunica.

- RF-5: el email se normaliza (trim + minusculas, igual que en el
  registro); la contrasena se usa intacta, sin trim ni modificacion.
- RF-6: lo estructuralmente invalido eleva LoginValidationError (la
  interfaz lo traduce a 422) ANTES de comprobar credenciales; con
  credenciales invalidas se eleva InvalidCredentialsError con un unico
  mensaje generico identico, sin revelar si el correo existe.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.modules.identity.domain.entities import (
    Session,
    User,
    validate_password,
)
from app.modules.identity.infrastructure.email_validator import EmailValidator
from app.modules.identity.infrastructure.password_hasher import (
    Argon2PasswordHasher,
)
from app.modules.identity.infrastructure.session_store import (
    InMemorySessionStore,
    hash_token,
)
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)

INVALID_CREDENTIALS_MESSAGE = "invalid email or password"

SESSION_LIFETIME = timedelta(hours=24)


class LoginValidationError(ValueError):
    """La solicitud incumple la validacion estructural (RF-6 -> 422)."""


class InvalidCredentialsError(ValueError):
    """Credenciales invalidas con mensaje generico identico (RF-6 -> 401)."""


def login_user(
    email: str,
    password: str,
    users: InMemoryUserRepository,
    sessions: InMemorySessionStore,
    hasher: Argon2PasswordHasher | None = None,
    validator: EmailValidator | None = None,
) -> tuple[User, str]:
    """Verifica credenciales y crea una sesion opaca de servidor.

    Devuelve (usuario, token en claro para la cookie). Lanza
    LoginValidationError si la solicitud es estructuralmente invalida
    (sin comprobar credenciales) e InvalidCredentialsError con el mismo
    mensaje generico si el correo no esta registrado o la contrasena es
    incorrecta.
    """
    try:
        clean_email = (validator or EmailValidator()).validate(email)
        clean_password = validate_password(password)
    except ValueError as exc:
        if isinstance(exc, LoginValidationError):
            raise
        raise LoginValidationError(str(exc)) from exc
    user = users.find_by_email(clean_email)
    if user is None:
        raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)
    if not (hasher or Argon2PasswordHasher()).verify(
        user.password_hash, clean_password
    ):
        raise InvalidCredentialsError(INVALID_CREDENTIALS_MESSAGE)
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    sessions.add(
        Session(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
    )
    return user, token
