"""Repositorio en memoria de comentarios de seguimiento (HU-07, RF-63).

Mismo contrato y patron que `InMemoryTicketRepository`: `add`,
`list_by_ticket`, `count`, `clear` y singleton
`get_ticket_comment_repository()`. Sustituible por un adaptador PostgreSQL
sobre la tabla `ticket_comments` sin cambiar los casos de uso ni la
interfaz.

El orden del listado es ascendente por `created_at` y estable: los
comentarios con la misma fecha y hora conservan el orden en que se
registraron, porque el `dict` interno mantiene la insercion y `sort` es
estable.
"""

from app.modules.tickets.domain.entities import TicketComment


class InMemoryTicketCommentRepository:
    """Guarda comentarios por identificador y los lista por ticket."""

    def __init__(self) -> None:
        self._by_id: dict[str, TicketComment] = {}

    def add(self, comment: TicketComment) -> None:
        """Guarda el comentario."""
        self._by_id[comment.id] = comment

    def list_by_ticket(self, ticket_id: str) -> list[TicketComment]:
        """Comentarios del ticket, del mas antiguo al mas reciente.

        Un empate de `created_at` conserva el orden de registro. Un ticket
        inexistente o sin comentarios devuelve una lista vacia.
        """
        comments = [
            comment
            for comment in self._by_id.values()
            if comment.ticket_id == ticket_id
        ]
        comments.sort(key=lambda comment: comment.created_at)
        return comments

    def count(self) -> int:
        """Numero de comentarios almacenados."""
        return len(self._by_id)

    def clear(self) -> None:
        """Vacia el repositorio (apoyo para pruebas)."""
        self._by_id.clear()


_comments = InMemoryTicketCommentRepository()


def get_ticket_comment_repository() -> InMemoryTicketCommentRepository:
    """Devuelve el repositorio compartido de comentarios."""
    return _comments
