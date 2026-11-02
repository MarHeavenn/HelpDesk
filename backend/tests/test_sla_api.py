"""HU-05 — SLA en las respuestas de ticket (RF-42, RF-44, RF-46..RF-49).

Mapa RF -> test:
- RF-42: `sla` nulo en creacion, listado y detalle sin prioridad.
- RF-44: `sla` con la misma composicion en creacion, listado, detalle,
  prioridad, estado y asignacion; `null` cuando no hay prioridad.
- RF-46: congelacion al resolver y reanudacion al reabrir.
- RF-47: el cambio de prioridad recalcula el vencimiento desde la creacion
  y la asignacion no altera el SLA.
- RF-48: el estado se deriva en cada consulta (un ticket envejecido pasa a
  `incumplido` sin tocar el ticket).
- RF-49: el cliente solo ve el SLA de sus tickets y no hay ruta publica de
  configuracion.

Los estados dependientes del reloj usan tickets envejecidos con margenes
amplios (horas), nunca limites exactos; los limites exactos se cubren en
`test_sla_domain.py` con `now` inyectado.
"""

import os
import sys
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
SLA_FIELDS = {
    "target_minutes",
    "started_at",
    "due_at",
    "elapsed_minutes",
    "remaining_minutes",
    "status",
    "near_due",
    "breached",
}

client_api = TestClient(app)
staff_api = TestClient(app)
admin_api = TestClient(app)
other_api = TestClient(app)
ALL_CLIENTS = (client_api, staff_api, admin_api, other_api)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    for api in ALL_CLIENTS:
        api.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    for api in ALL_CLIENTS:
        api.cookies.clear()


def _login(api: TestClient, email: str) -> None:
    logged = api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200


def _register_client(api: TestClient, email="ana@ejemplo.com"):
    registered = api.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    _login(api, email)
    return registered.json()


