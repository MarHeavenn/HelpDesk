"""Consulta autorizada de métricas HU-18, con lectura y SLA inyectados."""

from collections.abc import Callable, Iterable
from datetime import datetime

from app.modules.tickets.domain.entities import PRIORITIES, RESOLVED_STATUSES
from app.modules.tickets.domain.support_metrics import (
    SupportMetrics,
    TicketMetricsSnapshot,
    aggregate_resolution_metrics,
    compose_support_metrics,
    resolution_duration,
)

FrozenResolutionEvaluator = Callable[
    [str | None, datetime | None, datetime | None, int | None], bool | None
]


class SupportMetricsAccessDeniedError(ValueError):
    """Consulta no visible para el actor; la interfaz la traducirá a 404."""


def _is_sla_candidate(ticket: TicketMetricsSnapshot) -> bool:
    target = ticket.resolved_target_minutes
    return (
        ticket.status in RESOLVED_STATUSES
        and ticket.priority in PRIORITIES
        and isinstance(target, int)
        and not isinstance(target, bool)
        and target > 0
        and resolution_duration(ticket.created_at, ticket.resolved_at) is not None
    )


def get_support_metrics(
    *,
    actor_role: str,
    actor_company_id: str | None,
    read_snapshot: Callable[[], Iterable[TicketMetricsSnapshot]],
    evaluate_resolution: FrozenResolutionEvaluator,
) -> SupportMetrics:
    """Autoriza antes de leer y compone sobre un único conjunto por empresa.

    No resuelve identidad ni accede a repositorios o contratos ajenos.
    El evaluador solo recibe finalizados autorizados con datos candidatos;
    ningún objetivo ausente se completa con la configuración vigente.
    """
    if (
        actor_role != "administrador"
        or not isinstance(actor_company_id, str)
        or not actor_company_id.strip()
    ):
        raise SupportMetricsAccessDeniedError("not found")

    authorized = tuple(
        ticket for ticket in read_snapshot()
        if ticket.company_id == actor_company_id
    )
    resolution = aggregate_resolution_metrics(authorized)
    evaluations = [
        evaluate_resolution(
            ticket.priority, ticket.created_at, ticket.resolved_at,
            ticket.resolved_target_minutes,
        )
        for ticket in authorized
        if _is_sla_candidate(ticket)
    ]
    return compose_support_metrics(resolution, evaluations)
