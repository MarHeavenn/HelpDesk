"""HU-18 T2: instantánea mínima completa y estable (RF-180/181/184/188)."""

from dataclasses import FrozenInstanceError, asdict, fields
from datetime import datetime, timedelta, timezone

import pytest

from app.modules.tickets.domain.entities import STATUSES, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
)

CREATED = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
METRIC_FIELDS = (
    "id", "company_id", "status", "priority", "created_at", "resolved_at",
    "resolved_target_minutes",
)


def _ticket(identifier="ticket-1", **overrides):
    values = {
        "id": identifier,
        "title": "Título repetido",
        "description": "Descripción privada",
        "requester_id": "requester-private",
        "created_at": CREATED,
        "company_id": "company-a",
        "assignee_id": "technician-private",
        "assignee_name": "Nombre privado",
    }
    return Ticket(**{**values, **overrides})


def test_empty_repository_returns_materialized_empty_snapshot():
    assert InMemoryTicketRepository().snapshot_for_metrics() == ()


def test_snapshot_includes_all_history_without_pagination_or_deduplication():
    repository = InMemoryTicketRepository()
    tickets = [
        _ticket(
            f"ticket-{index}",
            created_at=datetime(1980, 1, 1, tzinfo=timezone.utc) + timedelta(days=index),
            status=STATUSES[index % len(STATUSES)],
            priority=None if index % 2 else "Alta",
            assignee_id=None if index % 2 else "technician-private",
            company_id=(None, "company-a", "company-b")[index % 3],
        )
        for index in range(125)
    ]
    for ticket in tickets:
        repository.add(ticket)

    snapshot = repository.snapshot_for_metrics()

    assert isinstance(snapshot, tuple)
    assert len(snapshot) == 125
    assert {row.id for row in snapshot} == {ticket.id for ticket in tickets}
    assert {row.company_id for row in snapshot} == {None, "company-a", "company-b"}
    assert {row.status for row in snapshot} == set(STATUSES)
    assert all(row.created_at.year == 1980 for row in snapshot)


def test_snapshot_keeps_invalid_dates_without_sorting_or_using_previous_lists(monkeypatch):
    repository = InMemoryTicketRepository()
    dates = (CREATED, None, CREATED.replace(tzinfo=None), "invalid", CREATED - timedelta(days=5))
    tickets = [
        _ticket(
            f"ticket-{index}", created_at=created, status="Cerrado",
            resolved_at=None if index % 2 else "invalid",
        )
        for index, created in enumerate(dates)
    ]
    for ticket in tickets:
        repository.add(ticket)

    def forbidden(*args, **kwargs):
        pytest.fail("La instantánea no debe depender de listados ordenados")

    monkeypatch.setattr(repository, "list_all", forbidden)
    monkeypatch.setattr(repository, "list_by_requester", forbidden)
    monkeypatch.setattr(repository, "list_by_assignee", forbidden)
    snapshot = repository.snapshot_for_metrics()

    by_id = {row.id: row for row in snapshot}
    assert len(by_id) == len(tickets)
    for ticket in tickets:
        assert by_id[ticket.id].created_at == ticket.created_at
        assert by_id[ticket.id].resolved_at == ticket.resolved_at
        assert by_id[ticket.id].status == "Cerrado"


def test_snapshot_contains_only_the_seven_minimal_fields():
    repository = InMemoryTicketRepository()
    ticket = _ticket(
        priority="Alta", status="Resuelto",
        resolved_at=CREATED + timedelta(minutes=60), resolved_target_minutes=60,
    )
    repository.add(ticket)

    row, = repository.snapshot_for_metrics()

    assert tuple(field.name for field in fields(row)) == METRIC_FIELDS
    assert asdict(row) == {name: getattr(ticket, name) for name in METRIC_FIELDS}
    assert row is not ticket
    assert all(not hasattr(row, name) for name in (
        "title", "description", "requester_id", "assignee_id", "assignee_name",
    ))


@pytest.mark.parametrize("field", METRIC_FIELDS)
def test_each_snapshot_record_is_immutable(field):
    repository = InMemoryTicketRepository()
    repository.add(_ticket())
    row, = repository.snapshot_for_metrics()

    with pytest.raises(FrozenInstanceError):
        setattr(row, field, None)


def test_original_mutation_and_repository_changes_do_not_change_captured_snapshot():
    repository = InMemoryTicketRepository()
    ticket = _ticket()
    repository.add(ticket)
    snapshot = repository.snapshot_for_metrics()
    captured = asdict(snapshot[0])

    ticket.id = "changed"
    ticket.company_id = "company-b"
    ticket.status = "Resuelto"
    ticket.priority = "Baja"
    ticket.created_at = CREATED - timedelta(days=10)
    ticket.resolved_at = CREATED
    ticket.resolved_target_minutes = 30
    repository.add(_ticket("new-ticket"))
    repository.clear()

    assert len(snapshot) == 1
    assert asdict(snapshot[0]) == captured
    assert repository.snapshot_for_metrics() == ()


def test_next_snapshot_reflects_updates_without_reusing_records():
    repository = InMemoryTicketRepository()
    ticket = _ticket()
    repository.add(ticket)
    first = repository.snapshot_for_metrics()
    ticket.status = "Resuelto"
    ticket.resolved_at = CREATED + timedelta(minutes=60)
    ticket.resolved_target_minutes = 60
    second = repository.snapshot_for_metrics()

    assert first[0].status == "Abierto"
    assert first[0].resolved_at is None
    assert second[0].status == "Resuelto"
    assert second[0].resolved_at == ticket.resolved_at
    assert second[0].resolved_target_minutes == 60
    assert first[0] is not second[0]


def test_snapshot_traverses_storage_once_and_does_not_modify_tickets():
    class CountingStorage(dict):
        reads = 0
        visits = 0

        def values(self):
            self.reads += 1
            for value in super().values():
                self.visits += 1
                yield value

    repository = InMemoryTicketRepository()
    storage = CountingStorage()
    repository._by_id = storage
    tickets = [_ticket(f"ticket-{index}") for index in range(3)]
    for ticket in tickets:
        repository.add(ticket)
    before = [asdict(ticket) for ticket in tickets]

    snapshot = repository.snapshot_for_metrics()

    assert len(snapshot) == 3
    assert storage.reads == 1
    assert storage.visits == 3
    assert [asdict(ticket) for ticket in tickets] == before
    assert all(repository.find_by_id(ticket.id) is ticket for ticket in tickets)
    assert repository.count() == 3


@pytest.mark.parametrize(
    "method,args",
    (("list_all", ()), ("list_by_requester", ("requester-private",)),
     ("list_by_assignee", ("technician-private",))),
)
def test_existing_reads_keep_their_order_and_original_ticket_references(method, args):
    repository = InMemoryTicketRepository()
    oldest = _ticket("old", created_at=CREATED - timedelta(days=10))
    newest = _ticket("new", created_at=CREATED)
    middle = _ticket("middle", created_at=CREATED - timedelta(days=5))
    for ticket in (oldest, newest, middle):
        repository.add(ticket)
    read = getattr(repository, method)
    before = read(*args)

    repository.snapshot_for_metrics()
    after = read(*args)

    assert [row.id for row in after] == ["new", "middle", "old"]
    assert all(left is right for left, right in zip(before, after))
