"""T8 — Barrido final RF-11 a RF-20 y composicion de respuestas (HU-02).

Comprueba de extremo a extremo los diez requisitos de la historia, la
composicion exacta de las respuestas (sobre el cuerpo crudo,
`response.text`), los duplicados permitidos, los empates de fecha sin
afirmar orden y que ningun rechazo usa 400 ni 403.

Mapa RF -> test (en este archivo):
- RF-11 -> test_sweep_create_happy_path
- RF-12 -> test_sweep_validation_rejections_use_422_only,
           test_sweep_duplicates_are_allowed
- RF-13 -> test_sweep_identifiers_are_distinct_uuids
- RF-14 -> test_sweep_requester_comes_from_session
- RF-15 -> test_sweep_list_summary_composition,
           test_sweep_list_empty_and_unknown_query_params,
           test_sweep_list_order_and_date_ties
- RF-16 -> test_sweep_detail_composition_without_personal_data
- RF-17 -> test_sweep_not_found_is_unified
- RF-18 -> test_sweep_no_rejection_uses_400_or_403,
           test_sweep_authentication_precedes_resource_resolution
- RF-19 -> test_sweep_status_stays_open_in_hu02_scope
- RF-20 -> test_sweep_two_sessions_are_isolated
- RF-11..RF-20 -> test_sweep_rf_map_covers_all_requirements (trazabilidad)

Nota conocida y aceptada (igual que en HU-01): los 422 de Pydantic
devuelven `detail` como lista y los del dominio como string. No se
introduce ningun handler global por esto.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.domain.entities import OPEN_STATUS, Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

client = TestClient(app)
client_other = TestClient(app)

PASSWORD = "Secreta123"

# Mapa RF -> test(s) que lo cubren (contrastado por
# `test_sweep_rf_map_covers_all_requirements`).
RF_MAP = {
    "RF-11": "test_sweep_create_happy_path",
    "RF-12": (
        "test_sweep_validation_rejections_use_422_only"
        " + test_sweep_duplicates_are_allowed"
    ),
    "RF-13": "test_sweep_identifiers_are_distinct_uuids",
    "RF-14": "test_sweep_requester_comes_from_session",
    "RF-15": (
        "test_sweep_list_summary_composition"
        " + test_sweep_list_empty_and_unknown_query_params"
        " + test_sweep_list_order_and_date_ties"
    ),
    "RF-16": "test_sweep_detail_composition_without_personal_data",
    "RF-17": "test_sweep_not_found_is_unified",
    "RF-18": (
        "test_sweep_no_rejection_uses_400_or_403"
        " + test_sweep_authentication_precedes_resource_resolution"
    ),
    "RF-19": "test_sweep_status_stays_open_in_hu02_scope",
    "RF-20": "test_sweep_two_sessions_are_isolated",
}

DETAIL_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "created_at",
    "requester_id",
}
SUMMARY_FIELDS = {"id", "title", "priority", "status", "created_at"}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    client_other.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    client_other.cookies.clear()


def _register_and_login(target=client, email="ana@ejemplo.com"):
    registered = target.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200
    return registered.json()


def _create(title, description, target=client):
    response = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


def _foreign_ticket():
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Ticket ajeno",
        description="contenido ajeno",
        requester_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
    )
    get_ticket_repository().add(ticket)
    return ticket


# --- Trazabilidad del mapa RF -> test ---


def test_sweep_rf_map_covers_all_requirements():
    expected = {f"RF-{number}" for number in range(11, 21)}
    assert set(RF_MAP) == expected
    for requirement, targets in RF_MAP.items():
        for name in targets.split(" + "):
            assert name in globals(), f"{requirement} apunta a {name} inexistente"


# --- RF-11: camino feliz y composicion del ticket creado ---


def test_sweep_create_happy_path():
    user = _register_and_login()

    response = client.post(
        "/api/tickets", json={"title": "Titulo de barrido", "description": "Descripcion de barrido"}
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["priority"] is None
    assert body["status"] == OPEN_STATUS == "Abierto"
    assert body["requester_id"] == user["id"]
    assert body["title"] == "Titulo de barrido"
    assert body["description"] == "Descripcion de barrido"
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert body["created_at"].endswith("+00:00")


# --- RF-12: validacion (422) y duplicados permitidos ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "   ", "description": "Descripcion"},
        {"title": "Titulo", "description": " \t\n "},
        {"title": "t" * 201, "description": "Descripcion"},
        {"title": "Titulo", "description": "d" * 5001},
        {"title": 5, "description": "Descripcion"},
        {"title": "Titulo", "description": None},
        {"title": "Titulo", "description": "Descripcion", "status": "Cerrado"},
        {"title": "Titulo", "description": "Descripcion", "requester_id": str(uuid.uuid4())},
    ],
    ids=[
        "sin_campos",
        "titulo_vacio",
        "descripcion_blanca",
        "titulo_201",
        "descripcion_5001",
        "titulo_numero",
        "descripcion_nula",
        "campo_status",
        "campo_requester_id",
    ],
)
def test_sweep_validation_rejections_use_422_only(payload):
    _register_and_login()

    response = client.post("/api/tickets", json=payload)

    assert response.status_code == 422
    assert response.status_code not in (400, 403)
    assert get_ticket_repository().count() == 0


def test_sweep_duplicates_are_allowed():
    _register_and_login()
    payload = {"title": "Duplicado", "description": "Misma descripcion"}

    first = client.post("/api/tickets", json=payload)
    second = client.post("/api/tickets", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert get_ticket_repository().count() == 2


# --- RF-13: identificadores UUID opacos y distintos ---


def test_sweep_identifiers_are_distinct_uuids():
    _register_and_login()

    ids = [_create("Titulo", "Descripcion")["id"] for _ in range(3)]

    assert len(set(ids)) == 3
    for value in ids:
        assert str(uuid.UUID(value)) == value


# --- RF-14: el solicitante viene de la sesion, nunca del cuerpo ---


def test_sweep_requester_comes_from_session():
    user = _register_and_login()
    created = _create("Titulo", "Descripcion")

    assert created["requester_id"] == user["id"]

    rejected = client.post(
        "/api/tickets",
        json={
            "title": "Titulo",
            "description": "Descripcion",
            "requester_id": str(uuid.uuid4()),
        },
    )
    assert rejected.status_code == 422
    assert get_ticket_repository().count() == 1


# --- RF-15: composicion del resumen, lista vacia y parametros ignorados ---


def test_sweep_list_summary_composition():
    _register_and_login()
    _create("Titulo de barrido", "Descripcion de barrido")

    response = client.get("/api/tickets")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert set(items[0]) == SUMMARY_FIELDS
    assert items[0]["priority"] is None
    # Sobre el cuerpo crudo: ni las claves ni los valores excluidos.
    assert '"description"' not in response.text
    assert "Descripcion de barrido" not in response.text
    assert '"requester_id"' not in response.text


def test_sweep_list_empty_and_unknown_query_params():
    _register_and_login()

    empty = client.get("/api/tickets")
    assert empty.status_code == 200
    assert empty.json() == []

    _create("Titulo", "Descripcion")
    plain = client.get("/api/tickets")
    with_params = client.get("/api/tickets?status=Abierto&page=2")
    assert with_params.status_code == 200
    assert with_params.json() == plain.json()


def test_sweep_list_order_and_date_ties():
    user = _register_and_login()
    repo = get_ticket_repository()
    base = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone.utc)
    for minutes in (0, 5, 10):
        repo.add(
            Ticket(
                id=f"t-{minutes}",
                title=f"Titulo {minutes}",
                description="Descripcion",
                requester_id=user["id"],
                created_at=base + timedelta(minutes=minutes),
            )
        )

    # Instantes distintos -> orden descendente estricto.
    ordered = client.get("/api/tickets").json()
    assert [item["id"] for item in ordered] == ["t-10", "t-5", "t-0"]

    # Empates de created_at: no fijan orden; se compara como conjunto.
    for tie in ("tie-1", "tie-2"):
        repo.add(
            Ticket(
                id=tie,
                title="Empate",
                description="Descripcion",
                requester_id=user["id"],
                created_at=base,
            )
        )
    tied = {
        item["id"]
        for item in client.get("/api/tickets").json()
        if item["id"] in {"tie-1", "tie-2"}
    }
    assert tied == {"tie-1", "tie-2"}


# --- RF-16: composicion del detalle sin datos personales ---


def test_sweep_detail_composition_without_personal_data():
    _register_and_login()
    created = _create("Titulo de barrido", "Descripcion de barrido")

    response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["description"] == "Descripcion de barrido"
    assert body["priority"] is None
    assert body["status"] == OPEN_STATUS
    text = response.text
    for forbidden in (
        '"name"',
        '"email"',
        '"role"',
        '"password"',
        '"password_hash"',
        '"hash"',
        '"token"',
    ):
        assert forbidden not in text


# --- RF-17: 404 unificado ---


def test_sweep_not_found_is_unified():
    _register_and_login()
    ajeno = _foreign_ticket()

    responses = [
        client.get(f"/api/tickets/{uuid.uuid4()}"),
        client.get("/api/tickets/no-es-uuid"),
        client.get("/api/tickets/123"),
        client.get(f"/api/tickets/{ajeno.id}"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.status_code not in (400, 403)
    assert len({response.text for response in responses}) == 1
    assert "contenido ajeno" not in responses[-1].text


# --- RF-18: ningun rechazo usa 400 ni 403; la autenticacion precede ---


def test_sweep_no_rejection_uses_400_or_403():
    _register_and_login()
    ajeno = _foreign_ticket()

    with_session = [
        client.post("/api/tickets", json={}),
        client.post("/api/tickets", json={"title": "  ", "description": "d"}),
        client.post(
            "/api/tickets",
            json={"title": "T", "description": "D", "status": "Cerrado"},
        ),
        client.get(f"/api/tickets/{uuid.uuid4()}"),
        client.get("/api/tickets/no-es-uuid"),
        client.get(f"/api/tickets/{ajeno.id}"),
        client.post("/api/tickets", json={"title": "T", "description": "D"}),
    ]

    assert [response.status_code for response in with_session] == [
        422,
        422,
        422,
        404,
        404,
        404,
        201,
    ]
    for response in with_session:
        assert response.status_code not in (400, 403)


def test_sweep_authentication_precedes_resource_resolution():
    _foreign_ticket()
    client.cookies.clear()

    without_session = [
        client.get("/api/tickets"),
        client.get(f"/api/tickets/{uuid.uuid4()}"),
        client.get("/api/tickets/no-es-uuid"),
        client.post("/api/tickets", json={"title": "T", "description": "D"}),
        client.post("/api/tickets", json={}),  # cuerpo invalido: aun asi 401
    ]

    for response in without_session:
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 422)


# --- RF-19: el estado permanece Abierto en el alcance de HU-02 ---


def test_sweep_status_stays_open_in_hu02_scope():
    _register_and_login()
    created = _create("Titulo", "Descripcion")

    for _ in range(3):
        assert client.get("/api/tickets").status_code == 200
        detail = client.get(f"/api/tickets/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "Abierto"
        _create("Otro titulo", "Otra descripcion")

    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    assert stored.status == OPEN_STATUS == "Abierto"

    # Las rutas de HU-02 siguen sin operaciones de modificacion. HU-03
    # anade la modificacion como subrecursos aparte (/priority y /status),
    # fuera de estas dos entradas de OpenAPI; aqui no se usan.
    paths = app.openapi()["paths"]
    assert set(paths["/api/tickets"]) == {"get", "post"}
    assert set(paths["/api/tickets/{ticket_id}"]) == {"get"}


# --- RF-20: aislamiento con dos sesiones simultaneas ---


def test_sweep_two_sessions_are_isolated():
    user_a = _register_and_login(client, "ana@ejemplo.com")
    user_b = _register_and_login(client_other, "bruno@ejemplo.com")
    ticket_a = _create("Ticket de Ana", "contenido de Ana", client)
    ticket_b = _create("Ticket de Bruno", "contenido de Bruno", client_other)

    list_a = client.get("/api/tickets").json()
    list_b = client_other.get("/api/tickets").json()
    assert [item["id"] for item in list_a] == [ticket_a["id"]]
    assert [item["id"] for item in list_b] == [ticket_b["id"]]

    assert client.get(f"/api/tickets/{ticket_a['id']}").json()["requester_id"] == user_a["id"]
    assert (
        client_other.get(f"/api/tickets/{ticket_b['id']}").json()["requester_id"]
        == user_b["id"]
    )
    assert client.get(f"/api/tickets/{ticket_b['id']}").status_code == 404
    assert client_other.get(f"/api/tickets/{ticket_a['id']}").status_code == 404
