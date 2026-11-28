"""Frontera de `identity` hacia `companies` para los agregados de cuentas.

`companies` consume estos datos para la ficha de RF-143 y para resolver la
rama de invitacion de RF-141. El contrato devuelve solo DTOs inmutables:
nunca `User`, el repositorio, el hash ni estructuras internas del modulo.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime

from app.modules.identity.application import invitations as identity_invitations
from app.modules.identity.application.company_accounts import (
    AccountAssociationNotAllowedError,
    AccountAssociationNotFoundError,
)
from app.modules.identity.application.invitations import InvitationNotResendableError
from app.modules.identity.application.users import (
    UserEmailConflictError,
    UserManagementValidationError,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
    get_user_repository,
)


@dataclass(frozen=True)
class CompanyAccountStats:
    """Agregado de cuentas de una empresa (RF-132 y RF-143)."""

    users_total: int
    has_administrator: bool
    administrator_invitation_pending: bool


@dataclass(frozen=True)
class CompanyAdministratorView:
    """Cuenta administradora de la empresa para la rama de RF-141."""

    id: str
    created_at: datetime
    status: str
    invitation_status: str


@dataclass(frozen=True)
class UnassignedAccountView:
    """Cuenta sin empresa para la consulta de RF-140."""

    id: str
    name: str
    email: str
    role: str
    status: str


@dataclass(frozen=True)
class CreatedCompanyAdministrator:
    """Resultado del alta de la administradora invitada (RF-135/RF-141)."""

    id: str
    email: str
    invitation_token: str


@dataclass(frozen=True)
class ResentCompanyAdministrator:
    """Resultado del reenvio de la invitacion (RF-141)."""

    id: str
    email: str
    invitation_token: str


def _normalize_account_name(name: str) -> str:
    """Forma normalizada de RF-128: recorte, NFC y minusculas.

    Replica la regla de `companies.domain.validators` para no hacer que
    `identity` importe el modulo `companies`: la direccion de dependencia es
    `companies` -> `identity` y este contrato es la frontera.
    """
    return unicodedata.normalize("NFC", name.strip()).lower()


def get_company_account_stats(
    company_id: str | None, users: InMemoryUserRepository | None = None
) -> CompanyAccountStats:
    """Cuenta todas las cuentas de la empresa y deriva los indicadores.

    El total incluye las cuentas desactivadas y las de invitacion pendiente,
    sin importar el rol (RF-143). `has_administrator` exige rol
    `administrador`, estado `active` e invitacion aceptada;
    `administrator_invitation_pending` la misma combinacion con invitacion
    pendiente.
    """
    if company_id is None:
        return CompanyAccountStats(
            users_total=0,
            has_administrator=False,
            administrator_invitation_pending=False,
        )
    repository = users if users is not None else get_user_repository()
    accounts = [
        user for user in repository.list_all() if user.company_id == company_id
    ]
    has_administrator = any(
        user.role == "administrador"
        and user.status == "active"
        and user.invitation_status == "accepted"
        for user in accounts
    )
    administrator_invitation_pending = any(
        user.role == "administrador"
        and user.status == "active"
        and user.invitation_status == "pending"
        for user in accounts
    )
    return CompanyAccountStats(
        users_total=len(accounts),
        has_administrator=has_administrator,
        administrator_invitation_pending=administrator_invitation_pending,
    )


def list_company_administrators(
    company_id: str | None, users: InMemoryUserRepository | None = None
) -> list[CompanyAdministratorView]:
    """Cuentas administradoras de la empresa en el orden de RF-141.

    Ordena por fecha de alta ascendente y, en empate, por identificador
    ascendente. Incluye cualquier estado: la rama de RF-141 se resuelve con
    `status` e `invitation_status`, no excluyendo cuentas.
    """
    if company_id is None:
        return []
    repository = users if users is not None else get_user_repository()
    administrators = [
        user
        for user in repository.list_all()
        if user.company_id == company_id and user.role == "administrador"
    ]
    administrators.sort(key=lambda user: (user.created_at, user.id))
    return [
        CompanyAdministratorView(
            id=user.id,
            created_at=user.created_at,
            status=user.status,
            invitation_status=user.invitation_status,
        )
        for user in administrators
    ]


def list_unassigned_accounts(
    users: InMemoryUserRepository | None = None,
) -> list[UnassignedAccountView]:
    """Cuentas sin empresa y sin rol `administrador` (RF-140).

    Excluye las cuentas con empresa y las cuentas de plataforma. Ordena por
    la forma normalizada del nombre en orden ascendente de code points y
    desempata por identificador ascendente.
    """
    repository = users if users is not None else get_user_repository()
    accounts = [
        user
        for user in repository.list_all()
        if user.company_id is None and user.role != "administrador"
    ]
    accounts.sort(key=lambda user: (_normalize_account_name(user.name), user.id))
    return [
        UnassignedAccountView(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            status=user.status,
        )
        for user in accounts
    ]


def invite_company_administrator(
    company_id: str,
    name: str,
    email: str,
    *,
    conn=None,
    users: InMemoryUserRepository | None = None,
):
    """Crea la cuenta administradora invitada de una empresa (RF-135, RF-141).

    Reutiliza el alta de cuentas de HU-13 (rol `administrador`, estado
    `active`, invitacion pendiente de 168 h y correo unico global). `conn`
    permite que el alta de empresa y la cuenta sean una sola transaccion
    (RF-135). Devuelve un DTO; nunca serializa en HTTP. Propaga
    `UserManagementValidationError` y `UserEmailConflictError`.
    """
    from app.modules.identity.application.users import create_user

    repository = users if users is not None else get_user_repository()
    user = create_user(
        name=name,
        email=email,
        role="administrador",
        phone=None,
        company_id=company_id,
        users=repository,
        conn=conn,
    )
    return CreatedCompanyAdministrator(
        id=user.id,
        email=user.email,
        invitation_token=user.invitation_token,
    )


def account_email_exists(
    email: str, users: InMemoryUserRepository | None = None
) -> bool:
    """Indica si ya existe una cuenta con ese correo (RF-135/RF-141)."""
    repository = users if users is not None else get_user_repository()
    # El repositorio ya trata los correos mal formados como ausentes.
    # Los fallos SQL no equivalen a un correo disponible.
    return repository.find_by_email(email) is not None


def resend_company_administrator_invitation(
    account_id: str,
    *,
    users: InMemoryUserRepository | None = None,
) -> ResentCompanyAdministrator:
    """Rota el token de la administradora pendiente indicada (RF-141)."""
    repository = users if users is not None else get_user_repository()
    user = repository.find_by_id(account_id)
    token = identity_invitations.resend_invitation(user, repository)
    return ResentCompanyAdministrator(
        id=user.id,
        email=user.email,
        invitation_token=token,
    )


def deliver_invitation(email: str, token: str) -> str:
    """Entrega la invitacion y devuelve `sent`/`failed`/`not-attempted`."""
    user = User(
        id="",
        name="",
        email=email,
        password_hash=None,
        role="administrador",
    )
    return identity_invitations.send_invitation(user, token)


def associate_account(
    company_id: str,
    account_id: str,
    *,
    company_status: str | None,
    conn=None,
    users: InMemoryUserRepository | None = None,
    actor_id: str | None = None,
) -> None:
    """Asocia una cuenta sin empresa a una empresa (RF-134).

    Delega en `identity/application/company_accounts.py`. El estado de la
    empresa lo resuelve y lo entrega el modulo llamador (`companies`), porque
    este contrato no importa contratos de otros modulos: la composicion entre
    modulos vive en `companies/interface/router.py` (T3). Devuelve `None`; el
    vínculo queda fijado en la cuenta. Propaga
    `AccountAssociationNotFoundError` y `AccountAssociationNotAllowedError`.
    """
    from app.modules.identity.application.company_accounts import (
        associate_account as _associate,
    )

    repository = users if users is not None else get_user_repository()
    _associate(
        company_id=company_id,
        account_id=account_id,
        users=repository,
        company_status=company_status,
        actor_id=actor_id,
        conn=conn,
    )
    return None