def _provision(api: TestClient, role, email):
    user = provision_user(
        name="Equipo Soporte",
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(api, email)
    return user


def _create(api: TestClient, title="Titulo", description="Descripcion"):
    response = api.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert response.status_code == 201
    return response.json()


def _set_priority(api: TestClient, ticket_id: str, priority: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": priority}
    )
    assert response.status_code == 200
    return response.json()


def _set_status(api: TestClient, ticket_id: str, status: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": status}
    )
    assert response.status_code == 200
    return response.json()


def _assign(api: TestClient, ticket_id: str, assignee_id: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/assignee",
        json={"assignee_id": assignee_id},
    )
    assert response.status_code == 200
    return response.json()


def _age_ticket(ticket_id: str, **delta) -> None:
    """Envejece el ticket almacenado sin tocar su estado ni su SLA."""
    ticket = get_ticket_repository().find_by_id(ticket_id)
    assert ticket is not None
    ticket.created_at = datetime.now(timezone.utc) - timedelta(**delta)


# --- RF-42: sin prioridad no hay SLA ---


def test_creation_returns_sla_null_without_priority():
    _register_client(client_api)

    created = _create(client_api)

    assert created["sla"] is None


def test_list_and_detail_return_sla_null_without_priority():
    _register_client(client_api)
    created = _create(client_api)

    detail = client_api.get(f"/api/tickets/{created['id']}")
    listing = client_api.get("/api/tickets")

    assert detail.status_code == 200
    assert listing.status_code == 200
    assert detail.json()["sla"] is None
    assert listing.json()[0]["sla"] is None
    assert '"sla":null' in detail.text


# --- RF-44: composicion del SLA ---


def test_setting_priority_returns_sla_from_creation():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")

    updated = _set_priority(staff_api, created["id"], "Alta")

    sla = updated["sla"]
    assert set(sla) == SLA_FIELDS
    assert sla["target_minutes"] == 240
    assert sla["status"] == "en_tiempo"
    assert sla["near_due"] is False
    assert sla["breached"] is False
    assert sla["remaining_minutes"] > 0
    started_at = datetime.fromisoformat(sla["started_at"])
    due_at = datetime.fromisoformat(sla["due_at"])
    assert started_at == datetime.fromisoformat(created["created_at"])
    assert due_at - started_at == timedelta(minutes=240)


def test_list_and_detail_share_the_same_sla():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _set_priority(staff_api, created["id"], "Media")

    detail = client_api.get(f"/api/tickets/{created['id']}").json()
    item = client_api.get("/api/tickets").json()[0]

    assert set(item["sla"]) == SLA_FIELDS
    for field in (
        "target_minutes",
        "started_at",
        "due_at",
        "status",
        "near_due",
        "breached",
    ):
        assert item["sla"][field] == detail["sla"][field]


def test_assignee_summary_includes_sla():
    _register_client(client_api)
    created = _create(client_api)
    technician = _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    _set_priority(staff_api, created["id"], "Alta")
    _assign(admin_api, created["id"], technician.id)

    items = staff_api.get("/api/assignments/mine").json()

    assert items
    assert set(items[0]["sla"]) == SLA_FIELDS


# --- RF-47: cambio de prioridad y asignacion ---


def test_priority_change_recalculates_due_without_restarting_the_counter():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")

    alta = _set_priority(staff_api, created["id"], "Alta")
    critica = _set_priority(staff_api, created["id"], "Crítica")

    assert critica["sla"]["started_at"] == alta["sla"]["started_at"]
    due_alta = datetime.fromisoformat(alta["sla"]["due_at"])
    due_critica = datetime.fromisoformat(critica["sla"]["due_at"])
    assert due_alta - due_critica == timedelta(minutes=120)
    assert critica["sla"]["target_minutes"] == 120


def test_assignment_does_not_change_the_sla():
    _register_client(client_api)
    created = _create(client_api)
    technician = _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    before = _set_priority(staff_api, created["id"], "Alta")["sla"]

    assigned = _assign(admin_api, created["id"], technician.id)

    after = assigned["sla"]
    for field in ("target_minutes", "started_at", "due_at"):
        assert after[field] == before[field]


# --- RF-48: el estado se actualiza sin intervencion manual ---


def test_aged_ticket_is_breached_without_touching_it():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _age_ticket(created["id"], hours=5)

    sla = _set_priority(staff_api, created["id"], "Alta")["sla"]

    assert sla["status"] == "incumplido"
    assert sla["breached"] is True
    assert sla["near_due"] is False
    assert sla["remaining_minutes"] == 0
    assert sla["elapsed_minutes"] >= 300


# --- RF-46: resolucion y reapertura ---


def test_resolution_within_due_freezes_the_sla_as_met():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _age_ticket(created["id"], hours=1)
    _set_priority(staff_api, created["id"], "Alta")

    resolved = _set_status(staff_api, created["id"], "Resuelto")

    sla = resolved["sla"]
    assert sla["status"] == "cumplido"
    assert sla["breached"] is False
    assert sla["remaining_minutes"] == 0
    # La consulta posterior mantiene el SLA congelado.
    detail = client_api.get(f"/api/tickets/{created['id']}").json()
    assert detail["sla"]["status"] == "cumplido"


def test_resolution_after_due_freezes_the_sla_as_breached():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _age_ticket(created["id"], hours=5)
    _set_priority(staff_api, created["id"], "Alta")

    resolved = _set_status(staff_api, created["id"], "Resuelto")

    assert resolved["sla"]["status"] == "incumplido"
    assert resolved["sla"]["breached"] is True


def test_resolved_to_closed_keeps_the_frozen_sla():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _age_ticket(created["id"], hours=1)
    _set_priority(staff_api, created["id"], "Alta")
    resolved = _set_status(staff_api, created["id"], "Resuelto")

    closed = _set_status(staff_api, created["id"], "Cerrado")

    # RF-46: `Resuelto` -> `Cerrado` conserva la resolucion original.
    assert closed["sla"]["status"] == "cumplido"
    assert closed["sla"]["elapsed_minutes"] == resolved["sla"][
        "elapsed_minutes"
    ]
    assert closed["sla"]["remaining_minutes"] == 0
    assert closed["sla"]["breached"] is False


def test_reopening_resumes_the_sla_from_creation():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _age_ticket(created["id"], hours=3)
    _set_priority(staff_api, created["id"], "Alta")
    resolved = _set_status(staff_api, created["id"], "Resuelto")
    assert resolved["sla"]["status"] == "cumplido"

    reopened = _set_status(staff_api, created["id"], "En progreso")

    sla = reopened["sla"]
    assert sla["status"] != "cumplido"
    assert sla["remaining_minutes"] > 0
    assert sla["elapsed_minutes"] >= 180


# --- RF-49: visibilidad y ausencia de configuracion publica ---


def test_client_does_not_see_the_sla_of_another_client():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _set_priority(staff_api, created["id"], "Alta")
    _register_client(other_api, "otro@ejemplo.com")

    response = other_api.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 404
    assert set(response.json()) == {"detail"}
    assert "sla" not in response.text


def test_there_is_no_public_sla_configuration_route():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    assert admin_api.get("/api/sla/policies").status_code == 404
    assert admin_api.put("/api/sla/policies").status_code == 404


def test_invalid_priority_returns_422_and_keeps_sla_null():
    _register_client(client_api)
    created = _create(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")

    response = staff_api.put(
        f"/api/tickets/{created['id']}/priority", json={"priority": "Urgente"}
    )

    assert response.status_code == 422
    detail = client_api.get(f"/api/tickets/{created['id']}").json()
    assert detail["sla"] is None
