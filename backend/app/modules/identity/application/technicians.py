"""Contrato de aplicacion de tecnicos de `identity` (RF-31, RF-39.3).

`list_technicians` expone el directorio a los roles `administrador` y
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
TECHNICIANS_READER_ROLES = frozenset({"administrador", "supervisor"})


class TechniciansAccessDeniedError(ValueError):
    """El rol del actor no puede consultar el directorio (RF-31)."""


@dataclass(frozen=True)
class TechnicianSummary:
    """Vista publica de un tecnico: solo identificador y nombre."""

    id: str
    name: str


@dataclass(frozen=True)
class TechnicianAssignmentCandidate:
    """Vista interna para clasificar un candidato de asignación."""

    id: str
    name: str
    eligible: bool


def list_technicians(
    actor_role: str,
    users: InMemoryUserRepository,
    company_id: str | None = None,
) -> list[TechnicianSummary]:
    """Devuelve los usuarios con rol `tecnico` como vistas id + nombre.

    Solo admite a los roles `administrador` y `supervisor`; cualquier otro rol lanza
    TechniciansAccessDeniedError sin devolver datos. El orden no se
    exige y una coleccion vacia es valida (RF-31).
    """
    if actor_role not in TECHNICIANS_READER_ROLES:
        raise TechniciansAccessDeniedError("technicians not found")
    return [
        TechnicianSummary(id=user.id, name=user.name)
        for user in users.list_all()
        if user.role == TECHNICIAN_ROLE
        and (company_id is None or user.company_id == company_id)
        and user.status == "active"
    ]


def find_technician(
    technician_id: object,
    users: InMemoryUserRepository,
    company_id: str | None = None,
    active_only: bool = False,
) -> TechnicianSummary | None:
    """Resuelve un tecnico existente como vista id + nombre.

    Devuelve None si el identificador no es textual, no existe o el
    usuario es cliente o administrador, sin distinguir entre esos casos
    ni revelar si el usuario existe (RF-39.3).
    """
    if not isinstance(technician_id, str):
        return None
    user = users.find_by_id(technician_id)
    if (
        user is None
        or user.role != TECHNICIAN_ROLE
        or (company_id is not None and user.company_id != company_id)
        or (active_only and user.status != "active")
    ):
        return None
    return TechnicianSummary(id=user.id, name=user.name)


def find_technician_for_assignment(
    technician_id: object,
    users: InMemoryUserRepository,
    company_id: str | None,
) -> TechnicianAssignmentCandidate | None:
    """Clasifica existencia/tenant antes de la elegibilidad de dominio."""
    if not isinstance(technician_id, str):
        return None
    user = users.find_by_id(technician_id)
    if user is None or user.company_id != company_id:
        return None
    return TechnicianAssignmentCandidate(
        id=user.id,
        name=user.name,
        eligible=user.role == TECHNICIAN_ROLE and user.status == "active",
    )
