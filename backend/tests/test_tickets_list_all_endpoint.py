"""HU-23 (RF-119, RF-122) — `GET /api/tickets/all`.

Verifica:
- RF-122: administrador y tecnico reciben **todos** los tickets, con el
  resumen exacto `{id, title, priority, status, assignee, sla, created_at}`
  y orden por `created_at` descendente.
- RF-122: un cliente recibe el 404 uniforme de tickets sin datos.
- RF-122: sin sesion valida la respuesta es 401.
- La ruta estatica `/all` no se captura como `/{ticket_id}` y no altera el
  detalle de HU-02/HU-06.
- Lista vacia, parametros desconocidos ignorados y misma referencia de SLA
  para todo el listado.
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
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": "ticket not found"}
SUMMARY_FIELDS = {
    "id",
    "title",
    "priority",
    "status",
    "assignee",
    "sla",
    "created_at",
}
BASE = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()


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
    registration = TestClient(app).post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registration.status_code == 201, registration.text
    return registration.json()


def _login(email: str) -> TestClient:
    """Cliente HTTP propio con la sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _insert(
    requester_id: str,
    *,
    ticket_id: str | None = None,
    title: str = "Ticket de prueba",
    created_at: datetime = BASE,
    priority: str | None = None,
    assignee_id: str | None = None,
) -> Ticket:
    ticket = Ticket(
        id=ticket_id or str(uuid.uuid4()),
        title=title,
        description="Descripcion",
        requester_id=requester_id,
        created_at=created_at,
        priority=priority,
        assignee_id=assignee_id,
        assignee_name="Tecnico" if assignee_id else None,
    )
    get_ticket_repository().add(ticket)
    return ticket


def _all_view(ticket: Ticket) -> dict:
    """Resumen compuesto por el endpoint para una entidad dada."""
    return {
        "id": ticket.id,
        "title": ticket.title,
        "priority": ticket.priority,
        "status": ticket.status,
        "assignee": (
            {"id": ticket.assignee_id, "name": ticket.assignee_name}
            if ticket.assignee_id and ticket.assignee_name
            else None
        ),
        "sla": None,
        "created_at": ticket.created_at.isoformat(),
    }


# --- RF-122: administrador y tecnico ven todo ---


@pytest.mark.parametrize(
    ("role", "email"),
    [("administrador", "admin@ejemplo.com"), ("tecnico", "tec@ejemplo.com")],
)
def test_management_roles_receive_every_ticket(role: str, email: str):
    _provision(role, "Usuario de gestion", email)
    api = _login(email)
    requester_a = str(uuid.uuid4())
    requester_b = str(uuid.uuid4())
    old = _insert(requester_a, title="Antiguo", created_at=BASE)
    new = _insert(
        requester_b,
        title="Nuevo",
        created_at=BASE + timedelta(minutes=5),
        priority="Alta",
        assignee_id=str(uuid.uuid4()),
    )

    response = api.get("/api/tickets/all")

    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [new.id, old.id]
    for item in items:
        assert set(item) == SUMMARY_FIELDS
        assert "description" not in item
        assert "requester_id" not in item
    assert items[0]["priority"] == "Alta"
    assert items[0]["assignee"] == {
        "id": new.assignee_id,
        "name": new.assignee_name,
    }
    assert items[1]["priority"] is None
    assert items[1]["assignee"] is None


# --- RF-122: el cliente no accede al listado global ---


def test_client_receives_uniform_404_without_data():
    client_user = _register_client("Cliente Uno", "cliente@ejemplo.com")
    api = _login(client_user["email"])
    _insert(client_user["id"], title="Ticket del cliente")

    response = api.get("/api/tickets/all")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert "Ticket del cliente" not in response.text
    assert "id" not in response.json()


# --- RF-122: sin sesion -> 401 ---


def test_without_session_returns_401():
    response = TestClient(app).get("/api/tickets/all")

    assert response.status_code == 401
    assert set(response.json()) == {"detail"}


# --- Lista vacia y parametros desconocidos ---


def test_empty_list_returns_200_with_empty_collection():
    _provision("administrador", "Admin", "admin@ejemplo.com")
    api = _login("admin@ejemplo.com")

    response = api.get("/api/tickets/all")

    assert response.status_code == 200
    assert response.json() == []


def test_unknown_query_parameters_are_ignored():
    _provision("administrador", "Admin", "admin@ejemplo.com")
    api = _login("admin@ejemplo.com")
    _insert(str(uuid.uuid4()), title="Unico")

    plain = api.get("/api/tickets/all")
    with_params = api.get("/api/tickets/all?status=Abierto&page=2")

    assert with_params.status_code == 200
    assert with_params.json() == plain.json()


# --- La ruta estatica no compite con el detalle ---


def test_all_route_does_not_shadow_ticket_detail():
    admin = _provision("administrador", "Admin", "admin@ejemplo.com")
    api = _login(admin["email"])
    ticket = _insert(admin["id"], title="Detalle visible")

    detail = api.get(f"/api/tickets/{ticket.id}")

    assert detail.status_code == 200
    assert detail.json()["id"] == ticket.id
    assert detail.json()["description"] == "Descripcion"
    assert api.get("/api/tickets/all").status_code == 200
    # Un identificador invalido sigue devolviendo el 404 uniforme y no la
    # lista global.
    invalid = api.get("/api/tickets/no-es-uuid")
    assert invalid.status_code == 404


def test_openapi_documents_get_only():
    paths = app.openapi()["paths"]
    assert set(paths["/api/tickets/all"]) == {"get"}
