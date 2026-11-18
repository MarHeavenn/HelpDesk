"""Consulta de administradores activos por empresa (HU-16, RF-157).

`tickets` necesita saber a que administradores dirigir una alerta de SLA.
Esta funcion devuelve solo identificadores: no expone correo, hash, rol ni
la entidad `User`, de modo que cruza la frontera del modulo con el minimo
dato necesario. La empresa se compara por igualdad, incluido el ambito sin
empresa (`None`) de los datos heredados de desarrollo.
"""

from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)


def list_active_administrator_ids(
    company_id: str | None,
    users: InMemoryUserRepository,
) -> list[str]:
    """Ids de los administradores activos de la empresa, sin duplicados."""
    return [
        user.id
        for user in users.list_all()
        if user.role == "administrador"
        and user.status == "active"
        and user.company_id == company_id
    ]
