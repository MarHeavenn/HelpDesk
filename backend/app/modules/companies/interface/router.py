"""Rutas HTTP de datos de empresa (HU-19, RF-125 a RF-143).

Cubre el catálogo, la ficha, el alta, la actualización, el cambio de estado y
la consulta/actualización de la propia empresa (RF-129 a RF-131, RF-135,
RF-136, RF-142 y RF-143), además de las superficies ya entregadas de
asociación de cuentas (RF-134) e invitación/reenvío del administrador
(RF-141).

Solo comunica: la autorización se resuelve en dependencias antes del cuerpo y
las reglas de negocio viven en `companies/application`. `me` se registra antes
que `/{company_id}` para que nunca se interprete como identificador.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError

from app.modules.companies.application.company_lifecycle import (
    change_company_status,
    create_company,
    list_companies,
    update_company,
)
from app.modules.companies.application.errors import (
    CompanyConflictError,
    CompanyDomainError,
)
from app.modules.companies.domain.entities import Company
from app.modules.companies.domain.validators import MISSING
from app.modules.companies.infrastructure.company_repository import (
    get_company_repository,
)
from app.modules.companies.interface.dependencies import (
    get_platform_company,
    get_session_company,
    require_platform_admin,
)
from app.modules.companies.interface.schemas import (
    CompanyResponse,
    CreateCompanyRequest,
    UpdateCompanyRequest,
    UpdateCompanyStatusRequest,
    json_body,
)
from app.modules.identity.interface.company_account_contract import (
    AccountAssociationNotAllowedError,
    AccountAssociationNotFoundError,
    UserEmailConflictError,
    UserManagementValidationError,
    associate_account,
    get_company_account_stats,
)
from app.modules.identity.interface.dependencies import get_current_user
from app.modules.tickets.interface.company_ticket_contract import (
    get_company_ticket_stats,
)


router = APIRouter(prefix="/api/companies", tags=["companies"])


def _company_response(company: Company) -> dict:
    account_stats = get_company_account_stats(company.id)
    ticket_stats = get_company_ticket_stats(company.id)
    return {
        "id": company.id,
        "name": company.name,
        "email": company.email,
        "phone": company.phone,
        "contact_name": company.contact_name,
        "status": company.status,
        "created_at": company.created_at.isoformat(),
        "users_total": account_stats.users_total,
        "tickets_total": ticket_stats.tickets_total,
        "tickets_by_status": dict(ticket_stats.by_status),
        "has_administrator": account_stats.has_administrator,
        "administrator_invitation_pending": account_stats.administrator_invitation_pending,
    }


# ---------------------------------------------------------------------------
# Cuerpos: se leen en una dependencia declarada al final (401/404 > 422)
# ---------------------------------------------------------------------------

_create_body = json_body(CreateCompanyRequest)
_update_body = json_body(UpdateCompanyRequest)
_status_body = json_body(UpdateCompanyStatusRequest)


def _apply_update(company: Company, payload: UpdateCompanyRequest) -> dict:
    """Aplica un PATCH ya validado estructuralmente (RF-131)."""
    supplied = payload.model_fields_set
    try:
        updated = update_company(
            company=company,
            name=getattr(payload, "name") if "name" in supplied else MISSING,
            email=getattr(payload, "email") if "email" in supplied else MISSING,
            phone=getattr(payload, "phone") if "phone" in supplied else MISSING,
            contact_name=(
                getattr(payload, "contact_name")
                if "contact_name" in supplied
                else MISSING
            ),
            companies=get_company_repository(),
        )
    except CompanyConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except CompanyDomainError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    return _company_response(updated)


# ---------------------------------------------------------------------------
# RF-129, RF-142 y RF-143 — catálogo y propia empresa
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CompanyResponse])
def list_companies_endpoint(
    current: dict = Depends(require_platform_admin),
) -> list[dict]:
    """Catálogo completo ordenado o `[]`; solo administrador de plataforma."""
    return [
        _company_response(company)
        for company in list_companies(get_company_repository())
    ]


@router.get("/me", response_model=CompanyResponse)
def get_my_company_endpoint(company: Company = Depends(get_session_company)) -> dict:
    """Ficha de la empresa de la sesión; nunca acepta identificador."""
    return _company_response(company)


@router.patch("/me", response_model=CompanyResponse)
def update_my_company_endpoint(
    company: Company = Depends(get_session_company),
    payload: UpdateCompanyRequest = Depends(_update_body),
) -> dict:
    """Actualiza la empresa derivada de la sesión (RF-131 y RF-142)."""
    return _apply_update(company, payload)


# ---------------------------------------------------------------------------
# RF-126, RF-130, RF-131 y RF-136 — plataforma por identificador
# ---------------------------------------------------------------------------


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company_endpoint(company: Company = Depends(get_platform_company)) -> dict:
    """Ficha de una empresa por identificador; 404 uniforme (RF-130)."""
    return _company_response(company)


@router.post("", status_code=201)
def create_company_endpoint(
    current: dict = Depends(require_platform_admin),
    payload: CreateCompanyRequest = Depends(_create_body),
) -> JSONResponse:
    """Alta de empresa, con o sin administrador inicial (RF-126 y RF-135)."""
    administrator = (
        payload.administrator.model_dump()
        if payload.administrator is not None
        else None
    )
    try:
        company, email_status = create_company(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            contact_name=payload.contact_name,
            administrator=administrator,
            companies=get_company_repository(),
            users=None,
        )
    except CompanyConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except CompanyDomainError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    except UserEmailConflictError as exc:
        raise HTTPException(status_code=409, detail="correo no disponible") from exc
    except UserManagementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    content: dict = {"company": _company_response(company)}
    if email_status is not None:
        content["email_status"] = email_status
    return JSONResponse(status_code=201, content=content)


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company_endpoint(
    company: Company = Depends(get_platform_company),
    payload: UpdateCompanyRequest = Depends(_update_body),
) -> dict:
    """Actualiza nombre y contacto de una empresa (RF-131)."""
    return _apply_update(company, payload)


@router.put("/{company_id}/status", response_model=CompanyResponse)
def update_company_status_endpoint(
    company: Company = Depends(get_platform_company),
    payload: UpdateCompanyStatusRequest = Depends(_status_body),
) -> dict:
    """Marca `active`/`inactive`; idempotente y sin 409 (RF-136)."""
    company = change_company_status(
        company=company,
        status=payload.status,
        companies=get_company_repository(),
    )
    return _company_response(company)


# ---------------------------------------------------------------------------
# RF-134 y RF-143 — asociación de cuentas sin empresa (T6)
# ---------------------------------------------------------------------------


_MISSING_BODY_ERROR = {
    "type": "missing",
    "loc": ("body",),
    "msg": "Field required",
    "input": None,
}


class _EmptyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _read_association_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
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
        _EmptyBody.model_validate(decoded)
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            normalized = {key: value for key, value in error.items() if key != "url"}
            normalized["loc"] = ("body", *error.get("loc", ()))
            errors.append(normalized)
        raise RequestValidationError(errors, body=decoded)
    return decoded


def _require_platform_admin(current: dict = Depends(get_current_user)) -> dict:
    if not (current.get("role") == "administrador" and current.get("company_id") is None):
        raise HTTPException(status_code=404, detail="not found")
    return current


@router.put("/{company_id}/accounts/{user_id}")
async def associate_account_endpoint(
    company_id: str,
    user_id: str,
    request: Request,
    current: dict = Depends(_require_platform_admin),
) -> dict:
    # RF-137: el identificador de empresa de la ruta se resuelve antes de leer
    # el cuerpo, de modo que una empresa inexistente (o fuera de alcance) da
    # siempre el 404 uniforme y nunca un 422 estructural.
    company = get_company_repository().find_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="not found")

    # Validacion estructural del cuerpo (422) despues de autenticacion y del
    # 404 de la ruta.
    try:
        await _read_association_body(request)
    except RequestValidationError as exc:
        raise exc

    try:
        associate_account(
            company_id=company_id,
            account_id=user_id,
            company_status=company.status,
            conn=None,
            users=None,
            actor_id=current.get("id"),
        )
    except AccountAssociationNotFoundError:
        raise HTTPException(status_code=404, detail="not found")
    except AccountAssociationNotAllowedError:
        raise HTTPException(status_code=409, detail="asociación no permitida")

    return {"company": _company_response(company)}


# ---------------------------------------------------------------------------
# RF-141 — invitación y reenvío del administrador (T5)
# ---------------------------------------------------------------------------


class _InvitationBody(BaseModel):
    """Cuerpo de la rama de invitacion (ambos campos requeridos)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str


