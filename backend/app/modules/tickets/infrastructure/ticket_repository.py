"""Repositorio de tickets con lecturas e inserción SQL (HU-26 B.I.3–6).

Mismo contrato y patron que `InMemoryUserRepository` de `identity`:
`add`, `find_by_id`, `list_by_requester` (orden descendente por
`created_at`), `count` y `clear`, con singleton
`get_ticket_repository()`. ID, listados y contador usan PostgreSQL si está
configurado, incluida la instantánea de métricas y el alta. Las mutaciones
siguen pendientes; no desplegar este adaptador transitorio parcialmente.

No impone deduplicacion: titulos y descripciones repetidos son validos
(RF-12.5).
"""

from uuid import UUID

from psycopg.pq import TransactionStatus

from app.infrastructure.db import (
    connection,
    in_memory_fallback_enabled,
    postgres_configured,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.domain.support_metrics import TicketMetricsSnapshot


class InMemoryTicketRepository:
    """Guarda tickets por identificador."""

    def __init__(self) -> None:
        self._by_id: dict[str, Ticket] = {}

    def add(self, ticket: Ticket, conn=None) -> None:
        """Inserta sin sobrescribir progreso ni publicar caché SQL.

        Con conexión propia retorna después del commit; con conexión externa
        solo libera su savepoint y el llamador conserva commit/rollback.
        """
        if conn is None and not postgres_configured():
            self._require_memory()
            self._by_id[ticket.id] = ticket
            return
        if conn is None:
            with connection() as owned:
                self.add(ticket, owned)
            return
        # Patrón A5: incluso idle/autocommit necesita una transacción externa
        # para que transaction() sea un savepoint, no un COMMIT del llamador.
        if conn.info.transaction_status == TransactionStatus.IDLE:
            conn.execute("BEGIN")
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO tickets (
                    id, company_id, requester_id, title, description,
                    created_at, priority, status, assignee_id, assignee_name,
                    resolved_at, resolved_target_minutes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticket.id, ticket.company_id, ticket.requester_id,
                    ticket.title, ticket.description, ticket.created_at,
                    ticket.priority, ticket.status, ticket.assignee_id,
                    ticket.assignee_name, ticket.resolved_at,
                    ticket.resolved_target_minutes,
                ),
            )

    def find_by_id(self, ticket_id: str) -> Ticket | None:
        """Relee la fila propia sin caché; memoria solo por seam explícito.

        Los IDs inválidos dan None; los errores SQL se propagan. Cada lectura
        crea un agregado nuevo sin mutar referencias retenidas ni completar
        nombres, resolución u objetivos ausentes.
        """
        if not isinstance(ticket_id, str):
            return None
        if postgres_configured():
            try:
                canonical_id = str(UUID(ticket_id))
            except ValueError:
                return None
            with connection() as conn:
                row = conn.execute(
                    """
                    SELECT id::text AS id, company_id::text AS company_id,
                           requester_id::text AS requester_id,
                           assignee_id::text AS assignee_id, title, description,
                           created_at, priority, status, assignee_name,
                           resolved_at, resolved_target_minutes
                    FROM tickets
                    WHERE id = %s
                    """,
                    (canonical_id,),
                ).fetchone()
            return Ticket(**row) if row is not None else None
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar tickets"
            )
        return self._by_id.get(ticket_id)

    def list_by_requester(self, requester_id: str) -> list[Ticket]:
        """Tickets del solicitante, ordenados por `created_at` descendente
        (los mas recientes primero). Un empate no fija orden."""
        if postgres_configured():
            return self._list_sql("requester_id", requester_id)
        self._require_memory()
        tickets = [
            ticket
            for ticket in self._by_id.values()
            if ticket.requester_id == requester_id
        ]
        tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
        return tickets

    def list_by_assignee(self, assignee_id: str) -> list[Ticket]:
        """Tickets del tecnico responsable, ordenados por `created_at`
        descendente (los mas recientes primero). Incluye cualquier estado,
        tambien `Cerrado` (RF-36); un empate no fija orden."""
        if postgres_configured():
            return self._list_sql("assignee_id", assignee_id)
        self._require_memory()
        tickets = [
            ticket
            for ticket in self._by_id.values()
            if ticket.assignee_id == assignee_id
        ]
        tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
        return tickets

    def list_all(self) -> list[Ticket]:
        """Todos los tickets del sistema, ordenados por created_at descendente.

        El agregado del dashboard recorre una sola vez esta lista para que
        las invariantes de estado, prioridad y tecnico se calculen sobre el
        mismo conjunto (RF-89).
        """
        if postgres_configured():
            return self._list_sql()
        self._require_memory()
        tickets = list(self._by_id.values())
        tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
        return tickets

    def _list_sql(self, field: str | None = None, value: str | None = None) -> list[Ticket]:
        """Consulta propia; field solo procede de los métodos internos anteriores."""
        parameters = ()
        if field is not None:
            if not isinstance(value, str):
                return []
            try:
                parameters = (str(UUID(value)),)
            except ValueError:
                return []
        query = """
            SELECT id::text AS id, company_id::text AS company_id,
                   requester_id::text AS requester_id,
                   assignee_id::text AS assignee_id, title, description,
                   created_at, priority, status, assignee_name,
                   resolved_at, resolved_target_minutes
            FROM tickets
        """
        if field is not None:
            query += f" WHERE {field} = %s"
        query += " ORDER BY created_at DESC"
        with connection() as conn:
            rows = conn.execute(query, parameters).fetchall()
        return [Ticket(**row) for row in rows]

    @staticmethod
    def _require_memory() -> None:
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar tickets"
            )

    def snapshot_for_metrics(self) -> tuple[TicketMetricsSnapshot, ...]:
        """Copia mínima de todos los tickets en una sola lectura (HU-18).

        Sin ordenar, filtrar ni paginar: las fechas inválidas permanecen
        disponibles para los conteos y su posterior exclusión de muestras.
        No conserva referencias a tickets mutables ni altera las lecturas
        existentes; el llamador debe autorizar y delimitar la empresa.
        """
        if postgres_configured():
            with connection() as conn:
                rows = conn.execute(
                    """
                    SELECT id::text AS id, company_id::text AS company_id,
                           status, priority, created_at, resolved_at,
                           resolved_target_minutes
                    FROM tickets
                    """
                ).fetchall()
            return tuple(TicketMetricsSnapshot(**row) for row in rows)
        self._require_memory()
        return tuple(
            TicketMetricsSnapshot(
                id=ticket.id,
                company_id=ticket.company_id,
                status=ticket.status,
                priority=ticket.priority,
                created_at=ticket.created_at,
                resolved_at=ticket.resolved_at,
                resolved_target_minutes=ticket.resolved_target_minutes,
            )
            for ticket in self._by_id.values()
        )

    def count(self) -> int:
        """Número de tickets confirmados; en el seam, número de objetos locales."""
        if postgres_configured():
            with connection() as conn:
                return conn.execute("SELECT count(*) AS total FROM tickets").fetchone()["total"]
        self._require_memory()
        return len(self._by_id)

    def clear(self) -> None:
        """Vacía solo el seam explícito; nunca limpia almacenamiento SQL."""
        if postgres_configured():
            raise RuntimeError("clear solo está disponible en el seam de memoria")
        self._require_memory()
        self._by_id.clear()


_tickets = InMemoryTicketRepository()


def get_ticket_repository() -> InMemoryTicketRepository:
    """Devuelve el repositorio compartido de tickets."""
    return _tickets
