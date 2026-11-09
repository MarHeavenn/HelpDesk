"""T1 (HU-10) — `list_all()` del repositorio de tickets (RF-62).

Verifica:
- RF-62: `list_all()` devuelve **todos** los tickets almacenados, sin
  filtrar por `requester_id` ni `assignee_id`: tickets de distintos
  solicitantes y de distintas asignaciones (o sin asignar) aparecen juntos.
- Orden base determinista por `created_at` descendente (los mas recientes
  primero).
- Devuelve lista vacia cuando no hay tickets.
- `list_by_requester` y `list_by_assignee` no cambian y siguen filtrando
  y ordenando igual que antes.

El orden de negocio del listado de atencion (por `sla.due_at`) se aplica
en el caso de uso, no aqui: el repositorio solo da el orden base por
`created_at`.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

BASE = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)


def _ticket(ticket_id, *, requester_id, created_at, assignee_id=None):
    values = {
        "id": ticket_id,
        "title": "Titulo",
        "description": "Descripcion",
        "requester_id": requester_id,
        "created_at": created_at,
    }
    if assignee_id is not None:
        values["assignee_id"] = assignee_id
        values["assignee_name"] = "Tecnico"
    return Ticket(**values)


def test_list_all_returns_empty_list_when_no_tickets():
    repo = InMemoryTicketRepository()

    assert repo.list_all() == []


def test_list_all_returns_every_ticket_regardless_of_requester_and_assignee():
    repo = InMemoryTicketRepository()
    a_requester = "u-1"
    b_requester = "u-2"
    a_assignee = "t-1"
    b_assignee = "t-2"
    # Distintos creadores, asignaciones y un ticket sin asignar: deben
    # aparecer todos juntos (RF-62, sin filtro por creador ni asignacion).
    tickets = [
        _ticket("t-1", requester_id=a_requester, created_at=BASE),
        _ticket(
            "t-2",
            requester_id=a_requester,
            created_at=BASE + timedelta(minutes=1),
            assignee_id=a_assignee,
        ),
        _ticket(
            "t-3",
            requester_id=b_requester,
            created_at=BASE + timedelta(minutes=2),
            assignee_id=b_assignee,
        ),
        _ticket(
            "t-4",
            requester_id=b_requester,
            created_at=BASE + timedelta(minutes=3),
        ),
    ]
    for ticket in tickets:
        repo.add(ticket)

    result = repo.list_all()

    assert {ticket.id for ticket in result} == {"t-1", "t-2", "t-3", "t-4"}
    assert len(result) == 4


def test_list_all_is_ordered_by_created_at_descending():
    repo = InMemoryTicketRepository()
    # Se insertan desordenados: el repositorio ordena por fecha descendente.
    for minutes, ticket_id in ((10, "t-10"), (0, "t-0"), (5, "t-5")):
        repo.add(
            _ticket(
                ticket_id,
                requester_id="u-1",
                created_at=BASE + timedelta(minutes=minutes),
            )
        )

    result = repo.list_all()

    assert [ticket.id for ticket in result] == ["t-10", "t-5", "t-0"]
    assert [ticket.created_at for ticket in result] == [
        BASE + timedelta(minutes=10),
        BASE + timedelta(minutes=5),
        BASE,
    ]


def test_list_all_does_not_fix_order_on_created_at_ties():
    repo = InMemoryTicketRepository()
    first = _ticket("t-a", requester_id="u-1", created_at=BASE)
    second = _ticket("t-b", requester_id="u-2", created_at=BASE)
    repo.add(first)
    repo.add(second)

    result = repo.list_all()

    # Un empate de fecha no fija orden entre los tickets.
    assert {ticket.id for ticket in result} == {"t-a", "t-b"}


def test_list_by_requester_and_list_by_assignee_keep_filtering_and_order():
    repo = InMemoryTicketRepository()
    a_requester = "u-1"
    b_requester = "u-2"
    a_assignee = "t-1"
    repo.add(_ticket("t-old", requester_id=a_requester, created_at=BASE))
    repo.add(
        _ticket(
            "t-new",
            requester_id=a_requester,
            created_at=BASE + timedelta(minutes=5),
            assignee_id=a_assignee,
        )
    )
    repo.add(
        _ticket(
            "t-other",
            requester_id=b_requester,
            created_at=BASE + timedelta(minutes=10),
        )
    )

    by_requester = repo.list_by_requester(a_requester)
    by_assignee = repo.list_by_assignee(a_assignee)

    # `list_by_requester` sigue devolviendo solo los del solicitante,
    # en orden descendente, sin tocar a los ajenos.
    assert [ticket.id for ticket in by_requester] == ["t-new", "t-old"]
    assert "t-other" not in {ticket.id for ticket in by_requester}
    assert repo.list_by_requester("u-3") == []
    # `list_by_assignee` sigue devolviendo solo los del tecnico.
    assert [ticket.id for ticket in by_assignee] == ["t-new"]
    assert repo.list_by_assignee("t-2") == []
