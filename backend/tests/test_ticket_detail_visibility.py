"""HU-06 T2 — visibilidad del detalle de un ticket por rol (RF-51, RF-52,
RF-53, RF-56, RF-57).

Verifica sobre `GET /api/tickets/{ticket_id}`:

- RF-51: un usuario con rol de gestion (`tecnico` o `administrador`) abre
  el detalle de cualquier ticket existente, este asignado o no y lo haya
  creado quien lo haya creado.
- RF-52: un cliente solo abre el detalle de los tickets que creo; un
  ticket ajeno, inexistente o con identificador invalido devuelve el
  mismo 404 uniforme de HU-02, sin datos del ticket.
- RF-53: `requester` expone `{id, name, email}` del solicitante, o `null`
  cuando el usuario no se puede resolver, sin romper el resto del detalle.
- RF-56: para el personal, ticket inexistente e identificador invalido
  comparten el mismo 404 (`{"detail": "ticket not found"}`).
- RF-57: sin sesion valida la respuesta es 401 antes de resolver el
  recurso, incluso con identificador invalido o inexistente.

Cada usuario usa su propio `TestClient` con sesion real (login), porque un
cliente HTTP guarda una unica cookie de sesion.
"""

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
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": "ticket not found"}
DETAIL_FIELDS = {
    "id",
    "title",
    "description",
    "priority",
    "status",
    "assignee",
    "requester",
    "sla",
    "created_at",
    "resolved_at",
    "requester_id",
}
REQUESTER_FIELDS = {"id", "name", "email"}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()


def _provision(role: str, name: str, email: str) -> dict[str, str]:
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


def _register_client(name: str, email: str) -> dict[str, str]:
    response = TestClient(app).post(
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


def _login(email: str) -> TestClient:
    """Cliente HTTP propio con la sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _create_ticket(api: TestClient, title="Titulo", description="Descripcion"):
    response = api.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _foreign_ticket(requester_id, title="Ticket ajeno", description="ajeno"):
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        requester_id=requester_id,
        created_at=datetime.now(timezone.utc),
    )
    get_ticket_repository().add(ticket)
    return ticket


# --- RF-52: el cliente conserva el aislamiento de HU-02 ---


def test_client_opens_the_detail_of_its_own_ticket():
    user = _register_client("Ana Perez", "ana@ejemplo.com")
    api = _login(user["email"])
    created = _create_ticket(api)

    response = api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["id"] == created["id"]
    assert body["requester"] == {
        "id": user["id"],
        "name": "Ana Perez",
        "email": "ana@ejemplo.com",
    }


def test_client_gets_the_same_404_for_foreign_unknown_or_invalid_ticket():
    owner = _register_client("Dueno Uno", "dueno@ejemplo.com")
    intruder = _register_client("Otro Dos", "otro@ejemplo.com")
    owner_api = _login(owner["email"])
    created = _create_ticket(
        owner_api, title="Secreto del dueno", description="No visible"
    )
    intruder_api = _login(intruder["email"])

    responses = [
        intruder_api.get(f"/api/tickets/{created['id']}"),
        intruder_api.get(f"/api/tickets/{uuid.uuid4()}"),
        intruder_api.get("/api/tickets/not-a-uuid"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY
        # Ningun dato del ticket ajeno se filtra en el error.
        raw = response.text
        assert "Secreto del dueno" not in raw
        assert "No visible" not in raw
        assert owner["email"] not in raw


# --- RF-51: tecnicos y administradores abren cualquier ticket ---


def test_technician_opens_an_unassigned_ticket_created_by_a_client():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = technician_api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["assignee"] is None  # no asignado: la visibilidad no lo exige
    assert body["requester"] == {
        "id": requester["id"],
        "name": "Cliente Uno",
        "email": "cliente@ejemplo.com",
    }


def test_technician_opens_a_ticket_assigned_to_another_technician():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    first = _provision("tecnico", "Tecnico Uno", "tec1@ejemplo.com")
    second = _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])
    assigned = admin_api.put(
        f"/api/tickets/{created['id']}/assignee",
        json={"assignee_id": first["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    second_api = _login(second["email"])

    response = second_api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["assignee"] == {"id": first["id"], "name": "Tecnico Uno"}


def test_administrator_opens_any_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    response = admin_api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


# --- RF-56: 404 uniforme para el personal ---


@pytest.mark.parametrize(
    "role,email,name",
    [
        ("tecnico", "tec@ejemplo.com", "Tecnico Uno"),
        ("administrador", "admin@ejemplo.com", "Admin Uno"),
    ],
)
def test_staff_gets_uniform_404_for_invalid_or_unknown_identifier(
    role, email, name
):
    _provision("tecnico", "Tecnico Dos", "tec2@ejemplo.com")
    actor = _provision(role, name, email)
    api = _login(actor["email"])

    for candidate in ("not-a-uuid", str(uuid.uuid4())):
        response = api.get(f"/api/tickets/{candidate}")
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


# --- RF-57: 401 antes que 404 ---


def test_missing_session_returns_401_before_resolving_the_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    anonymous = TestClient(app)

    for candidate in ("not-a-uuid", str(uuid.uuid4()), created["id"]):
        response = anonymous.get(f"/api/tickets/{candidate}")
        assert response.status_code == 401
        assert response.json() != NOT_FOUND_BODY


# --- RF-53: solicitante exacto y null cuando no se resuelve ---


def test_requester_is_exact_and_carries_no_credentials_or_role():
    requester = _register_client("Ana Perez", "ana@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = technician_api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body["requester"]) == REQUESTER_FIELDS
    assert body["requester"] == {
        "id": requester["id"],
        "name": "Ana Perez",
        "email": "ana@ejemplo.com",
    }
    raw = response.text
    for forbidden in (
        '"role"',
        '"password"',
        '"password_hash"',
        '"hash"',
        '"token"',
        '"session"',
    ):
        assert forbidden not in raw
    assert "$argon2" not in raw
    assert PASSWORD not in raw


def test_requester_is_null_when_the_user_cannot_be_resolved():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    orphan = _foreign_ticket(
        str(uuid.uuid4()), title="Sin solicitante", description="Detalle intacto"
    )

    response = technician_api.get(f"/api/tickets/{orphan.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["requester"] is None
    # El resto del detalle se devuelve con normalidad.
    assert body["id"] == orphan.id
    assert body["title"] == "Sin solicitante"
    assert body["description"] == "Detalle intacto"
    assert body["requester_id"] == orphan.requester_id
