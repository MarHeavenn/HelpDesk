"""Ruta HTTP del dashboard de tickets (RF-81 a RF-90).

Solo comunica: resuelve la sesion, delega el agregado en la aplicacion y
traduce el rol no autorizado a un 404 uniforme. No accede a tablas de
otros modulos: el directorio de tecnicos llega por el contrato de
`identity`.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.technicians_contract import (
    get_technician_directory,
    get_technician_summary,
)
from app.modules.tickets.application.dashboard import (
    ADMIN_ROLE,
    DashboardAccessDeniedError,
    TechnicianRef,
    TicketDashboard,
    get_ticket_dashboard,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardTechnicianResponse(BaseModel):
    id: str
    name: str


class DashboardStatusCountResponse(BaseModel):
    status: str
    count: int


class DashboardPriorityCountResponse(BaseModel):
    priority: str | None
    label: str
    count: int


class DashboardAssigneeCountResponse(BaseModel):
    technician: DashboardTechnicianResponse | None
    label: str
    count: int


class DashboardRecentTicketResponse(BaseModel):
    id: str
    title: str
    priority: str | None
    status: str
    assignee: DashboardTechnicianResponse | None
    created_at: str


class TicketDashboardResponse(BaseModel):
    total_tickets: int
    by_status: list[DashboardStatusCountResponse]
    by_priority: list[DashboardPriorityCountResponse]
    by_assignee: list[DashboardAssigneeCountResponse]
    recent_tickets: list[DashboardRecentTicketResponse]
    generated_at: str


def _technician_response(
    technician: TechnicianRef | None,
) -> DashboardTechnicianResponse | None:
    if technician is None:
        return None
    return DashboardTechnicianResponse(id=technician.id, name=technician.name)


def _serialize(dashboard: TicketDashboard) -> TicketDashboardResponse:
    return TicketDashboardResponse(
        total_tickets=dashboard.total_tickets,
        by_status=[
            DashboardStatusCountResponse(status=item.status, count=item.count)
            for item in dashboard.by_status
        ],
        by_priority=[
            DashboardPriorityCountResponse(
                priority=item.priority,
                label=item.label,
                count=item.count,
            )
            for item in dashboard.by_priority
        ],
        by_assignee=[
            DashboardAssigneeCountResponse(
                technician=_technician_response(item.technician),
                label=item.label,
                count=item.count,
            )
            for item in dashboard.by_assignee
        ],
        recent_tickets=[
            DashboardRecentTicketResponse(
                id=item.id,
                title=item.title,
                priority=item.priority,
                status=item.status,
                assignee=_technician_response(item.assignee),
                created_at=item.created_at.isoformat(),
            )
            for item in dashboard.recent_tickets
        ],
        generated_at=dashboard.generated_at.isoformat(),
    )


@router.get("/tickets", response_model=TicketDashboardResponse)
def get_tickets_dashboard_endpoint(
    current: dict = Depends(get_current_user),
) -> TicketDashboardResponse:
    """Resumen agregado; administrador global y tecnico con alcance propio.

    Sin sesion valida, `get_current_user` responde 401 (RF-81). El cliente
    recibe 404 uniforme sin datos del dashboard.
    """
    technicians: list[TechnicianRef] = []
    if current["role"] in {"administrador", "supervisor"}:
        technicians = [
            TechnicianRef(id=item.id, name=item.name)
            for item in get_technician_directory(current.get("company_id"))
        ]
    else:
        own = get_technician_summary(current["id"])
        technicians = [
            TechnicianRef(
                id=own.id if own else current["id"],
                name=own.name if own else current["email"],
            )
        ]

    try:
        dashboard = get_ticket_dashboard(
            actor_id=current["id"],
            actor_role=current["role"],
            tickets=get_ticket_repository(),
            technicians=technicians,
            company_id=current.get("company_id"),
        )
    except DashboardAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _serialize(dashboard)
