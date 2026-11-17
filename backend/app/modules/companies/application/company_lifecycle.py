"""Casos de uso de datos de empresa (HU-19, RF-126 a RF-131, RF-135, RF-136).

La capa de aplicacion orquesta el repositorio de empresas y los contratos de
`identity`: no conoce HTTP ni traduce codigos. Registra las reglas de RF-128
(unicidad por forma normalizada bajo `name_lock`), RF-135 (alta atomica con
administrador inicial) y RF-136 (cambio de estado idempotente y sin 409).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Mapping

from app.modules.companies.application.errors import (
    CompanyConflictError,
    CompanyDomainError,
    CompanyNotFoundError,
)
from app.modules.companies.domain.entities import Company
from app.modules.companies.domain.validators import (
    MISSING,
    normalize_company_name,
    validate_company_update,
    validate_new_company,
)
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
    get_company_repository,
)
from app.modules.identity.interface.company_account_contract import (
    CreatedCompanyAdministrator,
    deliver_invitation,
    invite_company_administrator,
)

STATUS_VALUES = frozenset({"active", "inactive"})

# Re-export for callers/tests that patch at module level.
send_invitation = deliver_invitation


def _companies(
    companies: InMemoryCompanyRepository | None,
) -> InMemoryCompanyRepository:
    return companies if companies is not None else get_company_repository()


def _users(users):
    return users


def list_companies(
    companies: InMemoryCompanyRepository | None = None,
) -> list[Company]:
    """Catalogo completo ordenado conforme a RF-129.

    Orden ascendente por forma normalizada en code points y desempate por
    fecha de alta y luego identificador. Incluye activas e inactivas.
    """
    repository = _companies(companies)
    return sorted(
        repository.list_all(),
        key=lambda company: (
            company.name_normalized or "",
            company.created_at,
            company.id,
        ),
    )


def get_company(
    company_id: str,
    companies: InMemoryCompanyRepository | None = None,
) -> Company:
    """Ficha de una empresa; `CompanyNotFoundError` si no existe (RF-130)."""
    company = _companies(companies).find_by_id(company_id)
    if company is None:
        raise CompanyNotFoundError("company not found")
    return company


def create_company(
    *,
    name: object,
    email: object,
    phone: object = None,
    contact_name: object = None,
    administrator: Mapping[str, object] | None = None,
    companies: InMemoryCompanyRepository | None = None,
    users=None,
) -> tuple[Company, str | None]:
    """Da de alta una empresa, con o sin administrador inicial (RF-126/RF-135).

    La comprobacion de nombre duplicado precede a la validacion de dominio
    (RF-137: 409 antes que 422 de dominio). Con `administrator` la empresa y
    la cuenta pendiente se crean dentro de la misma transaccion; si el correo
    ya esta tomado, el alta completa se revierte.
    """
    repository = _companies(companies)
    user_repository = users
    normalized = normalize_company_name(name)  # type: ignore[arg-type]

    with repository.name_lock(normalized) as conn:
        if repository.find_by_name_normalized(normalized, conn) is not None:
            raise CompanyConflictError("empresa no disponible")

        data = validate_new_company(
            name=name,  # type: ignore[arg-type]
            email=email,  # type: ignore[arg-type]
            phone=phone,  # type: ignore[arg-type]
            contact_name=contact_name,  # type: ignore[arg-type]
        )
        company = Company(
            id=str(uuid.uuid4()),
            name=data.name,
            name_normalized=data.name_normalized,
            email=data.email,
            phone=data.phone,
            contact_name=data.contact_name,
            status="active",
            created_at=datetime.now(timezone.utc),
        )
        created_administrator = None
        try:
            repository.add(company, conn=conn)
            if administrator is not None:
                created_administrator = invite_company_administrator(
                    company.id,
                    administrator["name"],
                    administrator["email"],
                    conn=conn,
                    users=user_repository,
                )
        except BaseException:
            # Compensacion en memoria; en PostgreSQL el contexto de `name_lock`
            # revierte la transaccion completa.
            repository.remove(company.id)
            raise

    email_status = None
    if created_administrator is not None:
        email_status = send_invitation(
            created_administrator.email,
            created_administrator.invitation_token,
        )
    return company, email_status


def _apply_changes(
    company: Company,
    changes: Mapping[str, object],
    repository: InMemoryCompanyRepository,
    conn,
) -> Company:
    """Aplica los campos ya validados y revierte el agregado si falla."""
    previous = {field: getattr(company, field) for field in changes}
    try:
        for field, value in changes.items():
            setattr(company, field, value)
        repository.update(company, conn=conn)
    except BaseException:
        for field, value in previous.items():
            setattr(company, field, value)
        raise
    return company


def update_company(
    *,
    company: Company,
    name: object = MISSING,
    email: object = MISSING,
    phone: object = MISSING,
    contact_name: object = MISSING,
    companies: InMemoryCompanyRepository | None = None,
) -> Company:
    """Actualiza nombre y datos de contacto (RF-131, RF-127 y RF-128).

    Un cambio efectivo de nombre comprueba duplicados antes de validar el
    resto de campos (RF-137). Un nombre que conserva la forma normalizada
    propia no es conflicto y no vuelve a exigir el rango (RF-128/RF-139).
    """
    repository = _companies(companies)

    if name is not MISSING and isinstance(name, str):
        candidate = normalize_company_name(name)
        if candidate != company.name_normalized:
            with repository.name_lock(candidate) as conn:
                other = repository.find_by_name_normalized(candidate, conn)
                if other is not None and other.id != company.id:
                    raise CompanyConflictError("empresa no disponible")
                changes = validate_company_update(
                    name=name,
                    email=email,
                    phone=phone,
                    contact_name=contact_name,
                    current_name_normalized=company.name_normalized,
                )
                return _apply_changes(company, changes, repository, conn)

    changes = validate_company_update(
        name=name,
        email=email,
        phone=phone,
        contact_name=contact_name,
        current_name_normalized=company.name_normalized,
    )
    return _apply_changes(company, changes, repository, None)


def change_company_status(
    *,
    company: Company,
    status: str,
    companies: InMemoryCompanyRepository | None = None,
) -> Company:
    """Marca `active` o `inactive`; repetir el estado no tiene efectos (RF-136)."""
    if status not in STATUS_VALUES:
        raise CompanyDomainError("status is invalid")
    if status == company.status:
        return company
    repository = _companies(companies)
    previous = company.status
    try:
        company.status = status
        repository.update(company)
    except BaseException:
        company.status = previous
        raise
    return company
