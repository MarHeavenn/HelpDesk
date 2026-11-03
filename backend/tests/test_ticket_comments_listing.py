"""HU-07 T3 — listado cronológico y visibilidad del seguimiento (RF-63,
RF-64, RF-67, RF-68, RF-69).

Verifica `GET /api/tickets/{ticket_id}/comments`:

- Lista completa y ascendente, vacía cuando no hay comentarios y aislada
  por ticket; los parámetros de consulta desconocidos se ignoran.
- Misma visibilidad que HU-06: cliente solo sus tickets; técnico y
  administrador cualquiera; 404 uniforme para ticket ajeno, inexistente o
  inválido.
- `author` se limita a `{id, name}` y es `null` si no se puede resolver.
- Un ticket `Cerrado` conserva la lectura del seguimiento.

Cada usuario usa su propio `TestClient` con sesión real.
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
from app.modules.tickets.domain.entities import TicketComment
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": "ticket not found"}
COMMENT_FIELDS = {"id", "ticket_id", "body", "author", "created_at"}
AUTHOR_FIELDS = {"id", "name"}


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()


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
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _create_ticket(api: TestClient, title="Titulo"):
    response = api.post(
        "/api/tickets",
        json={"title": title, "description": "Descripcion"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _comment(api: TestClient, ticket_id: str, body: str):
    response = api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _list(api: TestClient, ticket_id: str):
    return api.get(f"/api/tickets/{ticket_id}/comments")


# --- RF-63: lista vacía, orden y aislamiento ---


def test_ticket_without_comments_returns_an_empty_list():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = _list(technician_api, created["id"])

    assert response.status_code == 200
    assert response.json() == []


def test_listing_returns_comments_in_chronological_order():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, created["id"], "Primer avance")
    _comment(technician_api, created["id"], "Segundo avance")
    _comment(technician_api, created["id"], "Cierre del caso")

    response = _list(requester_api, created["id"])

    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == [
        "Primer avance",
        "Segundo avance",
        "Cierre del caso",
    ]


def test_listing_is_isolated_by_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    first = _create_ticket(requester_api, title="Primero")
    second = _create_ticket(requester_api, title="Segundo")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, first["id"], "Del primero")
    _comment(technician_api, second["id"], "Del segundo")

    first_list = _list(requester_api, first["id"])
    second_list = _list(requester_api, second["id"])

    assert [item["body"] for item in first_list.json()] == ["Del primero"]
    assert [item["body"] for item in second_list.json()] == ["Del segundo"]


def test_listing_contract_and_author_are_exact():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    created_comment = _comment(technician_api, created["id"], "Avance")

    response = _list(technician_api, created["id"])

    assert response.status_code == 200
    assert response.json() == [created_comment]
    item = response.json()[0]
    assert set(item) == COMMENT_FIELDS
    assert set(item["author"]) == AUTHOR_FIELDS
    assert item["author"] == {"id": technician["id"], "name": "Tecnico Uno"}
    assert item["ticket_id"] == created["id"]
    # El cuerpo crudo no filtra correo, rol ni credenciales del autor.
    raw = response.text
    assert '"email"' not in raw
    assert '"role"' not in raw
    assert "$argon2" not in raw
    assert PASSWORD not in raw
    assert '"token"' not in raw
    assert '"session"' not in raw


# --- RF-64: visibilidad de lectura ---


def test_client_can_read_comments_of_its_own_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, created["id"], "Avance visible")

    response = _list(requester_api, created["id"])

    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == ["Avance visible"]


def test_client_gets_uniform_404_for_foreign_unknown_or_invalid_ticket():
    owner = _register_client("Dueno Uno", "dueno@ejemplo.com")
    owner_api = _login(owner["email"])
    created = _create_ticket(owner_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, created["id"], "Seguimiento privado")
    intruder = _register_client("Otro Dos", "otro@ejemplo.com")
    intruder_api = _login(intruder["email"])

    responses = [
        _list(intruder_api, created["id"]),
        _list(intruder_api, str(uuid.uuid4())),
        _list(intruder_api, "not-a-uuid"),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY
        assert "Seguimiento privado" not in response.text


def test_staff_can_read_comments_of_any_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician_api = _login(technician["email"])
    admin_api = _login(admin["email"])
    _comment(technician_api, created["id"], "Avance del técnico")

    technician_list = _list(technician_api, created["id"])
    admin_list = _list(admin_api, created["id"])

    assert technician_list.status_code == 200
    assert [item["body"] for item in technician_list.json()] == [
        "Avance del técnico"
    ]
    assert admin_list.status_code == 200
    assert [item["body"] for item in admin_list.json()] == [
        "Avance del técnico"
    ]


def test_staff_gets_uniform_404_for_unknown_or_invalid_ticket():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    for candidate in ("not-a-uuid", str(uuid.uuid4())):
        response = _list(technician_api, candidate)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


def test_missing_session_returns_401_before_resolving_the_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    anonymous = TestClient(app)

    for candidate in ("not-a-uuid", str(uuid.uuid4()), created["id"]):
        response = anonymous.get(f"/api/tickets/{candidate}/comments")
        assert response.status_code == 401
        assert response.json() != NOT_FOUND_BODY


def test_unknown_query_parameters_are_ignored():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, created["id"], "Uno")
    _comment(technician_api, created["id"], "Dos")

    response = technician_api.get(
        f"/api/tickets/{created['id']}/comments"
        "?page=1&limit=1&order=desc&unknown=value"
    )

    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == ["Uno", "Dos"]


# --- RF-67: autor no resoluble ---


def test_author_is_null_when_the_user_cannot_be_resolved():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    orphan = TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=created["id"],
        author_id=str(uuid.uuid4()),
        body="Autor inexistente",
        created_at=datetime.now(timezone.utc),
    )
    get_ticket_comment_repository().add(orphan)

    response = _list(technician_api, created["id"])

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": orphan.id,
            "ticket_id": created["id"],
            "body": "Autor inexistente",
            "author": None,
            "created_at": orphan.created_at.isoformat(),
        }
    ]


# --- RF-66: lectura de un ticket cerrado ---


def test_closed_ticket_still_returns_its_comments():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _comment(technician_api, created["id"], "Antes del cierre")
    closed = technician_api.put(
        f"/api/tickets/{created['id']}/status", json={"status": "Cerrado"}
    )
    assert closed.status_code == 200

    response = _list(requester_api, created["id"])

    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == ["Antes del cierre"]
