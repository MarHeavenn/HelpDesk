"""Contrato de aplicacion de tecnicos de `identity` (RF-31, RF-39.3).

`list_technicians` expone el directorio solo al rol `administrador` y
`find_technician` resuelve un usuario existente con rol `tecnico`. La
vista `TechnicianSummary` contiene unicamente identificador y nombre:
nunca correo, hash, rol ni otros datos de credenciales (RF-35.4).
"""

from dataclasses import dataclass

from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)

TECHNICIAN_ROLE = "tecnico"
TECHNICIANS_READER_ROLE = "administrador"


class TechniciansAccessDeniedError(ValueError):
    """El rol del actor no puede consultar el directorio (RF-31)."""


@dataclass(frozen=True)
class TechnicianSummary:
    """Vista publica de un tecnico: solo identificador y nombre."""

    id: str
    name: str


def list_technicians(
    actor_role: str, users: InMemoryUserRepository
) -> list[TechnicianSummary]:
    """Devuelve los usuarios con rol `tecnico` como vistas id + nombre.

    Solo admite al rol `administrador`; cualquier otro rol lanza
    TechniciansAccessDeniedError sin devolver datos. El orden no se
    exige y una coleccion vacia es valida (RF-31).
    """
    if actor_role != TECHNICIANS_READER_ROLE:
        raise TechniciansAccessDeniedError("technicians not found")
    return [
        TechnicianSummary(id=user.id, name=user.name)
        for user in users.list_all()
        if user.role == TECHNICIAN_ROLE
    ]


def find_technician(
    technician_id: object, users: InMemoryUserRepository
) -> TechnicianSummary | None:
    """Resuelve un tecnico existente como vista id + nombre.

    Devuelve None si el identificador no es textual, no existe o el
    usuario es cliente o administrador, sin distinguir entre esos casos
    ni revelar si el usuario existe (RF-39.3).
    """
    if not isinstance(technician_id, str):
        return None
    user = users.find_by_id(technician_id)
    if user is None or user.role != TECHNICIAN_ROLE:
        return None
    return TechnicianSummary(id=user.id, name=user.name)
