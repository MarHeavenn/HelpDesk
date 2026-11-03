"""HU-07 T2 — registro de comentarios por API (RF-61, RF-62, RF-65,
RF-66, RF-67, RF-70).

Verifica `POST /api/tickets/{ticket_id}/comments`:

- Técnico y administrador crean el comentario (201) con autor de la sesión.
- El cuerpo se recorta y se valida (1-2000 code points, texto estricto,
  sin campos extra); cualquier incumplimiento responde 422 sin crear nada.
- El cliente no crea comentarios: 404 uniforme, incluso en su ticket.
- Un ticket `Cerrado` responde 409; un ticket inexistente o inválido 404.
- Sin sesión, 401 antes que 404/409/422.
- Registrar un comentario no muta el ticket ni su SLA.

Cada usuario usa su propio `TestClient` con sesión real.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta

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
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": "ticket not found"}
CLOSED_BODY = {"detail": "ticket is closed"}
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


def _create_ticket(api: TestClient):
    response = api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _comment(api: TestClient, ticket_id: str, body: str):
    return api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": body}
    )


def _close(api: TestClient, ticket_id: str):
    response = api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "Cerrado"}
    )
    assert response.status_code == 200, response.text


# --- RF-61: creación por técnico y administrador ---


def test_technician_creates_a_comment():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = _comment(
        technician_api, created["id"], "  Se revisó el acceso  "
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == COMMENT_FIELDS
    assert body["ticket_id"] == created["id"]
    assert body["body"] == "Se revisó el acceso"
    assert body["author"] == {
        "id": technician["id"],
        "name": "Tecnico Uno",
    }
    assert set(body["author"]) == AUTHOR_FIELDS
    assert uuid.UUID(body["id"])
    assert body["created_at"].endswith("+00:00")
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)


def test_administrator_creates_a_comment():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    admin_api = _login(admin["email"])

    response = _comment(admin_api, created["id"], "Supervisión del caso")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["author"] == {"id": admin["id"], "name": "Admin Uno"}
    assert body["body"] == "Supervisión del caso"


# --- RF-65: el cliente no escribe ---


def test_client_cannot_create_a_comment_even_on_its_own_ticket():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    client_api = _login(requester["email"])
    created = _create_ticket(client_api)

    response = _comment(client_api, created["id"], "Comentario del cliente")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    # El rechazo no filtra el título ni deja el comentario almacenado.
    assert "Titulo" not in response.text
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    listed = technician_api.get(f"/api/tickets/{created['id']}/comments")
    assert listed.status_code == 200
    assert listed.json() == []


def test_client_cannot_create_a_comment_on_a_foreign_ticket():
    owner = _register_client("Dueno Uno", "dueno@ejemplo.com")
    owner_api = _login(owner["email"])
    created = _create_ticket(owner_api)
    intruder = _register_client("Otro Dos", "otro@ejemplo.com")
    intruder_api = _login(intruder["email"])

    response = _comment(intruder_api, created["id"], "Ajeno")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


# --- RF-66: ticket cerrado ---


def test_closed_ticket_rejects_new_comments_with_409():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    first = _comment(technician_api, created["id"], "Antes del cierre")
    assert first.status_code == 201
    _close(technician_api, created["id"])

    response = _comment(technician_api, created["id"], "Después del cierre")

    assert response.status_code == 409
    assert response.json() == CLOSED_BODY
    listed = technician_api.get(f"/api/tickets/{created['id']}/comments")
    assert listed.status_code == 200
    assert [item["body"] for item in listed.json()] == ["Antes del cierre"]


# --- RF-62: validación del cuerpo ---


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"body": ""},
        {"body": "   "},
        {"body": "\n\t "},
        {"body": 123},
        {"body": None},
        {"body": ["texto"]},
        {"body": "a" * 2001},
        {"body": "válido", "author_id": "otro"},
        {"body": "válido", "created_at": "2026-11-02T00:00:00+00:00"},
    ],
)
def test_invalid_body_returns_422_and_creates_nothing(payload):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = technician_api.post(
        f"/api/tickets/{created['id']}/comments", json=payload
    )

    assert response.status_code == 422, response.text
    listed = technician_api.get(f"/api/tickets/{created['id']}/comments")
    assert listed.json() == []


@pytest.mark.parametrize(
    "content,content_type",
    [
        (b"", None),
        (b"no es json", "application/json"),
        (b'{"body": ', "application/json"),
        (b'{"body": "texto"}', "text/plain"),
    ],
)
def test_missing_or_invalid_json_returns_422(content, content_type):
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    headers = {"Content-Type": content_type} if content_type else {}

    response = technician_api.post(
        f"/api/tickets/{created['id']}/comments",
        content=content,
        headers=headers,
    )

    assert response.status_code == 422, response.text


def test_body_with_exactly_2000_code_points_is_accepted():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    response = _comment(technician_api, created["id"], "á" * 2000)

    assert response.status_code == 201, response.text
    assert response.json()["body"] == "á" * 2000


# --- RF-70: 404 y precedencia de errores ---


def test_staff_gets_uniform_404_for_unknown_or_invalid_ticket():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    for ticket_id in ("not-a-uuid", str(uuid.uuid4())):
        response = _comment(technician_api, ticket_id, "Texto")
        assert response.status_code == 404
        assert response.json() == NOT_FOUND_BODY


def test_missing_session_returns_401_before_ticket_or_body():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    _close(technician_api, created["id"])
    anonymous = TestClient(app)

    for ticket_id, payload in (
        ("not-a-uuid", {"body": ""}),
        (str(uuid.uuid4()), {"body": ""}),
        (created["id"], {"body": ""}),
    ):
        response = anonymous.post(
            f"/api/tickets/{ticket_id}/comments", json=payload
        )
        assert response.status_code == 401


# --- RF-69: el ticket y su SLA no cambian ---


def test_creating_a_comment_does_not_mutate_the_ticket_or_its_sla():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = _create_ticket(requester_api)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])
    priority = technician_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Alta"}
    )
    assert priority.status_code == 200
    before = requester_api.get(f"/api/tickets/{created['id']}").json()

    response = _comment(technician_api, created["id"], "Solo una nota")

    assert response.status_code == 201
    after = requester_api.get(f"/api/tickets/{created['id']}").json()
    for key in (
        "id",
        "title",
        "description",
        "priority",
        "status",
        "assignee",
        "requester",
        "created_at",
        "resolved_at",
        "requester_id",
    ):
        assert after[key] == before[key]
    assert after["sla"]["target_minutes"] == before["sla"]["target_minutes"]
    assert after["sla"]["started_at"] == before["sla"]["started_at"]
    assert after["sla"]["due_at"] == before["sla"]["due_at"]
    # El seguimiento vive en el subrecurso, no en la respuesta del ticket.
    assert "comments" not in after
