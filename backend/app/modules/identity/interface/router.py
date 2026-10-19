"""Rutas HTTP de autenticacion (RF-1, RF-3, RF-4, RF-5, RF-6, RF-7, RF-8).

Solo comunican: delegan en los casos de uso y traducen sus errores a
codigos HTTP con cuerpo consistente {"detail": <mensaje>}.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.modules.identity.application.login import (
    InvalidCredentialsError,
    LoginValidationError,
    login_user,
)
from app.modules.identity.application.logout import logout_user
from app.modules.identity.application.register import (
    EmailAlreadyExistsError,
    RegistrationValidationError,
    register_user,
)
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.dependencies import (
    SESSION_COOKIE_NAME,
    get_current_user,
)
from app.modules.identity.interface.schemas import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Regla SameSite/Secure del despliegue (D4): mismo sitio `Lax` sin
# `Secure` por defecto; si frontend y backend quedan en dominios
# distintos, desplegar con SESSION_COOKIE_SAMESITE=None y
# SESSION_COOKIE_SECURE=true (`SameSite=None` exige `Secure`).
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
SESSION_COOKIE_SECURE = (
    os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
)


@router.post("/register", response_model=UserResponse, status_code=201)
def register_endpoint(payload: RegisterRequest) -> UserResponse:
    """Registra un cliente (201) o rechaza con 422/409."""
    try:
        user = register_user(
            name=payload.name,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            users=get_user_repository(),
        )
    except RegistrationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmailAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse(
        id=user.id, name=user.name, email=user.email, role=user.role
    )


@router.post("/login", response_model=UserResponse, status_code=200)
def login_endpoint(payload: LoginRequest, response: Response) -> UserResponse:
    """Inicia sesion (200 + cookie) o rechaza con 422/401."""
    try:
        user, token = login_user(
            email=payload.email,
            password=payload.password,
            users=get_user_repository(),
            sessions=get_session_store(),
        )
    except LoginValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        path="/",
    )
    return UserResponse(
        id=user.id, name=user.name, email=user.email, role=user.role
    )


@router.get("/me", response_model=MeResponse, status_code=200)
def me_endpoint(current: dict = Depends(get_current_user)) -> MeResponse:
    """Devuelve la identidad y el rol de la sesion activa (RF-7)."""
    return MeResponse(**current)


@router.post("/logout", status_code=204)
def logout_endpoint(request: Request, response: Response) -> None:
    """Cierra la sesion activa con invalidacion efectiva (RF-8).

    Siempre 204, con o sin sesion (idempotente; unica excepcion al
    401 de RF-7). Revoca la sesion en el servidor y limpia la cookie.
    """
    logout_user(
        token=request.cookies.get(SESSION_COOKIE_NAME),
        sessions=get_session_store(),
    )
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return None
