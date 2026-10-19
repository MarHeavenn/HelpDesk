"""T3 — Validacion de la creacion (422) y duplicados permitidos (RF-12).

Mapa RF -> test (subclausulas de RF-12):
- RF-12.1 campos obligatorios y de tipo cadena sin coercion:
  `test_missing_fields_return_422_without_creating_ticket`,
  `test_non_text_values_return_422_without_coercion`.
- RF-12.2 titulo 1-200 y descripcion 1-5000 code points:
  `test_blank_after_trim_returns_422_without_creating_ticket`,
  `test_boundary_lengths_are_accepted_after_trim`,
  `test_lengths_over_limit_return_422_without_creating_ticket`,
  `test_non_latin_and_emoji_within_limit_are_accepted`.
- RF-12.3 recorte con semantica `strip()` (no elimina U+200B):
  `test_boundary_lengths_are_accepted_after_trim`,
  `test_zero_width_space_is_not_trimmed_and_remains_valid`.
- RF-12.4 el cuerpo solo admite titulo y descripcion:
  `test_extra_fields_return_422_without_creating_ticket`.
- RF-12.5 sin deduplicacion:
  `test_duplicate_title_and_description_are_allowed`.

Todos los rechazos deben responder 422 **sin crear ticket** (se verifica
inspeccionando el repositorio por su contrato publico, no por el listado).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()


def _register_and_login(email="ana@ejemplo.com"):
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": "Secreta123",
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    logged = client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert logged.status_code == 200
    return registered.json()


def _valid_payload(**overrides):
    payload = {"title": "Titulo valido", "description": "Descripcion valida"}
    payload.update(overrides)
    return payload


def _post(payload):
    return client.post("/api/tickets", json=payload)


# --- RF-12.1: campos obligatorios ausentes ---


@pytest.mark.parametrize(
    "payload",
    [
        {"description": "Descripcion valida"},
        {"title": "Titulo valido"},
        {},
    ],
    ids=["sin_title", "sin_description", "sin_ambos"],
)
def test_missing_fields_return_422_without_creating_ticket(payload):
    _register_and_login()

    response = _post(payload)

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().count() == 0


# --- RF-12.1: tipo JSON no textual, sin coercion ---


@pytest.mark.parametrize("raw", [5, 5.5, True, False, {"a": 1}, ["a"], None])
def test_non_text_values_return_422_without_coercion(raw):
    _register_and_login()

    for field in ("title", "description"):
        response = _post(_valid_payload(**{field: raw}))
        assert response.status_code == 422

    assert get_ticket_repository().count() == 0


# --- RF-12.2 y RF-12.3: vacio o solo espacios tras el recorte ---


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n", " \t\n ", "\r\n"])
def test_blank_after_trim_returns_422_without_creating_ticket(blank):
    _register_and_login()

    for field in ("title", "description"):
        response = _post(_valid_payload(**{field: blank}))
        assert response.status_code == 422

    assert get_ticket_repository().count() == 0


# --- RF-12.2: fronteras aceptadas (1, 200 y 5000 code points tras recorte) ---


def test_boundary_lengths_are_accepted_after_trim():
    user = _register_and_login()

    # 1 code point tras el recorte (con espacios, tabulador y salto).
    one = _post({"title": "  x  ", "description": "\t y \n"})
    assert one.status_code == 201
    assert one.json()["title"] == "x"
    assert one.json()["description"] == "y"

    # 200 y 5000 code points exactos tras el recorte.
    limits = _post(
        {"title": "  " + "t" * 200 + "  ", "description": "d" * 5000}
    )
    assert limits.status_code == 201
    assert limits.json()["title"] == "t" * 200
    assert limits.json()["description"] == "d" * 5000

    stored = get_ticket_repository().list_by_requester(user["id"])
    assert len(stored) == 2


# --- RF-12.2: fronteras rechazadas (201 y 5001 code points) ---


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "t" * 201),
        ("description", "d" * 5001),
        ("title", "  " + "t" * 201 + "  "),  # sigue fuera de limite tras el recorte
        ("description", "\n" + "d" * 5001 + "\n"),
    ],
)
def test_lengths_over_limit_return_422_without_creating_ticket(field, value):
    _register_and_login()

    response = _post(_valid_payload(**{field: value}))

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().count() == 0


# --- RF-12.3: U+200B no es espacio en blanco para `strip()` ---


def test_zero_width_space_is_not_trimmed_and_remains_valid():
    user = _register_and_login()

    # Un titulo compuesto solo por U+200B tiene 1 code point y es valido.
    solo = _post({"title": "\u200b", "description": "descripcion"})
    assert solo.status_code == 201
    assert solo.json()["title"] == "\u200b"

    # U+200B al final no se elimina; solo se recortan los espacios reales.
    mixto = _post({"title": "  hola\u200b  ", "description": "descripcion"})
    assert mixto.status_code == 201
    assert mixto.json()["title"] == "hola\u200b"

    assert get_ticket_repository().count() == 2
    assert len(get_ticket_repository().list_by_requester(user["id"])) == 2


# --- RF-12.2: limite en code points, no en bytes (no latino y emoji) ---


def test_non_latin_and_emoji_within_limit_are_accepted():
    _register_and_login()

    titulo = "é" * 200
    descripcion = "😀" * 5000
    assert len(titulo.encode("utf-8")) > 200  # bytes > code points
    assert len(descripcion.encode("utf-8")) > 5000

    response = _post({"title": titulo, "description": descripcion})

    assert response.status_code == 201
    assert response.json()["title"] == titulo
    assert response.json()["description"] == descripcion


# --- RF-12.4: el cuerpo solo admite titulo y descripcion ---


@pytest.mark.parametrize(
    "extra",
    [
        {"status": "Cerrado"},
        {"priority": "alta"},
        {"assignee": "tecnico-1"},
        {"requester_id": "00000000-0000-0000-0000-000000000000"},
        {"id": "00000000-0000-0000-0000-000000000000"},
        {"created_at": "2026-10-17T12:00:00+00:00"},
        {"campo_inventado": 1},
    ],
    ids=[
        "status",
        "priority",
        "assignee",
        "requester_id",
        "id",
        "created_at",
        "inventado",
    ],
)
def test_extra_fields_return_422_without_creating_ticket(extra):
    _register_and_login()

    response = _post(_valid_payload(**extra))

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_ticket_repository().count() == 0


# --- RF-12.5: duplicados permitidos ---


def test_duplicate_title_and_description_are_allowed():
    user = _register_and_login()
    payload = {"title": "Mismo titulo", "description": "Misma descripcion"}

    first = _post(payload)
    second = _post(payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    stored = get_ticket_repository().list_by_requester(user["id"])
    assert len(stored) == 2
    assert {ticket.title for ticket in stored} == {"Mismo titulo"}
