"""Caso de uso del listado global de tickets (HU-23, RF-119, RF-122).

Devuelve todos los tickets del sistema, en cualquier estado y con
independencia de quien los creo o de quien sea su tecnico responsable. El
orden por `created_at` descendente lo garantiza el repositorio.

Solo los roles de gestion (`tecnico`/`administrador`) pueden consultar el
listado; cualquier otro rol recibe el 404 uniforme (`TicketNotFoundError`
con `TICKET_NOT_FOUND_MESSAGE`) **antes** de leer el repositorio, sin
revelar datos (RF-122). La regla de acceso vive aqui, en la capa de
aplicacion, no en el controlador HTTP.

No muta tickets ni registros: es una consulta de solo lectura.
"""

from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.domain.entities import MANAGEMENT_ROLES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_all_tickets(
    actor_role: str,
    tickets: InMemoryTicketRepository,
) -> list[Ticket]:
    """Todos los tickets del sistema, mas recientes primero (RF-122).

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02/HU-03/HU-04) si
    el rol no es de gestion, antes de leer el repositorio.
    """
    if actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return tickets.list_all()
