"""Repositorio en memoria de tickets (RF-13, RF-15, RF-16, RF-17).

Mismo contrato y patron que `InMemoryUserRepository` de `identity`:
`add`, `find_by_id`, `list_by_requester` (orden descendente por
`created_at`), `count` y `clear`, con singleton
`get_ticket_repository()`. Sustituible por un adaptador PostgreSQL sin
cambiar los casos de uso ni la interfaz.

No impone deduplicacion: titulos y descripciones repetidos son validos
(RF-12.5).
"""

from app.modules.tickets.domain.entities import Ticket


class InMemoryTicketRepository:
    """Guarda tickets por identificador."""

    def __init__(self) -> None:
        self._by_id: dict[str, Ticket] = {}

    def add(self, ticket: Ticket) -> None:
        """Guarda el ticket."""
        self._by_id[ticket.id] = ticket

    def find_by_id(self, ticket_id: str) -> Ticket | None:
        """Busca por identificador; None si no existe o el valor no es texto."""
        if not isinstance(ticket_id, str):
            return None
        return self._by_id.get(ticket_id)

    def list_by_requester(self, requester_id: str) -> list[Ticket]:
        """Tickets del solicitante, ordenados por `created_at` descendente
        (los mas recientes primero). Un empate no fija orden."""
        tickets = [
            ticket
            for ticket in self._by_id.values()
            if ticket.requester_id == requester_id
        ]
        tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
        return tickets

    def count(self) -> int:
        """Numero de tickets almacenados."""
        return len(self._by_id)

    def clear(self) -> None:
        """Vacia el repositorio (apoyo para pruebas)."""
        self._by_id.clear()


_tickets = InMemoryTicketRepository()


def get_ticket_repository() -> InMemoryTicketRepository:
    """Devuelve el repositorio compartido de tickets."""
    return _tickets
