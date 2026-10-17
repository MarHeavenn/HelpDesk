"""Caso de uso de cierre de sesion (RF-8).

Invalida efectivamente la sesion en el servidor marcando
`revoked_at`. Es idempotente: sin token, con token desconocido o
con sesion ya revocada no eleva ningun error (la interfaz responde
siempre 204, unica excepcion al 401 de RF-7). Toda la regla vive
aqui y en el dominio; la interfaz solo comunica.
"""

from datetime import datetime, timezone

from app.modules.identity.infrastructure.session_store import (
    InMemorySessionStore,
)


def logout_user(
    token: str | None,
    sessions: InMemorySessionStore,
    now: datetime | None = None,
) -> None:
    """Revoca la sesion del token; no hace nada si no hay sesion activa."""
    if not token or not isinstance(token, str):
        return
    checked_at = now or datetime.now(timezone.utc)
    sessions.revoke_by_token(token, checked_at)
