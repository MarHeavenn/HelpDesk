"""T11 (HU-04) — Barrido final RF-31 a RF-40 y composicion de respuestas.

Comprueba de extremo a extremo los diez requisitos de la historia con
sesiones reales (cliente del autorregistro de HU-01 y tecnico/administrador
creados con `provision_user` y login real): la composicion cruda de las
respuestas (`response.text` y `json.loads`) con `assignee` `null` y con
valor en creacion, listado, detalle, asignacion, modificaciones de HU-03 y
tickets a cargo, la tabla de precedencia 401 > 404 > 409 > 422 (incluido
el cuerpo crudo sintacticamente invalido: la autenticacion, el permiso, la
resolucion y el estado cerrado preceden a su decodificacion), el contenido
y la invisibilidad total del registro de asignaciones, los empates de fecha
sin afirmar orden y que ningun rechazo usa 400 ni 403.

Mapa RF -> test (en este archivo):
- RF-31 -> test_sweep_technicians_directory_is_admin_only,
           test_sweep_auth_precedence_across_endpoints
- RF-32 -> test_sweep_creation_and_raw_composition_null_and_assigned
- RF-33 -> test_sweep_assignment_log_records_changes_without_exposing_them
- RF-34 -> test_sweep_creation_and_raw_composition_null_and_assigned
- RF-35 -> test_sweep_creation_and_raw_composition_null_and_assigned,
           test_sweep_tickets_assigned_to_me
- RF-35.5 -> test_sweep_creation_and_raw_composition_null_and_assigned
- RF-36 -> test_sweep_tickets_assigned_to_me,
           test_sweep_assigned_list_ties_do_not_assert_order
- RF-37 -> test_sweep_assignment_log_records_changes_without_exposing_them,
           test_sweep_assignment_log_ties_do_not_assert_order
- RF-38 -> test_sweep_precedence_table_with_real_sessions
- RF-39 -> test_sweep_precedence_table_with_real_sessions
- RF-40 -> test_sweep_precedence_table_with_real_sessions,
           test_sweep_auth_precedence_across_endpoints,
           test_sweep_no_rejection_uses_400_or_403
- RF-31..RF-40 -> test_sweep_rf_map_covers_all_requirements (trazabilidad)

Los tests de esta barrida son transversales: no repiten las tablas
exhaustivas de las pruebas por tarea, sino que verifican la composicion
exacta, la precedencia completa con sesiones reales, el registro interno y
los criterios de finalizacion que cruzan varios RF.

Nota conocida y aceptada (igual que en HU-01 a HU-03): los 422 de Pydantic
devuelven `detail` como lista y los del dominio como string. No se
introduce ningun handler global por esto.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.technicians_contract import (
    get_technician_summary,
)
from app.modules.tickets.application.assign_ticket import (
    INVALID_TECHNICIAN_MESSAGE,
    assign_ticket,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.assignment_log import (
    InMemoryAssignmentLog,
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

PASSWORD = "Secreta123"
BASE = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

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
ASSIGNEE_FIELDS = {"id", "name"}

# Claves internas del registro que no deben aparecer en ningun cuerpo.
FORBIDDEN_LOG_KEYS = (
    "previous_assignee_id",
    "new_assignee_id",
    "actor_id",
    "assigned_at",
    "ticket_assignments",
    "assignments",
)

JSON_HEADERS = {"Content-Type": "application/json"}
MALFORMED_ASSIGNEE_BODY = b'{"assignee_id": '
NO_BODY = object()

# Mapa RF -> test(s) que lo cubren (contrastado por
# `test_sweep_rf_map_covers_all_requirements`).
RF_MAP = {
    "RF-31": (
        "test_sweep_technicians_directory_is_admin_only"
        " + test_sweep_auth_precedence_across_endpoints"
    ),
    "RF-32": "test_sweep_creation_and_raw_composition_null_and_assigned",
    "RF-33": (
        "test_sweep_assignment_log_records_changes_without_exposing_them"
    ),
    "RF-34": "test_sweep_creation_and_raw_composition_null_and_assigned",
    "RF-35": (
        "test_sweep_creation_and_raw_composition_null_and_assigned"
        " + test_sweep_tickets_assigned_to_me"
    ),
    "RF-35.5": (
        "test_sweep_creation_and_raw_composition_null_and_assigned"
    ),
    "RF-36": (
        "test_sweep_tickets_assigned_to_me"
        " + test_sweep_assigned_list_ties_do_not_assert_order"
    ),
    "RF-37": (
        "test_sweep_assignment_log_records_changes_without_exposing_them"
        " + test_sweep_assignment_log_ties_do_not_assert_order"
    ),
    "RF-38": "test_sweep_precedence_table_with_real_sessions",
    "RF-39": "test_sweep_precedence_table_with_real_sessions",
    "RF-40": (
        "test_sweep_precedence_table_with_real_sessions"
        " + test_sweep_auth_precedence_across_endpoints"
        " + test_sweep_no_rejection_uses_400_or_403"
    ),
}

anon_api = TestClient(app)
client_api = TestClient(app)
tech_api = TestClient(app)
admin_api = TestClient(app)

CLIENTS = (anon_api, client_api, tech_api, admin_api)


@pytest.fixture(autouse=True)
def clean_state():
    _clear_state()
    yield
    _clear_state()


def _clear_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_assignment_log().clear()
    get_ticket_modification_log().clear()
    for target in CLIENTS:
        target.cookies.clear()


def _register_client(target=client_api, email=None, name="Cliente Uno"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    registered = target.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201, registered.text
    _login(target, email)
    return registered.json()


def _login(target, email):
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200, logged.text
    return logged


def _provision(role="tecnico", email=None, name="Equipo Soporte"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    return provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )


def _provision_and_login(
    target, role="tecnico", email=None, name="Equipo Soporte"
):
    user = _provision(role=role, email=email, name=name)
    _login(target, user.email)
    return user


def _create_ticket(target=client_api, title="Titulo", description="Descripcion"):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201, created.text
    return created.json()


def _put_assignee(ticket_id, body=NO_BODY, target=admin_api):
    url = f"/api/tickets/{ticket_id}/assignee"
    if body is NO_BODY:
        return target.put(url)
    if isinstance(body, bytes):
        # JSON sintacticamente invalido enviado crudo (no `json=`).
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _put_status(ticket_id, status, target=admin_api):
    return target.put(f"/api/tickets/{ticket_id}/status", json={"status": status})


def _put_priority(ticket_id, priority, target=admin_api):
    return target.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": priority}
    )


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
        stored.assignee_id,
        stored.assignee_name,
    )


def _snapshot(*ticket_ids):
    """Estado de los tickets y numero de registros de ambos logs."""
    return (
        {ticket_id: _ticket_state(ticket_id) for ticket_id in ticket_ids},
        get_assignment_log().count(),
        get_ticket_modification_log().count(),
    )


def _set_created_at(ticket_id, when):
    stored = get_ticket_repository().find_by_id(ticket_id)
    assert stored is not None
    stored.created_at = when


def _assert_no_forbidden_payload(response, extra_forbidden=()):
    assert response.status_code not in (400, 403)
    for forbidden in (*FORBIDDEN_LOG_KEYS, *extra_forbidden):
        assert forbidden not in response.text, (forbidden, response.text)


# --- Trazabilidad del mapa RF -> test ---


def test_sweep_rf_map_covers_all_requirements():
    expected = {f"RF-{number}" for number in range(31, 41)}
    # RF-35.5 es una regla de RF-35, no un requisito numerado nuevo.
    assert set(RF_MAP) == expected | {"RF-35.5"}
    for requirement, targets in RF_MAP.items():
        for name in targets.split(" + "):
            assert name in globals(), f"{requirement} apunta a {name} inexistente"


# --- RF-32, RF-34, RF-35 y RF-35.5: composicion cruda completa ---


def test_sweep_creation_and_raw_composition_null_and_assigned():
    requester = _register_client()
    tech = _provision_and_login(
        tech_api, email="tec@ejemplo.com", name="Tecnico Uno"
    )
    _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )

    creation = client_api.post(
        "/api/tickets",
        json={"title": "Barrido crudo", "description": "Contenido"},
    )
    assert creation.status_code == 201
    created = creation.json()
    raw_creation = json.loads(creation.text)
    assert set(raw_creation) == DETAIL_FIELDS
    assert raw_creation["assignee"] is None
    assert raw_creation["priority"] is None
    assert raw_creation["status"] == "Abierto"
    assert '"assignee":null' in creation.text

    # RF-34: nace sin asignacion y el tecnico en la creacion sigue siendo 422.
    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored.assignee_id is None and stored.assignee_name is None
    before_count = get_ticket_repository().count()
    rejected_creation = client_api.post(
        "/api/tickets",
        json={
            "title": "Con tecnico",
            "description": "No debe crearse",
            "assignee_id": tech.id,
        },
    )
    assert rejected_creation.status_code == 422
    assert rejected_creation.status_code not in (400, 403)
    assert get_ticket_repository().count() == before_count

    # Listado y detalle sin asignacion: mismo `null` crudo.
    listing = client_api.get("/api/tickets")
    detail = client_api.get(f"/api/tickets/{created['id']}")
    assert listing.status_code == detail.status_code == 200
    [listed] = json.loads(listing.text)
    assert set(listed) == SUMMARY_FIELDS
    assert listed["assignee"] is None
    assert '"assignee":null' in listing.text
    raw_detail = json.loads(detail.text)
    assert set(raw_detail) == DETAIL_FIELDS
    assert raw_detail["assignee"] is None
    assert raw_detail["requester_id"] == requester["id"]
    assert '"assignee":null' in detail.text

    # Primera asignacion: el cuerpo completo lleva `{id, name}` y conserva
    # prioridad, estado, fecha y solicitante (RF-32).
    assigned = _put_assignee(created["id"], {"assignee_id": tech.id})
    assert assigned.status_code == 200
    raw_assigned = json.loads(assigned.text)
    assert set(raw_assigned) == DETAIL_FIELDS
    assert raw_assigned["assignee"] == {"id": tech.id, "name": tech.name}
    assert set(raw_assigned["assignee"]) == ASSIGNEE_FIELDS
    assert raw_assigned["priority"] is None
    assert raw_assigned["status"] == "Abierto"
    assert raw_assigned["created_at"] == created["created_at"]
    assert raw_assigned["requester_id"] == requester["id"]
    assert '"assignee":{' in assigned.text
    _assert_no_forbidden_payload(
        assigned, extra_forbidden=(tech.email, "password", "hash", "role")
    )

    # Listado, detalle y tickets a cargo comparten la composicion con valor.
    listing = client_api.get("/api/tickets")
    detail = client_api.get(f"/api/tickets/{created['id']}")
    mine = tech_api.get("/api/assignments/mine")
    assert listing.status_code == detail.status_code == mine.status_code == 200
    [listed] = json.loads(listing.text)
    raw_detail = json.loads(detail.text)
    [assigned_to_me] = json.loads(mine.text)
    assert set(listed) == SUMMARY_FIELDS
    assert set(raw_detail) == DETAIL_FIELDS
    assert set(assigned_to_me) == SUMMARY_FIELDS
    for body in (listed, raw_detail, assigned_to_me):
        assert body["assignee"] == {"id": tech.id, "name": tech.name}

    # Modificaciones de HU-03 (RF-35.5): misma composicion y valores vigentes.
    priority_change = _put_priority(created["id"], "Alta")
    status_change = _put_status(created["id"], "En progreso")
    assert priority_change.status_code == status_change.status_code == 200
    for response in (priority_change, status_change):
        raw = json.loads(response.text)
        assert set(raw) == DETAIL_FIELDS
        assert raw["assignee"] == {"id": tech.id, "name": tech.name}
        assert '"assignee":{"id":"' in response.text
        _assert_no_forbidden_payload(
            response, extra_forbidden=(tech.email, "password", "hash", "role")
        )
    assert priority_change.json()["priority"] == "Alta"
    assert status_change.json()["status"] == "En progreso"

    # Reasignacion: las consultas muestran al tecnico vigente.
    other_tech = _provision(
        email="tec2@ejemplo.com", name="Tecnico Dos"
    )
    reassigned = _put_assignee(created["id"], {"assignee_id": other_tech.id})
    assert reassigned.status_code == 200
    assert reassigned.json()["assignee"] == {
        "id": other_tech.id,
        "name": other_tech.name,
    }
    for response in (
        client_api.get("/api/tickets"),
        client_api.get(f"/api/tickets/{created['id']}"),
    ):
        assert response.status_code == 200
        body = response.json()
        item = body[0] if isinstance(body, list) else body
        assert item["assignee"] == {
            "id": other_tech.id,
            "name": other_tech.name,
        }


# --- RF-33 y RF-37: registro interno, acumulacion e invisibilidad ---


def test_sweep_assignment_log_records_changes_without_exposing_them():
    requester = _register_client()
    admin = _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )
    tech_one = _provision(email="tec1@ejemplo.com", name="Tecnico Uno")
    tech_two = _provision(email="tec2@ejemplo.com", name="Tecnico Dos")
    created = _create_ticket()
    assert created["requester_id"] == requester["id"]

    before = datetime.now(timezone.utc)
    first = _put_assignee(created["id"], {"assignee_id": tech_one.id})
    after = datetime.now(timezone.utc)
    assert first.status_code == 200

    records = get_assignment_log().list_by_ticket(created["id"])
    assert len(records) == 1
    first_record = records[0]
    assert first_record.ticket_id == created["id"]
    assert first_record.previous_assignee_id is None
    assert first_record.new_assignee_id == tech_one.id
    assert first_record.actor_id == admin.id
    assert first_record.assigned_at.tzinfo is not None
    assert first_record.assigned_at.utcoffset().total_seconds() == 0
    assert before <= first_record.assigned_at <= after
    _assert_no_forbidden_payload(
        first, extra_forbidden=(tech_one.email, tech_two.email)
    )

    # RF-33: repetir el vigente no cambia ni registra.
    stored_before = _ticket_state(created["id"])
    repeated = _put_assignee(created["id"], {"assignee_id": tech_one.id})
    assert repeated.status_code == 200
    assert repeated.json()["assignee"] == {
        "id": tech_one.id,
        "name": tech_one.name,
    }
    assert _ticket_state(created["id"]) == stored_before
    assert get_assignment_log().count() == 1

    # Reasignacion efectiva: anterior vigente y nuevo en orden de alta.
    second = _put_assignee(created["id"], {"assignee_id": tech_two.id})
    assert second.status_code == 200
    records = get_assignment_log().list_by_ticket(created["id"])
    assert len(records) == 2
    assert [
        (record.previous_assignee_id, record.new_assignee_id)
        for record in records
    ] == [(None, tech_one.id), (tech_one.id, tech_two.id)]
    assert {record.actor_id for record in records} == {admin.id}
    assert get_assignment_log().count() == 2

    # Ticket cerrado: 409 incluso repitiendo el vigente, sin registro.
    closed = _put_status(created["id"], "Cerrado")
    assert closed.status_code == 200
    before_rejection = _snapshot(created["id"])
    rejected = _put_assignee(created["id"], {"assignee_id": tech_two.id})
    assert rejected.status_code == 409
    assert rejected.json() == {"detail": TICKET_CLOSED_MESSAGE}
    assert rejected.status_code not in (400, 403)
    assert _snapshot(created["id"]) == before_rejection
    assert get_assignment_log().count() == 2

    # Ninguna respuesta publica expone el registro (RF-37).
    public_responses = [
        first,
        repeated,
        second,
        closed,
        client_api.get("/api/tickets"),
        client_api.get(f"/api/tickets/{created['id']}"),
        tech_api.get("/api/assignments/mine"),
    ]
    for response in public_responses:
        _assert_no_forbidden_payload(
            response, extra_forbidden=(tech_one.email, tech_two.email)
        )

    # Tampoco existe una ruta publica de historial: solo la consulta a cargo.
    paths = app.openapi()["paths"]
    assignment_paths = [path for path in paths if "assignment" in path.lower()]
    assert assignment_paths == ["/api/assignments/mine"]
    assert set(paths["/api/tickets/{ticket_id}/assignee"]) == {"put"}
    for path in paths:
        if "ticket" not in path.lower() and "assignment" not in path.lower():
            continue
        assert not any(
            token in path.lower() for token in ("history", "log", "record")
        )


def test_sweep_assignment_log_ties_do_not_assert_order():
    """RF-37: un empate de `assigned_at` no fija orden entre los registros."""
    tech_one = _provision(email="tec1@ejemplo.com", name="Tecnico Uno")
    tech_two = _provision(email="tec2@ejemplo.com", name="Tecnico Dos")
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id=str(uuid.uuid4()),
        created_at=BASE,
    )
    repo = InMemoryTicketRepository()
    repo.add(ticket)
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket, tech_one.id, "admin-id", get_technician_summary, log, now=BASE
    )
    assign_ticket(
        ticket, tech_two.id, "admin-id", get_technician_summary, log, now=BASE
    )

    records = log.list_by_ticket(ticket.id)
    assert len(records) == 2  # ninguno se pierde en el empate
    assert {record.assigned_at for record in records} == {BASE}
    # Se compara como conjunto: no se afirma orden entre los empates.
    assert {
        (record.previous_assignee_id, record.new_assignee_id)
        for record in records
    } == {(None, tech_one.id), (tech_one.id, tech_two.id)}
    assert log.count() == 2


# --- RF-31: directorio de tecnicos solo para administradores ---


def test_sweep_technicians_directory_is_admin_only():
    admin = _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )
    assert admin.role == "administrador"

    # Coleccion vacia valida y parametros desconocidos ignorados (RF-31).
    empty = admin_api.get("/api/technicians")
    assert empty.status_code == 200
    assert json.loads(empty.text) == []
    assert admin_api.get("/api/technicians?page=9&role=cliente").text == empty.text

    # Sin sesion valida: 401 antes que cualquier otra cosa (RF-40).
    unauthenticated = anon_api.get("/api/technicians")
    assert unauthenticated.status_code == 401
    assert unauthenticated.status_code not in (400, 403)

    tech_one = _provision(email="tec1@ejemplo.com", name="Tecnico Uno")
    tech_two = _provision(email="tec2@ejemplo.com", name="Tecnico Dos")
    client = _register_client()
    _login(tech_api, tech_one.email)
    directory = admin_api.get("/api/technicians")
    assert directory.status_code == 200
    items = json.loads(directory.text)
    assert {item["id"] for item in items} == {tech_one.id, tech_two.id}
    for item in items:
        assert set(item) == {"id", "name"}
        assert item["id"] != admin.id  # el administrador no es tecnico
        assert item["id"] != client["id"]  # el cliente tampoco
    assert {item["name"] for item in items} == {
        tech_one.name,
        tech_two.name,
    }
    # Sin correo, credenciales, rol ni hash en el cuerpo crudo (RF-35.4).
    for forbidden in (
        tech_one.email,
        tech_two.email,
        "password",
        "hash",
        "role",
    ):
        assert forbidden not in directory.text

    # Parametros desconocidos ignorados en silencio.
    ignored = admin_api.get("/api/technicians?page=2&q=xxx")
    assert ignored.status_code == 200
    assert {item["id"] for item in json.loads(ignored.text)} == {
        tech_one.id,
        tech_two.id,
    }

    # Cliente y tecnico: 404 uniforme, sin datos (RF-31, RF-38, RF-40).
    denied = [
        client_api.get("/api/technicians"),
        tech_api.get("/api/technicians"),
    ]
    assert [response.status_code for response in denied] == [404, 404]
    assert denied[0].text == denied[1].text == '{"detail":"technicians not found"}'
    for response in denied:
        assert response.status_code not in (400, 403)


# --- RF-36: tickets a cargo, orden, estados, reasignacion y HU-02 intacta ---


def test_sweep_tickets_assigned_to_me():
    requester = _register_client()
    tech_one = _provision_and_login(
        tech_api, email="tec1@ejemplo.com", name="Tecnico Uno"
    )
    tech_two = _provision(email="tec2@ejemplo.com", name="Tecnico Dos")
    admin = _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )
    assert admin.role == "administrador"

    first = _create_ticket(title="Primero")
    second = _create_ticket(title="Segundo")
    foreign = tech_api.post(
        "/api/tickets", json={"title": "Del tecnico", "description": "Propio"}
    )
    assert foreign.status_code == 201
    foreign_ticket = foreign.json()

    # Fechas distintas y controladas: el orden descendente es verificable.
    _set_created_at(first["id"], BASE)
    _set_created_at(second["id"], BASE + timedelta(minutes=1))

    assert _put_assignee(first["id"], {"assignee_id": tech_one.id}).status_code == 200
    assert _put_assignee(second["id"], {"assignee_id": tech_one.id}).status_code == 200
    # Cualquier estado, incluido `Cerrado`, sigue en la lista (RF-36).
    assert _put_status(second["id"], "Cerrado").status_code == 200

    mine = tech_api.get("/api/assignments/mine")
    assert mine.status_code == 200
    items = json.loads(mine.text)
    assert [item["id"] for item in items] == [second["id"], first["id"]]
    assert [item["status"] for item in items] == ["Cerrado", "Abierto"]
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert item["assignee"] == {"id": tech_one.id, "name": tech_one.name}

    # Parametros desconocidos ignorados sin alterar el resultado.
    ignored = tech_api.get("/api/assignments/mine?page=3&status=Abierto")
    assert ignored.status_code == 200
    assert [item["id"] for item in json.loads(ignored.text)] == [
        second["id"],
        first["id"],
    ]

    # Coleccion vacia para cliente, administrador y tecnico sin tickets.
    for target in (client_api, admin_api):
        response = target.get("/api/assignments/mine")
        assert response.status_code == 200
        assert response.json() == []
    assert tech_two is not None
    _login(tech_api, "tec2@ejemplo.com")
    assert tech_api.get("/api/assignments/mine").json() == []
    _login(tech_api, tech_one.email)

    # Reasignacion: desaparece de una lista y aparece en la otra (RF-36).
    assert _put_assignee(first["id"], {"assignee_id": tech_two.id}).status_code == 200
    assert [item["id"] for item in tech_api.get("/api/assignments/mine").json()] == [
        second["id"]
    ]
    _login(tech_api, "tec2@ejemplo.com")
    assert [item["id"] for item in tech_api.get("/api/assignments/mine").json()] == [
        first["id"]
    ]

    # HU-02 intacta: cada usuario sigue viendo solo lo que creo.
    client_listing = client_api.get("/api/tickets")
    assert {item["id"] for item in client_listing.json()} == {
        first["id"],
        second["id"],
    }
    assert client_listing.json()[0]["assignee"] is not None
    _login(tech_api, tech_one.email)
    tech_listing = tech_api.get("/api/tickets")
    assert [item["id"] for item in tech_listing.json()] == [foreign_ticket["id"]]
    assert foreign_ticket["requester_id"] == tech_one.id
    assert requester["id"] != tech_one.id


def test_sweep_assigned_list_ties_do_not_assert_order():
    """RF-36: dos tickets con la misma fecha no fijan orden entre si."""
    _register_client()
    tech = _provision_and_login(
        tech_api, email="tec1@ejemplo.com", name="Tecnico Uno"
    )
    _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )

    first = _create_ticket(title="Empate uno")
    second = _create_ticket(title="Empate dos")
    _set_created_at(first["id"], BASE)
    _set_created_at(second["id"], BASE)
    for ticket in (first, second):
        assert (
            _put_assignee(ticket["id"], {"assignee_id": tech.id}).status_code
            == 200
        )

    items = tech_api.get("/api/assignments/mine").json()
    assert len(items) == 2
    # Se compara como conjunto: no se afirma orden entre los empates.
    assert {item["id"] for item in items} == {first["id"], second["id"]}
    assert {item["created_at"] for item in items} == {BASE.isoformat()}


# --- RF-38, RF-39 y RF-40: tabla de precedencia con sesiones reales ---


def test_sweep_precedence_table_with_real_sessions():
    client = _register_client()
    tech = _provision_and_login(
        tech_api, email="tec1@ejemplo.com", name="Tecnico Uno"
    )
    admin = _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )

    open_ticket = _create_ticket(title="Abierto")
    closed_ticket = _create_ticket(title="Cerrado")
    foreign_ticket = tech_api.post(
        "/api/tickets", json={"title": "Ajeno", "description": "Del tecnico"}
    )
    assert foreign_ticket.status_code == 201
    foreign = foreign_ticket.json()

    # Ticket cerrado con tecnico vigente, para el 409 incluida la repeticion.
    assert (
        _put_assignee(closed_ticket["id"], {"assignee_id": tech.id}).status_code
        == 200
    )
    assert _put_status(closed_ticket["id"], "Cerrado").status_code == 200

    # Cuerpo 404 uniforme de HU-02, identico en todos los intentos.
    unified = client_api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert unified.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
    unified_text = unified.text

    valid_body = {"assignee_id": tech.id}
    ticket_ids = {
        "open": open_ticket["id"],
        "closed": closed_ticket["id"],
        "foreign": foreign["id"],
        "missing": str(uuid.uuid4()),
        "invalid": "no-es-uuid",
    }
    sessions = {
        "anon": anon_api,
        "client": client_api,
        "tech": tech_api,
        "admin": admin_api,
    }

    # (etiqueta, sesion, ticket, cuerpo, codigo esperado).
    rejections = [
        # 401: sin sesion valida, aunque el ticket o el cuerpo sean invalidos.
        ("anon-invalid", "anon", "invalid", MALFORMED_ASSIGNEE_BODY, 401),
        ("anon-open", "anon", "open", valid_body, 401),
        ("anon-closed", "anon", "closed", MALFORMED_ASSIGNEE_BODY, 401),
        ("anon-missing", "anon", "missing", NO_BODY, 401),
        # 404 uniforme: cliente y tecnico, sin revelar ticket ni contenido.
        ("client-own", "client", "open", valid_body, 404),
        ("client-foreign", "client", "foreign", valid_body, 404),
        ("client-closed", "client", "closed", MALFORMED_ASSIGNEE_BODY, 404),
        ("client-missing", "client", "missing", {}, 404),
        ("client-invalid", "client", "invalid", valid_body, 404),
        ("tech-own", "tech", "open", valid_body, 404),
        ("tech-foreign", "tech", "foreign", MALFORMED_ASSIGNEE_BODY, 404),
        ("tech-closed", "tech", "closed", {}, 404),
        ("tech-invalid", "tech", "invalid", NO_BODY, 404),
        # 404 del administrador: ticket inexistente o identificador invalido.
        ("admin-missing", "admin", "missing", valid_body, 404),
        ("admin-invalid", "admin", "invalid", MALFORMED_ASSIGNEE_BODY, 404),
        # 409: ticket cerrado, con cualquier entrada y al repetir el vigente.
        ("admin-closed", "admin", "closed", valid_body, 409),
        ("admin-closed-current", "admin", "closed", valid_body, 409),
        ("admin-closed-malformed", "admin", "closed", MALFORMED_ASSIGNEE_BODY, 409),
        ("admin-closed-empty", "admin", "closed", {}, 409),
        # 422: cuerpo ausente, nulo, no textual, con extra o JSON invalido.
        ("admin-open-empty", "admin", "open", {}, 422),
        ("admin-open-no-body", "admin", "open", NO_BODY, 422),
        ("admin-open-null", "admin", "open", {"assignee_id": None}, 422),
        ("admin-open-number", "admin", "open", {"assignee_id": 3}, 422),
        ("admin-open-boolean", "admin", "open", {"assignee_id": True}, 422),
        ("admin-open-list", "admin", "open", {"assignee_id": ["x"]}, 422),
        ("admin-open-object", "admin", "open", {"assignee_id": {}}, 422),
        (
            "admin-open-extra-actor",
            "admin",
            "open",
            {"assignee_id": tech.id, "actor_id": "otro"},
            422,
        ),
        (
            "admin-open-extra-date",
            "admin",
            "open",
            {"assignee_id": tech.id, "assigned_at": "2026-10-19T12:00:00+00:00"},
            422,
        ),
        ("admin-open-malformed", "admin", "open", MALFORMED_ASSIGNEE_BODY, 422),
        # 422 uniforme del tecnico: inexistente, no UUID, cliente o admin.
        (
            "invalid-tech-missing",
            "admin",
            "open",
            {"assignee_id": str(uuid.uuid4())},
            422,
        ),
        ("invalid-tech-format", "admin", "open", {"assignee_id": "no-es-uuid"}, 422),
        ("invalid-tech-client", "admin", "open", {"assignee_id": client["id"]}, 422),
        ("self-assign", "admin", "open", {"assignee_id": admin.id}, 422),
    ]

    seen = set()
    for label, origin, ticket_key, body, expected in rejections:
        before = _snapshot(open_ticket["id"], closed_ticket["id"], foreign["id"])
        response = _put_assignee(
            ticket_ids[ticket_key], body, target=sessions[origin]
        )
        seen.add(response.status_code)
        assert response.status_code == expected, (
            label,
            response.status_code,
            response.text,
        )
        assert response.status_code not in (400, 403)
        # Ningun rechazo modifica tickets ni genera registros.
        assert _snapshot(
            open_ticket["id"], closed_ticket["id"], foreign["id"]
        ) == before

        if expected == 404:
            assert response.text == unified_text, label
        elif expected == 409:
            assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}, label
        else:
            assert set(response.json()) == {"detail"}, label
            if label.startswith(("invalid-tech", "self-assign")):
                assert (
                    response.json()["detail"] == INVALID_TECHNICIAN_MESSAGE
                ), label

    # Camino valido: el administrador asigna un ticket que no creo y luego
    # repite el tecnico vigente (200 sin cambio ni registro).
    success = _put_assignee(
        open_ticket["id"], {"assignee_id": tech.id}, target=admin_api
    )
    seen.add(success.status_code)
    assert success.status_code == 200
    assert success.json()["assignee"] == {"id": tech.id, "name": tech.name}
    after_success = _snapshot(
        open_ticket["id"], closed_ticket["id"], foreign["id"]
    )
    assert after_success[1] == 2  # primera asignacion + la del ticket cerrado
    repeated = _put_assignee(
        open_ticket["id"], {"assignee_id": tech.id}, target=admin_api
    )
    seen.add(repeated.status_code)
    assert repeated.status_code == 200
    assert _snapshot(
        open_ticket["id"], closed_ticket["id"], foreign["id"]
    ) == after_success

    assert seen == {200, 401, 404, 409, 422}


# --- RF-31, RF-36 y RF-40: 401 > permiso en las consultas ---


def test_sweep_auth_precedence_across_endpoints():
    _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )
    _provision_and_login(
        tech_api, email="tec1@ejemplo.com", name="Tecnico Uno"
    )
    _register_client()

    # 401 sin sesion valida, tambien con parametros desconocidos.
    for path in ("/api/technicians?x=1", "/api/assignments/mine?x=1"):
        response = anon_api.get(path)
        assert response.status_code == 401
        assert response.status_code not in (400, 403)

    # Consulta de tecnicos: solo administrador (404 uniforme para el resto).
    client_denied = client_api.get("/api/technicians")
    tech_denied = tech_api.get("/api/technicians")
    assert client_denied.status_code == tech_denied.status_code == 404
    assert client_denied.text == tech_denied.text
    assert client_denied.status_code not in (400, 403)
    assert admin_api.get("/api/technicians").status_code == 200

    # Tickets a cargo: cualquier sesion valida; sin permiso adicional.
    for target in (client_api, tech_api, admin_api):
        response = target.get("/api/assignments/mine")
        assert response.status_code == 200
        assert response.status_code not in (400, 403)


# --- RF-40: ningun rechazo usa 400 ni 403 ---


def test_sweep_no_rejection_uses_400_or_403():
    _register_client()
    tech = _provision_and_login(
        tech_api, email="tec1@ejemplo.com", name="Tecnico Uno"
    )
    _provision_and_login(
        admin_api, role="administrador", email="admin@ejemplo.com", name="Admin"
    )
    open_ticket = _create_ticket()
    closed_ticket = _create_ticket()
    assert _put_status(closed_ticket["id"], "Cerrado").status_code == 200

    before = _snapshot(open_ticket["id"], closed_ticket["id"])
    ticket_count = get_ticket_repository().count()
    responses = [
        # Asignacion: 401, 404, 409 y 422, incluido JSON sintacticamente invalido.
        _put_assignee(open_ticket["id"], {"assignee_id": tech.id}, target=anon_api),
        _put_assignee("no-es-uuid", MALFORMED_ASSIGNEE_BODY, target=anon_api),
        _put_assignee(open_ticket["id"], {"assignee_id": tech.id}, target=client_api),
        _put_assignee(str(uuid.uuid4()), {"assignee_id": tech.id}),
        _put_assignee(open_ticket["id"], MALFORMED_ASSIGNEE_BODY, target=client_api),
        _put_assignee(closed_ticket["id"], {"assignee_id": tech.id}),
        _put_assignee(closed_ticket["id"], MALFORMED_ASSIGNEE_BODY),
        _put_assignee(open_ticket["id"], {}),
        _put_assignee(open_ticket["id"], {"assignee_id": "no-es-uuid"}),
        _put_assignee(open_ticket["id"], MALFORMED_ASSIGNEE_BODY),
        # Consultas: 401 sin sesion y 404 uniforme por permiso.
        anon_api.get("/api/technicians"),
        client_api.get("/api/technicians"),
        tech_api.get("/api/technicians"),
        anon_api.get("/api/assignments/mine"),
        # HU-02 sigue con sus codigos: 401 y 404 sin 400/403.
        anon_api.get(f"/api/tickets/{open_ticket['id']}"),
        client_api.get(f"/api/tickets/{uuid.uuid4()}"),
        # Creacion con tecnico: 422 de HU-02/RF-34, sin crear el ticket.
        client_api.post(
            "/api/tickets",
            json={
                "title": "Titulo",
                "description": "Descripcion",
                "assignee_id": tech.id,
            },
        ),
    ]

    codes = {response.status_code for response in responses}
    assert codes == {401, 404, 409, 422}
    for response in responses:
        assert response.status_code not in (400, 403)

    # Ningun rechazo ha mutado tickets ni generado registros.
    assert _snapshot(open_ticket["id"], closed_ticket["id"]) == before
    assert get_ticket_repository().count() == ticket_count
