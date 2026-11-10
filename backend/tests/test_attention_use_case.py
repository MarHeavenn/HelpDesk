"""T2 (HU-10) — caso de uso `list_attention_tickets` (RF-61, RF-62, RF-63, RF-65, RF-66, RF-67).

Verifica:
- RF-63: un rol que no es de gestion (`cliente`) lanza `TicketNotFoundError`
  con el mensaje unificado (`TICKET_NOT_FOUND_MESSAGE`) **antes** de leer el
  repositorio, sin revelar datos.
- RF-61: aparece solo el ticket activo (`Abierto`/`En progreso`) cuyo SLA
  esta `en_riesgo` (`near_due`) o `incumplido` (`breached`); no aparece el
  activo `en_tiempo`, ni los `Resuelto`/`Cerrado` (aunque esten incumplidos),
  ni el ticket sin prioridad (`sla` nulo).
- RF-65: orden por `sla.due_at` ascendente (los incumplidos primero).
- RF-66: coleccion vacia valida (200 -> `[]`).
- RF-67: reutiliza `get_ticket_sla` (no introduce logica de SLA ni umbral
  nuevos): el filtro coincide con los indicadores de HU-05.

Los instantes se controlan con `now` inyectado, sin depender del reloj real.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.interface.contract import get_ticket_sla
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
)
from app.modules.tickets.application.list_attention_tickets import (
    list_attention_tickets,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

NOW = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)


def _ticket(
    ticket_id,
    *,
    created_at,
    priority=None,
    status="Abierto",
    resolved_at=None,
):
    return Ticket(
        id=ticket_id,
        title="Titulo",
        description="Descripcion",
        requester_id="u-1",
        created_at=created_at,
        priority=priority,
        status=status,
        resolved_at=resolved_at,
    )


# --- RF-63: guardia de rol antes de leer el repositorio ---


class _BoomRepository:
    """Repositorio que falla si se lee: demuestra que la guardia va primero."""

    def list_all(self):
        raise AssertionError("el repositorio no deberia leerse")


def test_client_role_raises_before_reading_repository():
    with pytest.raises(TicketNotFoundError) as exc:
        list_attention_tickets("cliente", _BoomRepository(), now=NOW)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_role_error_matches_h02_h03_unified_message():
    # El mismo tipo de error y el mismo mensaje que HU-02/HU-03/HU-04.
    repo = InMemoryTicketRepository()
    repo.add(
        _ticket(
            "t-1",
            created_at=NOW - timedelta(hours=3),
            priority="Crítica",
        )
    )

    with pytest.raises(TicketNotFoundError) as exc:
        list_attention_tickets("cliente", repo, now=NOW)

    assert isinstance(exc.value, ValueError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


# --- RF-66: coleccion vacia valida ---


def test_empty_repository_returns_empty_list_for_management_role():
    repo = InMemoryTicketRepository()

    assert list_attention_tickets("tecnico", repo, now=NOW) == []
    assert list_attention_tickets("administrador", repo, now=NOW) == []


# --- RF-61: filtro de activos con near_due o breached ---


def test_attention_keeps_at_risk_and_breached_and_drops_the_rest():
    repo = InMemoryTicketRepository()
    # Incumplido: Critica (120 min) creada hace 3 h -> vencio hace 1 h.
    repo.add(
        _ticket(
            "t-breached",
            created_at=NOW - timedelta(hours=3),
            priority="Crítica",
        )
    )
    # En riesgo: Baja (1440 min) creada hace 23 h -> vence en 1 h (<= 20 %).
    repo.add(
        _ticket(
            "t-risk",
            created_at=NOW - timedelta(hours=23),
            priority="Baja",
        )
    )
    # En tiempo: Alta (240 min) creada ahora -> no esta cerca de vencer.
    repo.add(
        _ticket(
            "t-on-time",
            created_at=NOW,
            priority="Alta",
        )
    )
    # Resuelto fuera de plazo: aunque su SLA quedaria incumplido, no aparece.
    repo.add(
        _ticket(
            "t-resolved",
            created_at=NOW - timedelta(hours=3),
            priority="Crítica",
            status="Resuelto",
            resolved_at=NOW - timedelta(hours=2),
        )
    )
    # Cerrado fuera de plazo: tampoco aparece.
    repo.add(
        _ticket(
            "t-closed",
            created_at=NOW - timedelta(hours=3),
            priority="Crítica",
            status="Cerrado",
            resolved_at=NOW - timedelta(hours=2),
        )
    )
    # Sin prioridad: sla nulo, no aparece.
    repo.add(
        _ticket(
            "t-no-priority",
            created_at=NOW - timedelta(hours=3),
            priority=None,
        )
    )

    result = list_attention_tickets("tecnico", repo, now=NOW)

    assert {ticket.id for ticket in result} == {"t-breached", "t-risk"}


def test_active_en_progreso_at_risk_appears():
    repo = InMemoryTicketRepository()
    repo.add(
        _ticket(
            "t-progress",
            created_at=NOW - timedelta(hours=23),
            priority="Baja",
            status="En progreso",
        )
    )

    result = list_attention_tickets("administrador", repo, now=NOW)

    assert [ticket.id for ticket in result] == ["t-progress"]


# --- RF-65: orden por due_at ascendente ---


def test_attention_is_ordered_by_due_at_ascending():
    repo = InMemoryTicketRepository()
    # Tres tickets con vencimientos distintos y crecientes.
    # Breached (due = NOW - 1 h) debe quedar primero.
    repo.add(
        _ticket(
            "t-breach",
            created_at=NOW - timedelta(hours=3),
            priority="Crítica",
        )
    )
    # Media (720 min) creada hace 11 h -> vence en 1 h (en riesgo).
    repo.add(
        _ticket(
            "t-risk-media",
            created_at=NOW - timedelta(hours=11),
            priority="Media",
        )
    )
    # Baja (1440 min) creada hace 20 h -> vence en 4 h (en riesgo).
    repo.add(
        _ticket(
            "t-risk-baja",
            created_at=NOW - timedelta(hours=20),
            priority="Baja",
        )
    )

    result = list_attention_tickets("tecnico", repo, now=NOW)

    assert [ticket.id for ticket in result] == [
        "t-breach",
        "t-risk-media",
        "t-risk-baja",
    ]


# --- RF-67: reutiliza el calculo de HU-05 (sin logica ni umbral nuevos) ---


def test_attention_filter_matches_get_ticket_sla_indicators():
    # El criterio del caso de uso es exactamente el de HU-05: `near_due` o
    # `breached`. Se comprueba que el listado coincide con aplicar el contrato.
    from app.modules.sla.domain.entities import TicketSlaSnapshot

    repo = InMemoryTicketRepository()
    created = NOW - timedelta(hours=23)
    repo.add(
        _ticket(
            "t-risk",
            created_at=created,
            priority="Baja",
        )
    )

    result = list_attention_tickets("tecnico", repo, now=NOW)

    sla = get_ticket_sla(
        TicketSlaSnapshot("Baja", created, None),
        now=NOW,
    )
    assert sla is not None
    assert sla.near_due and not sla.breached
    assert [ticket.id for ticket in result] == ["t-risk"]
