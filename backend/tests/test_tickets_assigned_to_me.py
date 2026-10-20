"""T7 (HU-04) — Tickets a cargo (RF-36).

Mapa RF -> test:
- RF-36 (solo los tickets cuyo responsable es el usuario autenticado, en
  cualquier estado, orden descendente, composicion de resumen, coleccion
  vacia para cliente/administrador/tecnico sin tickets, parametros
  desconocidos ignorados, reasignacion entre listas y HU-02 intacto):
  todos los tests de este archivo.

La consulta es de solo lectura: no muta tickets ni registros. El resumen
usa la composicion uniforme de RF-35.1/RF-35.5: `assignee` es `null` sin
asignacion y `{id, name}` para el tecnico responsable, y las aserciones
fijan el conjunto exacto de claves.

Sesiones reales: tecnico y administrador por `provision_user` + login;
cliente por el registro de HU-01 + login. Un `TestClient` por rol cuando
coexisten sesiones (un cliente guarda una sola cookie).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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
from app.modules.identity.interface.dependencies import SESSION_COOKIE_NAME
from app.modules.identity.interface.technicians_contract import (
    get_technician_summary,
)
from app.modules.tickets.application.assign_ticket import assign_ticket
from app.modules.tickets.application.list_assigned_tickets import (
    list_assigned_tickets,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.assignment_log import (
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
# Composicion exacta del resumen (RF-15, RF-35.1, RF-36), con `assignee`.
SUMMARY_FIELDS = {"id", "title", "priority", "status", "assignee", "created_at"}
ASSIGNEE_FIELDS = {"id", "name"}

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
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def _register_client(name="Cliente Uno", email=None):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    response = api.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(email):
    """Cliente HTTP propio con sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    me = own.get("/api/auth/me")
    assert me.status_code == 200, me.text
    return own


def _ticket(assignee_id=None, assignee_name=None, **overrides):
    values = {
        "id": str(uuid.uuid4()),
        "title": "Titulo",
        "description": "Descripcion",
        "requester_id": str(uuid.uuid4()),
        "created_at": BASE,
    }
    if assignee_id is not None:
        values["assignee_id"] = assignee_id
        values["assignee_name"] = assignee_name or "Tecnico"
    values.update(overrides)
    return Ticket(**values)


def _ids(items):
    return [item["id"] for item in items]


# --- Repositorio: solo los asignados, cualquier estado y orden descendente ---


def test_list_by_assignee_returns_only_the_assignee_tickets():
    technician_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    repo = InMemoryTicketRepository()
    assigned = _ticket(
        assignee_id=technician_id,
        assignee_name="Tecnico Uno",
        status="Cerrado",
    )
    other = _ticket(assignee_id=other_id, assignee_name="Tecnico Dos")
    unassigned = _ticket()
    for ticket in (assigned, other, unassigned):
        repo.add(ticket)

    result = repo.list_by_assignee(technician_id)

    assert [ticket.id for ticket in result] == [assigned.id]
    assert result[0].status == "Cerrado"
    assert repo.list_by_assignee(str(uuid.uuid4())) == []


def test_list_by_assignee_is_ordered_by_created_at_descending():
    technician_id = str(uuid.uuid4())
    repo = InMemoryTicketRepository()
    # Se insertan desordenados: el repositorio ordena por fecha descendente.
    for minutes, status in ((5, "En progreso"), (10, "Cerrado"), (0, "Abierto")):
        repo.add(
            _ticket(
                assignee_id=technician_id,
                assignee_name="Tecnico Uno",
                status=status,
                created_at=BASE + timedelta(minutes=minutes),
            )
        )

    result = repo.list_by_assignee(technician_id)

    assert [ticket.created_at for ticket in result] == [
        BASE + timedelta(minutes=10),
        BASE + timedelta(minutes=5),
        BASE,
    ]
    assert [ticket.status for ticket in result] == [
        "Cerrado",
        "En progreso",
        "Abierto",
    ]


def test_list_by_assignee_does_not_fix_order_on_created_at_ties():
    technician_id = str(uuid.uuid4())
    repo = InMemoryTicketRepository()
    first = _ticket(
        assignee_id=technician_id,
        assignee_name="Tecnico Uno",
        created_at=BASE,
    )
    second = _ticket(
        assignee_id=technician_id,
        assignee_name="Tecnico Uno",
        created_at=BASE,
    )
    repo.add(first)
    repo.add(second)

    result = repo.list_by_assignee(technician_id)

    # RF-36: un empate de fecha no fija orden entre los tickets.
    assert {ticket.id for ticket in result} == {first.id, second.id}


# --- Caso de uso: consulta por el identificador de la sesion ---


