"""T9 (HU-04) — Composicion uniforme de `assignee` (RF-35, RF-35.5).

Mapa RF -> test:
- RF-35.1 (el resumen del listado incluye el tecnico responsable):
  `test_listing_includes_assignee_null`, `test_listing_and_detail_show_the_current_technician`
  y las aserciones de resumen de `test_reassignment_updates_assignee_everywhere`.
- RF-35.2 (el detalle incluye el tecnico responsable):
  `test_detail_includes_assignee_null`, `test_listing_and_detail_show_the_current_technician`
  y las aserciones de detalle de `test_reassignment_updates_assignee_everywhere`.
- RF-35.3 (el tecnico se representa como `{id, name}` o `null` inequivoco):
  `test_creation_includes_assignee_null`,
  `test_priority_and_status_responses_include_assignee_null`,
  `test_assignment_response_contains_the_assigned_technician`,
  `test_summary_and_detail_use_the_same_assignee_shape`,
  `test_reassignment_updates_assignee_everywhere`.
- RF-35.4 (sin correo ni credenciales; solo nombre):
  `test_assignee_object_has_only_id_and_name` y
  `test_no_response_exposes_email_credentials_or_assignment_log`.
- RF-35.5 (composicion uniforme en creacion, listado, detalle, asignacion y
  modificaciones de HU-03):
  `test_creation_includes_assignee_null`,
  `test_listing_includes_assignee_null`,
  `test_detail_includes_assignee_null`,
  `test_priority_and_status_responses_include_assignee_null`,
  `test_assignment_response_contains_the_assigned_technician`,
  `test_listing_and_detail_show_the_current_technician`,
  `test_reassignment_updates_assignee_everywhere`,
  `test_raw_bodies_include_the_null_token_when_unassigned` y
  `test_no_response_exposes_email_credentials_or_assignment_log`.

La forma es la misma en resumen y detalle: `assignee: {"id", "name"} | null`
(D7), y se aplica a `PUT .../priority` y `PUT .../status` de HU-03
(decisión derivada 6) y a la creacion (decisión derivada 7). Esta tarea no
cambia codigos ni reglas: solo compone y serializa.
"""

import os
import sys
import uuid

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
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"

