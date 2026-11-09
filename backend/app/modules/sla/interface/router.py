"""Rutas HTTP de la configuracion de SLA (HU-14, RF-72..RF-75).

Solo comunican: delegan en `application/manage_sla_policies.py` y
traducen su resultado a los esquemas. El rol se toma de la sesion
mediante `require_sla_admin`; la autorizacion real y la validacion de
regla viven en la aplicacion y en el dominio. No se introducen codigos
nuevos: 200 en el camino valido, 401 sin sesion, 404 uniforme para roles
sin permiso y 422 de cuerpo (RF-75, RF-78).

Precedencia (RF-75): `get_current_user` (401) -> `require_sla_admin` (404)
-> validacion del cuerpo (422). El cuerpo del `PUT` no se declara como
parametro (FastAPI lo decodificaria antes de las dependencias) sino en una
dependencia declarada en ultimo lugar, que lo lee y valida una vez
resuelta la sesion y el rol, igual que en `tickets/interface/router.py`.
"""

import json
import math
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.modules.sla.application.manage_sla_policies import (
    list_sla_policies,
    replace_sla_policies,
)
from app.modules.sla.domain.entities import SlaPolicy
from app.modules.sla.domain.policy_config import SlaPolicyValidationError
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.sla.interface.dependencies import require_sla_admin
from app.modules.sla.interface.schemas import (
    SlaPolicyResponse,
    UpdateSlaPoliciesRequest,
)

router = APIRouter(prefix="/api/sla", tags=["sla"])

# Error de cuerpo ausente con el mismo formato que usaba FastAPI al validar
# el cuerpo de forma declarativa (`detail` como lista de errores).
_MISSING_BODY_ERROR = {
    "type": "missing",
    "loc": ("body",),
    "msg": "Field required",
    "input": None,
}


def _sanitize(value: Any) -> Any:
    """Hace serializable el valor de un error de validacion.

    Los errores conservan el valor recibido en `input`; con `NaN` o
    `Infinity` (que Python acepta al decodificar JSON pero el estandar
    prohibe) Starlette no podria serializar el 422 porque usa
    `json.dumps(..., allow_nan=False)`. Se representan como texto sin
    cambiar el resto del error.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, Decimal) and not value.is_finite():
        return str(value)
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _body_error(error: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un error de esquema al formato que usaba FastAPI."""
    normalized = {key: value for key, value in error.items() if key != "url"}
    normalized["loc"] = ("body", *error.get("loc", ()))
    return normalized


def _json_invalid_error(
    position: int, message: str, raw: bytes
) -> RequestValidationError:
    """422 de cuerpo que no es JSON decodificable."""
    return RequestValidationError(
        [
            {
                "type": "json_invalid",
                "loc": ("body", position),
                "msg": "JSON decode error",
                "input": {},
                "ctx": {"error": message},
            }
        ],
        body=raw,
    )


async def _read_policies_body(request: Request) -> UpdateSlaPoliciesRequest:
    """Lee y valida el cuerpo del reemplazo (se declara despues del rol).

    Un cuerpo ausente, no decodificable o fuera de esquema -> 422 sin
    cambios; la regla de negocio y la escritura siguen en la aplicacion.
    """
    raw = await request.body()
    if not raw:
        raise RequestValidationError([_MISSING_BODY_ERROR], body=None)
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _json_invalid_error(exc.pos, exc.msg, raw) from exc
    except UnicodeDecodeError as exc:
        raise _json_invalid_error(exc.start, "Invalid UTF-8", raw) from exc
    if decoded is None:
        raise RequestValidationError([_MISSING_BODY_ERROR], body=None)
    try:
        return UpdateSlaPoliciesRequest.model_validate(decoded)
    except ValidationError as exc:
        errors = [_sanitize(_body_error(error)) for error in exc.errors()]
        raise RequestValidationError(
            errors, body=_sanitize(decoded)
        ) from exc


def _json_body_documentation() -> dict[str, Any]:
    """Documenta en OpenAPI el cuerpo que se valida en la dependencia."""
    schema = UpdateSlaPoliciesRequest.model_json_schema()
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": schema}},
        }
    }


def _policy_response(policy: SlaPolicy) -> SlaPolicyResponse:
    """Proyecta una politica a `{priority, hours}` (cociente exacto)."""
    return SlaPolicyResponse(
        priority=policy.priority,
        hours=policy.target_minutes / 60,
    )


@router.get("/policies", response_model=list[SlaPolicyResponse])
def get_sla_policies_endpoint(
    current: dict = Depends(require_sla_admin),
) -> list[SlaPolicyResponse]:
    """Consulta la configuracion vigente (RF-72).

    Solo lectura y solo administrador. No declara parametros de consulta:
    los desconocidos se ignoran en silencio (misma regla que RF-15/RF-66).
    """
    policies = list_sla_policies(
        actor_role=current["role"],
        policies=get_sla_policy_repository(),
    )
    return [_policy_response(policy) for policy in policies]


@router.put(
    "/policies",
    response_model=list[SlaPolicyResponse],
    openapi_extra=_json_body_documentation(),
)
def replace_sla_policies_endpoint(
    current: dict = Depends(require_sla_admin),
    payload: UpdateSlaPoliciesRequest = Depends(_read_policies_body),
) -> list[SlaPolicyResponse]:
    """Reemplaza la configuracion completa y devuelve el resultado (RF-73).

    La guardia de rol se declara antes que el cuerpo, de modo que
    401 > 404 > 422 (RF-75). La forma del mapa la valida el esquema; la
    regla de negocio (positividad, minimo de 1 minuto y conversion) la
    valida el dominio dentro del caso de uso. Un error de regla responde
    422 con `detail` cadena, sin escribir la configuracion (RF-74).
    """
    try:
        policies = replace_sla_policies(
            actor_role=current["role"],
            values={
                "Crítica": payload.Crítica,
                "Alta": payload.Alta,
                "Media": payload.Media,
                "Baja": payload.Baja,
            },
            policies=get_sla_policy_repository(),
        )
    except SlaPolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [_policy_response(policy) for policy in policies]
