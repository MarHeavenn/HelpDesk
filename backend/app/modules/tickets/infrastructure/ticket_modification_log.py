"""Registro en memoria de modificaciones de tickets, append-only (RF-26).

Mismo contrato y patron que `InMemorySessionStore` de `identity` y
`InMemoryTicketRepository` de este modulo: `add`, `list_by_ticket`,
`count` y `clear`, con singleton `get_ticket_modification_log()`.
Sustituible por un adaptador PostgreSQL (tabla `ticket_modifications`,
indice `(ticket_id, changed_at)`) sin cambiar los casos de uso.

El registro es acumulativo: solo se anaden cambios efectivos (lo decide
el caso de uso) y nada se elimina ni se sobreescribe por altas
posteriores. Los registros se conservan en orden de alta y un empate de
`changed_at` no fija orden entre ellos (RF-26). El registro es interno:
no se expone por ninguna operacion publica.
"""

from app.modules.tickets.domain.entities import TicketModification


class InMemoryTicketModificationLog:
    """Guarda modificaciones en orden de alta, sin eliminarlas."""

    def __init__(self) -> None:
        self._records: list[TicketModification] = []

    def add(self, modification: TicketModification) -> None:
        """Anade un registro al final; nunca sobreescribe ni elimina."""
        self._records.append(modification)

    def list_by_ticket(self, ticket_id: str) -> list[TicketModification]:
        """Registros del ticket, en orden de alta.

        Devuelve una lista vacia si el ticket no tiene registros. La
        lectura no altera el registro.
        """
        return [
            modification
            for modification in self._records
            if modification.ticket_id == ticket_id
        ]

    def count(self) -> int:
        """Numero de registros almacenados de todos los tickets."""
        return len(self._records)

    def clear(self) -> None:
        """Vacia el registro (apoyo para pruebas)."""
        self._records.clear()


_modifications = InMemoryTicketModificationLog()


def get_ticket_modification_log() -> InMemoryTicketModificationLog:
    """Devuelve el registro compartido de modificaciones."""
    return _modifications
