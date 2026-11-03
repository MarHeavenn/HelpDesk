"""HU-07 T1 — dominio y repositorio de comentarios (RF-62, RF-63).

Verifica sin HTTP:

- `validate_comment_body` aplica tipo estricto, recorte `strip()`, límites
  de 1 a 2000 code points y devuelve el valor que debe almacenarse.
- `TicketComment` asocia identificador, ticket, autor, cuerpo y fecha.
- `InMemoryTicketCommentRepository` filtra por ticket, ordena por
  `created_at` ascendente y conserva el orden de registro en los empates.
"""

import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.domain.entities import (
    COMMENT_MAX_LENGTH,
    COMMENT_MIN_LENGTH,
    TicketComment,
    validate_comment_body,
)
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    InMemoryTicketCommentRepository,
)

BASE = datetime(2026, 11, 2, 12, 0, 0, tzinfo=timezone.utc)


def _comment(ticket_id="t-1", author_id="u-1", body="Avance", created_at=BASE):
    return TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author_id=author_id,
        body=body,
        created_at=created_at,
    )


# --- RF-62: validación del contenido ---


def test_validate_comment_body_trims_and_returns_the_stored_value():
    assert validate_comment_body("  Se revisó el acceso  ") == (
        "Se revisó el acceso"
    )
    assert COMMENT_MIN_LENGTH == 1
    assert COMMENT_MAX_LENGTH == 2000


def test_validate_comment_body_accepts_the_exact_limits():
    assert validate_comment_body("a") == "a"
    assert validate_comment_body("a" * 2000) == "a" * 2000
    # Los límites se cuentan en code points, no en bytes.
    assert len(validate_comment_body("á" * 2000)) == 2000


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "\n\t ",
        "a" * 2001,
        None,
        123,
        1.5,
        True,
        ["texto"],
        {"body": "texto"},
        b"texto",
    ],
)
def test_validate_comment_body_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        validate_comment_body(raw)


# --- Entidad ---


def test_ticket_comment_has_only_the_documented_fields():
    comment = _comment(body="Texto")

    assert type(comment) is TicketComment
    assert set(asdict(comment)) == {
        "id",
        "ticket_id",
        "author_id",
        "body",
        "created_at",
    }
    assert comment.ticket_id == "t-1"
    assert comment.author_id == "u-1"
    assert comment.body == "Texto"
    assert comment.created_at == BASE


# --- RF-63: repositorio, orden y aislamiento ---


def test_repository_lists_only_the_comments_of_the_ticket():
    repository = InMemoryTicketCommentRepository()
    first = _comment(ticket_id="t-1", body="Primero")
    other = _comment(ticket_id="t-2", body="Otro ticket")
    second = _comment(ticket_id="t-1", body="Segundo")
    repository.add(first)
    repository.add(other)
    repository.add(second)

    assert repository.list_by_ticket("t-1") == [first, second]
    assert repository.list_by_ticket("t-2") == [other]
    assert repository.list_by_ticket("t-3") == []
    assert repository.count() == 3


def test_repository_orders_by_created_at_ascending():
    repository = InMemoryTicketCommentRepository()
    later = _comment(body="Tarde", created_at=BASE + timedelta(minutes=5))
    earlier = _comment(
        body="Temprano", created_at=BASE - timedelta(minutes=5)
    )
    repository.add(later)
    repository.add(earlier)

    assert [item.body for item in repository.list_by_ticket("t-1")] == [
        "Temprano",
        "Tarde",
    ]


def test_repository_keeps_registration_order_when_created_at_ties():
    repository = InMemoryTicketCommentRepository()
    first = _comment(body="Primero", created_at=BASE)
    second = _comment(body="Segundo", created_at=BASE)
    third = _comment(body="Tercero", created_at=BASE)
    for item in (first, second, third):
        repository.add(item)

    assert [item.body for item in repository.list_by_ticket("t-1")] == [
        "Primero",
        "Segundo",
        "Tercero",
    ]


def test_repository_clear_and_empty_state():
    repository = InMemoryTicketCommentRepository()
    repository.add(_comment())
    repository.clear()

    assert repository.count() == 0
    assert repository.list_by_ticket("t-1") == []
