"""HU-14 T5 — API de la configuracion de SLA: consulta (RF-72, RF-75, RF-78).

Mapa RF -> test:
- RF-72: el administrador recibe 200 con el array ordenado de la semilla y
  `hours` numerico; los parametros desconocidos se ignoran; la consulta es
  de solo lectura.
- RF-75: sin sesion -> 401; cliente y tecnico -> 404 uniforme
  `{"detail": "not found"}`; `require_sla_admin` resuelve el 404 desde la
  sesion, nunca desde la peticion.
- RF-78: el router queda registrado y no se usan codigos nuevos.

Un `TestClient` por rol (una sola cookie por cliente), como en HU-05/HU-10.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
)
from app.modules.sla.interface.dependencies import require_sla_admin
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
SEED = [
    {"priority": "Crítica", "hours": 2},
    {"priority": "Alta", "hours": 4},
    {"priority": "Media", "hours": 12},
    {"priority": "Baja", "hours": 24},
]

admin_api = TestClient(app)
staff_api = TestClient(app)
client_api = TestClient(app)
ALL_CLIENTS = (admin_api, staff_api, client_api)


@pytest.fixture(autouse=True)
def clean_state():
    """Aisla usuarios, sesiones, tickets y configuracion global."""
    _clear()
    yield
    _clear()


def _clear() -> None:
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()
    for api in ALL_CLIENTS:
        api.cookies.clear()


def _login(api: TestClient, email: str) -> None:
    logged = api.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200


def _provision(api: TestClient, role: str, email: str) -> None:
    provision_user(
        name="Equipo Soporte",
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(api, email)


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


# --- RF-72: consulta del administrador ---


def test_admin_gets_the_seed_in_catalog_order():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    response = admin_api.get("/api/sla/policies")

    assert response.status_code == 200
    assert response.json() == SEED
    assert [item["priority"] for item in response.json()] == [
        "Crítica",
        "Alta",
        "Media",
        "Baja",
    ]
    for item in response.json():
        assert set(item) == {"priority", "hours"}
        assert isinstance(item["hours"], (int, float))
        assert not isinstance(item["hours"], bool)


def test_unknown_query_parameters_are_ignored():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    response = admin_api.get(
        "/api/sla/policies", params={"company_id": "x", "page": 2}
    )

    assert response.status_code == 200
    assert response.json() == SEED


def test_the_query_does_not_mutate_configuration_or_tickets():
    _register_client(client_api)
    created = client_api.post(
        "/api/tickets",
        json={"title": "Titulo", "description": "Descripcion"},
    )
    assert created.status_code == 201
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    ticket = get_ticket_repository().find_by_id(created.json()["id"])
    assert ticket is not None
    before_ticket = (ticket.priority, ticket.status, ticket.created_at)
    before_policies = get_sla_policy_repository().get_all()

    response = admin_api.get("/api/sla/policies")

    assert response.status_code == 200
    assert get_sla_policy_repository().get_all() == before_policies
    ticket = get_ticket_repository().find_by_id(created.json()["id"])
    assert ticket is not None
    assert (ticket.priority, ticket.status, ticket.created_at) == before_ticket


# --- RF-75: autenticacion y autorizacion ---


def test_no_session_returns_401():
    response = admin_api.get("/api/sla/policies")

    assert response.status_code == 401
    assert set(response.json()) == {"detail"}
    assert "Crítica" not in response.text


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_non_admin_roles_get_the_uniform_404(role):
    if role == "cliente":
        _register_client(client_api)
        target = client_api
    else:
        _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
        target = staff_api

    response = target.get("/api/sla/policies")

    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}
    assert "Crítica" not in response.text


def test_require_sla_admin_rejects_non_admins_with_the_uniform_404():
    current = {"id": "id-1", "email": "x@ejemplo.com", "role": "tecnico"}

    with pytest.raises(HTTPException) as excinfo:
        require_sla_admin(current)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "not found"


def test_require_sla_admin_accepts_the_admin_session():
    current = {"id": "id-1", "email": "x@ejemplo.com", "role": "administrador"}

    assert require_sla_admin(current) is current


# --- RF-78: registro del router ---


def test_the_router_is_registered_in_the_app():
    assert "/api/sla/policies" in app.openapi()["paths"]


# --- RF-73 y RF-74: reemplazo total (PUT) ---

SEED_HOURS = {"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 24}


def _put_policies(api: TestClient, body: dict):
    return api.put("/api/sla/policies", json=body)


def test_admin_replaces_the_configuration_and_gets_the_result():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    response = _put_policies(admin_api, SEED_HOURS)

    assert response.status_code == 200
    assert response.json() == SEED
    assert [item["priority"] for item in response.json()] == [
        "Crítica",
        "Alta",
        "Media",
        "Baja",
    ]


def test_decimal_hours_are_stored_as_integer_minutes_and_reflected_in_get():
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    body = {"Crítica": 0.5, "Alta": 0.25, "Media": 0.02, "Baja": 1}

    response = _put_policies(admin_api, body)

    assert response.status_code == 200
    assert get_sla_policy_repository().get_all() == {
        "Crítica": 30,
        "Alta": 15,
        "Media": 1,
        "Baja": 60,
    }
    detail = admin_api.get("/api/sla/policies").json()
    assert [item["hours"] for item in detail] == [0.5, 0.25, 1 / 60, 1]


def test_saving_150_minutes_returns_hours_2_5():
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    body = {"Crítica": 2.5, "Alta": 4, "Media": 12, "Baja": 24}

    response = _put_policies(admin_api, body)

    assert response.status_code == 200
    assert response.json()[0] == {"priority": "Crítica", "hours": 2.5}
    assert get_sla_policy_repository().get_target_minutes("Crítica") == 150
    assert admin_api.get("/api/sla/policies").json()[0]["hours"] == 2.5


def test_replacing_with_the_same_values_is_idempotent():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    first = _put_policies(admin_api, SEED_HOURS)
    second = _put_policies(admin_api, SEED_HOURS)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json() == SEED
    assert admin_api.get("/api/sla/policies").json() == SEED


def test_two_consecutive_puts_leave_the_last_one():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    _put_policies(
        admin_api, {"Crítica": 1, "Alta": 2, "Media": 3, "Baja": 4}
    )
    last = _put_policies(
        admin_api, {"Crítica": 10, "Alta": 20, "Media": 30, "Baja": 40}
    )

    assert last.status_code == 200
    assert admin_api.get("/api/sla/policies").json() == [
        {"priority": "Crítica", "hours": 10},
        {"priority": "Alta", "hours": 20},
        {"priority": "Media", "hours": 30},
        {"priority": "Baja", "hours": 40},
    ]
    assert get_sla_policy_repository().get_all() == {
        "Crítica": 600,
        "Alta": 1200,
        "Media": 1800,
        "Baja": 2400,
    }


def test_the_configuration_survives_during_the_process():
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    body = {"Crítica": 1.5, "Alta": 2, "Media": 3, "Baja": 4}

    _put_policies(admin_api, body)
    admin_api.get("/api/sla/policies")
    admin_api.get("/api/tickets")

    assert admin_api.get("/api/sla/policies").json() == [
        {"priority": "Crítica", "hours": 1.5},
        {"priority": "Alta", "hours": 2},
        {"priority": "Media", "hours": 3},
        {"priority": "Baja", "hours": 4},
    ]


def test_put_without_a_session_returns_401():
    response = _put_policies(admin_api, SEED_HOURS)

    assert response.status_code == 401
    assert get_sla_policy_repository().get_all() == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_put_is_not_allowed_for_non_admin_roles(role):
    if role == "cliente":
        _register_client(client_api)
        target = client_api
    else:
        _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
        target = staff_api

    response = _put_policies(target, {"Crítica": 1, "Alta": 2, "Media": 3, "Baja": 4})

    assert response.status_code == 404
    assert response.json() == {"detail": "not found"}
    assert get_sla_policy_repository().get_target_minutes("Crítica") == 120


# --- RF-74 y RF-75: validacion 422 y precedencias ---

CUSTOM_HOURS = {"Crítica": 1, "Alta": 2, "Media": 3, "Baja": 4}

FORM_ERROR_BODIES = [
    {},
    {"Crítica": 2, "Alta": 4, "Media": 12},
    {**CUSTOM_HOURS, "Urgente": 1},
    {**CUSTOM_HOURS, "Baja": "24"},
    {**CUSTOM_HOURS, "Baja": True},
    {**CUSTOM_HOURS, "Baja": False},
    {**CUSTOM_HOURS, "Baja": None},
    {**CUSTOM_HOURS, "Baja": [24]},
    {**CUSTOM_HOURS, "Baja": {"horas": 24}},
]

RULE_ERROR_BODIES = [
    {**CUSTOM_HOURS, "Baja": 0},
    {**CUSTOM_HOURS, "Baja": -1},
    {**CUSTOM_HOURS, "Baja": -0.5},
    {**CUSTOM_HOURS, "Baja": 0.001},
]


def _admin_with_custom_configuration() -> list:
    """Deja al administrador logueado con una configuracion no semilla."""
    _provision(admin_api, "administrador", "admin@ejemplo.com")
    assert _put_policies(admin_api, CUSTOM_HOURS).status_code == 200
    return admin_api.get("/api/sla/policies").json()


@pytest.mark.parametrize("body", FORM_ERROR_BODIES)
def test_form_errors_return_422_with_a_detail_list_and_do_not_mutate(body):
    before = _admin_with_custom_configuration()

    response = _put_policies(admin_api, body)

    assert response.status_code == 422
    assert response.status_code != 403
    assert set(response.json()) == {"detail"}
    assert isinstance(response.json()["detail"], list)
    assert admin_api.get("/api/sla/policies").json() == before


@pytest.mark.parametrize("body", RULE_ERROR_BODIES)
def test_rule_errors_return_422_with_a_string_detail_and_do_not_mutate(body):
    before = _admin_with_custom_configuration()

    response = _put_policies(admin_api, body)

    assert response.status_code == 422
    assert response.status_code != 403
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert detail
    assert admin_api.get("/api/sla/policies").json() == before


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_values_are_rejected_without_mutating(literal):
    before = _admin_with_custom_configuration()
    raw = (
        '{"Crítica": 2, "Alta": 4, "Media": 12, "Baja": '
        + literal
        + "}"
    )

    response = admin_api.put(
        "/api/sla/policies",
        content=raw,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert admin_api.get("/api/sla/policies").json() == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {**CUSTOM_HOURS, "Baja": 0},
        {**CUSTOM_HOURS, "Baja": "24"},
    ],
)
def test_no_session_with_an_invalid_body_returns_401(body):
    response = _put_policies(admin_api, body)

    assert response.status_code == 401
    assert response.status_code != 403
    assert set(response.json()) == {"detail"}
    assert get_sla_policy_repository().get_all() == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {**CUSTOM_HOURS, "Baja": 0},
        {**CUSTOM_HOURS, "Baja": "24"},
    ],
)
def test_non_admins_get_the_uniform_404_before_validating_the_body(role, body):
    if role == "cliente":
        _register_client(client_api)
        target = client_api
    else:
        _provision(staff_api, "tecnico", "tecnico@ejemplo.com")
        target = staff_api

    response = _put_policies(target, body)

    assert response.status_code == 404
    assert response.status_code != 403
    assert response.json() == {"detail": "not found"}
    assert get_sla_policy_repository().get_all() == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }


def test_admin_with_an_invalid_body_gets_422_not_404():
    _provision(admin_api, "administrador", "admin@ejemplo.com")

    response = _put_policies(admin_api, {**CUSTOM_HOURS, "Baja": 0})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
