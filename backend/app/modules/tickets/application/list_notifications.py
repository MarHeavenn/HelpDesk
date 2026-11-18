"""Consulta de notificaciones visibles para un actor (HU-15, RF-147, RF-148).

La visibilidad depende del rol:

- `administrador` y `supervisor` supervisan todas las notificaciones de su
  misma empresa (`company_id`), con el mismo aislamiento multitenant que
  el detalle de ticket de HU-06;
- `tecnico` y `cliente` solo ven las dirigidas a ellos.

El repositorio ya devuelve el orden descendente determinista de RF-147. La
visibilidad de la notificacion no altera las reglas de acceso al ticket:
solo autoriza a leer el aviso.
"""

from app.modules.tickets.domain.entities import (
    NOTIFICATION_VIEW_ALL_ROLES,
    TicketNotification,
)
from app.modules.tickets.infrastructure.notification_repository import (
    InMemoryNotificationRepository,
)


def list_notifications(
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    notifications: InMemoryNotificationRepository,
) -> list[TicketNotification]:
    """Notificaciones visibles para el actor, de la mas reciente a la mas
    antigua (RF-147, RF-148)."""
    if actor_role in NOTIFICATION_VIEW_ALL_ROLES:
        return notifications.list_by_company(actor_company_id)
    return notifications.list_by_recipient(actor_id)
