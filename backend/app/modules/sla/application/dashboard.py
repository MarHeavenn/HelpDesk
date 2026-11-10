"""Agregado del dashboard de cumplimiento de SLA (HU-12, RF-94..RF-101).

El calculo de SLA ya existe en HU-05/HU-14: este modulo no duplica la
politica ni el dominio, solo recorre una instantanea de tickets, llama a
`calculate_ticket_sla` y acumula los estados. La configuracion vigente se
lee en cada llamada (HU-14, RF-76), de modo que un cambio de politica se
refleja sin recalcular ni persistir nada.

Reglas:
- Solo `administrador` y `tecnico`; otro rol lanza
  `SlaDashboardAccessDeniedError` (-> 404 uniforme).
- El administrador agrega todos los tickets; el tecnico solo los asignados
  a el (mismo alcance que HU-11, RF-100).
- El periodo filtra por `created_at` entre `generated_at - days` y
  `generated_at`, incluido el limite inferior y excluidas fechas futuras.
- Un ticket sin prioridad cuenta en `sin_sla` y no en `total_evaluated`.
- Un ticket `Resuelto`/`Cerrado` sin `resolved_at` cuenta como `cumplido`
  y se informa en `closed_without_resolved_at` (RF-97).
- Los porcentajes se redondean a dos decimales y valen `0.0` sin tickets
  evaluables (RF-98, RF-101).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.modules.sla.application.calculate_ticket_sla import (
    calculate_ticket_sla,
)
from app.modules.sla.domain.entities import (
    RISK_THRESHOLD_RATIO,
    SLA_AT_RISK,
    SLA_BREACHED,
    SLA_MET,
    SLA_ON_TIME,
    TicketSlaSnapshot,
)
from app.modules.sla.domain.policy_config import SLA_PRIORITIES

ADMIN_ROLE = "administrador"
TECHNICIAN_ROLE = "tecnico"
MANAGEMENT_ROLES = frozenset({ADMIN_ROLE, TECHNICIAN_ROLE})
DENIED_MESSAGE = "sla not found"
DEFAULT_PERIOD_DAYS = 30
PERIOD_DAYS = (7, 30, 90)


class SlaDashboardAccessDeniedError(ValueError):
    """El rol del actor no puede consultar el dashboard (-> 404)."""


@dataclass(frozen=True)
class SlaDashboardTicket:
    """Datos minimos de un ticket para la agregacion de SLA.

    `is_resolved` lo deriva el contrato de `tickets`; el modulo `sla` no
    necesita conocer los nombres de estado del ciclo de vida.
    """

    id: str
    priority: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolved_target_minutes: int | None
    assignee_id: str | None
    is_resolved: bool


@dataclass(frozen=True)
class SlaPriorityCount:
    """Conteos de SLA de una prioridad (RF-99)."""

    priority: str
    en_tiempo: int
    en_riesgo: int
    cumplido: int
    incumplido: int
    compliance_percentage: float


@dataclass(frozen=True)
class SlaDashboard:
    """Resumen agregado de cumplimiento de SLA (RF-98)."""

    total_evaluated: int
    en_tiempo: int
    en_riesgo: int
    cumplido: int
    incumplido: int
    sin_sla: int
    compliance_percentage: float
    closed_without_resolved_at: int
    threshold_percent: int
    period_days: int
    by_priority: list[SlaPriorityCount]
    generated_at: datetime


def _percentage(met: int, total: int) -> float:
    """Porcentaje de cumplimiento redondeado a dos decimales (RF-98)."""
    if total == 0:
        return 0.0
    return round(met / total * 100, 2)


def _empty_counts() -> dict[str, int]:
    """Contadores de los cuatro estados de SLA en cero."""
    return {
        SLA_ON_TIME: 0,
        SLA_AT_RISK: 0,
        SLA_MET: 0,
        SLA_BREACHED: 0,
    }


def get_sla_dashboard(
    *,
    actor_id: str,
    actor_role: str,
    tickets: Sequence[SlaDashboardTicket],
    now: datetime | None = None,
    days: int = DEFAULT_PERIOD_DAYS,
) -> SlaDashboard:
    """Construye el resumen de cumplimiento del alcance y periodo del actor.

    Administrador: todos los tickets. Tecnico: solo los asignados a el.
    Cualquier otro rol lanza `SlaDashboardAccessDeniedError` (RF-100). El
    calculo se hace en una sola pasada sobre la misma instantanea, sin
    persistir ni mutar tickets (RF-104).
    """
    if actor_role not in MANAGEMENT_ROLES:
        raise SlaDashboardAccessDeniedError(DENIED_MESSAGE)

    generated_at = now or datetime.now(timezone.utc)
    period_start = generated_at - timedelta(days=days)

    totals = _empty_counts()
    by_priority = {
        priority: _empty_counts() for priority in SLA_PRIORITIES
    }
    sin_sla = 0
    closed_without_resolved_at = 0

    for ticket in tickets:
        if not period_start <= ticket.created_at <= generated_at:
            continue
        if actor_role == TECHNICIAN_ROLE and ticket.assignee_id != actor_id:
            continue

        if ticket.priority is None:
            sin_sla += 1
            continue

        if ticket.is_resolved and ticket.resolved_at is None:
            # Ticket antiguo sin fecha de resolucion: no se puede comparar
            # contra el vencimiento; se informa en lugar de ocultarlo.
            totals[SLA_MET] += 1
            closed_without_resolved_at += 1
            priority_counts = by_priority.get(ticket.priority)
            if priority_counts is not None:
                priority_counts[SLA_MET] += 1
            continue

        sla = calculate_ticket_sla(
            TicketSlaSnapshot(
                priority=ticket.priority,
                created_at=ticket.created_at,
                resolved_at=ticket.resolved_at,
                resolved_target_minutes=ticket.resolved_target_minutes,
            ),
            now=generated_at,
        )
        if sla is None:
            # Prioridad fuera del catalogo o sin objetivo vigente: no hay
            # SLA que evaluar (defensivo; `tickets` ya valida el catalogo).
            sin_sla += 1
            continue

        totals[sla.status] += 1
        priority_counts = by_priority.get(ticket.priority)
        if priority_counts is not None:
            priority_counts[sla.status] += 1

    total_evaluated = sum(totals.values())
    priority_breakdown = [
        SlaPriorityCount(
            priority=priority,
            en_tiempo=counts[SLA_ON_TIME],
            en_riesgo=counts[SLA_AT_RISK],
            cumplido=counts[SLA_MET],
            incumplido=counts[SLA_BREACHED],
            compliance_percentage=_percentage(
                counts[SLA_ON_TIME] + counts[SLA_MET],
                sum(counts.values()),
            ),
        )
        for priority, counts in by_priority.items()
    ]

    return SlaDashboard(
        total_evaluated=total_evaluated,
        en_tiempo=totals[SLA_ON_TIME],
        en_riesgo=totals[SLA_AT_RISK],
        cumplido=totals[SLA_MET],
        incumplido=totals[SLA_BREACHED],
        sin_sla=sin_sla,
        compliance_percentage=_percentage(
            totals[SLA_ON_TIME] + totals[SLA_MET],
            total_evaluated,
        ),
        closed_without_resolved_at=closed_without_resolved_at,
        threshold_percent=int(RISK_THRESHOLD_RATIO * 100),
        period_days=days,
        by_priority=priority_breakdown,
        generated_at=generated_at,
    )
