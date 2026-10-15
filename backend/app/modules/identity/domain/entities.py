"""Entidades y reglas de dominio del modulo identity (HU-01).

Cubre RF-3 (normalizacion y limites), RF-4 (base de unicidad
case-insensitive: el email se almacena ya normalizado) y el ajuste
aprobado en el plan: `Session` incluye `expires_at`.

Reglas:
- Email: trim + minusculas para comparar/almacenar (case-insensitive).
  La validacion sintactica vive en el adaptador de infraestructura
  (`infrastructure/email_validator.py`); el dominio solo normaliza y
  aplica el limite de longitud.
- Contrasena: intacta, sin trim ni otra modificacion; solo longitud.
- Nombre: obligatorio, 2-100 caracteres tras trim.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def normalize_email(raw: str) -> str:
    """Normaliza un email: trim + minusculas. Lanza ValueError si es vacio
    o supera EMAIL_MAX_LENGTH."""
    if not isinstance(raw, str):
        raise ValueError("email is required")
    normalized = raw.strip().lower()
    if not normalized:
        raise ValueError("email is required")
    if len(normalized) > EMAIL_MAX_LENGTH:
        raise ValueError("email exceeds 254 characters")
    return normalized


def validate_name(raw: str) -> str:
    """Devuelve el nombre con trim. Lanza ValueError si queda fuera de
    2-100 caracteres."""
    if not isinstance(raw, str):
        raise ValueError("name is required")
    name = raw.strip()
    if not (NAME_MIN_LENGTH <= len(name) <= NAME_MAX_LENGTH):
        raise ValueError("name must have 2-100 characters")
    return name


def validate_password(raw: str) -> str:
    """Devuelve la contrasena intacta (sin trim). Lanza ValueError si esta
    fuera de 8-128 caracteres."""
    if not isinstance(raw, str):
        raise ValueError("password is required")
    if not (PASSWORD_MIN_LENGTH <= len(raw) <= PASSWORD_MAX_LENGTH):
        raise ValueError("password must have 8-128 characters")
    return raw


@dataclass
class User:
    """Usuario con email ya normalizado y contrasena solo como hash."""

    id: str
    name: str
    email: str
    password_hash: str
    role: str


@dataclass
class Session:
    """Sesion opaca de servidor.

    Solo se transporta un token aleatorio en cookie; aqui se guarda su
    huella (`token_hash`). `expires_at` marca el tiempo de vida maximo:
    pasada esa marca la sesion se rechaza igual que una revocada.
    """

    id: str
    user_id: str
    token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None

    def is_expired(self, now: datetime) -> bool:
        """True cuando `now >= expires_at`."""
        return now >= self.expires_at

    def is_valid(self, now: datetime) -> bool:
        """Valida si no esta revocada ni expirada."""
        return self.revoked_at is None and not self.is_expired(now)