def test_list_assigned_tickets_returns_only_the_authenticated_assignee():
    technician_id = str(uuid.uuid4())
    repo = InMemoryTicketRepository()
    first = _ticket(
        assignee_id=technician_id,
        assignee_name="Tecnico Uno",
        created_at=BASE,
    )
    second = _ticket(
        assignee_id=technician_id,
        assignee_name="Tecnico Uno",
        created_at=BASE + timedelta(minutes=1),
    )
    repo.add(first)
    repo.add(
        _ticket(
            assignee_id=str(uuid.uuid4()),
            assignee_name="Tecnico Dos",
            created_at=BASE + timedelta(minutes=2),
        )
    )
    repo.add(_ticket(created_at=BASE + timedelta(minutes=3)))
    repo.add(second)

    result = list_assigned_tickets(technician_id, repo)

    assert [ticket.id for ticket in result] == [second.id, first.id]


# --- API: 401 sin sesion valida ---


def test_assigned_to_me_without_session_returns_401():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")

    response = api.get("/api/assignments/mine")

    assert response.status_code == 401
    assert "detail" in response.json()


def test_assigned_to_me_with_invalid_session_cookie_returns_401():
    _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api.cookies.set(SESSION_COOKIE_NAME, "token-invalido")

    response = api.get("/api/assignments/mine")

    assert response.status_code == 401
    assert "detail" in response.json()


# --- API: solo los asignados, cualquier estado y resumen ---


def test_assigned_to_me_returns_only_tickets_assigned_to_the_session_user():
    technician = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    other = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    repo = get_ticket_repository()
    opened = _ticket(
        assignee_id=technician["id"],
        assignee_name=technician["name"],
        title="Abierto asignado",
        priority="Alta",
        status="Abierto",
        created_at=BASE,
    )
    closed = _ticket(
        assignee_id=technician["id"],
        assignee_name=technician["name"],
        title="Cerrado asignado",
        priority="Baja",
        status="Cerrado",
        created_at=BASE + timedelta(minutes=1),
    )
    from_other = _ticket(
        assignee_id=other["id"],
        assignee_name=other["name"],
        created_at=BASE + timedelta(minutes=2),
    )
    unassigned = _ticket(created_at=BASE + timedelta(minutes=3))
    for ticket in (opened, closed, from_other, unassigned):
        repo.add(ticket)

    response = _login(technician["email"]).get("/api/assignments/mine")

    assert response.status_code == 200
    items = response.json()
    assert _ids(items) == [closed.id, opened.id]
    assert {item["id"] for item in items} == {opened.id, closed.id}
    assert {item["status"] for item in items} == {"Abierto", "Cerrado"}
    assert {item["priority"] for item in items} == {"Alta", "Baja"}
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert set(item["assignee"]) == ASSIGNEE_FIELDS
        assert item["assignee"] == {
            "id": technician["id"],
            "name": technician["name"],
        }
        assert "description" not in item
        assert "requester_id" not in item
        assert technician["email"] not in response.text


def test_assigned_to_me_is_ordered_by_created_at_descending():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    repo = get_ticket_repository()
    tickets = []
    for minutes in (5, 10, 0):
        ticket = _ticket(
            assignee_id=technician["id"],
            assignee_name=technician["name"],
            created_at=BASE + timedelta(minutes=minutes),
        )
        repo.add(ticket)
        tickets.append(ticket)

    items = _login(technician["email"]).get("/api/assignments/mine").json()

    assert _ids(items) == [tickets[1].id, tickets[0].id, tickets[2].id]
    assert [item["created_at"] for item in items] == [
        (BASE + timedelta(minutes=10)).isoformat(),
        (BASE + timedelta(minutes=5)).isoformat(),
        BASE.isoformat(),
    ]
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert item["assignee"] == {
            "id": technician["id"],
            "name": technician["name"],
        }


# --- API: coleccion vacia para cliente, administrador y tecnico sin tickets ---


