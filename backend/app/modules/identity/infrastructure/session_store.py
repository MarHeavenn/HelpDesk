"""Almacen en memoria de sesiones opacas de servidor (RF-5, RF-10).

Guarda solo la huella SHA-256 del token (`token_hash`); el token viaja
en la cookie HttpOnly. Sustituible por un adaptador PostgreSQL
(tabla `sessions`) sin cambiar el contrato.
"""

import hashlib
from datetime import datetime

from app.modules.identity.domain.entities import Session


def hash_token(token: str) -> str:
    """Huella SHA-256 hex del token de sesion."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InMemorySessionStore:
    """Guarda sesiones por huella de token."""

    def __init__(self) -> None:
        self._by_token_hash: dict[str, Session] = {}

    def add(self, session: Session) -> None:
        """Guarda la sesion."""
        self._by_token_hash[session.token_hash] = session

    def find_by_token(self, token: str) -> Session | None:
        """Busca por token en claro (se compara su huella); None si no existe."""
        try:
            token_hash = hash_token(token)
        except (ValueError, AttributeError, TypeError):
            return None
        return self._by_token_hash.get(token_hash)

    def revoke_by_token(self, token: str, now: datetime) -> bool:
        """Marca `revoked_at` la sesion del token.

        Idempotente: devuelve False si no existe o ya estaba revocada,
        True si la revoca ahora. Nunca eleva error por token ausente.
        """
        session = self.find_by_token(token)
        if session is None or session.revoked_at is not None:
            return False
        session.revoked_at = now
        return True

    def count(self) -> int:
        """Numero de sesiones almacenadas."""
        return len(self._by_token_hash)

    def clear(self) -> None:
        """Vacia el almacen (apoyo para pruebas)."""
        self._by_token_hash.clear()


_sessions = InMemorySessionStore()


def get_session_store() -> InMemorySessionStore:
    """Devuelve el almacen compartido de sesiones."""
    return _sessions
