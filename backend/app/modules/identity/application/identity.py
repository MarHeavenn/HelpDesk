"""Caso de uso de identidad actual (RF-7, RF-10).

Resuelve el usuario dueno de una sesion opaca de servidor. Toda la
regla de negocio vive aqui y en el dominio; la interfaz solo comunica.

Una sesion es valida cuando existe, no esta revocada (`revoked_at`
es None) y no esta expirada (`now < expires_at`). Cualquier otro
caso eleva InvalidSessionError (la interfaz lo traduce a 401).
"""

from datetime import datetime, timezone

from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.session_store import (
    InMemorySessionStore,
)
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)


class InvalidSessionError(ValueError):
    """Sesion ausente, desconocida, revocada o expirada (RF-7 -> 401)."""


def get_current_identity(
    token: str | None,
    users: InMemoryUserRepository,
    sessions: InMemorySessionStore,
    now: datetime | None = None,
) -> User:
    """Devuelve el usuario dueno de la sesion del token.

    Lanza InvalidSessionError si no hay token, la sesion no existe,
    esta revocada o expirada, o su usuario ya no existe.
    """
    if not token or not isinstance(token, str):
        raise InvalidSessionError("not authenticated")
    session = sessions.find_by_token(token)
    checked_at = now or datetime.now(timezone.utc)
    if session is None or not session.is_valid(checked_at):
        raise InvalidSessionError("not authenticated")
    user = users.find_by_id(session.user_id)
    if user is None:
        raise InvalidSessionError("not authenticated")
    return user
