"""HTTP de consulta y alta de usuarios de la empresa del administrador."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.application.users import (
    UserEmailConflictError,
    UserManagementValidationError,
    UserNotVisibleError,
    create_user,
    update_user,
    change_user_role,
    change_user_status,
    LastActiveAdministratorError,
    find_visible_user,
    list_visible_users,
)
from app.modules.identity.application.invitations import send_invitation
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.schemas import (
    CreateUserRequest, UserRepresentation, UpdateRoleRequest, UpdateStatusRequest,
    UpdateUserRequest,
)
from app.modules.identity.infrastructure.session_store import get_session_store

router = APIRouter(prefix="/api/users", tags=["users"])


def _require_admin(current: dict) -> None:
    if current.get("role") != "administrador":
        raise HTTPException(status_code=404, detail="user not found")


def _representation(user) -> UserRepresentation:
    return UserRepresentation(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        company_id=user.company_id,
        role=user.role,
        status=user.status,
        invitation_status=user.invitation_status,
    )


@router.get("", response_model=list[UserRepresentation])
def list_users(current: dict = Depends(get_current_user)) -> list[UserRepresentation]:
    _require_admin(current)
    try:
        users = list_visible_users(get_user_repository(), current.get("company_id"))
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_representation(user) for user in users]


@router.get("/{user_id}", response_model=UserRepresentation)
def get_user(user_id: str, current: dict = Depends(get_current_user)) -> UserRepresentation:
    _require_admin(current)
    try:
        user = find_visible_user(user_id, get_user_repository(), current.get("company_id"))
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _representation(user)


@router.post("", status_code=201)
def create_user_endpoint(
    payload: CreateUserRequest, current: dict = Depends(get_current_user)
) -> dict:
    _require_admin(current)
    try:
        user = create_user(
            name=payload.name,
            email=payload.email,
            role=payload.role,
            phone=payload.phone,
            company_id=current.get("company_id"),
            users=get_user_repository(),
        )
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UserManagementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UserEmailConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"user": _representation(user), "email_status": send_invitation(user, user.invitation_token)}


@router.patch("/{user_id}")
def update_user_endpoint(user_id: str, payload: UpdateUserRequest, current: dict = Depends(get_current_user)) -> dict:
    _require_admin(current)
    try:
        user = find_visible_user(user_id, get_user_repository(), current.get("company_id"))
        changes = payload.model_dump(exclude_unset=True)
        user, email_status = update_user(user, changes, get_user_repository())
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UserManagementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UserEmailConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = _representation(user).model_dump()
    if email_status:
        return {"user": result, "email_status": send_invitation(user, user.invitation_token)}
    return result


@router.post("/{user_id}/invitation/resend")
def resend_invitation_endpoint(user_id: str, current: dict = Depends(get_current_user)) -> dict:
    _require_admin(current)
    try:
        user = find_visible_user(user_id, get_user_repository(), current.get("company_id"))
        from app.modules.identity.application.invitations import (
            InvitationNotResendableError, resend_invitation,
        )
        token = resend_invitation(user, get_user_repository())
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvitationNotResendableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"user": _representation(user), "email_status": send_invitation(user, token)}


@router.put("/{user_id}/role")
def update_role_endpoint(user_id: str, payload: UpdateRoleRequest, current: dict = Depends(get_current_user)) -> UserRepresentation:
    _require_admin(current)
    try:
        user = find_visible_user(user_id, get_user_repository(), current.get("company_id"))
        user = change_user_role(user, payload.role, get_user_repository())
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LastActiveAdministratorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UserManagementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _representation(user)


@router.put("/{user_id}/status")
def update_status_endpoint(user_id: str, payload: UpdateStatusRequest, current: dict = Depends(get_current_user)) -> UserRepresentation:
    _require_admin(current)
    try:
        user = find_visible_user(user_id, get_user_repository(), current.get("company_id"))
        user = change_user_status(user, payload.status, get_user_repository())
    except UserNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LastActiveAdministratorError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UserManagementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.status == "deactivated":
        get_session_store().revoke_by_user(user.id, datetime.now(timezone.utc))
    return _representation(user)
