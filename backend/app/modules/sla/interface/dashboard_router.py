"""Ruta HTTP del dashboard de cumplimiento de SLA (HU-12, RF-93..RF-101).

Solo comunica: resuelve la sesion, obtiene la vista de lectura de
`tickets`, delega la agregacion en `sla.application.dashboard` y traduce
el rol no autorizado a un 404 uniforme. No accede a las tablas internas
de `tickets`: usa su contrato de lectura.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AfterValidator, BaseModel

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.sla.application.dashboard import (
    PERIOD_DAYS,
    SlaDashboard,
    SlaDashboardAccessDeniedError,
    SlaDashboardTicket,
    get_sla_dashboard,
)
from app.modules.tickets.interface.sla_contract import (
    SlaTicketView,
    list_sla_tickets,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _validate_period_days(value: int) -> int:
    """Acepta solo los periodos soportados por el dashboard (RF-94)."""
    if value not in PERIOD_DAYS:
        raise ValueError("days must be 7, 30 or 90")
    return value


PeriodDays = Annotated[int, AfterValidator(_validate_period_days)]


class SlaPriorityBreakdownResponse(BaseModel):
    """Conteos de SLA de una prioridad (RF-99)."""

    priority: str
    en_tiempo: int
    en_riesgo: int
    cumplido: int
    incumplido: int
    compliance_percentage: float


class SlaDashboardResponse(BaseModel):
    """Contrato de `GET /api/dashboard/sla` (RF-98)."""

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
    by_priority: list[SlaPriorityBreakdownResponse]
    generated_at: str


def _serialize(dashboard: SlaDashboard) -> SlaDashboardResponse:
    """Proyecta el agregado al contrato HTTP."""
    return SlaDashboardResponse(
        total_evaluated=dashboard.total_evaluated,
        en_tiempo=dashboard.en_tiempo,
        en_riesgo=dashboard.en_riesgo,
        cumplido=dashboard.cumplido,
        incumplido=dashboard.incumplido,
        sin_sla=dashboard.sin_sla,
        compliance_percentage=dashboard.compliance_percentage,
        closed_without_resolved_at=dashboard.closed_without_resolved_at,
        threshold_percent=dashboard.threshold_percent,
        period_days=dashboard.period_days,
        by_priority=[
            SlaPriorityBreakdownResponse(
                priority=item.priority,
                en_tiempo=item.en_tiempo,
                en_riesgo=item.en_riesgo,
                cumplido=item.cumplido,
                incumplido=item.incumplido,
                compliance_percentage=item.compliance_percentage,
            )
            for item in dashboard.by_priority
        ],
        generated_at=dashboard.generated_at.isoformat(),
    )


def _to_dashboard_ticket(ticket: SlaTicketView) -> SlaDashboardTicket:
    """Mapea la vista de `tickets` al DTO de la aplicacion de SLA."""
    return SlaDashboardTicket(
        id=ticket.id,
        priority=ticket.priority,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
        resolved_target_minutes=ticket.resolved_target_minutes,
        assignee_id=ticket.assignee_id,
        is_resolved=ticket.is_resolved,
    )


@router.get("/sla", response_model=SlaDashboardResponse)
def get_sla_dashboard_endpoint(
    current: dict = Depends(get_current_user),
    days: PeriodDays = 30,
) -> SlaDashboardResponse:
    """Resumen de cumplimiento; administrador global y tecnico con alcance.

    Sin sesion valida, `get_current_user` responde 401 antes de validar
    `days` (RF-93). El cliente recibe 404 uniforme sin datos (RF-100).
    """
    try:
        dashboard = get_sla_dashboard(
            actor_id=current["id"],
            actor_role=current["role"],
            tickets=[
                _to_dashboard_ticket(ticket) for ticket in list_sla_tickets()
            ],
            days=days,
        )
    except SlaDashboardAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _serialize(dashboard)
