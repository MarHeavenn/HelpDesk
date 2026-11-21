"""Frontera de `identity` hacia otros modulos para resolver administradores.

HU-16 (RF-157, RF-163) necesita los administradores activos de una empresa
para dirigirles alertas de SLA. El contrato devuelve solo identificadores:
nunca expone `User`, el correo, el hash ni estructuras internas de
`identity`. La composicion con el repositorio compartido ocurre aqui.
"""

from app.modules.identity.application.administrators import (
    list_active_administrator_ids,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)


def list_company_administrator_ids(company_id: str | None) -> list[str]:
    """Identificadores de los administradores activos de la empresa."""
    return list_active_administrator_ids(company_id, get_user_repository())
