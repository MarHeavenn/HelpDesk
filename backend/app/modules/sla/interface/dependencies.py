"""Dependencia de autorizacion de la configuracion de SLA (RF-75).

Toma el rol de la sesion (`get_current_user`, nunca de la peticion).
Sin sesion valida la dependencia de autenticacion eleva 401 antes que
cualquier otra resolucion (precedencia 401 > 404); con un rol distinto
de `administrador` se eleva el 404 uniforme `{"detail": "not found"}` sin
revelar la existencia del recurso y sin devolver datos.

Al ser una dependencia de ruta, FastAPI la resuelve antes del cuerpo:
cliente y tecnico reciben 404 tambien con un cuerpo invalido (RF-75).
"""

from fastapi import Depends, HTTPException

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.sla.application.manage_sla_policies import (
    SlaPolicyAccessDeniedError,
    ensure_sla_admin,
)


def require_sla_admin(
    current: dict = Depends(get_current_user),
) -> dict:
    """Exige el rol `administrador` para operar sobre la configuracion."""
    try:
        ensure_sla_admin(current["role"])
    except SlaPolicyAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return current
