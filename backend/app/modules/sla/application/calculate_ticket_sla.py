"""Caso de uso de calculo del SLA de un ticket (RF-42, RF-43, RF-47).

Resuelve el tiempo objetivo de la prioridad vigente y delega el calculo
en el dominio. No almacena ni cachea el resultado: el SLA se deriva en
cada consulta del ticket y de la politica vigente, de modo que un cambio
de prioridad o el paso del tiempo lo actualizan sin intervencion manual
(RF-47, RF-48).

Un ticket sin prioridad no tiene SLA (`None`, RF-42). Una prioridad fuera
del catalogo tampoco (defensivo: `tickets` ya la valida).
"""

from datetime import datetime, timezone

from app.modules.sla.application.policies import target_minutes_for
from app.modules.sla.domain.entities import (
    TicketSla,
    TicketSlaSnapshot,
    calculate_sla,
)


def calculate_ticket_sla(
    snapshot: TicketSlaSnapshot,
    now: datetime | None = None,
) -> TicketSla | None:
    """Calcula el SLA del ticket o devuelve None si no tiene prioridad."""
    target_minutes = target_minutes_for(snapshot.priority)
    if target_minutes is None:
        return None
    reference = now if now is not None else datetime.now(timezone.utc)
    return calculate_sla(snapshot, target_minutes, reference)
