"""T6 (HU-04) — Caso de uso `assign_ticket` (RF-32, RF-33, RF-34, RF-37, RF-39.3).

Mapa RF -> test:
- RF-32 (primera asignacion a un tecnico registrado, conservando la
  informacion actualizada del ticket):
  `test_first_assignment_sets_the_resolved_technician`,
  `test_first_assignment_keeps_priority_status_creation_and_requester`,
  `test_first_assignment_mutates_the_ticket_stored_in_the_repository`,
  `test_ticket_whose_requester_is_the_technician_can_be_assigned`.
- RF-33 (reasignacion con el anterior en el registro; repetir el vigente
  no cambia ni registra):
  `test_reassignment_replaces_the_technician_and_records_the_previous`,
  `test_successive_reassignments_accumulate_in_registration_order`,
  `test_repeating_the_current_technician_does_not_change_or_record`,
  `test_repeating_the_current_technician_after_reassignment_is_a_noop`.
- RF-34 (el ticket sigue sin asignacion hasta que se asigna; asignar no
  toca el estado ni la prioridad):
  `test_first_assignment_keeps_priority_status_creation_and_requester`,
  `test_invalid_technician_does_not_mutate_an_unassigned_ticket`.
- RF-37 (registro con ticket, anterior vacio o vigente, nuevo, actor de
  la sesion y fecha del sistema; solo cambios efectivos; fuera del
  ticket):
  todos los tests de registro, en particular
  `test_first_assignment_record_keeps_all_assignment_data`,
  `test_default_assigned_at_uses_the_system_time_in_utc`,
  `test_returned_ticket_does_not_include_the_assignment_record`,
  `test_assignment_does_not_touch_the_hu03_modification_log`,
  `test_http_two_admin_sessions_record_each_actor_on_reassignment`.
- RF-39.3 (tecnico inexistente, no UUID, cliente o administrador -> 422
  uniforme sin revelar si existe, sin mutar ni registrar):
  `test_nonexistent_technician_is_rejected_without_change_or_record`,
  `test_non_uuid_or_non_text_technician_is_rejected_without_resolving`,
  `test_client_and_administrator_are_not_valid_technicians`,
  `test_invalid_technician_does_not_mutate_an_unassigned_ticket`,
  `test_invalid_technician_does_not_mutate_an_assigned_ticket`,
  `test_validation_error_message_is_uniform_and_fixed`.

El ticket ya llega resuelto y autorizado por `get_assignable_ticket`
(T5), que rechaza permisos, formato/existencia y tickets `Cerrado`
(409); `assign_ticket` no duplica esas reglas. El tecnico se resuelve con
el contrato de `identity` inyectado (`get_technician_summary`), nunca con
sus estructuras internas (D10). Desde T8 la seccion HTTP prueba
`PUT /api/tickets/{ticket_id}/assignee`: 200 con el ticket actualizado,
reasignacion, repeticion sin registro, tecnico invalido uniforme y cuerpo
estricto; la tabla de precedencia vive en `test_tickets_assign_access.py`.
"""

import dataclasses
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
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
from app.modules.tickets.application.create_ticket import TicketValidationError
from app.modules.tickets.domain.entities import (
    OPEN_STATUS,
    AssignmentRecord,
    Ticket,
)
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

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
PASSWORD = "Secreta123"
ASSIGNMENT_RECORD_FIELDS = {
    "ticket_id",
    "previous_assignee_id",
    "new_assignee_id",
    "actor_id",
    "assigned_at",
}

api = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_assignment_log().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_assignment_log().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()


def _provision(role="tecnico", name="Tecnico Uno", email=None):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    return provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )


def _register_client(name="Cliente Uno", email="cliente@ejemplo.com"):
    response = api.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201
    return response.json()


def _ticket(**overrides) -> Ticket:
    values = {
        "id": str(uuid.uuid4()),
        "title": "Titulo",
        "description": "Descripcion",
        "requester_id": str(uuid.uuid4()),
        "created_at": NOW,
    }
    values.update(overrides)
    return Ticket(**values)


