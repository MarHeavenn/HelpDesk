"""Esquemas HTTP de datos de empresa (HU-19, RF-143).

Solo validan presencia, tipo y campos extra: la validacion semantica (rango
del nombre, sintaxis del correo, longitudes de contacto, forma normalizada)
vive en el dominio y el caso de uso. Los cuerpos se leen en una dependencia
declarada en ultimo lugar para que 401/404 precedan al 422 estructural.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Coroutine, Literal, TypeVar

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)

_MISSING_BODY_ERROR = {
    "type": "missing",
    "loc": ("body",),
    "msg": "Field required",
    "input": None,
}


class CompanyAdministratorRequest(BaseModel):
    """Administrador inicial del alta: rol fijo y campos exactos (RF-135)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str


class CreateCompanyRequest(BaseModel):
    """Cuerpo exacto de `POST /api/companies` (RF-143)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    phone: str | None = None
    contact_name: str | None = None
    administrator: CompanyAdministratorRequest | None = None


class UpdateCompanyRequest(BaseModel):
    """Cuerpo de `PATCH /api/companies/{id}` y `PATCH /api/companies/me`."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_name: str | None = None


class UpdateCompanyStatusRequest(BaseModel):
    """Cuerpo exacto de `PUT /api/companies/{id}/status` (RF-136)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "inactive"]


class CompanyResponse(BaseModel):
    """Ficha exacta de RF-143 (sin cuentas, tickets ni políticas)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    email: str | None
    phone: str | None
    contact_name: str | None
    status: Literal["active", "inactive"]
    created_at: str
    users_total: int
    tickets_total: int
    tickets_by_status: dict[str, int]
    has_administrator: bool
    administrator_invitation_pending: bool


def json_body(
    schema: type[_SchemaT],
) -> Callable[[Request], Coroutine[Any, Any, _SchemaT]]:
    """Devuelve la dependencia que lee y valida el cuerpo JSON.

    Se declara después de las dependencias de sesión y alcance para que 401 y
    404 precedan al 422 estructural (RF-137). Un cuerpo ausente, no JSON,
    inválido o fuera de esquema produce 422 con `detail` lista.
    """

    async def _read_body(request: Request) -> _SchemaT:
        raw = await request.body()
        if not raw:
            raise RequestValidationError([_MISSING_BODY_ERROR], body=None)
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise RequestValidationError(
                [
                    {
                        "type": "json_invalid",
                        "loc": ("body", 0),
                        "msg": "JSON decode error",
                        "input": {},
                    }
                ],
                body=raw,
            )
        if decoded is None:
            raise RequestValidationError([_MISSING_BODY_ERROR], body=None)
        if not isinstance(decoded, dict):
            raise RequestValidationError([_MISSING_BODY_ERROR], body=decoded)
        try:
            return schema.model_validate(decoded)
        except ValidationError as exc:
            errors = []
            for error in exc.errors():
                normalized = {
                    key: value for key, value in error.items() if key != "url"
                }
                normalized["loc"] = ("body", *error.get("loc", ()))
                errors.append(normalized)
            raise RequestValidationError(errors, body=decoded)

    return _read_body