# Composiciones exactas de RF-35.1, RF-35.2 y RF-35.3 (D7). `assignee` es
# el unico campo anadido a las composiciones de HU-02/HU-03.
SUMMARY_FIELDS = {"id", "title", "priority", "status", "assignee", "created_at"}
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
ASSIGNEE_FIELDS = {"id", "name"}
FORBIDDEN_ASSIGNMENT_FIELDS = {
    "assignments",
    "previous_assignee_id",
    "new_assignee_id",
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


def _client_session(email=None, name="Cliente Uno"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
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


def _login(email):
    """Cliente HTTP propio con sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _admin_session(email=None, name="Admin Uno"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    admin = _provision("administrador", name, email)
    return _login(email), admin


def _create_ticket(target, title="Titulo", description="Descripcion"):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201, created.text
    return created


def _assign(target, ticket_id, technician_id):
    return target.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician_id},
    )


def _assert_null_assignee(body):
    assert "assignee" in body
    assert body["assignee"] is None


def _assert_technician_assignee(body, technician):
    assert set(body["assignee"]) == ASSIGNEE_FIELDS
    assert body["assignee"] == {"id": technician.id, "name": technician.name}


def _assert_no_sensitive_content(response, technician):
    raw = response.text
    assert technician.email not in raw
    assert PASSWORD not in raw
    for forbidden in FORBIDDEN_ASSIGNMENT_FIELDS | {"email", "password"}:
        assert forbidden not in raw


# --- RF-35.5 / decision derivada 7: creacion con `assignee: null` ---


def test_creation_includes_assignee_null():
    client_api, client = _client_session()

    response = _create_ticket(client_api, title="Impresora rota")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    _assert_null_assignee(body)
    assert body["requester_id"] == client["id"]
    assert '"assignee":null' in response.text


# --- RF-35.5: listado y detalle sin asignacion ---


def test_listing_includes_assignee_null():
    client_api, _ = _client_session()
    for title in ("Primero", "Segundo"):
        assert _create_ticket(client_api, title=title).status_code == 201

    response = client_api.get("/api/tickets")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        _assert_null_assignee(item)
    assert response.text.count('"assignee":null') == 2


def test_detail_includes_assignee_null():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)

    response = client_api.get(f"/api/tickets/{created.json()['id']}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    _assert_null_assignee(body)
    assert '"assignee":null' in response.text


# --- RF-35.5 / decision derivada 6: modificaciones de HU-03 ---


def test_priority_and_status_responses_include_assignee_null():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    ticket_id = created.json()["id"]

    priority = admin_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )
    status = admin_api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "En progreso"}
    )

    for response in (priority, status):
        assert response.status_code == 200
        body = response.json()
        assert set(body) == DETAIL_FIELDS
        _assert_null_assignee(body)
        assert '"assignee":null' in response.text


# --- RF-35.3 / RF-35.5: asignacion y respuestas posteriores ---


def test_assignment_response_contains_the_assigned_technician():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")

    response = _assign(admin_api, created.json()["id"], technician.id)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    _assert_technician_assignee(body, technician)
    _assert_no_sensitive_content(response, technician)


def test_listing_and_detail_show_the_current_technician():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket_id = created.json()["id"]
    assert _assign(admin_api, ticket_id, technician.id).status_code == 200

    listed = client_api.get("/api/tickets")
    detail = client_api.get(f"/api/tickets/{ticket_id}")

    assert listed.status_code == 200
    [item] = listed.json()
    assert set(item) == SUMMARY_FIELDS
    _assert_technician_assignee(item, technician)
    assert detail.status_code == 200
    body = detail.json()
    assert set(body) == DETAIL_FIELDS
    _assert_technician_assignee(body, technician)
    _assert_no_sensitive_content(listed, technician)
    _assert_no_sensitive_content(detail, technician)


def test_summary_and_detail_use_the_same_assignee_shape():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket_id = created.json()["id"]
    assert _assign(admin_api, ticket_id, technician.id).status_code == 200

    [summary] = client_api.get("/api/tickets").json()
    detail = client_api.get(f"/api/tickets/{ticket_id}").json()

    assert summary["assignee"] == detail["assignee"]
    assert set(summary["assignee"]) == ASSIGNEE_FIELDS


def test_assigned_to_me_summary_includes_the_current_technician():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    ticket_id = created.json()["id"]
    assert _assign(admin_api, ticket_id, technician.id).status_code == 200

    response = _login(technician.email).get("/api/assignments/mine")

    assert response.status_code == 200
    [item] = response.json()
    assert set(item) == SUMMARY_FIELDS
    _assert_technician_assignee(item, technician)
    _assert_no_sensitive_content(response, technician)


def test_reassignment_updates_assignee_everywhere():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    first = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    second = _provision("tecnico", "Luis Perez", "luis@ejemplo.com")
    ticket_id = created.json()["id"]

    first_assignment = _assign(admin_api, ticket_id, first.id)
    second_assignment = _assign(admin_api, ticket_id, second.id)

    assert first_assignment.status_code == 200
    _assert_technician_assignee(first_assignment.json(), first)
    assert second_assignment.status_code == 200
    _assert_technician_assignee(second_assignment.json(), second)

    [summary] = client_api.get("/api/tickets").json()
    _assert_technician_assignee(summary, second)
    detail = client_api.get(f"/api/tickets/{ticket_id}").json()
    _assert_technician_assignee(detail, second)
    [mine] = _login(second.email).get("/api/assignments/mine").json()
    _assert_technician_assignee(mine, second)

    priority = admin_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Media"}
    )
    status = admin_api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "Resuelto"}
    )
    for response in (priority, status):
        assert response.status_code == 200
        _assert_technician_assignee(response.json(), second)


# --- RF-35.4: solo identificador y nombre; sin correo, credenciales ni log ---


def test_assignee_object_has_only_id_and_name():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    ticket_id = created.json()["id"]

    body = _assign(admin_api, ticket_id, technician.id).json()

    assert set(body["assignee"]) == ASSIGNEE_FIELDS
    assert body["assignee"]["name"] == "Ana Torres"
    assert body["assignee"]["id"] == technician.id
    assert technician.email not in repr(body)


def test_raw_bodies_include_the_null_token_when_unassigned():
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    ticket_id = created.json()["id"]

    responses = [
        created,
        client_api.get("/api/tickets"),
        client_api.get(f"/api/tickets/{ticket_id}"),
        admin_api.put(
            f"/api/tickets/{ticket_id}/priority", json={"priority": "Baja"}
        ),
        admin_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "En progreso"}
        ),
    ]

    for response in responses:
        assert response.status_code in (200, 201)
        assert '"assignee":null' in response.text


def test_no_response_exposes_email_credentials_or_assignment_log():
    technician = _provision("tecnico", "Ana Torres", "ana@ejemplo.com")
    client_api, _ = _client_session()
    created = _create_ticket(client_api)
    admin_api, _ = _admin_session()
    ticket_id = created.json()["id"]

    responses = [
        created,
        _assign(admin_api, ticket_id, technician.id),
        client_api.get("/api/tickets"),
        client_api.get(f"/api/tickets/{ticket_id}"),
        admin_api.put(
            f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
        ),
        admin_api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": "Resuelto"}
        ),
        _login(technician.email).get("/api/assignments/mine"),
    ]

    for response in responses:
        assert response.status_code in (200, 201)
        _assert_no_sensitive_content(response, technician)
