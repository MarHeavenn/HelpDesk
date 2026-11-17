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
import uuid
from datetime import datetime, timedelta, timezone

# El arranque local usa repositorios en memoria salvo que se configure una
# base de datos. El seam evita exigir PostgreSQL para la demostracion.
os.environ.setdefault("HELPDESK_ALLOW_IN_MEMORY", "1")

import uvicorn

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.application.register import (
    EmailAlreadyExistsError,
    RegistrationValidationError,
    register_user,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
    get_user_repository,
)
from app.modules.sla.application.policies import target_minutes_for
from app.modules.tickets.domain.entities import (
    IN_PROGRESS_STATUS,
    OPEN_STATUS,
    RESOLVED_STATUS,
    AssignmentRecord,
    Ticket,
)
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

DEFAULT_ADMIN_EMAIL = "admin@helpdesk.dev"
DEFAULT_TECH_EMAIL = "tecnico@helpdesk.dev"
DEFAULT_CLIENT_EMAIL = "cliente@helpdesk.dev"

# Tickets de demostracion de HU-16. Las edades se expresan en minutos
# respecto al arranque y se calculan con los objetivos vigentes de SLA:
# uno queda en riesgo, otro incumplido, otro en tiempo y otro resuelto.
SLA_DEMO_TICKETS = (
    {
        "title": "Correo corporativo no sincroniza",
        "description": "El correo dejo de actualizarse esta manana.",
        "priority": "Crítica",
        "age_minutes": 110,
        "status": OPEN_STATUS,
        "assigned": True,
        "resolved_minutes_ago": None,
    },
    {
        "title": "Factura de octubre no se genera",
        "description": "El modulo de facturacion devuelve un error al cerrar.",
        "priority": "Alta",
        "age_minutes": 255,
        "status": IN_PROGRESS_STATUS,
        "assigned": True,
        "resolved_minutes_ago": None,
    },
    {
        "title": "Solicitud de acceso a reportes",
        "description": "Necesito permisos de solo lectura para el tablero.",
        "priority": "Media",
        "age_minutes": 30,
        "status": IN_PROGRESS_STATUS,
        "assigned": True,
        "resolved_minutes_ago": None,
    },
    {
        "title": "Impresora del piso 3 sin conexion",
        "description": "La impresora no responde desde ayer.",
        "priority": "Crítica",
        "age_minutes": 60,
        "status": RESOLVED_STATUS,
        "assigned": False,
        "resolved_minutes_ago": 10,
    },
)


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
) -> dict[str, User]:
    """Crea el administrador y el tecnico si sus correos no existen."""
    demo_users = (
        (admin_name, admin_email, admin_password, "administrador"),
        (tech_name, tech_email, tech_password, "tecnico"),
    )
    seeded: dict[str, User] = {}
    for name, email, password, role in demo_users:
        existing = _find_demo_user(users, email, role)
        if existing is not None:
            seeded[role] = existing
            continue
        seeded[role] = provision_user(
            name=name,
            email=email,
            password=password,
            role=role,
            users=users,
        )
    return seeded


def _find_demo_user(users: InMemoryUserRepository, email: str, role: str) -> User | None:
    """Recupera la cuenta local o persistida sin cambiar sus credenciales."""
    existing = users.find_by_email(email)
    if existing is None:
        existing = users.find_by_email_persistent(email)
        if existing is not None:
            if existing.role != role or existing.company_id is not None:
                raise RegistrationValidationError("demo email belongs to an incompatible account")
            existing = users.cache_persistent_user(existing)
    if existing is not None and (existing.role != role or existing.company_id is not None):
        raise RegistrationValidationError("demo email belongs to an incompatible account")
    return existing


def seed_sla_demo_client(
    users: InMemoryUserRepository,
    *,
    name: str,
    email: str,
    password: str,
) -> User:
    """Crea el cliente de demostracion si no existe (idempotente)."""
    existing = _find_demo_user(users, email, "cliente")
    if existing is not None:
        return existing
    return register_user(
        name=name,
        email=email,
        password=password,
        role="cliente",
        users=users,
    )


