"""Repositorio en memoria de notificaciones de ticket (HU-15, RF-146).

Mismo contrato y patron que los demas repositorios en memoria de
`tickets`: `add`, busquedas de lectura, `count` y `clear`, con singleton
`get_notification_repository()`. Sustituible por un adaptador PostgreSQL
sin cambiar los casos de uso.

Las notificaciones se conservan en orden de alta. La lectura devuelve
siempre de la mas reciente a la mas antigua; cuando dos comparten
`created_at`, el desempate es por orden de registro descendente, de modo
que el orden es determinista (RF-147). El repositorio no conoce reglas de
visibilidad ni de destinatarios: eso vive en la capa de aplicacion.

`find_by_dedupe_key` permite que las alertas de SLA de HU-16 no se
repitan para el mismo evento (RF-158). Las notificaciones de HU-15 no
tienen clave y nunca coinciden.
"""

from threading import Lock

from app.modules.tickets.domain.entities import TicketNotification


class InMemoryNotificationRepository:
    """Guarda notificaciones y las lee ordenadas por fecha descendente."""

    def __init__(self) -> None:
        self._items: list[TicketNotification] = []
        self._dedupe_lock = Lock()

    def add(self, notification: TicketNotification) -> None:
        """Anade una notificacion al final del registro."""
        self._items.append(notification)

    def add_if_new(self, notification: TicketNotification) -> bool:
        """Inserta una alerta con clave solo si no existe, de forma atomica."""
        if notification.dedupe_key is None:
            raise ValueError("dedupe_key is required")
        with self._dedupe_lock:
            if self.find_by_dedupe_key(notification.dedupe_key) is not None:
                return False
            self.add(notification)
            return True

    def find_by_id(self, notification_id: str) -> TicketNotification | None:
        """Busca por identificador; None si no existe o no es texto."""
        if not isinstance(notification_id, str):
            return None
        for notification in self._items:
            if notification.id == notification_id:
                return notification
        return None

    def list_by_recipient(self, recipient_id: str) -> list[TicketNotification]:
        """Notificaciones dirigidas al usuario, de la mas reciente a la mas
        antigua (RF-147)."""
        return self._ordered(
            lambda notification: notification.recipient_id == recipient_id
        )

    def find_by_dedupe_key(
        self, dedupe_key: str
    ) -> TicketNotification | None:
        """Busca una alerta por su clave de deduplicacion (HU-16, RF-158)."""
        for notification in self._items:
            if notification.dedupe_key == dedupe_key:
                return notification
        return None

    def list_by_company(self, company_id: str | None) -> list[TicketNotification]:
        """Notificaciones de la empresa, de la mas reciente a la mas antigua.

        Compara `company_id` por igualdad, de modo que el ambito sin empresa
        (`None`) tambien se resuelve (RF-148).
        """
        return self._ordered(
            lambda notification: notification.company_id == company_id
        )

    def _ordered(self, predicate) -> list[TicketNotification]:
        indexed = [
            (index, notification)
            for index, notification in enumerate(self._items)
            if predicate(notification)
        ]
        indexed.sort(key=lambda pair: (pair[1].created_at, pair[0]), reverse=True)
        return [notification for _, notification in indexed]

    def count(self) -> int:
        """Numero de notificaciones almacenadas."""
        return len(self._items)

    def clear(self) -> None:
        """Vacia el repositorio (apoyo para pruebas)."""
        self._items.clear()


_notifications = InMemoryNotificationRepository()


def get_notification_repository() -> InMemoryNotificationRepository:
    """Devuelve el repositorio compartido de notificaciones."""
    return _notifications