def test_assigned_to_me_returns_empty_for_client_and_administrator():
    client_user = _register_client("Cliente Uno", "cliente@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    repo = get_ticket_repository()
    # Tickets del cliente y del administrador, sin asignacion: solo los
    # tecnicos pueden ser responsables, asi que su consulta es vacia.
    repo.add(_ticket(requester_id=client_user["id"]))
    repo.add(_ticket(requester_id=admin["id"]))
    repo.add(
        _ticket(
            assignee_id=technician["id"],
            assignee_name=technician["name"],
        )
    )

    for email in (client_user["email"], admin["email"]):
        response = _login(email).get("/api/assignments/mine")
        assert response.status_code == 200
        assert response.json() == []


def test_assigned_to_me_returns_empty_for_technician_without_tickets():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    other = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    get_ticket_repository().add(
        _ticket(assignee_id=other["id"], assignee_name=other["name"])
    )

    response = _login(technician["email"]).get("/api/assignments/mine")

    assert response.status_code == 200
    assert response.json() == []


# --- API: parametros desconocidos ignorados ---


def test_assigned_to_me_ignores_unknown_query_parameters():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    get_ticket_repository().add(
        _ticket(
            assignee_id=technician["id"],
            assignee_name=technician["name"],
        )
    )
    technician_client = _login(technician["email"])

    plain = technician_client.get("/api/assignments/mine")
    noisy = technician_client.get(
        "/api/assignments/mine",
        params={
            "status": "Abierto",
            "assignee_id": str(uuid.uuid4()),
            "page": 2,
            "limit": 1,
        },
    )

    assert plain.status_code == 200
    assert noisy.status_code == 200
    assert noisy.json() == plain.json()
    assert len(noisy.json()) == 1


def test_assigned_to_me_operation_declares_no_parameters():
    operation = app.openapi()["paths"]["/api/assignments/mine"]["get"]

    assert operation.get("parameters", []) == []


# --- RF-36: reasignacion entre listas ---


def test_reassignment_moves_the_ticket_between_technicians_lists():
    first = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    second = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket(created_at=BASE)
    get_ticket_repository().add(ticket)
    first_client = _login(first["email"])
    second_client = _login(second["email"])

    assign_ticket(
        ticket,
        first["id"],
        admin["id"],
        get_technician_summary,
        get_assignment_log(),
        now=BASE,
    )

    [first_item] = first_client.get("/api/assignments/mine").json()
    assert first_item["id"] == ticket.id
    assert set(first_item) == SUMMARY_FIELDS
    assert first_item["assignee"] == {
        "id": first["id"],
        "name": first["name"],
    }
    assert second_client.get("/api/assignments/mine").json() == []

    assign_ticket(
        ticket,
        second["id"],
        admin["id"],
        get_technician_summary,
        get_assignment_log(),
        now=BASE + timedelta(minutes=1),
    )

    assert first_client.get("/api/assignments/mine").json() == []
    [second_item] = second_client.get("/api/assignments/mine").json()
    assert second_item["id"] == ticket.id
    assert set(second_item) == SUMMARY_FIELDS
    assert second_item["assignee"] == {
        "id": second["id"],
        "name": second["name"],
    }
    assert get_assignment_log().count() == 2


# --- RF-36: el listado y el detalle de HU-02 no cambian ---


def test_assigned_tickets_do_not_change_the_hu02_list_or_detail():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    requester = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician_client = _login(technician["email"])
    own = technician_client.post(
        "/api/tickets",
        json={"title": "Propio", "description": "Creado por el tecnico"},
    )
    assert own.status_code == 201, own.text
    assigned = _ticket(
        requester_id=requester["id"],
        assignee_id=technician["id"],
        assignee_name=technician["name"],
    )
    get_ticket_repository().add(assigned)

    listed = technician_client.get("/api/tickets")
    detail = technician_client.get(f"/api/tickets/{assigned.id}")

    assert listed.status_code == 200
    assert _ids(listed.json()) == [own.json()["id"]]
    assert detail.status_code == 404
    # El ticket asignado si aparece en la consulta a cargo.
    assert _ids(
        technician_client.get("/api/assignments/mine").json()
    ) == [assigned.id]


# --- RF-36: consulta de solo lectura ---


def test_assigned_to_me_does_not_mutate_tickets_or_logs():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    ticket = _ticket(
        title="Intacto",
        description="Sin cambios",
        priority="Media",
        status="En progreso",
        created_at=BASE,
    )
    get_ticket_repository().add(ticket)
    assign_ticket(
        ticket,
        technician["id"],
        admin["id"],
        get_technician_summary,
        get_assignment_log(),
        now=BASE,
    )
    repository_count = get_ticket_repository().count()
    assignments_count = get_assignment_log().count()
    modifications_count = get_ticket_modification_log().count()

    response = _login(technician["email"]).get("/api/assignments/mine")

    assert response.status_code == 200
    assert get_ticket_repository().count() == repository_count
    assert get_assignment_log().count() == assignments_count
    assert get_ticket_modification_log().count() == modifications_count
    assert ticket.title == "Intacto"
    assert ticket.description == "Sin cambios"
    assert ticket.priority == "Media"
    assert ticket.status == "En progreso"
    assert ticket.created_at == BASE
    assert ticket.assignee_id == technician["id"]
    assert ticket.assignee_name == technician["name"]
