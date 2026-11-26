"""Caso de uso del listado global de tickets (HU-23, RF-119, RF-122).

Devuelve todos los tickets de la empresa de la sesión, en cualquier estado y con
independencia de quien los creo o de quien sea su tecnico responsable. El
orden por `created_at` descendente lo garantiza el repositorio.

Solo los roles de lectura (`tecnico`/`administrador`/`supervisor`) pueden consultar el
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
from app.modules.tickets.domain.entities import TICKET_READ_ROLES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)


def list_all_tickets(
    actor_role: str,
    tickets: InMemoryTicketRepository,
    actor_company_id: str | None,
) -> list[Ticket]:
    """Todos los tickets del tenant, mas recientes primero (RF-122/RF-177).

    Lanza `TicketNotFoundError` (mensaje unificado de HU-02/HU-03/HU-04) si
    el rol no tiene lectura o no hay empresa, antes de leer el repositorio.
    """
    if actor_company_id is None or actor_role not in TICKET_READ_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return [
        ticket for ticket in tickets.list_all()
        if ticket.company_id == actor_company_id
    ]
