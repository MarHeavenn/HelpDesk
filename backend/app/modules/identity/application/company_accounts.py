"""Casos de uso de asociacion de cuentas sin empresa a una empresa (HU-19).

La asociacion fija el vínculo `company_id` de una cuenta sin empresa, sin
alterar ningun otro dato ni crear ni revocar sesiones. La empresa efectiva
se resuelve desde la cuenta en cada peticion (RF-134).
"""

from __future__ import annotations

from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
)


class AccountAssociationNotFoundError(ValueError):
    """La cuenta o la empresa no existe o no es visible."""


class AccountAssociationNotAllowedError(ValueError):
    """La cuenta no es asociable o la empresa no está activa."""


def associate_account(
    *,
    company_id: str,
    account_id: str,
    users: InMemoryUserRepository,
    company_status: str | None,
    actor_id: str | None = None,
    conn=None,
) -> User:
    """Asocia una cuenta sin empresa a una empresa activa.

    Conserva nombre, correo, rol, estado, credenciales e invitacion. Lanza
    `AccountAssociationNotFoundError` si la empresa o la cuenta no existen,
    y `AccountAssociationNotAllowedError` si la empresa esta inactiva, la
    cuenta ya tiene empresa, su rol es `administrador` o es la propia cuenta
    del actor.
    """
    if company_status is None:
        raise AccountAssociationNotFoundError("not found")

    user = users.find_by_id(account_id)
    if user is None:
        raise AccountAssociationNotFoundError("not found")

    if company_status != "active":
        raise AccountAssociationNotAllowedError("asociación no permitida")
    if user.company_id is not None:
        raise AccountAssociationNotAllowedError("asociación no permitida")
    if user.role == "administrador":
        raise AccountAssociationNotAllowedError("asociación no permitida")
    if actor_id is not None and user.id == actor_id:
        raise AccountAssociationNotAllowedError("asociación no permitida")

    user.company_id = company_id
    if conn is not None:
        users.sync_persistent(user, conn)
    else:
        users.sync_persistent(user)
    return user