"""Arranque local del backend con datos de demostracion.

Solo para desarrollo. Crea un administrador y un tecnico en el
repositorio en memoria (no existe endpoint publico para esos roles) y
levanta la API en localhost. Los datos se pierden al detener el proceso.

Uso (desde backend/):
    ..\\.venv\\Scripts\\python.exe dev_server.py

Variables de entorno opcionales:
    HOST, PORT
    DEV_ADMIN_NAME, DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD
    DEV_TECH_NAME, DEV_TECH_EMAIL, DEV_TECH_PASSWORD

Si no se define una contrasena, se genera una aleatoria y se muestra en
la consola. No se guardan credenciales en el repositorio.
"""

import os
import secrets

import uvicorn

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.application.register import (
    EmailAlreadyExistsError,
    RegistrationValidationError,
)
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
    get_user_repository,
)

DEFAULT_ADMIN_EMAIL = "admin@helpdesk.dev"
DEFAULT_TECH_EMAIL = "tecnico@helpdesk.dev"


def _resolve_password(env_name: str) -> tuple[str, bool]:
    """Devuelve la contrasena configurada o una generada y si fue generada."""
    configured = os.getenv(env_name)
    if configured:
        return configured, False
    return secrets.token_urlsafe(12), True


def seed_demo_users(
    users: InMemoryUserRepository,
    *,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    tech_name: str,
    tech_email: str,
    tech_password: str,
) -> None:
    """Crea el administrador y el tecnico si sus correos no existen."""
    demo_users = (
        (admin_name, admin_email, admin_password, "administrador"),
        (tech_name, tech_email, tech_password, "tecnico"),
    )
    for name, email, password, role in demo_users:
        if users.find_by_email(email) is not None:
            continue
        provision_user(
            name=name,
            email=email,
            password=password,
            role=role,
            users=users,
        )


def _print_credentials(
    role: str,
    email: str,
    password: str,
    generated: bool,
    env_name: str,
) -> None:
    """Muestra el acceso de desarrollo sin ocultar la contrasena generada."""
    if generated:
        print(f"  {role}: {email} / {password}")
    else:
        print(f"  {role}: {email} / (contrasena de {env_name})")


def main() -> None:
    """Siembra los usuarios de desarrollo y arranca uvicorn."""
    admin_name = os.getenv("DEV_ADMIN_NAME", "Administrador Local")
    admin_email = os.getenv("DEV_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    admin_password, admin_generated = _resolve_password("DEV_ADMIN_PASSWORD")
    tech_name = os.getenv("DEV_TECH_NAME", "Tecnico Local")
    tech_email = os.getenv("DEV_TECH_EMAIL", DEFAULT_TECH_EMAIL)
    tech_password, tech_generated = _resolve_password("DEV_TECH_PASSWORD")

    try:
        seed_demo_users(
            get_user_repository(),
            admin_name=admin_name,
            admin_email=admin_email,
            admin_password=admin_password,
            tech_name=tech_name,
            tech_email=tech_email,
            tech_password=tech_password,
        )
    except (EmailAlreadyExistsError, RegistrationValidationError) as exc:
        raise SystemExit(
            f"Error al crear los usuarios de desarrollo: {exc}"
        ) from exc

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    print("")
    print("HelpDesk API local")
    print(f"  API:     http://{host}:{port}")
    print(f"  Swagger: http://{host}:{port}/docs")
    print(f"  Health:  http://{host}:{port}/health")
    print("")
    print("Usuarios de desarrollo:")
    _print_credentials(
        "administrador",
        admin_email,
        admin_password,
        admin_generated,
        "DEV_ADMIN_PASSWORD",
    )
    _print_credentials(
        "tecnico",
        tech_email,
        tech_password,
        tech_generated,
        "DEV_TECH_PASSWORD",
    )
    print("")
    print("Datos en memoria: se pierden al detener el servidor.")
    print("Pulsa Ctrl+C para detenerlo.")
    print("")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
