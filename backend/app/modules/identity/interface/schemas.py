"""Esquemas HTTP del modulo identity (RF-1, RF-3, RF-9).

La validacion semantica (longitudes con trim, sintaxis de email,
contrasena intacta) vive en el dominio y el caso de uso; aqui solo se
exige presencia y tipo, y se rechazan campos extra. La respuesta nunca
incluye contrasena ni hash.
"""

from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    """Cuerpo de POST /api/auth/register."""

    model_config = ConfigDict(extra="forbid")

    name: str
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    """Cuerpo de POST /api/auth/login."""

    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class UserResponse(BaseModel):
    """Usuario devuelto al registrarse (sin contrasena ni hash)."""

    id: str
    name: str
    email: str
    role: str


class MeResponse(BaseModel):
    """Identidad devuelta por GET /api/auth/me (RF-7)."""

    id: str
    email: str
    role: str


class TechnicianResponse(BaseModel):
    """Tecnico del directorio (RF-31): solo identificador y nombre.

    Nunca incluye correo, hash, rol ni otros datos de credenciales
    (RF-35.4).
    """

    id: str
    name: str
