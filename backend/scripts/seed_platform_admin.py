"""Semilla idempotente del administrador de plataforma (HU-19, RO-01).

Aprovisiona —fuera de la interfaz y de la API— la cuenta con rol
`administrador` y sin empresa que gestiona el catalogo completo de empresas
clientes (D9). No existe ningun endpoint ni pantalla para crearla.

Uso (desde `backend/`, con las migraciones aplicadas):

    python scripts/seed_platform_admin.py

Variables de entorno (nunca se guardan credenciales en el repositorio):

    PLATFORM_ADMIN_EMAIL     Correo de la cuenta. Obligatoria: identifica la
                             cuenta existente y normaliza a minusculas.
    PLATFORM_ADMIN_NAME      Nombre de 2 a 100 caracteres. Obligatoria solo
                             cuando hay que crear la cuenta.
    PLATFORM_ADMIN_PASSWORD  Contrasena de 8 a 128 caracteres. Obligatoria
                             solo cuando hay que crear la cuenta; se guarda
                             exclusivamente como hash Argon2id (HU-01).

Comportamiento (RO-01):

- Sin cuenta con ese correo: crea una cuenta `active`, con invitacion
  aceptada y contrasena en hash. Ejecutarla dos veces no crea una segunda
  cuenta ni cambia datos existentes.
- Cuenta existente `active` y aceptada: no cambia nada y termina con exito.
- Cuenta existente `deactivated` y aceptada: la reactiva conservando el hash.
- Cuenta pendiente de invitacion, con otro rol o con empresa: falla sin
  modificarla e informa; no puede habilitar el acceso sin credenciales.
- Cualquier fallo se propaga sin dejar cuentas parciales: la creacion se
  compensa y la reactivacion revierte el estado del agregado.

Entrega de correo (RO-02, requisito de operacion): la semilla no envia
correo. Las invitaciones de la plataforma (alta con administrador inicial,
invitacion o reenvio de RF-141 y las operaciones de HU-13) requieren un
servicio SMTP configurado fuera de esta historia:

    SMTP_HOST, SMTP_PORT, SMTP_USE_TLS, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM, INVITATION_BASE_URL

Sin `SMTP_HOST` la cuenta y la invitacion se crean o rotan igual, el codigo
de exito no cambia y la respuesta informa `email_status: "not-attempted"`.
Con el servicio configurado y entrega fallida se informa
`email_status: "failed"` y se reintenta con la misma operacion. El token y el
enlace solo viajan en el correo entregado: nunca aparecen en una respuesta
HTTP, en la interfaz ni en la salida de esta semilla.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.identity.domain.entities import (  # noqa: E402
    User,
    validate_name,
    validate_password,
)
from app.modules.identity.infrastructure.email_validator import (  # noqa: E402
    EmailValidator,
)
from app.modules.identity.infrastructure.password_hasher import (  # noqa: E402
    Argon2PasswordHasher,
)
from app.modules.identity.infrastructure.user_repository import (  # noqa: E402
    InMemoryUserRepository,
    get_user_repository,
)

ENV_NAME = "PLATFORM_ADMIN_NAME"
ENV_EMAIL = "PLATFORM_ADMIN_EMAIL"
ENV_PASSWORD = "PLATFORM_ADMIN_PASSWORD"

PLATFORM_ROLE = "administrador"

CREATED = "created"
UNCHANGED = "unchanged"
REACTIVATED = "reactivated"


class SeedError(RuntimeError):
    """La semilla no puede completarse sin modificar datos."""


@dataclass(frozen=True)
class SeedResult:
    """Resultado de la semilla: estado de la cuenta y sin secretos."""

    status: str
    user: User


def _required(environ: Mapping[str, str], name: str) -> str:
    """Valor obligatorio del entorno, nunca credencial por defecto."""
    value = environ.get(name)
    if value is None or not str(value).strip():
        raise SeedError(f"{name} es obligatoria")
    return value


def _find_account(
    users: InMemoryUserRepository, email: str
) -> User | None:
    """Cuenta con ese correo en el proceso o en el almacen compartido."""
    local = users.find_by_email(email)
    if local is not None:
        return local
    return users.find_by_email_persistent(email)


def _create_account(
    users: InMemoryUserRepository,
    *,
    name: str,
    email: str,
    password: str,
    hasher: Argon2PasswordHasher,
) -> User:
    """Crea la cuenta plataforma y compensa el alta si la persistencia falla.

    Se compone con las mismas primitivas de HU-01 que `provision_user`
    (validadores, hash Argon2id y repositorio de usuarios) para conocer el
    identificador antes de persistir y poder retirar la cuenta parcial.
    """
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        password_hash=hasher.hash(password),
        role=PLATFORM_ROLE,
        company_id=None,
        status="active",
        invitation_status="accepted",
    )
    try:
        users.add(user)
    except BaseException:
        users.remove(user.id)
        raise
    return user


def _reactivate(users: InMemoryUserRepository, user: User) -> User:
    """Reactiva la cuenta conservando el hash y revierte si la persistencia falla."""
    previous_status = user.status
    try:
        user.status = "active"
        if users.find_by_id(user.id) is None:
            # Upsert del mismo identificador: registra la cuenta en el proceso
            # y no crea una segunda cuenta con el mismo correo.
            users.add(user)
        else:
            users.sync_persistent(user)
    except BaseException:
        user.status = previous_status
        raise
    return user


def _create_from_environment(
    environ: Mapping[str, str],
    users: InMemoryUserRepository,
    email: str,
    hasher: Argon2PasswordHasher,
) -> SeedResult:
    """Valida nombre y contrasena y crea la cuenta (solo al crear)."""
    try:
        name = validate_name(_required(environ, ENV_NAME))
        password = validate_password(_required(environ, ENV_PASSWORD))
    except ValueError as exc:
        raise SeedError(str(exc)) from exc
    user = _create_account(
        users, name=name, email=email, password=password, hasher=hasher
    )
    return SeedResult(status=CREATED, user=user)


def seed_platform_admin(
    *,
    environ: Mapping[str, str] | None = None,
    users: InMemoryUserRepository | None = None,
    hasher: Argon2PasswordHasher | None = None,
    validator: EmailValidator | None = None,
) -> SeedResult:
    """Garantiza una cuenta de administrador de plataforma (RO-01).

    `environ` aporta solo los datos de la cuenta; la configuracion de
    persistencia (`DATABASE_URL`/`POSTGRES_PASSWORD`) se lee del proceso,
    igual que en el resto de la aplicacion.
    """
    environment = os.environ if environ is None else environ
    repository = users if users is not None else get_user_repository()
    password_hasher = hasher or Argon2PasswordHasher()
    email_validator = validator or EmailValidator()

    try:
        email = email_validator.validate(_required(environment, ENV_EMAIL))
    except ValueError as exc:
        raise SeedError(str(exc)) from exc

    existing = _find_account(repository, email)
    if existing is None:
        return _create_from_environment(
            environment, repository, email, password_hasher
        )

    if existing.role != PLATFORM_ROLE or existing.company_id is not None:
        raise SeedError(
            "la cuenta con ese correo tiene otro rol o empresa; "
            "la semilla no la modifica"
        )
    if existing.invitation_status != "accepted":
        raise SeedError(
            "la cuenta con ese correo está pendiente de invitación; "
            "completa la aceptación o restablece la contraseña fuera de esta "
            "historia"
        )
    if existing.status == "active":
        return SeedResult(status=UNCHANGED, user=existing)
    return SeedResult(status=REACTIVATED, user=_reactivate(repository, existing))


def format_result(result: SeedResult) -> str:
    """Mensaje de operacion sin contrasena, hash, token ni enlace."""
    if result.status == CREATED:
        return f"Administrador de plataforma creado: {result.user.email}"
    if result.status == REACTIVATED:
        return (
            "Administrador de plataforma reactivado (hash conservado): "
            f"{result.user.email}"
        )
    return f"Administrador de plataforma sin cambios: {result.user.email}"


def main(
    environ: Mapping[str, str] | None = None,
    users: InMemoryUserRepository | None = None,
) -> int:
    """Ejecuta la semilla; 0 si termina con exito y 1 si falla."""
    try:
        result = seed_platform_admin(environ=environ, users=users)
    except SeedError as exc:
        print(f"Error de la semilla: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - no se expone el detalle sensible
        print(
            "Error de la semilla "
            f"({type(exc).__name__}): no se creó ninguna cuenta. "
            "Revisa DATABASE_URL y las migraciones sin exponer credenciales.",
            file=sys.stderr,
        )
        return 1
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
