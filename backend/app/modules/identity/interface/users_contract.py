"""Frontera de `identity` hacia otros modulos para resolver usuarios.

Une `find_user_summary` con el repositorio compartido de `identity` y
devuelve solo la vista `UserSummary` (id, nombre y correo) o None. Nunca
expone `User`, el hash, el rol ni estructuras internas (HU-06, RF-53).
"""

from app.modules.identity.application.user_summaries import (
    UserSummary,
    find_user_summary,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)


def get_user_summary(user_id: object) -> UserSummary | None:
    """Resuelve un usuario contra el repositorio compartido de `identity`."""
    return find_user_summary(user_id, get_user_repository())