class _ResendInvitationBody(BaseModel):
    """Cuerpo de la rama de reenvio: ningun campo aceptado.

    `name` y `email` se declaran para que su presencia no sea un campo
    desconocido (lo que daria 422 estructural) sino un error de dominio
    (`"resend does not accept name or email"`).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    email: str | None = None


def _normalize_structural_errors(exc: ValidationError) -> list[dict]:
    """Forma unificada: loc con prefijo `body`, sin `url` ni `input` (R1)."""
    errors: list[dict] = []
    for error in exc.errors():
        normalized = {
            key: value
            for key, value in error.items()
            if key not in ("url", "input")
        }
        normalized["loc"] = ("body", *error.get("loc", ()))
        errors.append(normalized)
    return errors


def _structural_422(errors: list[dict]) -> None:
    raise RequestValidationError(errors, body=None)


@router.post("/{company_id}/administrator/invitation")
async def manage_administrator_invitation(
    company_id: str, request: Request, current: dict = Depends(get_current_user)
):
    if current.get("role") != "administrador" or current.get("company_id") is not None:
        raise HTTPException(status_code=404, detail="company not found")

    companies = get_company_repository()

    company = companies.find_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="company not found")

    from app.modules.companies.application.manage_administrator_invitation import (
        resolve_administrator_branch,
        CompanyAlreadyHasAdministratorError,
        manage_administrator_invitation as run_invitation,
        CompanyInactiveError,
    )

    # La rama se resuelve aqui una sola vez (la regla de negocio vive en
    # `application`): sirve para elegir el esquema del cuerpo y se pasa ya
    # resuelta al caso de uso, que no la vuelve a calcular (RF-141).
    try:
        pending = resolve_administrator_branch(company_id)
    except CompanyAlreadyHasAdministratorError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc

    # Lectura y parseo del cuerpo (422 estructural si no es JSON valido o no es
    # un objeto). Un cuerpo ausente se trata como `{}` para que la rama de
    # reenvio lo admita y la de invitacion lo rechace por campos requeridos.
    raw = await request.body()
    if not raw:
        body: dict = {}
    else:
        try:
            decoded = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            _structural_422(
                [
                    {
                        "type": "json_invalid",
                        "loc": ("body", 0),
                        "msg": "JSON decode error",
                    }
                ]
            )
            return  # inalcanzable: _structural_422 lanza
        if not isinstance(decoded, dict):
            _structural_422(
                [
                    {
                        "type": "missing",
                        "loc": ("body",),
                        "msg": "Field required",
                    }
                ]
            )
            return
        body = decoded

    if pending:
        # Validacion estructural del esquema (extra="forbid") antes del dominio.
        try:
            _ResendInvitationBody.model_validate(body)
        except ValidationError as exc:
            _structural_422(_normalize_structural_errors(exc))
            return
    else:
        # Rama de invitacion: validacion estructural con campos requeridos.
        try:
            _InvitationBody.model_validate(body)
        except ValidationError as exc:
            _structural_422(_normalize_structural_errors(exc))
            return

    try:
        result = run_invitation(
            company_id,
            pending=pending,
            body=body,
            companies=companies,
        )
    except CompanyAlreadyHasAdministratorError as exc:
        raise HTTPException(status_code=409, detail=exc.detail) from exc
    except CompanyDomainError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    except UserEmailConflictError:
        raise HTTPException(status_code=409, detail="correo no disponible")
    except CompanyInactiveError:
        raise HTTPException(status_code=409, detail="empresa no activa")

    return JSONResponse(
        status_code=result.status_code,
        content={
            "company": _company_response(company),
            "email_status": result.email_status,
        },
    )
