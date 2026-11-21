"""Frontera de `identity` hacia otros modulos para resolver tecnicos.

Une `find_technician` con el repositorio compartido de `identity` y
devuelve solo la vista `TechnicianSummary` (id + nombre) o None. Nunca
expone `User`, correo, hash ni estructuras internas del modulo (D3,
RF-31, RF-39.3).
"""

from app.modules.identity.application.technicians import (
    TECHNICIANS_READER_ROLE,
    TechnicianSummary,
    find_technician,
    find_technician_for_assignment,
    list_technicians,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)


def get_technician_summary(technician_id: object) -> TechnicianSummary | None:
    """Resuelve un tecnico contra el repositorio compartido de `identity`."""
    return find_technician(technician_id, get_user_repository())


def get_technician_assignment_candidate(
    technician_id: object, company_id: str | None
):
    return find_technician_for_assignment(
        technician_id, get_user_repository(), company_id
    )


def get_technician_directory(
    company_id: str | None = None,
) -> list[TechnicianSummary]:
    """Directorio completo de tecnicos (id + nombre) para el dashboard.

    Incluye a los tecnicos sin tickets para que el resumen administrativo
    muestre su carga en cero (RF-87). El acceso se resuelve dentro del
    modulo: esta funcion es una frontera interna, no una operacion publica.
    """
    return list_technicians(
        TECHNICIANS_READER_ROLE,
        get_user_repository(),
        company_id=company_id,
    )

