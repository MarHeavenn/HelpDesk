"""Adaptador de validacion sintactica de email (RF-3).

Biblioteca: email-validator (version en EMAIL_VALIDATOR_VERSION), sin
comprobacion DNS (`check_deliverability=False`): solo sintaxis. Aplica
primero la normalizacion del dominio (trim + minusculas) y devuelve el
email ya normalizado listo para almacenar/comparar.
"""

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_syntax

from app.modules.identity.domain.entities import normalize_email

EMAIL_VALIDATOR_LIBRARY_NAME = "email-validator"
EMAIL_VALIDATOR_VERSION = "2.3.0"


class EmailValidator:
    """Valida sintaxis y devuelve el email normalizado."""

    def validate(self, raw: str) -> str:
        """Normaliza (trim + minusculas, limite 254) y valida sintaxis.
        Lanza ValueError si el email es invalido."""
        normalized = normalize_email(raw)
        try:
            _validate_syntax(normalized, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError(str(exc)) from exc
        return normalized
