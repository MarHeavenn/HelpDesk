"""T1 — Dominio y repositorio en memoria de tickets (RF-12, RF-13, RF-19).

Verifica:
- RF-12.1: titulo y descripcion obligatorios y de tipo cadena de texto;
  cualquier valor JSON de otro tipo (numero, booleano, objeto, lista o
  nulo) se rechaza sin coercion.
- RF-12.2: titulo de 1-200 y descripcion de 1-5000 caracteres contados en
  code points (no bytes) tras el recorte.
- RF-12.3: recorte con semantica `strip()` sin argumentos aplicado al
  validar y al almacenar; U+200B no cuenta como espacio en blanco y no se
  elimina.
- RF-12.5: no hay deduplicacion (el dominio no impone unicidad de texto).
- RF-13: el identificador es un UUID opaco con formato validable.
- RF-19: todo ticket nuevo nace con el estado inicial `Abierto`.
- RF-15: `list_by_requester` devuelve solo los tickets del solicitante,
  ordenados por `created_at` descendente.
- Patron de HU-01: repositorio en memoria con singleton
  `get_ticket_repository()` y `clear()` para pruebas, sin dependencias nuevas.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.domain.entities import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    OPEN_STATUS,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    Ticket,
    is_valid_uuid_format,
    validate_description,
    validate_title,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_repository():
    get_ticket_repository().clear()
    yield
    get_ticket_repository().clear()


def _ticket(*, ticket_id, requester_id, created_at):
    return Ticket(
        id=ticket_id,
        title="Titulo",
        description="Descripcion",
        requester_id=requester_id,
        created_at=created_at,
    )


# --- Constantes de dominio (RF-12.2, RF-19) ---


def test_domain_constants_match_spec():
    assert TITLE_MIN_LENGTH == 1
    assert TITLE_MAX_LENGTH == 200
    assert DESCRIPTION_MIN_LENGTH == 1
    assert DESCRIPTION_MAX_LENGTH == 5000
    assert OPEN_STATUS == "Abierto"


# --- RF-12.1: tipo estricto sin coercion ---


@pytest.mark.parametrize("raw", [5, 5.5, True, False, {"a": 1}, ["a"], None, b"texto"])
def test_validate_rejects_non_string_values_without_coercion(raw):
    with pytest.raises(ValueError):
        validate_title(raw)
    with pytest.raises(ValueError):
        validate_description(raw)


# --- RF-12.2 y RF-12.3: recorte y limites ---


def test_validate_returns_stripped_value():
    assert validate_title("  hola  ") == "hola"
    assert validate_title("\thola\n") == "hola"
    assert validate_description("  descripcion con espacios  ") == "descripcion con espacios"


def test_zero_width_space_is_not_stripped():
    # U+200B no es espacio en blanco para `strip()`: no se elimina.
    assert validate_title("\u200b") == "\u200b"
    assert validate_title("\u200b hola ") == "\u200b hola"
    assert validate_description("fin\u200b") == "fin\u200b"


def test_title_boundaries_after_strip():
    assert validate_title("x") == "x"
    assert validate_title("   x   ") == "x"
    assert validate_title("t" * TITLE_MAX_LENGTH) == "t" * TITLE_MAX_LENGTH
    assert (
        validate_title("  " + "t" * TITLE_MAX_LENGTH + "\n")
        == "t" * TITLE_MAX_LENGTH
    )
    with pytest.raises(ValueError):
        validate_title("t" * (TITLE_MAX_LENGTH + 1))
    with pytest.raises(ValueError):
        validate_title("")
    with pytest.raises(ValueError):
        validate_title("   ")


def test_description_boundaries_after_strip():
    assert validate_description("d") == "d"
    assert validate_description("  d  ") == "d"
    assert (
        validate_description("d" * DESCRIPTION_MAX_LENGTH)
        == "d" * DESCRIPTION_MAX_LENGTH
    )
    assert (
        validate_description("  " + "d" * DESCRIPTION_MAX_LENGTH + "\n")
        == "d" * DESCRIPTION_MAX_LENGTH
    )
    with pytest.raises(ValueError):
        validate_description("d" * (DESCRIPTION_MAX_LENGTH + 1))
    with pytest.raises(ValueError):
        validate_description("")
    with pytest.raises(ValueError):
        validate_description(" \t\n ")


def test_length_is_counted_in_code_points_not_bytes():
    acentos = "é" * TITLE_MAX_LENGTH
    assert len(acentos.encode("utf-8")) > TITLE_MAX_LENGTH  # bytes > code points
    assert validate_title(acentos) == acentos
    assert validate_title("😀" * TITLE_MAX_LENGTH) == "😀" * TITLE_MAX_LENGTH
    with pytest.raises(ValueError):
        validate_title("é" * (TITLE_MAX_LENGTH + 1))
    assert (
        validate_description("😀" * DESCRIPTION_MAX_LENGTH)
        == "😀" * DESCRIPTION_MAX_LENGTH
    )
    with pytest.raises(ValueError):
        validate_description("é" * (DESCRIPTION_MAX_LENGTH + 1))


# --- RF-13: formato de identificador opaco (UUID) ---


def test_is_valid_uuid_format():
    assert is_valid_uuid_format(str(uuid.uuid4())) is True
    for bad in ["no-es-uuid", "123", "", "TCK-000001", None, 123]:
        assert is_valid_uuid_format(bad) is False


# --- RF-19: estado inicial ---


def test_new_ticket_has_open_status():
    ticket = _ticket(
        ticket_id=str(uuid.uuid4()), requester_id=str(uuid.uuid4()), created_at=NOW
    )
    assert ticket.status == "Abierto"
    assert ticket.status == OPEN_STATUS


# --- Repositorio en memoria (patron HU-01) ---


def test_repository_is_singleton_with_clear():
    repo = get_ticket_repository()
    assert repo is get_ticket_repository()
    assert isinstance(repo, InMemoryTicketRepository)

    repo.add(_ticket(ticket_id="t-1", requester_id="u-1", created_at=NOW))
    assert repo.count() == 1

    repo.clear()
    assert repo.count() == 0
    assert repo.find_by_id("t-1") is None


def test_find_by_id_returns_ticket_or_none():
    repo = InMemoryTicketRepository()
    ticket = _ticket(ticket_id="t-1", requester_id="u-1", created_at=NOW)
    repo.add(ticket)

    assert repo.find_by_id("t-1") is ticket
    assert repo.find_by_id("t-x") is None
    assert repo.find_by_id(None) is None


def test_list_by_requester_returns_only_own_tickets_descending():
    repo = InMemoryTicketRepository()
    old = _ticket(ticket_id="t-old", requester_id="u-1", created_at=NOW)
    new = _ticket(
        ticket_id="t-new",
        requester_id="u-1",
        created_at=NOW + timedelta(minutes=5),
    )
    other = _ticket(
        ticket_id="t-other",
        requester_id="u-2",
        created_at=NOW + timedelta(hours=1),
    )
    for ticket in (old, new, other):
        repo.add(ticket)

    mine = repo.list_by_requester("u-1")

    assert [t.id for t in mine] == ["t-new", "t-old"]
    assert other.id not in [t.id for t in mine]
    assert repo.list_by_requester("u-3") == []
