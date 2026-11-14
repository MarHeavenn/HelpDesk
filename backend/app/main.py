"""Punto de entrada del backend (HU-01: router de identidad + CORS)."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.identity.interface.router import router as auth_router, invitation_router
from app.modules.identity.interface.technicians_router import (
    router as technicians_router,
)
from app.modules.identity.interface.users_router import router as users_router
from app.modules.sla.interface.dashboard_router import (
    router as sla_dashboard_router,
)
from app.modules.sla.interface.router import router as sla_router
from app.modules.tickets.interface.assignments_router import (
    router as assignments_router,
)
from app.modules.tickets.interface.comments_router import (
    router as comments_router,
)
from app.modules.tickets.interface.dashboard_router import (
    router as tickets_dashboard_router,
)
from app.modules.tickets.interface.history_router import (
    router as history_router,
)
from app.modules.tickets.interface.router import router as tickets_router

# Origenes explicitos del frontend (sin comodin "*" con credenciales:
# los navegadores rechazan `allow_origins=["*"]` combinado con
# `allow_credentials=True` y la cookie de sesion no viajaria).
# Ajustar por despliegue con la variable FRONTEND_ORIGINS
# (lista separada por comas).
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="HelpDesk API")


def initialize_database() -> None:
    """Aplica migraciones antes de aceptar solicitudes.

    PostgreSQL es obligatorio salvo por el seam explícito de tests unitarios.
    Cuando hay configuración de base de datos, cualquier error se propaga para
    impedir un arranque con esquema parcial.
    """
    if not (os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PASSWORD")):
        if os.getenv("HELPDESK_ALLOW_IN_MEMORY") == "1":
            return
        raise RuntimeError(
            "Configura DATABASE_URL o POSTGRES_PASSWORD para iniciar la aplicación"
        )
    from app.infrastructure import db
    from migrations.run import apply_migrations

    with db.connect() as conn:
        apply_migrations(conn)


@app.on_event("startup")
def startup_database() -> None:
    initialize_database()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(invitation_router)
app.include_router(technicians_router)
app.include_router(users_router)
app.include_router(tickets_router)
app.include_router(assignments_router)
app.include_router(comments_router)
app.include_router(history_router)
app.include_router(sla_router)
app.include_router(sla_dashboard_router)
app.include_router(tickets_dashboard_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
