"""Dependencias de ruta para el alta de tickets (HU-19, RF-136/RF-137).

El bloqueo por empresa inactiva vive en una dependencia de ruta: FastAPI la
resuelve antes del cuerpo, de modo que el 409 `"empresa no activa"` precede al
422 de validación de la entrada, como exige RF-137. La autorización de HU-13
(401 y 404 uniforme) se conserva primero porque se evalúa dentro de la misma
dependencia antes del estado de la empresa.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException

from app.modules.companies.interface.company_status_contract import (
    get_company_status,
)
from app.modules.identity.interface.dependencies import get_current_user


def creatable_actor(current: dict = Depends(get_current_user)) -> dict:
    """Autoriza el alta antes de leer/validar el cuerpo de la petición."""
    if current.get("role") not in {"administrador", "cliente"}:
        raise HTTPException(status_code=404, detail="ticket not found")
    if current.get("company_id") is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    # RF-136: una empresa inactiva solo bloquea los tickets nuevos. RF-139:
    # solo bloquea el estado persistido exactamente `inactive`; un estado
    # `None` (ticket/cuenta heredados con `company_id` sin fila en
    # `companies`) NO bloquea.
    if get_company_status(current.get("company_id")) == "inactive":
        raise HTTPException(status_code=409, detail="empresa no activa")
    return current
