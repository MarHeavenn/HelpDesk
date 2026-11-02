"""Vista de resumen de usuario para otros modulos (HU-06, RF-53).

`find_user_summary` resuelve un usuario existente como `{id, name, email}`.
La vista no incluye rol, hash ni otros datos de credenciales: es lo unico
que `tickets` necesita para componer el objeto `requester` del detalle.

Un identificador no textual o inexistente devuelve `None`, sin revelar si
el usuario existe (mismo criterio que `find_technician` de HU-04).
"""

from dataclasses import dataclass

from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)


@dataclass(frozen=True)
class UserSummary:
    """Vista publica de un usuario: identificador, nombre y correo."""

    id: str
    name: str
    email: str


def find_user_summary(
    user_id: object, users: InMemoryUserRepository
) -> UserSummary | None:
    """Devuelve la vista del usuario o None si no se puede resolver."""
    if not isinstance(user_id, str):
        return None
    user = users.find_by_id(user_id)
    if user is None:
        return None
    return UserSummary(id=user.id, name=user.name, email=user.email)
