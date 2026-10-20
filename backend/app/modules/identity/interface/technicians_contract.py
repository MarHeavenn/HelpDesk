"""Frontera de `identity` hacia otros modulos para resolver tecnicos.

Une `find_technician` con el repositorio compartido de `identity` y
devuelve solo la vista `TechnicianSummary` (id + nombre) o None. Nunca
expone `User`, correo, hash ni estructuras internas del modulo (D3,
RF-31, RF-39.3).
"""

from app.modules.identity.application.technicians import (
    TechnicianSummary,
    find_technician,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)


def get_technician_summary(technician_id: object) -> TechnicianSummary | None:
    """Resuelve un tecnico contra el repositorio compartido de `identity`."""
    return find_technician(technician_id, get_user_repository())
