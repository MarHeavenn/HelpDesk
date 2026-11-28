"""Frontera HTTP de las métricas de soporte HU-18; solo composición."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.sla.interface.contract import evaluate_frozen_resolution
from app.modules.tickets.application.support_metrics import (
    SupportMetricsAccessDeniedError,
    get_support_metrics,
)
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class SupportMetricsResponse(BaseModel):
    total_tickets: int
    resolved_tickets: int
    pending_tickets: int
    average_resolution_minutes: float | None
    resolution_sample_size: int
    resolution_excluded_count: int
    sla_compliance_percentage: float | None
    sla_sample_size: int
    sla_met_count: int
    sla_excluded_count: int


@router.get("/support-metrics", response_model=SupportMetricsResponse)
def get_support_metrics_endpoint(
    current: dict = Depends(get_current_user),
) -> SupportMetricsResponse:
    """Resuelve sesión, delega autorización/cálculo y serializa el agregado."""
    try:
        metrics = get_support_metrics(
            actor_role=current["role"],
            actor_company_id=current.get("company_id"),
            read_snapshot=get_ticket_repository().snapshot_for_metrics,
            evaluate_resolution=evaluate_frozen_resolution,
        )
    except SupportMetricsAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="not found") from exc
    return SupportMetricsResponse(**asdict(metrics))
