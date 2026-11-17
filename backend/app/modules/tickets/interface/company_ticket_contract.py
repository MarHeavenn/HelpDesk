"""Frontera de `tickets` hacia `companies` para el agregado de tickets.

`companies` consume este agregado para la ficha de RF-143. El contrato
devuelve solo un DTO inmutable: nunca `Ticket`, el repositorio, el titulo,
la descripcion, el solicitante ni el contenido de los tickets.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.modules.tickets.domain.entities import STATUSES
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)


@dataclass(frozen=True)
class CompanyTicketStats:
    """Agregado de tickets de una empresa (RF-132 y RF-143)."""

    tickets_total: int
    by_status: Mapping[str, int]


def get_company_ticket_stats(
    company_id: str | None, tickets: InMemoryTicketRepository | None = None
) -> CompanyTicketStats:
    """Cuenta todos los tickets de la empresa, excluyendo los sin empresa.

    `by_status` tiene siempre las cuatro claves del catalogo, tambien con
    valor cero, y su suma es igual a `tickets_total` (RF-143). El mapa se
    devuelve en solo lectura para que ningun consumidor lo mutacione.
    """
    if company_id is None:
        return CompanyTicketStats(
            tickets_total=0,
            by_status=MappingProxyType({status: 0 for status in STATUSES}),
        )
    repository = tickets if tickets is not None else get_ticket_repository()
    company_tickets = [
        ticket for ticket in repository.list_all() if ticket.company_id == company_id
    ]
    by_status = {status: 0 for status in STATUSES}
    for ticket in company_tickets:
        if ticket.status in by_status:
            by_status[ticket.status] += 1
    return CompanyTicketStats(
        tickets_total=len(company_tickets),
        by_status=MappingProxyType(by_status),
    )
