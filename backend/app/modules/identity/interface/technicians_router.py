"""Rutas HTTP del directorio de tecnicos (RF-31).

Solo comunican: delegan en el caso de uso de aplicacion y traducen sus
errores a codigos HTTP con cuerpo consistente {"detail": <mensaje>}. El
rol se toma siempre de la sesion (`get_current_user`), nunca de la
peticion; la autorizacion y el filtrado viven en `list_technicians`.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.application.technicians import (
    TechniciansAccessDeniedError,
    list_technicians,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.schemas import TechnicianResponse

router = APIRouter(prefix="/api/technicians", tags=["technicians"])


@router.get("", response_model=list[TechnicianResponse])
def list_technicians_endpoint(
    current: dict = Depends(get_current_user),
) -> list[TechnicianResponse]:
    """Lista los tecnicos registrados para un administrador (RF-31).

    `get_current_user` responde 401 sin sesion valida (RF-40). Un rol sin
    permiso (cliente o tecnico) recibe 404 uniforme con el mismo mensaje
    del contrato, sin revelar ningun dato del directorio (RF-31).
    """
    try:
        technicians = list_technicians(
            actor_role=current["role"], users=get_user_repository()
        )
    except TechniciansAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        TechnicianResponse(id=item.id, name=item.name)
        for item in technicians
    ]