class _SpyResolver:
    """Envuelve el contrato de `identity` y registra las resoluciones."""

    def __init__(self) -> None:
        self.calls: list[object] = []

    def __call__(self, technician_id: object):
        self.calls.append(technician_id)
        return get_technician_summary(technician_id)


# --- Helpers de la seccion HTTP (T8) ---

JSON_HEADERS = {"Content-Type": "application/json"}
# Cuerpo crudo con JSON sintacticamente invalido (se envia con `content=`).
MALFORMED_ASSIGNEE_BODY = b'{"assignee_id": '
# Centinela para enviar la peticion sin cuerpo.
NO_BODY = object()


def _login(email):
    """Cliente HTTP propio con sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert own.get("/api/auth/me").status_code == 200
    return own


def _client_session(email="cliente@ejemplo.com", name="Cliente Uno"):
    target = TestClient(app)
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
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200, logged.text
    return target, registered.json()


def _admin_session(email="admin@ejemplo.com", name="Admin Uno"):
    admin = _provision("administrador", name, email)
    return _login(email), admin


def _create_ticket(target, title="Titulo", description="Descripcion"):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201, created.text
    return created.json()


def _put_assignee(ticket_id, body=NO_BODY, target=None):
    assert target is not None
    url = f"/api/tickets/{ticket_id}/assignee"
    if body is NO_BODY:
        return target.put(url)
    if isinstance(body, bytes):
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _stored(ticket_id):
    stored = get_ticket_repository().find_by_id(ticket_id)
    assert stored is not None
    return stored


# --- RF-32: primera asignacion ---


def test_first_assignment_sets_the_resolved_technician():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    actor = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    returned = assign_ticket(
        ticket,
        technician.id,
        actor.id,
        get_technician_summary,
        log,
        now=NOW,
    )

    assert returned is ticket
    assert ticket.assignee_id == technician.id
    assert ticket.assignee_name == "Ana Torres"
    assert log.count() == 1


def test_first_assignment_record_keeps_all_assignment_data():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    actor = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket,
        technician.id,
        actor.id,
        get_technician_summary,
        log,
        now=NOW,
    )

    [record] = log.list_by_ticket(ticket.id)
    assert type(record) is AssignmentRecord
    assert record.ticket_id == ticket.id
    assert record.previous_assignee_id is None
    assert record.new_assignee_id == technician.id
    assert record.actor_id == actor.id
    assert record.assigned_at == NOW


def test_first_assignment_keeps_priority_status_creation_and_requester():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    requester_id = str(uuid.uuid4())
    ticket = _ticket(
        title="Impresora rota",
        description="No imprime",
        priority="Alta",
        status="En progreso",
        requester_id=requester_id,
    )
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket,
        technician.id,
        "u-admin",
        get_technician_summary,
        log,
        now=NOW,
    )

    assert ticket.title == "Impresora rota"
    assert ticket.description == "No imprime"
    assert ticket.priority == "Alta"
    assert ticket.status == "En progreso"
    assert ticket.created_at == NOW
    assert ticket.requester_id == requester_id


def test_first_assignment_mutates_the_ticket_stored_in_the_repository():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket,
        technician.id,
        "u-admin",
        get_technician_summary,
        log,
        now=NOW,
    )

    stored = repo.find_by_id(ticket.id)
    assert stored is ticket
    assert stored.assignee_id == technician.id
    assert stored.assignee_name == "Ana Torres"


def test_ticket_whose_requester_is_the_technician_can_be_assigned():
    """RF-32: no hay restriccion por solicitante."""
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket(requester_id=technician.id)
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket,
        technician.id,
        "u-admin",
        get_technician_summary,
        log,
        now=NOW,
    )

    assert ticket.assignee_id == technician.id
    assert log.count() == 1


# --- RF-33: reasignacion ---


def test_reassignment_replaces_the_technician_and_records_the_previous():
    first = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    second = _provision("tecnico", "Luis Perez", "luis@ejemplo.com")
    actor = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket, first.id, actor.id, get_technician_summary, log, now=NOW
    )
    assign_ticket(
        ticket, second.id, actor.id, get_technician_summary, log, now=NOW
    )

    assert ticket.assignee_id == second.id
    assert ticket.assignee_name == "Luis Perez"
    records = log.list_by_ticket(ticket.id)
    assert [(r.previous_assignee_id, r.new_assignee_id) for r in records] == [
        (None, first.id),
        (first.id, second.id),
    ]
    assert log.count() == 2


def test_successive_reassignments_accumulate_in_registration_order():
    technicians = [
        _provision("tecnico", f"Tecnico {index}", f"tec{index}@ejemplo.com")
        for index in range(1, 4)
    ]
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    for technician in technicians:
        assign_ticket(
            ticket,
            technician.id,
            "u-admin",
            get_technician_summary,
            log,
            now=NOW,
        )

    records = log.list_by_ticket(ticket.id)
    assert [(r.previous_assignee_id, r.new_assignee_id) for r in records] == [
        (None, technicians[0].id),
        (technicians[0].id, technicians[1].id),
        (technicians[1].id, technicians[2].id),
    ]
    assert ticket.assignee_id == technicians[2].id
    assert log.count() == 3


def test_repeating_the_current_technician_does_not_change_or_record():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log, now=NOW
    )
    returned = assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log, now=NOW
    )

    assert returned is ticket
    assert ticket.assignee_id == technician.id
    assert ticket.assignee_name == "Ana Torres"
    assert log.count() == 1
    assert len(log.list_by_ticket(ticket.id)) == 1


def test_repeating_the_current_technician_after_reassignment_is_a_noop():
    first = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    second = _provision("tecnico", "Luis Perez", "luis@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket, first.id, "u-admin", get_technician_summary, log, now=NOW
    )
    assign_ticket(
        ticket, second.id, "u-admin", get_technician_summary, log, now=NOW
    )
    assign_ticket(
        ticket, second.id, "u-admin", get_technician_summary, log, now=NOW
    )

    assert ticket.assignee_id == second.id
    assert log.count() == 2


# --- RF-37: fecha del sistema, registro fuera del ticket, independencia ---


def test_default_assigned_at_uses_the_system_time_in_utc():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    before = datetime.now(timezone.utc)
    assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log
    )
    after = datetime.now(timezone.utc)

    [record] = log.list_by_ticket(ticket.id)
    assert record.assigned_at.tzinfo is not None
    assert record.assigned_at.utcoffset().total_seconds() == 0
    assert before <= record.assigned_at <= after


def test_returned_ticket_does_not_include_the_assignment_record():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    returned = assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log, now=NOW
    )

    # El registro vive solo en el log: el ticket devuelto no lo incorpora.
    assert returned is ticket
    field_names = {field.name for field in dataclasses.fields(Ticket)}
    assert field_names.isdisjoint(ASSIGNMENT_RECORD_FIELDS)
    for name in ASSIGNMENT_RECORD_FIELDS | {"assignments"}:
        assert not hasattr(returned, name)


def test_assignment_does_not_touch_the_hu03_modification_log():
    """RF-37: el registro de asignaciones es independiente del de HU-03."""
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log, now=NOW
    )

    assert get_ticket_modification_log().count() == 0
    assert log.count() == 1


# --- RF-39.3: tecnico invalido con 422 uniforme, sin mutar ni registrar ---


def test_nonexistent_technician_is_rejected_without_change_or_record():
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    with pytest.raises(TicketValidationError) as exc:
        assign_ticket(
            ticket,
            str(uuid.uuid4()),
            "u-admin",
            get_technician_summary,
            log,
            now=NOW,
        )

    assert str(exc.value) == INVALID_TECHNICIAN_MESSAGE
    assert ticket.assignee_id is None
    assert ticket.assignee_name is None
    assert log.count() == 0


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "no-es-uuid",
        "123",
        "123e4567-e89b-12d3-a456-42661417400",
        None,
        123,
        1.5,
        True,
        False,
        ["id"],
        {"id": "x"},
        b"id",
        object(),
    ],
)
def test_non_uuid_or_non_text_technician_is_rejected_without_resolving(raw):
    ticket = _ticket()
    log = InMemoryAssignmentLog()
    resolver = _SpyResolver()

    with pytest.raises(TicketValidationError) as exc:
        assign_ticket(
            ticket, raw, "u-admin", resolver, log, now=NOW
        )

    # D10: el formato UUID lo valida `tickets`; el contrato de `identity`
    # no llega a consultarse y no se revela si el usuario existe.
    assert resolver.calls == []
    assert str(exc.value) == INVALID_TECHNICIAN_MESSAGE
    assert ticket.assignee_id is None
    assert ticket.assignee_name is None
    assert log.count() == 0


@pytest.mark.parametrize("role", ["cliente", "administrador"])
def test_client_and_administrator_are_not_valid_technicians(role):
    if role == "cliente":
        user_id = _register_client()["id"]
    else:
        user_id = _provision(
            "administrador", "Admin Uno", "admin@ejemplo.com"
        ).id

    ticket = _ticket()
    log = InMemoryAssignmentLog()

    with pytest.raises(TicketValidationError) as exc:
        assign_ticket(
            ticket, user_id, "u-admin", get_technician_summary, log, now=NOW
        )

    assert str(exc.value) == INVALID_TECHNICIAN_MESSAGE
    assert ticket.assignee_id is None
    assert ticket.assignee_name is None
    assert log.count() == 0


def test_invalid_technician_does_not_mutate_an_unassigned_ticket():
    ticket = _ticket(priority="Media", status=OPEN_STATUS)
    log = InMemoryAssignmentLog()

    with pytest.raises(TicketValidationError):
        assign_ticket(
            ticket,
            "no-es-uuid",
            "u-admin",
            get_technician_summary,
            log,
            now=NOW,
        )

    assert ticket.assignee_id is None
    assert ticket.assignee_name is None
    assert ticket.priority == "Media"
    assert ticket.status == OPEN_STATUS
    assert log.count() == 0


def test_invalid_technician_does_not_mutate_an_assigned_ticket():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()
    assign_ticket(
        ticket, technician.id, "u-admin", get_technician_summary, log, now=NOW
    )

    with pytest.raises(TicketValidationError):
        assign_ticket(
            ticket,
            str(uuid.uuid4()),
            "u-admin",
            get_technician_summary,
            log,
            now=NOW,
        )

    assert ticket.assignee_id == technician.id
    assert ticket.assignee_name == "Ana Torres"
    assert log.count() == 1


def test_validation_error_message_is_uniform_and_fixed():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket()
    log = InMemoryAssignmentLog()

    candidates = [
        "no-es-uuid",
        "",
        str(uuid.uuid4()),
        admin.id,
        None,
        123,
    ]
    messages = []
    for candidate in candidates:
        with pytest.raises(TicketValidationError) as exc:
            assign_ticket(
                ticket,
                candidate,
                "u-admin",
                get_technician_summary,
                log,
                now=NOW,
            )
        messages.append(str(exc.value))

    assert messages == [INVALID_TECHNICIAN_MESSAGE] * len(candidates)
    assert INVALID_TECHNICIAN_MESSAGE == "assignee is not a valid technician"
    assert ticket.assignee_id is None
    assert log.count() == 0


# --- T8 / RF-32, RF-33: API real de asignacion y reasignacion ---


def test_http_first_assignment_returns_the_complete_updated_ticket():
    client_api, client = _client_session()
    created = _create_ticket(
        client_api, title="Impresora rota", description="No imprime"
    )
    admin_api, admin = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")

    # La asignacion no altera prioridad, estado, creacion ni solicitante.
    assert (
        admin_api.put(
            f"/api/tickets/{created['id']}/priority",
            json={"priority": "Alta"},
        ).status_code
        == 200
    )
    assert (
        admin_api.put(
            f"/api/tickets/{created['id']}/status",
            json={"status": "En progreso"},
        ).status_code
        == 200
    )
    modifications_before = get_ticket_modification_log().count()
    assert modifications_before == 2

    response = _put_assignee(
        created["id"], {"assignee_id": technician.id}, target=admin_api
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["title"] == "Impresora rota"
    assert body["description"] == "No imprime"
    assert body["priority"] == "Alta"
    assert body["status"] == "En progreso"
    assert body["created_at"] == created["created_at"]
    assert body["requester_id"] == client["id"]

    stored = _stored(created["id"])
    assert stored.assignee_id == technician.id
    assert stored.assignee_name == "Ana Torres"
    assert stored.priority == "Alta"
    assert stored.status == "En progreso"
    assert stored.requester_id == client["id"]

    [record] = get_assignment_log().list_by_ticket(created["id"])
    assert record.previous_assignee_id is None
    assert record.new_assignee_id == technician.id
    assert record.actor_id == admin.id
    assert get_ticket_modification_log().count() == modifications_before

    # Ninguna respuesta expone el registro de asignaciones (RF-37).
    for forbidden in (
        "assignments",
        "previous_assignee_id",
        "new_assignee_id",
        "assigned_at",
    ):
        assert forbidden not in body


def test_http_reassignment_returns_the_new_technician_and_records_previous():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, admin = _admin_session()
    first = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    second = _provision("tecnico", "Luis Perez", "luis@ejemplo.com")

    assert (
        _put_assignee(
            created["id"], {"assignee_id": first.id}, target=admin_api
        ).status_code
        == 200
    )
    response = _put_assignee(
        created["id"], {"assignee_id": second.id}, target=admin_api
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    stored = _stored(created["id"])
    assert stored.assignee_id == second.id
    assert stored.assignee_name == "Luis Perez"

    records = get_assignment_log().list_by_ticket(created["id"])
    assert [(r.previous_assignee_id, r.new_assignee_id) for r in records] == [
        (None, first.id),
        (first.id, second.id),
    ]
    assert [record.actor_id for record in records] == [admin.id, admin.id]


def test_http_two_admin_sessions_record_each_actor_on_reassignment():
    """RF-37: cada sesion real de administrador deja su propio `actor_id`."""
    admin_a_api, admin_a = _admin_session("admin.a@ejemplo.com", "Admin A")
    admin_b_api, admin_b = _admin_session("admin.b@ejemplo.com", "Admin B")
    first = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    second = _provision("tecnico", "Luis Perez", "luis@ejemplo.com")
    created = _create_ticket(admin_a_api, title="Impresora rota")

    first_response = _put_assignee(
        created["id"], {"assignee_id": first.id}, target=admin_a_api
    )
    second_response = _put_assignee(
        created["id"], {"assignee_id": second.id}, target=admin_b_api
    )

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["assignee"] == {
        "id": first.id,
        "name": first.name,
    }
    assert second_response.json()["assignee"] == {
        "id": second.id,
        "name": second.name,
    }
    stored = _stored(created["id"])
    assert stored.assignee_id == second.id
    assert stored.assignee_name == second.name

    records = get_assignment_log().list_by_ticket(created["id"])
    assert len(records) == 2
    # Se localizan por actor: los `assigned_at` podrian empatar y el empate
    # no fija orden entre los registros (RF-37).
    by_actor = {record.actor_id: record for record in records}
    assert set(by_actor) == {admin_a.id, admin_b.id}

    first_record = by_actor[admin_a.id]
    assert first_record.ticket_id == created["id"]
    assert first_record.previous_assignee_id is None
    assert first_record.new_assignee_id == first.id

    second_record = by_actor[admin_b.id]
    assert second_record.ticket_id == created["id"]
    assert second_record.previous_assignee_id == first.id
    assert second_record.new_assignee_id == second.id

    # Orden de alta del log (no se ordena por fecha).
    assert records == [first_record, second_record]


def test_http_repeating_the_current_technician_is_200_without_record():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")

    assert (
        _put_assignee(
            created["id"], {"assignee_id": technician.id}, target=admin_api
        ).status_code
        == 200
    )
    before = _stored(created["id"])
    before_state = (before.assignee_id, before.assignee_name)

    response = _put_assignee(
        created["id"], {"assignee_id": technician.id}, target=admin_api
    )

    assert response.status_code == 200
    after = _stored(created["id"])
    assert (after.assignee_id, after.assignee_name) == before_state
    assert get_assignment_log().count() == 1


# --- T8 / RF-39.3: tecnico invalido -> 422 uniforme en la API ---


@pytest.mark.parametrize(
    "candidate", ["nonexistent", "non_uuid", "client", "administrator"]
)
def test_http_invalid_technician_returns_the_uniform_422(candidate):
    client_api, client = _client_session()
    created = _create_ticket(client_api)
    admin_api, admin = _admin_session()

    value = {
        "nonexistent": str(uuid.uuid4()),
        "non_uuid": "no-es-uuid",
        "client": client["id"],
        "administrator": admin.id,
    }[candidate]

    response = _put_assignee(
        created["id"], {"assignee_id": value}, target=admin_api
    )

    assert response.status_code == 422
    assert response.status_code not in (400, 403, 404, 409)
    assert response.json() == {"detail": INVALID_TECHNICIAN_MESSAGE}
    stored = _stored(created["id"])
    assert stored.assignee_id is None
    assert stored.assignee_name is None
    assert get_assignment_log().count() == 0


def test_http_invalid_technician_does_not_mutate_an_assigned_ticket():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    current = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")

    assert (
        _put_assignee(
            created["id"], {"assignee_id": current.id}, target=admin_api
        ).status_code
        == 200
    )
    before = _stored(created["id"])
    before_state = (before.assignee_id, before.assignee_name)

    response = _put_assignee(
        created["id"], {"assignee_id": str(uuid.uuid4())}, target=admin_api
    )

    assert response.status_code == 422
    assert response.json() == {"detail": INVALID_TECHNICIAN_MESSAGE}
    after = _stored(created["id"])
    assert (after.assignee_id, after.assignee_name) == before_state
    assert get_assignment_log().count() == 1


# --- T8 / RF-39.1, RF-39.2: cuerpo mono-campo estricto ---


def _invalid_bodies(technician_id):
    return (
        {},
        {"assignee_id": None},
        {"assignee_id": 3},
        {"assignee_id": 1.5},
        {"assignee_id": True},
        {"assignee_id": ["id"]},
        {"assignee_id": {"id": "x"}},
        {"assignee_id": ""},
        {"assignee_id": technician_id, "actor_id": "otro-usuario"},
        {"assignee_id": technician_id, "assigned_at": "2026-10-19T12:00:00Z"},
        {"assignee_id": technician_id, "previous_assignee_id": None},
        {"assignee_id": technician_id, "new_assignee_id": technician_id},
        {"assignee_id": technician_id, "status": "Cerrado"},
        {"assignee_id": technician_id, "priority": "Alta"},
        {"assignee_id": technician_id, "ticket_id": str(uuid.uuid4())},
    )


@pytest.mark.parametrize("body", [NO_BODY, MALFORMED_ASSIGNEE_BODY])
def test_http_absent_or_malformed_body_returns_422_without_change(body):
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()

    response = _put_assignee(created["id"], body, target=admin_api)

    assert response.status_code == 422
    assert response.status_code not in (400, 403, 404, 409)
    assert set(response.json()) == {"detail"}
    stored = _stored(created["id"])
    assert stored.assignee_id is None
    assert stored.assignee_name is None
    assert get_assignment_log().count() == 0


@pytest.mark.parametrize("body", _invalid_bodies("technician"))
def test_http_strict_body_is_rejected_with_422_without_change(body):
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")

    if isinstance(body, dict):
        body = {
            key: technician.id if value == "technician" else value
            for key, value in body.items()
        }

    response = _put_assignee(created["id"], body, target=admin_api)

    assert response.status_code == 422
    assert response.status_code not in (400, 403, 404, 409)
    assert set(response.json()) == {"detail"}
    stored = _stored(created["id"])
    assert stored.assignee_id is None
    assert stored.assignee_name is None
    assert get_assignment_log().count() == 0
