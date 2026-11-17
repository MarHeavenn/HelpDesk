"""Resolucion de la rama de invitacion/reenvio del administrador (HU-19, RF-141).

No duplica la logica de invitaciones: delega en el contrato de `identity`
(token de un solo uso, hash, 168 h) y en el alta de cuentas. La rama se
resuelve con `list_company_administrators` antes de validar el cuerpo y se
recibe ya resuelta por parametro, de modo que cada peticion la calcula una
sola vez (`interface` solo elige el esquema del cuerpo con esa misma rama).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.companies.application.errors import CompanyDomainError
from app.modules.companies.domain.validators import validate_invitation_payload
from app.modules.companies.interface.company_status_contract import get_company_status
from app.modules.identity.interface.company_account_contract import (
    CompanyAdministratorView,
    UserEmailConflictError,
    account_email_exists,
    deliver_invitation,
    invite_company_administrator,
    list_company_administrators,
    resend_company_administrator_invitation,
)


class CompanyInactiveError(ValueError):
    """La empresa esta inactiva y no admite la alta de invitacion."""

    def __init__(self, detail: str = "empresa no activa") -> None:
        super().__init__(detail)
        self.detail = detail


class CompanyAlreadyHasAdministratorError(ValueError):
    """La empresa ya tiene una administradora activa y aceptada."""

    def __init__(self, detail: str = "la empresa ya tiene administrador") -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class AdministratorInvitationResult:
    status_code: int
    email_status: str


def resolve_administrator_branch(
    company_id: str, users=None
) -> list[CompanyAdministratorView]:
    """Resuelve la rama de invitacion/reenvio.

    Lanza `CompanyAlreadyHasAdministratorError` si la empresa ya tiene una
    administradora activa y aceptada (la decision de negocio vive en la
    capa de aplicacion, no en HTTP). En caso contrario devuelve las cuentas
    administradoras activas con invitacion pendiente, en el orden determinista
    de RF-141: una lista vacia significa rama de invitacion.
    """
    administrators = list_company_administrators(company_id, users=users)
    if any(
        administrator.status == "active"
        and administrator.invitation_status == "accepted"
        for administrator in administrators
    ):
        raise CompanyAlreadyHasAdministratorError("la empresa ya tiene administrador")
    pending = [
        administrator
        for administrator in administrators
        if administrator.status == "active"
        and administrator.invitation_status == "pending"
    ]
    return pending


def manage_administrator_invitation(
    company_id: str,
    *,
    pending: list[CompanyAdministratorView],
    body: dict,
    users=None,
    companies: Any = None,
) -> AdministratorInvitationResult:
    """Operacion unica de invitacion/reenvio (RF-141).

    `pending` es la rama ya resuelta por `resolve_administrator_branch`: una
    lista con la administradora pendiente mas antigua aplica la rama de
    reenvio y una lista vacia, la de invitacion. El cuerpo se valida despues
    de resolver la rama, conforme a la precedencia de RF-137.
    """
    if pending:
        if "name" in body or "email" in body:
            raise CompanyDomainError("resend does not accept name or email")
        resent = resend_company_administrator_invitation(pending[0].id, users=users)
        email_status = deliver_invitation(resent.email, resent.invitation_token)
        return AdministratorInvitationResult(status_code=200, email_status=email_status)

    data = validate_invitation_payload(name=body.get("name"), email=body.get("email"))
    if account_email_exists(data.email, users=users):
        raise UserEmailConflictError("correo no disponible")
    status = get_company_status(company_id, companies)
    if status != "active":
        raise CompanyInactiveError("empresa no activa")
    created = invite_company_administrator(
        company_id,
        name=data.name,
        email=data.email,
        users=users,
        conn=None,
    )
    email_status = deliver_invitation(created.email, created.invitation_token)
    return AdministratorInvitationResult(status_code=201, email_status=email_status)
