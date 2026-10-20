"""T10 (HU-03) — Barrido final RF-21 a RF-30 y composicion de respuestas.

Comprueba de extremo a extremo los diez requisitos de la historia con
sesiones reales (cliente del autorregistro de HU-01 y tecnico/administrador
creados con `provision_user` y login real), la composicion cruda de las
respuestas de modificacion (`response.text` y `json.loads`, con `priority`
`null` y con valor, y `assignee` `null` mientras no haya asignacion), la
tabla completa de precedencia 401 > 404 > 409 >
422 (incluido el cuerpo crudo sintacticamente invalido: la autenticacion,
el permiso, la resolucion y el estado cerrado preceden a su decodificacion),
los empates de fecha del registro sin afirmar orden y que ningun rechazo
usa 400 ni 403.

Mapa RF -> test (en este archivo):
- RF-21 -> test_sweep_each_catalog_value_is_accepted
- RF-22 -> test_sweep_modification_raw_composition
- RF-23 -> test_sweep_modification_raw_composition,
           test_sweep_free_transitions_accumulate
- RF-24 -> test_sweep_two_sessions_management_roles_modify_any_ticket,
           test_sweep_precedence_table_with_real_sessions
- RF-25 -> test_sweep_precedence_table_with_real_sessions
- RF-26 -> test_sweep_log_records_each_change_without_exposing_it,
           test_sweep_log_ties_do_not_assert_order
- RF-27 -> test_sweep_queries_show_current_values_raw,
           test_sweep_modification_raw_composition
- RF-28 -> test_sweep_free_transitions_accumulate,
           test_sweep_precedence_table_with_real_sessions
- RF-29 -> test_sweep_invalid_requests_return_422
- RF-30 -> test_sweep_precedence_table_with_real_sessions,
           test_sweep_no_rejection_uses_400_or_403
- RF-21..RF-30 -> test_sweep_rf_map_covers_all_requirements (trazabilidad)

Los tests de esta barrida son transversales: no repiten las tablas
exhaustivas de las pruebas por tarea, sino que verifican la composicion
exacta, la precedencia completa con sesiones reales y los criterios de
finalizacion que cruzan varios RF.

Nota conocida y aceptada (igual que en HU-01 y HU-02): los 422 de Pydantic
devuelven `detail` como lista y los del dominio como string. No se
introduce ningun handler global por esto.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.application.set_ticket_priority import set_ticket_priority
from app.modules.tickets.application.update_ticket_status import (
    update_ticket_status,
)
from app.modules.tickets.domain.entities import (
    OPEN_STATUS,
    PRIORITIES,
    PRIORITY_FIELD,
    STATUSES,
    STATUS_FIELD,
    Ticket,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    InMemoryTicketModificationLog,
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
PASSWORD = "Secreta123"

client = TestClient(app)
staff_client = TestClient(app)
other_client = TestClient(app)
anon_client = TestClient(app)

DETAIL_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "assignee",
    "created_at",
    "requester_id",
}
SUMMARY_FIELDS = {"id", "title", "priority", "status", "assignee", "created_at"}

# Mapa RF -> test(s) que lo cubren (contrastado por
# `test_sweep_rf_map_covers_all_requirements`).
RF_MAP = {
    "RF-21": "test_sweep_each_catalog_value_is_accepted",
    "RF-22": "test_sweep_modification_raw_composition",
    "RF-23": (
        "test_sweep_modification_raw_composition"
        " + test_sweep_free_transitions_accumulate"
    ),
    "RF-24": (
        "test_sweep_two_sessions_management_roles_modify_any_ticket"
        " + test_sweep_precedence_table_with_real_sessions"
    ),
    "RF-25": "test_sweep_precedence_table_with_real_sessions",
    "RF-26": (
        "test_sweep_log_records_each_change_without_exposing_it"
        " + test_sweep_log_ties_do_not_assert_order"
    ),
    "RF-27": (
        "test_sweep_queries_show_current_values_raw"
        " + test_sweep_modification_raw_composition"
    ),
    "RF-28": (
        "test_sweep_free_transitions_accumulate"
        " + test_sweep_precedence_table_with_real_sessions"
    ),
    "RF-29": "test_sweep_invalid_requests_return_422",
    "RF-30": (
        "test_sweep_precedence_table_with_real_sessions"
        " + test_sweep_no_rejection_uses_400_or_403"
    ),
}

VALID_BODIES = {
    "priority": {"priority": "Alta"},
    "status": {"status": "Resuelto"},
}
OUT_OF_CATALOG = {
    "priority": {"priority": "Urgente"},
    "status": {"status": "Abierta"},
}

# Cuerpo crudo sintacticamente invalido (JSON mal formado) enviado con
# `content=` y `Content-Type: application/json`, no con `json=`.
MALFORMED_BODIES = {
    "priority": b'{"priority": ',
    "status": b'{"status": ',
}

JSON_HEADERS = {"Content-Type": "application/json"}

# Centinela para enviar la peticion sin cuerpo (RF-29.1).
NO_BODY = object()


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    for target in (client, staff_client, other_client, anon_client):
        target.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    for target in (client, staff_client, other_client, anon_client):
        target.cookies.clear()


def _register_and_login(target=client, email="ana@ejemplo.com", name="Ana Perez"):
    registered = target.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    _login(target, email)
    return registered.json()


def _login(target, email):
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200


def _provision_and_login(
    target=staff_client,
    role="tecnico",
    email="gestion@ejemplo.com",
    name="Equipo Soporte",
):
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(target, email)
    return user


def _create_ticket(target=client, title="Titulo", description="Descripcion"):
    response = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


def _put(endpoint, ticket_id, body=NO_BODY, target=staff_client):
    url = f"/api/tickets/{ticket_id}/{endpoint}"
    if body is NO_BODY:
        return target.put(url)
    if isinstance(body, bytes):
        # JSON sintacticamente invalido enviado crudo (no `json=`).
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _ticket_state(ticket_id):
    stored = get_ticket_repository().find_by_id(ticket_id)
    assert stored is not None
    return (
        stored.title,
        stored.description,
        stored.priority,
        stored.status,
        stored.requester_id,
        stored.created_at,
    )


def _snapshot(*ticket_ids):
    """Estado de los tickets y numero de registros, para probar no-cambios."""
    return (
        {ticket_id: _ticket_state(ticket_id) for ticket_id in ticket_ids},
        get_ticket_modification_log().count(),
    )


# --- Trazabilidad del mapa RF -> test ---


def test_sweep_rf_map_covers_all_requirements():
    expected = {f"RF-{number}" for number in range(21, 31)}
    assert set(RF_MAP) == expected
    for requirement, targets in RF_MAP.items():
        for name in targets.split(" + "):
            assert name in globals(), f"{requirement} apunta a {name} inexistente"


# --- RF-21: los cuatro valores de cada catalogo son los unicos admitidos ---


def test_sweep_each_catalog_value_is_accepted():
    assert PRIORITIES == ("Crítica", "Alta", "Media", "Baja")
    assert STATUSES == ("Abierto", "En progreso", "Resuelto", "Cerrado")

    _register_and_login(client)
    _provision_and_login()

    for priority in PRIORITIES:
        created = _create_ticket(client)
        response = _put("priority", created["id"], {"priority": priority})
        assert response.status_code == 200, priority
        assert response.json()["priority"] == priority

    for status in STATUSES:
        created = _create_ticket(client)
        if status == OPEN_STATUS:
            # Para ejercitar el valor como cambio, se sale y se vuelve.
            assert (
                _put("status", created["id"], {"status": "En progreso"}).status_code
                == 200
            )
        response = _put("status", created["id"], {"status": status})
        assert response.status_code == 200, status
        assert response.json()["status"] == status


# --- RF-22, RF-23 y RF-27: composicion cruda de la respuesta de modificacion ---


def test_sweep_modification_raw_composition():
    requester = _register_and_login(client)
    creation = client.post(
        "/api/tickets",
        json={"title": "Titulo de barrido", "description": "Descripcion de barrido"},
    )
    assert creation.status_code == 201
    created = creation.json()
    raw_creation = json.loads(creation.text)
    assert set(raw_creation) == DETAIL_FIELDS
    assert raw_creation["assignee"] is None
    assert '"priority":null' in creation.text
    assert '"assignee":null' in creation.text
    _provision_and_login()

    # Modificacion de estado antes de fijar prioridad: `priority` va null.
    status_change = _put("status", created["id"], {"status": "En progreso"})
    assert status_change.status_code == 200
    raw_status = json.loads(status_change.text)
    assert raw_status == {
        "id": created["id"],
        "title": "Titulo de barrido",
        "description": "Descripcion de barrido",
        "priority": None,
        "status": "En progreso",
        "assignee": None,
        "created_at": created["created_at"],
        "requester_id": requester["id"],
    }
    assert '"priority":null' in status_change.text
    assert '"status":"En progreso"' in status_change.text
    assert '"assignee":null' in status_change.text

    # Modificacion de prioridad: la respuesta completa lleva el valor vigente.
    priority_change = _put("priority", created["id"], {"priority": "Alta"})
    assert priority_change.status_code == 200
    raw_priority = json.loads(priority_change.text)
    assert raw_priority == {
        "id": created["id"],
        "title": "Titulo de barrido",
        "description": "Descripcion de barrido",
        "priority": "Alta",
        "status": "En progreso",
        "assignee": None,
        "created_at": created["created_at"],
        "requester_id": requester["id"],
    }
    assert '"priority":"Alta"' in priority_change.text
    assert '"status":"En progreso"' in priority_change.text
    assert '"assignee":null' in priority_change.text

    # El registro de modificaciones no aparece en ningun cuerpo crudo.
    for response in (status_change, priority_change):
        assert response.status_code not in (400, 403)
        for forbidden in (
            "previous_value",
            "new_value",
            "actor_id",
            "changed_at",
            "modifications",
        ):
            assert forbidden not in response.text


# --- RF-23 y RF-28: transiciones libres, acumulacion y cerrado inmutable ---


def test_sweep_free_transitions_accumulate():
    _register_and_login(client)
    created = _create_ticket(client)
    actor = _provision_and_login()

    # Saltos y retrocesos sin reglas de secuencia (RF-23).
    transitions = ["Resuelto", "En progreso", "Cerrado"]
    responses = [
        _put("status", created["id"], {"status": status})
        for status in transitions
    ]
    assert [response.status_code for response in responses] == [200, 200, 200]

    records = get_ticket_modification_log().list_by_ticket(created["id"])
    assert [(record.previous_value, record.new_value) for record in records] == [
        (OPEN_STATUS, "Resuelto"),
        ("Resuelto", "En progreso"),
        ("En progreso", "Cerrado"),
    ]
    assert {record.actor_id for record in records} == {actor.id}
    assert get_ticket_repository().find_by_id(created["id"]).status == "Cerrado"

    # El cliente ve el estado vigente (RF-27.1).
    detail = client.get(f"/api/tickets/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "Cerrado"

    # Ticket cerrado: inmutable aunque el valor sea valido o el vigente.
    before = _snapshot(created["id"])
    closed_attempts = [
        _put("priority", created["id"], {"priority": "Alta"}),
        _put("priority", created["id"], {"priority": "Urgente"}),
        _put("status", created["id"], {"status": "Cerrado"}),
        _put("status", created["id"], {"status": "Abierto"}),
        _put("priority", created["id"], {}),
        _put("status", created["id"]),
    ]
    assert [response.status_code for response in closed_attempts] == [409] * 6
    for response in closed_attempts:
        assert response.status_code not in (400, 403, 404, 422)
        assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
    assert _snapshot(created["id"]) == before


# --- RF-24 y RF-27.1: dos sesiones reales coexistentes ---


def test_sweep_two_sessions_management_roles_modify_any_ticket():
    requester = _register_and_login(client)
    created = _create_ticket(client, "Ticket de Ana", "contenido de Ana")

    # Un tecnico y un administrador modifican un ticket que no crearon y
    # sin asignacion (HU-04): la autorizacion es solo por rol (RF-24).
    # Cada rol actua con su propia sesion real (se inicia sesion antes de
    # sus peticiones, no ambas al principio).
    tech = _provision_and_login(role="tecnico")
    responses = [
        _put("priority", created["id"], {"priority": "Crítica"}),
        _put("status", created["id"], {"status": "En progreso"}),
    ]
    admin = _provision_and_login(
        role="administrador", email="admin@ejemplo.com", name="Admin Soporte"
    )
    responses.extend(
        [
            _put("priority", created["id"], {"priority": "Alta"}),
            _put("status", created["id"], {"status": "Resuelto"}),
        ]
    )
    assert [response.status_code for response in responses] == [200] * 4
    for response in responses:
        assert response.json()["requester_id"] == requester["id"]
        assert response.json()["created_at"] == created["created_at"]

    records = get_ticket_modification_log().list_by_ticket(created["id"])
    assert [record.actor_id for record in records] == [
        tech.id,
        tech.id,
        admin.id,
        admin.id,
    ]

    # El cliente ve los valores vigentes en sus consultas (RF-27.1).
    [item] = client.get("/api/tickets").json()
    assert item["priority"] == "Alta"
    assert item["status"] == "Resuelto"
    detail = client.get(f"/api/tickets/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["priority"] == "Alta"
    assert detail.json()["status"] == "Resuelto"

    # Sus intentos de modificacion no alteran nada ni revelan el ticket.
    before = _snapshot(created["id"])
    client_attempts = [
        _put("priority", created["id"], {"priority": "Baja"}, target=client),
        _put("status", created["id"], {"status": "Cerrado"}, target=client),
    ]
    assert [response.status_code for response in client_attempts] == [404, 404]
    unified = client.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert client_attempts[0].text == client_attempts[1].text == unified.text
    assert _snapshot(created["id"]) == before


# --- RF-26: contenido del registro y no exposicion en las respuestas ---


def test_sweep_log_records_each_change_without_exposing_it():
    requester = _register_and_login(client)
    created = _create_ticket(client)
    actor = _provision_and_login()

    before = datetime.now(timezone.utc)
    priority_response = _put("priority", created["id"], {"priority": "Baja"})
    status_response = _put("status", created["id"], {"status": "Resuelto"})
    after = datetime.now(timezone.utc)

    assert priority_response.status_code == status_response.status_code == 200
    records = get_ticket_modification_log().list_by_ticket(created["id"])
    assert len(records) == 2
    by_field = {record.field: record for record in records}
    priority_record = by_field[PRIORITY_FIELD]
    status_record = by_field[STATUS_FIELD]

    assert priority_record.ticket_id == created["id"]
    assert priority_record.previous_value is None  # primera prioridad
    assert priority_record.new_value == "Baja"
    assert priority_record.actor_id == actor.id
    assert priority_record.changed_at.tzinfo is not None
    assert priority_record.changed_at.utcoffset().total_seconds() == 0
    assert before <= priority_record.changed_at <= after

    assert status_record.ticket_id == created["id"]
    assert status_record.previous_value == OPEN_STATUS
    assert status_record.new_value == "Resuelto"
    assert status_record.actor_id == actor.id
    assert before <= status_record.changed_at <= after

    assert get_ticket_modification_log().count() == 2
    for response in (priority_response, status_response):
        assert response.status_code not in (400, 403)
        for forbidden in (
            "previous_value",
            "new_value",
            "actor_id",
            "changed_at",
            "modifications",
            "ticket_id",
        ):
            assert forbidden not in response.text

    # Tampoco existe una ruta publica que exponga el registro.
    for path in app.openapi()["paths"]:
        assert "modification" not in path.lower()


def test_sweep_log_ties_do_not_assert_order():
    """RF-26: un empate de `changed_at` no fija orden entre los registros."""
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id="u-cliente",
        created_at=NOW,
    )
    log = InMemoryTicketModificationLog()

    set_ticket_priority(ticket, "Media", "u-tech", log, now=NOW)
    update_ticket_status(ticket, "En progreso", "u-tech", log, now=NOW)

    records = log.list_by_ticket(ticket.id)
    assert len(records) == 2  # ninguno se pierde en el empate
    assert {record.changed_at for record in records} == {NOW}
    # Se compara como conjunto: no se afirma orden entre los empates.
    assert {(record.field, record.previous_value, record.new_value) for record in records} == {
        (PRIORITY_FIELD, None, "Media"),
        (STATUS_FIELD, OPEN_STATUS, "En progreso"),
    }
    assert log.count() == 2


# --- RF-27: consultas con prioridad (null y con valor) y creacion intacta ---


def test_sweep_queries_show_current_values_raw():
    requester = _register_and_login(client)

    creation = client.post(
        "/api/tickets",
        json={"title": "Con prioridad", "description": "Detalle"},
    )
    assert creation.status_code == 201
    created = creation.json()
    second = _create_ticket(client, "Sin prioridad", "Otra descripcion")

    raw_creation = json.loads(creation.text)
    assert set(raw_creation) == DETAIL_FIELDS
    assert raw_creation["assignee"] is None
    assert '"priority":null' in creation.text
    assert '"assignee":null' in creation.text
    assert creation.json()["status"] == OPEN_STATUS

    # La creacion sigue rechazando `priority` con 422 (RF-27.3).
    rejected = client.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion", "priority": "Alta"},
    )
    assert rejected.status_code == 422
    assert rejected.status_code not in (400, 403)
    assert get_ticket_repository().count() == 2

    _provision_and_login()
    assert (
        _put("priority", created["id"], {"priority": "Media"}).status_code == 200
    )
    assert (
        _put("status", created["id"], {"status": "Resuelto"}).status_code == 200
    )

    listing = client.get("/api/tickets")
    assert listing.status_code == 200
    items = json.loads(listing.text)
    assert len(items) == 2
    by_id = {item["id"]: item for item in items}
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert item["assignee"] is None
    assert by_id[created["id"]]["priority"] == "Media"
    assert by_id[created["id"]]["status"] == "Resuelto"
    assert by_id[second["id"]]["priority"] is None
    assert '"priority":"Media"' in listing.text
    assert '"priority":null' in listing.text
    assert '"assignee":null' in listing.text
    assert '"description"' not in listing.text
    assert '"requester_id"' not in listing.text

    detail = client.get(f"/api/tickets/{created['id']}")
    assert detail.status_code == 200
    raw_detail = json.loads(detail.text)
    assert set(raw_detail) == DETAIL_FIELDS
    assert raw_detail["priority"] == "Media"
    assert raw_detail["status"] == "Resuelto"
    assert raw_detail["assignee"] is None
    assert raw_detail["requester_id"] == requester["id"]
    assert '"priority":"Media"' in detail.text


# --- RF-29: entradas invalidas -> 422 sin modificar ni registrar ---


def test_sweep_invalid_requests_return_422():
    _register_and_login(client)
    created = _create_ticket(client)
    _provision_and_login()
    before = _snapshot(created["id"])

    invalid_bodies = {
        "priority": [
            {},
            {"priority": None},
            {"priority": 3},
            {"priority": True},
            {"priority": ["Alta"]},
            {"priority": {"valor": "Alta"}},
            {"priority": "Urgente"},
            {"priority": "alta"},
            {"priority": " Alta "},
            {"priority": "Alta", "actor_id": "otro-usuario"},
            {"priority": "Alta", "changed_at": "2026-10-19T12:00:00+00:00"},
            {"priority": "Alta", "status": "Resuelto"},
        ],
        "status": [
            {},
            {"status": None},
            {"status": 3},
            {"status": True},
            {"status": ["Resuelto"]},
            {"status": {"valor": "Resuelto"}},
            {"status": "Abierta"},
            {"status": "abierto"},
            {"status": "En Progreso"},
            {"status": "Resuelto", "actor_id": "otro-usuario"},
            {"status": "Resuelto", "changed_at": "2026-10-19T12:00:00+00:00"},
            {"status": "Resuelto", "priority": "Alta"},
        ],
    }

    for endpoint, payloads in invalid_bodies.items():
        for payload in payloads:
            response = _put(endpoint, created["id"], payload)
            assert response.status_code == 422, (endpoint, payload)
            assert response.status_code not in (400, 403, 404, 409)
            assert set(response.json()) == {"detail"}

        malformed = _put(endpoint, created["id"], MALFORMED_BODIES[endpoint])
        assert malformed.status_code == 422, (endpoint, "json invalido")
        assert malformed.status_code not in (400, 403, 404, 409)
        assert set(malformed.json()) == {"detail"}

        no_body = _put(endpoint, created["id"])
        assert no_body.status_code == 422
        assert no_body.status_code not in (400, 403, 404, 409)

    assert _snapshot(created["id"]) == before


# --- RF-24, RF-25, RF-28 y RF-30: tabla completa de precedencia ---


def test_sweep_precedence_table_with_real_sessions():
    _register_and_login(client)
    _register_and_login(
        other_client, email="bruno@ejemplo.com", name="Bruno Diaz"
    )
    open_ticket = _create_ticket(client, "Propio abierto")
    closed_ticket = _create_ticket(client, "Propio cerrado")
    foreign_ticket = _create_ticket(other_client, "Ajeno")
    _provision_and_login()

    # Ticket cerrado con prioridad vigente, para probar la precedencia 409.
    assert (
        _put("priority", closed_ticket["id"], {"priority": "Media"}).status_code
        == 200
    )
    assert (
        _put("status", closed_ticket["id"], {"status": "Cerrado"}).status_code
        == 200
    )

    unified = client.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert unified.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}

    ticket_ids = {
        "open": open_ticket["id"],
        "closed": closed_ticket["id"],
        "foreign": foreign_ticket["id"],
        "missing": str(uuid.uuid4()),
        "invalid": "no-es-uuid",
    }
    sessions = {
        "anon": anon_client,
        "client": client,
        "tech": staff_client,
    }
    current_closed = {
        "priority": {"priority": "Media"},
        "status": {"status": "Cerrado"},
    }

    # Tabla de precedencia:
    # (endpoint, sesion, ticket, cuerpo, codigo esperado).
    cases = []
    for endpoint in ("priority", "status"):
        cases.extend(
            [
                (endpoint, "anon", "invalid", {}, 401),
                (endpoint, "anon", "open", VALID_BODIES[endpoint], 401),
                (endpoint, "anon", "closed", {}, 401),
                (endpoint, "client", "open", VALID_BODIES[endpoint], 404),
                (endpoint, "client", "open", {}, 404),
                (endpoint, "client", "foreign", VALID_BODIES[endpoint], 404),
                (endpoint, "client", "missing", VALID_BODIES[endpoint], 404),
                (endpoint, "client", "invalid", {}, 404),
                (endpoint, "client", "closed", {}, 404),
                (endpoint, "tech", "missing", {}, 404),
                (endpoint, "tech", "invalid", VALID_BODIES[endpoint], 404),
                (endpoint, "tech", "closed", {}, 409),
                (endpoint, "tech", "closed", VALID_BODIES[endpoint], 409),
                (endpoint, "tech", "closed", current_closed[endpoint], 409),
                (endpoint, "tech", "open", {}, 422),
                (endpoint, "tech", "open", OUT_OF_CATALOG[endpoint], 422),
                # JSON sintacticamente invalido (cuerpo crudo): la
                # precedencia se resuelve antes de decodificarlo (RF-30).
                (endpoint, "anon", "invalid", MALFORMED_BODIES[endpoint], 401),
                (endpoint, "anon", "open", MALFORMED_BODIES[endpoint], 401),
                (endpoint, "anon", "closed", MALFORMED_BODIES[endpoint], 401),
                (endpoint, "client", "open", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "client", "foreign", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "client", "missing", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "client", "closed", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "tech", "missing", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "tech", "invalid", MALFORMED_BODIES[endpoint], 404),
                (endpoint, "tech", "closed", MALFORMED_BODIES[endpoint], 409),
                (endpoint, "tech", "open", MALFORMED_BODIES[endpoint], 422),
                (endpoint, "tech", "open", VALID_BODIES[endpoint], 200),
            ]
        )

    seen = set()
    for endpoint, origin, ticket_key, body, expected in cases:
        before = _snapshot(
            open_ticket["id"], closed_ticket["id"], foreign_ticket["id"]
        )
        response = _put(
            endpoint,
            ticket_ids[ticket_key],
            body,
            target=sessions[origin],
        )
        seen.add(response.status_code)
        assert response.status_code == expected, (
            endpoint,
            origin,
            ticket_key,
            body,
            response.text,
        )
        assert response.status_code not in (400, 403)

        if expected == 200:
            # Un unico cambio efectivo en el ticket abierto.
            assert _snapshot(
                open_ticket["id"], closed_ticket["id"], foreign_ticket["id"]
            )[1] == before[1] + 1
        else:
            # Ningun rechazo modifica ticket ni genera registro.
            assert _snapshot(
                open_ticket["id"], closed_ticket["id"], foreign_ticket["id"]
            ) == before
            if expected == 404:
                assert response.text == unified.text
            elif expected == 409:
                assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
            else:
                assert set(response.json()) == {"detail"}

    assert seen == {200, 401, 404, 409, 422}


# --- RF-30: ningun rechazo usa 400 ni 403 ---


def test_sweep_no_rejection_uses_400_or_403():
    _register_and_login(client)
    open_ticket = _create_ticket(client)
    to_close = _create_ticket(client)
    _provision_and_login()
    assert (
        _put("status", to_close["id"], {"status": "Cerrado"}).status_code == 200
    )

    before = _snapshot(open_ticket["id"], to_close["id"])
    responses = []

    for endpoint in ("priority", "status"):
        responses.extend(
            [
                # 401: sin sesion valida, incluso con cuerpo o id invalidos.
                _put(
                    endpoint,
                    open_ticket["id"],
                    VALID_BODIES[endpoint],
                    target=anon_client,
                ),
                _put(endpoint, "no-es-uuid", {}, target=anon_client),
                _put(
                    endpoint,
                    open_ticket["id"],
                    MALFORMED_BODIES[endpoint],
                    target=anon_client,
                ),
                # 404: cliente (propio y ajeno) y ticket inexistente.
                _put(
                    endpoint,
                    open_ticket["id"],
                    VALID_BODIES[endpoint],
                    target=client,
                ),
                _put(endpoint, str(uuid.uuid4()), VALID_BODIES[endpoint]),
                _put(
                    endpoint,
                    open_ticket["id"],
                    MALFORMED_BODIES[endpoint],
                    target=client,
                ),
                # 409: ticket cerrado.
                _put(endpoint, to_close["id"], VALID_BODIES[endpoint]),
                _put(endpoint, to_close["id"], MALFORMED_BODIES[endpoint]),
                # 422: validacion de la solicitud.
                _put(endpoint, open_ticket["id"], {}),
                _put(endpoint, open_ticket["id"], OUT_OF_CATALOG[endpoint]),
                _put(endpoint, open_ticket["id"], MALFORMED_BODIES[endpoint]),
            ]
        )

    # La creacion con prioridad se sigue rechazando con 422 (RF-27.3).
    responses.append(
        client.post(
            "/api/tickets",
            json={
                "title": "Titulo",
                "description": "Descripcion",
                "priority": "Alta",
            },
        )
    )

    assert {response.status_code for response in responses} == {
        401,
        404,
        409,
        422,
    }
    for response in responses:
        assert response.status_code not in (400, 403)

    # Ningun rechazo ha modificado tickets ni generado registros.
    assert _snapshot(open_ticket["id"], to_close["id"]) == before
    assert get_ticket_repository().count() == 2
