"""HU-14 T8 — Configuracion vigente y congelacion del SLA (RF-76, RF-78).

Mapa RF -> test:
- RF-76: un ticket `Resuelto` o `Cerrado` conserva `target_minutes`,
  `due_at`, `elapsed_minutes` y `status` tras cambiar la configuracion; al
  reabrir se descarta el objetivo congelado y el SLA vuelve a derivarse de
  la configuracion vigente; al cambiar la prioridad de un `Resuelto` se usa
  la configuracion vigente en ese momento y queda re-congelado; un ticket
  sin prioridad sigue con `sla: null` (HU-05, RF-42).
- RF-78: `get_ticket_sla` conserva su firma y `resolved_target_minutes`
  sigue siendo un dato interno, fuera de `TicketResponse` y
  `TicketSummaryResponse`.

La seccion de efecto en vivo sobre tickets activos pertenece a T9; aqui
solo se prueba la congelacion y la re-congelacion. Los tickets se envejecen
mutando `created_at` en el repositorio, nunca durmiendo.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from inspect import signature

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
from app.modules.sla.interface.contract import get_ticket_sla
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
SEED_HOURS = {"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 24}
SEED_MINUTES = {"Crítica": 120, "Alta": 240, "Media": 720, "Baja": 1440}

client_api = TestClient(app)
staff_api = TestClient(app)
admin_api = TestClient(app)
ALL_CLIENTS = (client_api, staff_api, admin_api)


@pytest.fixture(autouse=True)
def clean_state():
    """Aisla usuarios, sesiones, tickets, registros y configuracion global."""
    _clear()
    yield
    _clear()


def _clear() -> None:
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_sla_policy_repository().reset()
    for api in ALL_CLIENTS:
        api.cookies.clear()


def _login(api: TestClient, email: str) -> None:
    logged = api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200


def _provision(api: TestClient, role: str, email: str) -> dict:
    user = provision_user(
        name="Equipo Soporte",
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(api, email)
    return user


def _register_client(api: TestClient, email="ana@ejemplo.com") -> None:
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


def _create(api: TestClient, title="Titulo", description="Descripcion") -> dict:
    created = api.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201
    return created.json()


def _set_priority(api: TestClient, ticket_id: str, priority: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/priority", json={"priority": priority}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_status(api: TestClient, ticket_id: str, status: str) -> dict:
    response = api.put(
        f"/api/tickets/{ticket_id}/status", json={"status": status}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _put_policies(api: TestClient, body: dict):
    return api.put("/api/sla/policies", json=body)


def _age_ticket(ticket_id: str, **delta) -> None:
    """Envejece el ticket almacenado sin tocar su estado ni su SLA."""
    ticket = get_ticket_repository().find_by_id(ticket_id)
    assert ticket is not None
    ticket.created_at = datetime.now(timezone.utc) - timedelta(**delta)


def _detail(ticket_id: str) -> dict:
    response = client_api.get(f"/api/tickets/{ticket_id}")
    assert response.status_code == 200
    return response.json()


def _stored(ticket_id: str):
    ticket = get_ticket_repository().find_by_id(ticket_id)
    assert ticket is not None
    return ticket


# --- RF-76: congelacion de resueltos y cerrados ---


def test_a_resolved_ticket_keeps_its_sla_when_the_configuration_changes():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], hours=10)
    _set_priority(staff_api, created["id"], "Crítica")

    resolved = _set_status(staff_api, created["id"], "Resuelto")
    frozen = resolved["sla"]
    assert frozen["target_minutes"] == 120
    assert frozen["status"] == "incumplido"
    assert frozen["elapsed_minutes"] >= 600

    changed = _put_policies(
        admin_api,
        {"Crítica": 20, "Alta": 4, "Media": 12, "Baja": 24},
    )
    assert changed.status_code == 200

    detail = _detail(created["id"])
    assert detail["status"] == "Resuelto"
    assert detail["resolved_at"] == resolved["resolved_at"]
    assert detail["sla"] == frozen


def test_a_closed_ticket_keeps_its_sla_when_the_configuration_changes():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], hours=30)
    _set_priority(staff_api, created["id"], "Baja")
    _set_status(staff_api, created["id"], "Resuelto")

    closed = _set_status(staff_api, created["id"], "Cerrado")
    frozen = closed["sla"]
    assert frozen["target_minutes"] == 1440
    assert frozen["status"] == "incumplido"

    changed = _put_policies(
        admin_api,
        {"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 48},
    )
    assert changed.status_code == 200

    detail = _detail(created["id"])
    assert detail["status"] == "Cerrado"
    assert detail["sla"] == frozen


def test_reopening_clears_the_frozen_target_and_derives_from_the_current_configuration():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], hours=10)
    _set_priority(staff_api, created["id"], "Crítica")
    _set_status(staff_api, created["id"], "Resuelto")
    assert _stored(created["id"]).resolved_target_minutes == 120

    changed = _put_policies(
        admin_api,
        {"Crítica": 0.5, "Alta": 4, "Media": 12, "Baja": 24},
    )
    assert changed.status_code == 200

    reopened = _set_status(staff_api, created["id"], "Abierto")

    assert reopened["resolved_at"] is None
    assert reopened["sla"]["target_minutes"] == 30
    assert reopened["sla"]["status"] == "incumplido"
    stored = _stored(created["id"])
    assert stored.resolved_at is None
    assert stored.resolved_target_minutes is None
    assert _detail(created["id"])["sla"]["target_minutes"] == 30


def test_changing_the_priority_of_a_resolved_ticket_re_freezes_it_with_the_current_configuration():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], hours=10)
    _set_priority(staff_api, created["id"], "Crítica")
    resolved = _set_status(staff_api, created["id"], "Resuelto")
    assert resolved["sla"]["target_minutes"] == 120
    assert resolved["sla"]["status"] == "incumplido"

    changed = _put_policies(
        admin_api,
        {"Crítica": 20, "Alta": 12, "Media": 12, "Baja": 24},
    )
    assert changed.status_code == 200

    updated = _set_priority(staff_api, created["id"], "Alta")

    sla = updated["sla"]
    assert updated["status"] == "Resuelto"
    assert sla["target_minutes"] == 720
    started_at = datetime.fromisoformat(sla["started_at"])
    due_at = datetime.fromisoformat(sla["due_at"])
    assert due_at - started_at == timedelta(minutes=720)
    # Resuelto a las 10 h, antes del nuevo vencimiento de 12 h: cumplido.
    assert sla["status"] == "cumplido"
    assert _stored(created["id"]).resolved_target_minutes == 720

    # Un cambio posterior de la configuracion no mueve el SLA re-congelado.
    changed_again = _put_policies(
        admin_api,
        {"Crítica": 20, "Alta": 1, "Media": 12, "Baja": 24},
    )
    assert changed_again.status_code == 200

    detail = _detail(created["id"])
    assert detail["sla"]["target_minutes"] == 720
    assert detail["sla"]["status"] == "cumplido"


def test_a_ticket_without_priority_keeps_sla_null_after_a_configuration_change():
    _register_client(client_api)
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)

    changed = _put_policies(
        admin_api,
        {"Crítica": 0.5, "Alta": 1, "Media": 2, "Baja": 3},
    )
    assert changed.status_code == 200

    assert _detail(created["id"])["sla"] is None
    listing = client_api.get("/api/tickets")
    assert listing.status_code == 200
    assert listing.json()[0]["sla"] is None


# --- RF-76: efecto en vivo sobre tickets activos ---


def _ticket_state(ticket_id: str) -> tuple:
    """Campos del ticket que la configuracion no debe tocar (RF-76)."""
    ticket = _stored(ticket_id)
    return (
        ticket.created_at,
        ticket.priority,
        ticket.status,
        ticket.resolved_at,
        ticket.resolved_target_minutes,
    )


def test_an_active_ticket_reflects_the_current_configuration_on_the_next_read():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], minutes=45)
    _set_priority(staff_api, created["id"], "Crítica")

    before = _detail(created["id"])
    assert before["sla"]["target_minutes"] == 120
    assert before["sla"]["status"] == "en_tiempo"
    assert 70 <= before["sla"]["remaining_minutes"] <= 75
    state = _ticket_state(created["id"])

    changed = _put_policies(
        admin_api,
        {"Crítica": 0.5, "Alta": 4, "Media": 12, "Baja": 24},
    )
    assert changed.status_code == 200

    after = _detail(created["id"])
    sla = after["sla"]
    assert sla["target_minutes"] == 30
    assert sla["remaining_minutes"] == 0
    assert sla["status"] == "incumplido"
    assert sla["breached"] is True
    assert sla["near_due"] is False
    # Solo cambia el SLA derivado: el ticket no se muta (RF-76).
    assert after["created_at"] == before["created_at"]
    assert after["priority"] == "Crítica"
    assert after["status"] == "Abierto"
    assert after["resolved_at"] is None
    assert _ticket_state(created["id"]) == state


def test_an_active_ticket_in_risk_becomes_on_time_when_the_target_is_extended():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], hours=23)
    _set_priority(staff_api, created["id"], "Baja")

    before = _detail(created["id"])
    assert before["sla"]["target_minutes"] == 1440
    assert before["sla"]["status"] == "en_riesgo"
    assert before["sla"]["near_due"] is True

    changed = _put_policies(
        admin_api,
        {"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 48},
    )
    assert changed.status_code == 200

    after = _detail(created["id"])
    sla = after["sla"]
    assert sla["target_minutes"] == 2880
    assert sla["status"] == "en_tiempo"
    assert sla["near_due"] is False
    assert sla["breached"] is False
    assert sla["remaining_minutes"] > 0


def test_the_attention_listing_reflects_entries_and_exits_without_history():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _age_ticket(created["id"], minutes=45)
    _set_priority(staff_api, created["id"], "Crítica")
    second = _create(client_api, title="Segundo")
    _age_ticket(second["id"], hours=23)
    _set_priority(staff_api, second["id"], "Baja")

    def attention_ids() -> list[str]:
        response = staff_api.get("/api/tickets/requiring-attention")
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()]

    assert created["id"] not in attention_ids()
    assert second["id"] in attention_ids()
    states = {
        created["id"]: _ticket_state(created["id"]),
        second["id"]: _ticket_state(second["id"]),
    }

    changed = _put_policies(
        admin_api,
        {"Crítica": 0.5, "Alta": 4, "Media": 12, "Baja": 48},
    )
    assert changed.status_code == 200

    ids = attention_ids()
    assert created["id"] in ids
    assert second["id"] not in ids
    for ticket_id, state in states.items():
        assert _ticket_state(ticket_id) == state


def test_configuration_reads_and_writes_do_not_mutate_tickets():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    active = _create(client_api, title="Activo")
    _set_priority(staff_api, active["id"], "Alta")
    resolved = _create(client_api, title="Resuelto")
    _set_priority(staff_api, resolved["id"], "Media")
    _set_status(staff_api, resolved["id"], "Resuelto")
    before = {
        active["id"]: _ticket_state(active["id"]),
        resolved["id"]: _ticket_state(resolved["id"]),
    }

    assert admin_api.get("/api/sla/policies").status_code == 200
    changed = _put_policies(
        admin_api,
        {"Crítica": 1, "Alta": 1, "Media": 1, "Baja": 1},
    )
    assert changed.status_code == 200

    for ticket_id, state in before.items():
        assert _ticket_state(ticket_id) == state


# --- RF-78: contrato intacto y campo interno no expuesto ---


def test_get_ticket_sla_keeps_its_public_signature():
    parameters = signature(get_ticket_sla).parameters

    assert list(parameters) == ["snapshot", "now"]
    assert parameters["now"].default is None


def test_the_internal_frozen_target_is_not_exposed_in_the_http_contract():
    _register_client(client_api)
    _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    created = _create(client_api)
    _set_priority(staff_api, created["id"], "Crítica")
    _set_status(staff_api, created["id"], "Resuelto")

    detail = _detail(created["id"])
    listing = client_api.get("/api/tickets").json()[0]

    assert "resolved_target_minutes" not in detail
    assert "resolved_target_minutes" not in listing
    assert "resolved_target_minutes" not in detail["sla"]
    assert "resolved_target_minutes" not in listing["sla"]
