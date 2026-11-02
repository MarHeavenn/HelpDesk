"""Entidades y reglas de dominio del modulo sla (HU-05).

Cubre RF-41 (tiempos objetivo por prioridad), RF-42 (ticket sin prioridad
sin SLA), RF-43 (inicio, vencimiento, transcurrido y restante), RF-45
(estados y umbral), RF-46 (congelacion al resolver) y RF-50 (precision).

Reglas:
- El SLA solo existe si el ticket tiene prioridad.
- El inicio es siempre `created_at` del ticket, aunque la prioridad se
  haya fijado despues (RF-43.1).
- El vencimiento es el inicio mas `target_minutes` (RF-43.2).
- `resolved_at` distinto de None congela el SLA: `cumplido` si la
  resolucion es en el vencimiento o antes; `incumplido` si es despues
  (RF-45.3, RF-46).
- Sin resolucion: `en_riesgo` cuando falta un 20 % o menos del objetivo
  y aun queda tiempo; `incumplido` cuando el instante de referencia es
  igual o posterior al vencimiento; `en_tiempo` en el resto (RF-45.1,
  RF-45.2).
- Los minutos se truncan y `remaining_minutes` nunca es negativo
  (RF-50). El estado se decide con duraciones exactas, no con los minutos
  redondeados.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

# Estados del SLA (RF-45). Alineados con el ADR-006 del frontend.
SLA_ON_TIME = "en_tiempo"
SLA_AT_RISK = "en_riesgo"
SLA_MET = "cumplido"
SLA_BREACHED = "incumplido"
SLA_STATUSES = (SLA_ON_TIME, SLA_AT_RISK, SLA_MET, SLA_BREACHED)

# Proporcion del tiempo objetivo que marca "proximo a vencer" (RF-45.1).
RISK_THRESHOLD_RATIO = 0.20

SECONDS_PER_MINUTE = 60


@dataclass(frozen=True)
class SlaPolicy:
    """Tiempo objetivo de SLA de una prioridad (RF-41)."""

    priority: str
    target_minutes: int


@dataclass(frozen=True)
class TicketSlaSnapshot:
    """Datos del ticket que necesita el SLA, sin acoplarse a `tickets`.

    `priority` vacia significa que el ticket aun no tiene SLA (RF-42).
    `resolved_at` distinto de None indica que el ticket se resolvio y el
    SLA debe congelarse en ese instante (RF-46).
    """

    priority: str | None
    created_at: datetime
    resolved_at: datetime | None = None


@dataclass(frozen=True)
class TicketSla:
    """Resultado del calculo de SLA de un ticket (RF-43, RF-44, RF-45)."""

    target_minutes: int
    started_at: datetime
    due_at: datetime
    elapsed_minutes: int
    remaining_minutes: int
    status: str
    near_due: bool
    breached: bool


def _whole_minutes_between(start: datetime, end: datetime) -> int:
    """Minutos completos entre dos instantes, nunca negativos (RF-50)."""
    return max(0, int((end - start).total_seconds() // SECONDS_PER_MINUTE))


def calculate_sla(
    snapshot: TicketSlaSnapshot,
    target_minutes: int,
    now: datetime,
) -> TicketSla:
    """Calcula el SLA de un ticket que ya tiene prioridad (RF-43, RF-45).

    `target_minutes` debe ser positivo. `now` es el instante de referencia
    cuando el ticket no esta resuelto; si `snapshot.resolved_at` tiene
    valor, el SLA se congela y `now` no influye en el estado (RF-46).
    """
    started_at = snapshot.created_at
    due_at = started_at + timedelta(minutes=target_minutes)
    resolved_at = snapshot.resolved_at

    if resolved_at is not None:
        status = SLA_MET if resolved_at <= due_at else SLA_BREACHED
        reference = resolved_at
        remaining_minutes = 0
    else:
        reference = now
        if now >= due_at:
            status = SLA_BREACHED
            remaining_minutes = 0
        else:
            time_to_due = due_at - now
            risk_window = timedelta(
                minutes=target_minutes * RISK_THRESHOLD_RATIO
            )
            if time_to_due <= risk_window:
                status = SLA_AT_RISK
            else:
                status = SLA_ON_TIME
            remaining_minutes = _whole_minutes_between(now, due_at)

    return TicketSla(
        target_minutes=target_minutes,
        started_at=started_at,
        due_at=due_at,
        elapsed_minutes=_whole_minutes_between(started_at, reference),
        remaining_minutes=remaining_minutes,
        status=status,
        near_due=status == SLA_AT_RISK,
        breached=status == SLA_BREACHED,
    )
