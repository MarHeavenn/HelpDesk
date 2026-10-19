"""Dependencia de autenticacion (RF-7, RF-10).

Unico punto de contacto hacia otros modulos (contrato del plan,
seccion 2): devuelve `{id, email, role}` o eleva 401. Los demas
modulos nunca acceden a las tablas internas de `identity`.
Solo comunica: la regla de sesion valida vive en el caso de uso.
"""

from fastapi import HTTPException, Request

from app.modules.identity.application.identity import (
    InvalidSessionError,
    get_current_identity,
)
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)

SESSION_COOKIE_NAME = "session"


def get_current_user(request: Request) -> dict[str, str]:
    """Resuelve la identidad desde la cookie de sesion o eleva 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        user = get_current_identity(
            token,
            users=get_user_repository(),
            sessions=get_session_store(),
        )
    except InvalidSessionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"id": user.id, "email": user.email, "role": user.role}
