"""Rutas HTTP del centro de notificaciones interno (HU-15).

Prefijo `/api/notifications`. La consulta aplica la visibilidad por rol y
empresa de RF-148; el contador y las acciones de lectura solo afectan a las
notificaciones dirigidas al actor. La interfaz solo compone y serializa: las
reglas viven en `application` y los nombres se resuelven con el contrato
publico de `identity`.

Todas las rutas dependen de `get_current_user`, de modo que una sesion
invalida responde 401 antes que cualquier 404 (RF-150).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.modules.identity.interface.administrators_contract import (
    list_company_administrator_ids,
)
from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.users_contract import get_user_summary
from app.modules.tickets.application.generate_sla_alerts import (
    generate_sla_alerts,
)
from app.modules.tickets.application.list_notifications import list_notifications
from app.modules.tickets.application.notification_reads import (
    NotificationNotFoundError,
    count_unread,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.modules.tickets.domain.entities import (
    SYSTEM_ACTOR_ID,
    SYSTEM_ACTOR_NAME,
    TicketNotification,
)
from app.modules.tickets.infrastructure.notification_repository import (
    get_notification_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.schemas import (
    MarkAllReadResponse,
    NotificationResponse,
    NotificationTicketResponse,
    NotificationUserResponse,
    UnreadCountResponse,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _user_response(user_id: str) -> NotificationUserResponse:
    """Resuelve el nombre visible de un usuario (RF-146).

    Conserva el identificador aunque el usuario ya no exista; en ese caso
    el nombre queda vacio. El actor del sistema de las alertas de SLA
    (HU-16) no es una cuenta real y se traduce a un nombre fijo. No revela
    correo, rol ni credenciales.
    """
    if user_id == SYSTEM_ACTOR_ID:
        return NotificationUserResponse(
            id=SYSTEM_ACTOR_ID,
            name=SYSTEM_ACTOR_NAME,
        )
    user = get_user_summary(user_id)
    return NotificationUserResponse(
        id=user_id,
        name=user.name if user is not None else None,
    )


def _generate_pending_sla_alerts(current: dict) -> None:
    """Genera las alertas de SLA visibles antes de consultar (HU-16)."""
    generate_sla_alerts(
        actor_id=current["id"],
        actor_role=current["role"],
        actor_company_id=current.get("company_id"),
        tickets=get_ticket_repository(),
        notifications=get_notification_repository(),
        administrator_ids=list_company_administrator_ids,
    )


def _notification_response(notification: TicketNotification) -> NotificationResponse:
    """Serializa una notificacion (fechas con offset UTC)."""
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        ticket=NotificationTicketResponse(
            id=notification.ticket_id,
            title=notification.ticket_title,
        ),
        recipient=_user_response(notification.recipient_id),
        actor=_user_response(notification.actor_id),
        previous_value=notification.previous_value,
        new_value=notification.new_value,
        created_at=notification.created_at.isoformat(),
        read_at=(
            notification.read_at.isoformat()
            if notification.read_at is not None
            else None
        ),
    )


@router.get("", response_model=list[NotificationResponse])
def list_notifications_endpoint(
    current: dict = Depends(get_current_user),
) -> list[NotificationResponse]:
    """Notificaciones visibles para el actor (RF-147, RF-148, HU-16)."""
    _generate_pending_sla_alerts(current)
    visible = list_notifications(
        actor_id=current["id"],
        actor_role=current["role"],
        actor_company_id=current.get("company_id"),
        notifications=get_notification_repository(),
    )
    return [_notification_response(notification) for notification in visible]


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count_endpoint(
    current: dict = Depends(get_current_user),
) -> UnreadCountResponse:
    """Notificaciones propias no leidas del actor (RF-149, HU-16)."""
    _generate_pending_sla_alerts(current)
    return UnreadCountResponse(
        count=count_unread(current["id"], get_notification_repository())
    )


@router.post("/read-all", response_model=MarkAllReadResponse)
def mark_all_read_endpoint(
    current: dict = Depends(get_current_user),
) -> MarkAllReadResponse:
    """Marca como leidas todas las notificaciones propias (RF-151)."""
    updated = mark_all_notifications_read(
        current["id"], get_notification_repository()
    )
    return MarkAllReadResponse(updated=updated)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read_endpoint(
    notification_id: str,
    current: dict = Depends(get_current_user),
) -> NotificationResponse:
    """Marca como leida una notificacion propia (RF-150).

    `notification_id` se declara como `str` (no `uuid.UUID`) para que un
    identificador mal formado no devuelva 422: el formato, la existencia y
    la propiedad se resuelven en la logica y se traducen aqui a 404
    uniforme, sin revelar si la notificacion existe.
    """
    try:
        notification = mark_notification_read(
            notification_id,
            current["id"],
            get_notification_repository(),
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _notification_response(notification)
