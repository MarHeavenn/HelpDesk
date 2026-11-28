"""Evaluación pura de resolución con objetivo conservado (HU-18)."""

from datetime import datetime, timedelta, timezone

from app.modules.sla.domain.entities import SLA_MET, TicketSlaSnapshot, calculate_sla
from app.modules.sla.domain.policy_config import SLA_PRIORITIES


def evaluate_frozen_resolution(
    priority: str | None,
    created_at: datetime | None,
    resolved_at: datetime | None,
    resolved_target_minutes: int | None,
) -> bool | None:
    """Devuelve cumplimiento o None si los datos no son evaluables.

    No consulta configuración ni completa objetivos ausentes. Las fechas
    deben representar instantes con zona explícita; se normalizan a UTC
    para medir tiempo continuo incluso entre cambios de horario. El
    llamador selecciona los estados y el conjunto autorizado de tickets.
    """
    if not isinstance(priority, str) or priority not in SLA_PRIORITIES:
        return None
    if (
        not isinstance(resolved_target_minutes, int)
        or isinstance(resolved_target_minutes, bool)
        or resolved_target_minutes <= 0
    ):
        return None
    if not isinstance(created_at, datetime) or not isinstance(resolved_at, datetime):
        return None

    # Validar solo los datos de entrada: un fallo técnico del cálculo no
    # se transforma en ausencia de muestra.
    try:
        if created_at.utcoffset() is None or resolved_at.utcoffset() is None:
            return None
        created_at = created_at.astimezone(timezone.utc)
        resolved_at = resolved_at.astimezone(timezone.utc)
        if resolved_at < created_at:
            return None
        # Un entero positivo puede exceder el rango de un vencimiento.
        created_at + timedelta(minutes=resolved_target_minutes)
    except (ValueError, OverflowError):
        return None

    snapshot = TicketSlaSnapshot(
        priority=priority,
        created_at=created_at,
        resolved_at=resolved_at,
        resolved_target_minutes=resolved_target_minutes,
    )
    result = calculate_sla(snapshot, resolved_target_minutes, now=resolved_at)
    return result.status == SLA_MET
