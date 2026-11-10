"""HU-07 T4 — flujo completo del seguimiento (RF-61 a RF-70).

Integra HU-02 (creación), HU-04 (asignación), HU-05 (prioridad y SLA),
HU-06 (detalle y visibilidad) y HU-07 (comentarios) en un solo recorrido:

1. El cliente crea el ticket; el administrador lo asigna a un técnico.
2. El técnico fija prioridad, lo pasa a `En progreso` y comenta.
3. El administrador supervisa y comenta.
4. El cliente lee el seguimiento cronológico y el detalle consolidado,
   sin poder escribir.
5. El técnico cierra el ticket: el detalle refleja la resolución y el
   SLA congelado, el listado sigue disponible y un comentario nuevo
   responde 409.

Comprueba también que los comentarios no se cuelan en las respuestas de
ticket ni en los resúmenes, y que el autor de cada nota es el usuario de
la sesión.
"""

import os
import sys
import uuid
from datetime import datetime

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


def _comment(api: TestClient, ticket_id: str, body: str):
    return api.post(
        f"/api/tickets/{ticket_id}/comments", json={"body": body}
    )


def test_full_follow_up_flow_from_creation_to_closure():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    technician_api = _login(technician["email"])
    admin_api = _login(admin["email"])

    # 1. HU-02: el cliente crea el ticket.
    creation = requester_api.post(
        "/api/tickets",
        json={"title": "No puedo acceder", "description": "Error al entrar"},
    )
    assert creation.status_code == 201, creation.text
    created = creation.json()
    ticket_id = created["id"]

    # 2. HU-04: el administrador asigna el ticket al técnico.
    assignment = admin_api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": technician["id"]},
    )
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()["assignee"] == {
        "id": technician["id"],
        "name": "Tecnico Uno",
    }

    # 3. HU-03/HU-05: prioridad y estado; el SLA aparece.
    priority = technician_api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": "Alta"}
    )
    assert priority.status_code == 200, priority.text
    assert priority.json()["sla"] is not None
    status = technician_api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "En progreso"}
    )
    assert status.status_code == 200, status.text

    # 4. HU-07: técnico y administrador registran avances.
    first = _comment(
        technician_api, ticket_id, "  Se revisó el acceso y se reinició  "
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert set(first_body) == COMMENT_FIELDS
    assert first_body["body"] == "Se revisó el acceso y se reinició"
    assert first_body["author"] == {
        "id": technician["id"],
        "name": "Tecnico Uno",
    }
    assert first_body["ticket_id"] == ticket_id

    second = _comment(admin_api, ticket_id, "Supervisión conforme")
    assert second.status_code == 201, second.text
    assert second.json()["author"] == {
        "id": admin["id"],
        "name": "Admin Uno",
    }

    # 5. El cliente lee el seguimiento y el detalle consolidado de HU-06.
    listing = requester_api.get(f"/api/tickets/{ticket_id}/comments")
    assert listing.status_code == 200
    listing_body = listing.json()
    assert [item["body"] for item in listing_body] == [
        "Se revisó el acceso y se reinició",
        "Supervisión conforme",
    ]
    assert [item["author"]["name"] for item in listing_body] == [
        "Tecnico Uno",
        "Admin Uno",
    ]

    detail = requester_api.get(f"/api/tickets/{ticket_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["priority"] == "Alta"
    assert detail_body["status"] == "En progreso"
    assert detail_body["assignee"] == {
        "id": technician["id"],
        "name": "Tecnico Uno",
    }
    assert detail_body["requester"] == {
        "id": requester["id"],
        "name": "Cliente Uno",
        "email": "cliente@ejemplo.com",
    }
    assert detail_body["sla"] is not None
    assert detail_body["resolved_at"] is None
    assert "comments" not in detail_body

    # Los resúmenes siguen sin comentarios.
    summary = requester_api.get("/api/tickets")
    assert summary.status_code == 200
    assert summary.json()[0]["id"] == ticket_id
    assert "comments" not in summary.json()[0]

    # 6. El cliente no puede escribir en su propio ticket.
    forbidden = _comment(requester_api, ticket_id, "Comentario del cliente")
    assert forbidden.status_code == 404
    assert forbidden.json() == NOT_FOUND_BODY

    # 7. El técnico resuelve y cierra el ticket: el detalle refleja la resolución.
    resolved = technician_api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "Resuelto"}
    )
    assert resolved.status_code == 200, resolved.text
    closed = technician_api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "Cerrado"}
    )
    assert closed.status_code == 200, closed.text
    closed_body = closed.json()
    assert closed_body["status"] == "Cerrado"
    assert closed_body["resolved_at"] is not None
    assert closed_body["sla"] is not None
    resolved_at = closed_body["resolved_at"]
    assert datetime.fromisoformat(resolved_at).utcoffset() is not None

    # 8. El cierre impide nuevos comentarios, pero no borra el historial.
    rejected = _comment(technician_api, ticket_id, "Después del cierre")
    assert rejected.status_code == 409
    assert rejected.json() == CLOSED_BODY
    still_listed = requester_api.get(f"/api/tickets/{ticket_id}/comments")
    assert still_listed.status_code == 200
    assert [item["body"] for item in still_listed.json()] == [
        "Se revisó el acceso y se reinició",
        "Supervisión conforme",
    ]


def test_comment_ids_are_opaque_and_unique():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    requester_api = _login(requester["email"])
    created = requester_api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    ).json()
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    technician_api = _login(technician["email"])

    ids = []
    for body in ("Uno", "Dos", "Tres"):
        response = _comment(technician_api, created["id"], body)
        assert response.status_code == 201
        comment_id = response.json()["id"]
        uuid.UUID(comment_id)
        ids.append(comment_id)

    assert len(set(ids)) == 3
