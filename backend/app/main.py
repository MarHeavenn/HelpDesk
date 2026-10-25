"""Punto de entrada del backend (HU-01: router de identidad + CORS)."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.identity.interface.router import router as auth_router
from app.modules.identity.interface.technicians_router import (
    router as technicians_router,
)
from app.modules.tickets.interface.assignments_router import (
    router as assignments_router,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(technicians_router)
app.include_router(tickets_router)
app.include_router(assignments_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
