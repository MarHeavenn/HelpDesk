"""Registro en memoria de asignaciones de tickets, append-only (RF-37).

Mismo contrato y patron que `InMemoryTicketModificationLog` de este
modulo (y que `InMemorySessionStore` de `identity`): `add`,
`list_by_ticket`, `count` y `clear`, con singleton
`get_assignment_log()`. Sustituible por un adaptador PostgreSQL (tabla
`ticket_assignments`, indice `(ticket_id, assigned_at)`, seccion 3 del
plan) sin cambiar los casos de uso.

El registro es acumulativo: solo se anaden asignaciones efectivas (lo
decide el caso de uso; la repeticion del tecnico vigente no se registra)
y nada se elimina ni se sobreescribe por altas posteriores. Los registros
se conservan en orden de alta y un empate de `assigned_at` no fija orden
entre ellos (RF-37). El registro es la auditoria del ticket, aparte del
estado vigente: es interno y no se expone por ninguna operacion publica
ni forma parte de las respuestas de ticket.
"""

from app.modules.tickets.domain.entities import AssignmentRecord


class InMemoryAssignmentLog:
    """Guarda asignaciones en orden de alta, sin eliminarlas."""

    def __init__(self) -> None:
        self._records: list[AssignmentRecord] = []

    def add(self, record: AssignmentRecord) -> None:
        """Anade un registro al final; nunca sobreescribe ni elimina."""
        self._records.append(record)

    def list_by_ticket(self, ticket_id: str) -> list[AssignmentRecord]:
        """Registros del ticket, en orden de alta.

        Devuelve una lista vacia si el ticket no tiene registros. La
        lectura no altera el registro.
        """
        return [
            record for record in self._records if record.ticket_id == ticket_id
        ]

    def count(self) -> int:
        """Numero de registros almacenados de todos los tickets."""
        return len(self._records)

    def clear(self) -> None:
        """Vacia el registro (apoyo para pruebas)."""
        self._records.clear()


_assignments = InMemoryAssignmentLog()


def get_assignment_log() -> InMemoryAssignmentLog:
    """Devuelve el registro compartido de asignaciones."""
    return _assignments
