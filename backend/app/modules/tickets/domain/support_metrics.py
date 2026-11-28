"""Instantáneas y agregado puro de volumen y resolución (HU-18)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.modules.tickets.domain.entities import RESOLVED_STATUSES


@dataclass(frozen=True)
class TicketMetricsSnapshot:
    """Copia de solo lectura, sin personas ni contenido del ticket.

    Conserva los datos registrados sin validar ni completar fechas u
    objetivos. La selección autorizada y los cálculos pertenecen a sus
    respectivas capas, no a la captura de esta instantánea.
    """

    id: str
    company_id: str | None
    status: str
    priority: str | None
    created_at: datetime | None
    resolved_at: datetime | None
    resolved_target_minutes: int | None


@dataclass(frozen=True)
class ResolutionMetrics:
    """Volumen y promedio con muestra explícita; no evalúa ni presupone SLA."""

    total_tickets: int
    resolved_tickets: int
    pending_tickets: int
    average_resolution_minutes: float | None
    resolution_sample_size: int
    resolution_excluded_count: int


@dataclass(frozen=True)
class SupportMetrics(ResolutionMetrics):
    """Resultado completo, sin registros individuales ni datos personales."""

    sla_compliance_percentage: float | None
    sla_sample_size: int
    sla_met_count: int
    sla_excluded_count: int


def resolution_duration(created_at: object, resolved_at: object) -> timedelta | None:
    """Duración continua válida o None, sin inferir fechas ni zonas horarias."""
    if not isinstance(created_at, datetime) or not isinstance(resolved_at, datetime):
        return None
    try:
        if created_at.utcoffset() is None or resolved_at.utcoffset() is None:
            return None
        start = created_at.astimezone(timezone.utc)
        end = resolved_at.astimezone(timezone.utc)
        if end < start:
            return None
        return end - start
    except (ValueError, OverflowError):
        # Solo datos temporales inválidos/no representables, no errores
        # técnicos de la fuente ni del resto del cálculo.
        return None


def aggregate_resolution_metrics(
    tickets: Iterable[TicketMetricsSnapshot],
) -> ResolutionMetrics:
    """Agrega una vez las instantáneas únicas del conjunto ya autorizado.

    La autorización y selección por empresa corresponden a la aplicación.
    Solo Resuelto/Cerrado aportan muestras; el resto cuenta como pendiente,
    incluso si conserva una fecha de resolución. No exige prioridad ni SLA.
    """
    total = resolved = sample_size = total_microseconds = 0
    for ticket in tickets:
        total += 1
        if ticket.status not in RESOLVED_STATUSES:
            continue
        resolved += 1
        duration = resolution_duration(ticket.created_at, ticket.resolved_at)
        if duration is None:
            continue
        sample_size += 1
        # División entera exacta: timedelta tiene precisión de microsegundos.
        # Acumular enteros evita truncar minutos y desbordar un timedelta.
        total_microseconds += duration // timedelta(microseconds=1)

    return ResolutionMetrics(
        total_tickets=total,
        resolved_tickets=resolved,
        pending_tickets=total - resolved,
        average_resolution_minutes=(
            total_microseconds / (60_000_000 * sample_size) if sample_size else None
        ),
        resolution_sample_size=sample_size,
        resolution_excluded_count=resolved - sample_size,
    )


def compose_support_metrics(
    resolution: ResolutionMetrics,
    sla_results: Iterable[bool | None],
) -> SupportMetrics:
    """Completa el agregado con resultados del SLA ya autorizado/evaluado.

    None queda fuera de numerador y denominador. False participa en la
    muestra sin sumar cumplimiento; solo True suma a ambos. Aquí no se
    reconstruye el SLA ni se consulta una política.
    """
    sample_size = met_count = 0
    for result in sla_results:
        if result is None:
            continue
        if not isinstance(result, bool):
            raise TypeError("SLA evaluation must return bool or None")
        sample_size += 1
        met_count += int(result)

    return SupportMetrics(
        total_tickets=resolution.total_tickets,
        resolved_tickets=resolution.resolved_tickets,
        pending_tickets=resolution.pending_tickets,
        average_resolution_minutes=resolution.average_resolution_minutes,
        resolution_sample_size=resolution.resolution_sample_size,
        resolution_excluded_count=resolution.resolution_excluded_count,
        sla_compliance_percentage=(
            round(100 * met_count / sample_size, 2) if sample_size else None
        ),
        sla_sample_size=sample_size,
        sla_met_count=met_count,
        sla_excluded_count=resolution.resolved_tickets - sample_size,
    )