def seed_sla_demo_tickets(
    *,
    requester_id: str,
    administrator_id: str,
    technician_id: str,
    technician_name: str,
    tickets: InMemoryTicketRepository,
    assignments: InMemoryAssignmentLog | None = None,
    now: datetime | None = None,
) -> list[Ticket]:
    """Siembra tickets de HU-16 con antiguedades calculadas (idempotente).

    Repite el alta solo si falta un ticket con el mismo titulo para el
    mismo solicitante. Los tickets asignados dejan su registro de
    asignacion para que el detalle y el historial sean coherentes.
    """
    reference = now if now is not None else datetime.now(timezone.utc)
    existing_titles = {
        ticket.title for ticket in tickets.list_by_requester(requester_id)
    }
    created: list[Ticket] = []

    for spec in SLA_DEMO_TICKETS:
        if spec["title"] in existing_titles:
            continue
        created_at = reference - timedelta(minutes=spec["age_minutes"])
        resolved_minutes_ago = spec["resolved_minutes_ago"]
        resolved_at = (
            reference - timedelta(minutes=resolved_minutes_ago)
            if resolved_minutes_ago is not None
            else None
        )
        assigned = bool(spec["assigned"])
        ticket = Ticket(
            id=str(uuid.uuid4()),
            title=spec["title"],
            description=spec["description"],
            requester_id=requester_id,
            created_at=created_at,
            priority=spec["priority"],
            status=spec["status"],
            assignee_id=technician_id if assigned else None,
            assignee_name=technician_name if assigned else None,
            resolved_at=resolved_at,
            resolved_target_minutes=(
                target_minutes_for(spec["priority"])
                if resolved_at is not None
                else None
            ),
        )
        tickets.add(ticket)
        if assigned and assignments is not None:
            assignments.add(
                AssignmentRecord(
                    ticket_id=ticket.id,
                    previous_assignee_id=None,
                    new_assignee_id=technician_id,
                    actor_id=administrator_id,
                    assigned_at=created_at + timedelta(minutes=1),
                )
            )
        created.append(ticket)
    return created


def _print_credentials(
    role: str,
    email: str,
    password: str,
    generated: bool,
    env_name: str,
    user: User,
) -> None:
    """Muestra el acceso de desarrollo sin ocultar la contrasena generada."""
    if not user.password_hash or not Argon2PasswordHasher().verify(user.password_hash, password):
        print(f"  {role}: {email} / (cuenta existente; conserva su contrasena anterior)")
    elif generated:
        print(f"  {role}: {email} / {password}")
    else:
        print(f"  {role}: {email} / (contrasena de {env_name})")


def main() -> None:
    """Siembra los usuarios y tickets de desarrollo y arranca uvicorn."""
    admin_name = os.getenv("DEV_ADMIN_NAME", "Administrador Local")
    admin_email = os.getenv("DEV_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    admin_password, admin_generated = _resolve_password("DEV_ADMIN_PASSWORD")
    tech_name = os.getenv("DEV_TECH_NAME", "Tecnico Local")
    tech_email = os.getenv("DEV_TECH_EMAIL", DEFAULT_TECH_EMAIL)
    tech_password, tech_generated = _resolve_password("DEV_TECH_PASSWORD")
    client_name = os.getenv("DEV_CLIENT_NAME", "Cliente Local")
    client_email = os.getenv("DEV_CLIENT_EMAIL", DEFAULT_CLIENT_EMAIL)
    client_password, client_generated = _resolve_password("DEV_CLIENT_PASSWORD")

    try:
        seeded = seed_demo_users(
            get_user_repository(),
            admin_name=admin_name,
            admin_email=admin_email,
            admin_password=admin_password,
            tech_name=tech_name,
            tech_email=tech_email,
            tech_password=tech_password,
        )
        client = seed_sla_demo_client(
            get_user_repository(),
            name=client_name,
            email=client_email,
            password=client_password,
        )
        seed_sla_demo_tickets(
            requester_id=client.id,
            administrator_id=seeded["administrador"].id,
            technician_id=seeded["tecnico"].id,
            technician_name=seeded["tecnico"].name,
            tickets=get_ticket_repository(),
            assignments=get_assignment_log(),
        )
    except (EmailAlreadyExistsError, RegistrationValidationError) as exc:
        raise SystemExit(
            f"Error al crear los datos de desarrollo: {exc}"
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
        seeded["administrador"],
    )
    _print_credentials(
        "tecnico",
        tech_email,
        tech_password,
        tech_generated,
        "DEV_TECH_PASSWORD",
        seeded["tecnico"],
    )
    _print_credentials(
        "cliente",
        client_email,
        client_password,
        client_generated,
        "DEV_CLIENT_PASSWORD",
        client,
    )
    print("")
    print("Tickets demo de SLA: uno en riesgo, uno incumplido, uno en")
    print("tiempo y uno resuelto. Entra en Notificaciones como")
    print("administrador o tecnico para ver las alertas.")
    print("")
    print("Datos en memoria: se pierden al detener el servidor.")
    print("Pulsa Ctrl+C para detenerlo.")
    print("")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
