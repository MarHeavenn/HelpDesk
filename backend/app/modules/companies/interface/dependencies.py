"""Dependencias de alcance de la gestion de empresas (HU-19, RF-125/RF-137).

El alcance se deriva solo de la sesion: no existe rol nuevo ni parámetro de
empresa enviado por el cliente. Las dos dependencias devuelven el mismo 404
`"company not found"` para supervisor, técnico, cliente y para el administrador
del alcance contrario. Se resuelven antes del cuerpo de la petición, de modo
que 401 y 404 precedan al 422 estructural.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure.company_repository import (
    get_company_repository,
)
from app.modules.identity.interface.dependencies import get_current_user

UNIFORM_NOT_FOUND = "company not found"


def require_platform_admin(
    current: dict = Depends(get_current_user),
) -> dict:
    """Administrador con rol `administrador` y sin empresa (RF-125)."""
    if not (
        current.get("role") == "administrador"
        and current.get("company_id") is None
    ):
        raise HTTPException(status_code=404, detail=UNIFORM_NOT_FOUND)
    return current


def require_company_admin(
    current: dict = Depends(get_current_user),
) -> dict:
    """Administrador de empresa: rol `administrador` con empresa (RF-142)."""
    if not (
        current.get("role") == "administrador"
        and current.get("company_id") is not None
    ):
        raise HTTPException(status_code=404, detail=UNIFORM_NOT_FOUND)
    return current


def get_platform_company(
    company_id: str,
    current: dict = Depends(require_platform_admin),
) -> Company:
    """Empresa de la ruta por identificador; 404 uniforme si no existe."""
    company = get_company_repository().find_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail=UNIFORM_NOT_FOUND)
    return company


def get_session_company(
    current: dict = Depends(require_company_admin),
) -> Company:
    """Empresa derivada de la sesión; nunca acepta identificador del cliente."""
    company = get_company_repository().find_by_id(current.get("company_id"))
    if company is None:
        raise HTTPException(status_code=404, detail=UNIFORM_NOT_FOUND)
    return company
