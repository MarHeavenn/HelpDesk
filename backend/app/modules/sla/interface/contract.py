"""Frontera del modulo sla hacia otros modulos (RF-44).

`tickets` compone el SLA de sus respuestas llamando a `get_ticket_sla`
con un `TicketSlaSnapshot`. El modulo sla no importa nada de `tickets` ni
accede a sus repositorios: solo recibe los datos que necesita (prioridad,
creacion y resolucion) y devuelve el resultado o None. Es el contrato que
evita una dependencia circular entre ambos modulos.
"""

from datetime import datetime

from app.modules.sla.application.calculate_ticket_sla import (
    calculate_ticket_sla,
)
from app.modules.sla.domain.entities import TicketSla, TicketSlaSnapshot


def get_ticket_sla(
    snapshot: TicketSlaSnapshot,
    now: datetime | None = None,
) -> TicketSla | None:
    """Devuelve el SLA del ticket o None si no tiene prioridad (RF-42)."""
    return calculate_ticket_sla(snapshot, now=now)
