"""HU-18 T5: contrato HTTP, sesión y composición real de métricas."""

from datetime import datetime, timedelta, timezone
from importlib import import_module
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.sla.infrastructure.sla_policy_repository import get_sla_policy_repository
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

URL = "/api/dashboard/support-metrics"
PASSWORD = "Hu18TestPassword123"
CREATED = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)
ROLES = ("administrador", "supervisor", "tecnico", "cliente")
EMPTY = {
    "total_tickets": 0, "resolved_tickets": 0, "pending_tickets": 0,
    "average_resolution_minutes": None, "resolution_sample_size": 0,
    "resolution_excluded_count": 0, "sla_compliance_percentage": None,
    "sla_sample_size": 0, "sla_met_count": 0, "sla_excluded_count": 0,
}


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


@pytest.fixture(autouse=True)
def clean_state():
    def reset():
        get_user_repository().clear()
        get_session_store().clear()
        get_ticket_repository().clear()
        get_sla_policy_repository().reset()

    reset()
    yield
    reset()


@pytest.fixture
def session(password_hash):
    clients = []

    def build(role="administrador", company="company-a"):
        user = User(
            id=str(uuid4()), name="Persona privada", email=f"{uuid4()}@example.com",
            password_hash=password_hash, role=role, company_id=company,
        )
        get_user_repository().add(user)
        assert user.company_id == company  # Sin adaptación tenant legacy.
        api = TestClient(app, raise_server_exceptions=False)
        clients.append(api)
        response = api.post("/api/auth/login", json={
            "email": user.email, "password": PASSWORD,
        })
        assert response.status_code == 200, response.text
        return api, user

    yield build
    for api in clients:
        api.close()


def _ticket(**overrides):
    values = dict(
        id=str(uuid4()), title="Título confidencial", description="Contenido privado",
        requester_id=str(uuid4()), company_id="company-a", status="Resuelto",
        priority="Alta", created_at=CREATED,
        resolved_at=CREATED + timedelta(minutes=60), resolved_target_minutes=60,
    )
    ticket = Ticket(**{**values, **overrides})
    get_ticket_repository().add(ticket)
    return ticket


def _forbidden(*args, **kwargs):
    pytest.fail("La consulta denegada/no evaluable no debe leer tickets ni política")


def _http():
    return import_module("app.modules.tickets.interface.metrics_router")


def _assert_contract(body):
    assert set(body) == set(EMPTY)
    for key in EMPTY:
        if key not in {"average_resolution_minutes", "sla_compliance_percentage"}:
            assert type(body[key]) is int
            assert body[key] >= 0
        else:
            assert body[key] is None or type(body[key]) in (int, float)
    assert body["total_tickets"] == body["resolved_tickets"] + body["pending_tickets"]
    assert body["resolved_tickets"] == body["resolution_sample_size"] + body["resolution_excluded_count"]
    assert body["resolved_tickets"] == body["sla_sample_size"] + body["sla_excluded_count"]
    assert 0 <= body["sla_met_count"] <= body["sla_sample_size"] <= body["resolution_sample_size"]


@pytest.mark.parametrize("role", ROLES)
def test_only_administrator_with_company_can_consult(session, monkeypatch, role):
    api, _ = session(role)
    if role != "administrador":
        monkeypatch.setattr(get_ticket_repository(), "snapshot_for_metrics", _forbidden)
    response = api.get(URL, params={"role": "administrador", "company_id": "company-b"})

    if role == "administrador":
        assert response.status_code == 200, response.text
        assert response.json() == EMPTY
    else:
        assert response.status_code == 404, response.text
        assert response.json() == {"detail": "not found"}


@pytest.mark.parametrize("role", ROLES)
def test_account_without_company_gets_uniform_404_without_reading(session, monkeypatch, role):
    api, _ = session(role, company=None)
    monkeypatch.setattr(get_ticket_repository(), "snapshot_for_metrics", _forbidden)
    response = api.get(URL, params={"company_id": "company-a", "actor_role": "administrador"})

    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "not found"}


@pytest.mark.parametrize("session_kind", ("absent", "unknown", "revoked"))
def test_invalid_session_has_401_precedence_before_data_access(session, monkeypatch, session_kind):
    if session_kind == "revoked":
        api, _ = session()
        get_session_store().clear()
    else:
        api = TestClient(app)
        if session_kind == "unknown":
            api.cookies.set("session", "invalid-session-token")
    monkeypatch.setattr(get_ticket_repository(), "snapshot_for_metrics", _forbidden)
    response = api.get(URL, params={"period": "invalid", "page": "-999", "company_id": "company-a"})

    assert response.status_code == 401, response.text
    assert response.json() == {"detail": "not authenticated"}
    if session_kind != "revoked":
        api.close()


def test_empty_authorized_response_preserves_nulls_and_exact_types(session):
    api, _ = session()
    response = api.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == EMPTY
    _assert_contract(response.json())


def test_reference_five_tickets_serializes_independent_samples(session):
    api, _ = session()
    _ticket(status="Abierto", resolved_at=None)
    _ticket(status="En progreso", resolved_at=None)
    _ticket()
    _ticket(status="Cerrado", resolved_at=CREATED + timedelta(minutes=120))
    _ticket(status="Cerrado", resolved_at=None)

    response = api.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "total_tickets": 5, "resolved_tickets": 3, "pending_tickets": 2,
        "average_resolution_minutes": 90.0, "resolution_sample_size": 2,
        "resolution_excluded_count": 1, "sla_compliance_percentage": 50.0,
        "sla_sample_size": 2, "sla_met_count": 1, "sla_excluded_count": 1,
    }
    _assert_contract(response.json())


@pytest.mark.parametrize("case,average,resolution_sample,sla_sample,percentage", (
    ("pending", None, 0, 0, None),
    ("invalid-date", None, 0, 0, None),
    ("no-target", 180, 1, 0, None),
    ("zero-duration", 0, 1, 1, 100),
    ("breached", 180, 1, 1, 0),
))
def test_no_sample_is_distinct_from_zero_and_missing_target_has_no_fallback(
    session, monkeypatch, case, average, resolution_sample, sla_sample, percentage,
):
    api, _ = session()
    overrides = {
        "pending": {"status": "Abierto", "resolved_at": None},
        "invalid-date": {"created_at": None},
        "no-target": {"resolved_at": CREATED + timedelta(minutes=180), "resolved_target_minutes": None},
        "zero-duration": {"resolved_at": CREATED},
        "breached": {"resolved_at": CREATED + timedelta(minutes=180)},
    }
    _ticket(**overrides[case])
    monkeypatch.setattr(get_sla_policy_repository(), "get_target_minutes", _forbidden)

    response = api.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_tickets"] == 1
    assert body["average_resolution_minutes"] == average
    assert body["resolution_sample_size"] == resolution_sample
    assert body["sla_sample_size"] == sla_sample
    assert body["sla_compliance_percentage"] == percentage
    _assert_contract(body)


@pytest.mark.parametrize("company,expected_total,expected_average", (
    ("company-a", 2, 90), ("company-b", 1, 300),
))
def test_response_uses_session_company_not_crossed_links_or_query(
    session, company, expected_total, expected_average,
):
    api, actor = session(company=company)
    _ticket(requester_id="foreign-requester", assignee_id="foreign-technician")
    _ticket(resolved_at=CREATED + timedelta(minutes=120))
    foreign = _ticket(company_id="company-b", requester_id=actor.id, assignee_id=actor.id,
                      resolved_at=CREATED + timedelta(minutes=300))
    legacy = _ticket(company_id=None, requester_id=actor.id, assignee_id=actor.id)

    response = api.get(URL, params={"company_id": "company-b", "requester_id": actor.id})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_tickets"] == expected_total
    assert body["average_resolution_minutes"] == expected_average
    for private in (actor.id, actor.email, actor.name, foreign.id, legacy.id,
                    "Título confidencial", "Contenido privado", "company-a", "company-b"):
        assert private not in response.text
    _assert_contract(body)


@pytest.mark.parametrize("params", (
    {"company_id": "company-b"}, {"period": "invalid", "from": "2100-01-01"},
    {"page": "999", "page_size": "1"}, {"priority": "Baja", "status": "Abierto"},
    {"q": "no coincide", "requester_id": "other", "assignee_id": "other"},
))
def test_unknown_parameters_never_filter_or_expand_the_history(session, params):
    api, _ = session()
    old = datetime(1980, 1, 1, tzinfo=timezone.utc)
    for index in range(35):
        _ticket(created_at=old, resolved_at=old + timedelta(minutes=60))
    _ticket(company_id="company-b")

    baseline = api.get(URL)
    response = api.get(URL, params=params)

    assert baseline.status_code == response.status_code == 200
    assert response.json() == baseline.json()
    assert response.json()["total_tickets"] == 35


def test_real_composition_reads_once_and_only_evaluates_frozen_candidates(session, monkeypatch):
    api, _ = session()
    _ticket()
    _ticket(resolved_at=CREATED + timedelta(minutes=120))
    _ticket(resolved_at=CREATED + timedelta(minutes=180), resolved_target_minutes=None)
    _ticket(company_id="company-b")
    http = _http()
    original_read = get_ticket_repository().snapshot_for_metrics
    original_evaluate = http.evaluate_frozen_resolution
    reads, evaluations = [], []

    def read():
        reads.append(1)
        return original_read()

    def evaluate(*args):
        evaluations.append(args)
        return original_evaluate(*args)

    monkeypatch.setattr(get_ticket_repository(), "snapshot_for_metrics", read)
    monkeypatch.setattr(http, "evaluate_frozen_resolution", evaluate)
    response = api.get(URL)

    assert response.status_code == 200, response.text
    assert reads == [1]
    assert evaluations == [
        ("Alta", CREATED, CREATED + timedelta(minutes=60), 60),
        ("Alta", CREATED, CREATED + timedelta(minutes=120), 60),
    ]
    assert response.json()["average_resolution_minutes"] == 120
    assert response.json()["sla_compliance_percentage"] == 50
    assert response.json()["sla_excluded_count"] == 1


@pytest.mark.parametrize("failing_component", ("reader", "evaluator"))
def test_technical_failure_is_500_not_success_with_zero_or_null(session, monkeypatch, failing_component):
    api, _ = session()
    _ticket()

    def broken(*args):
        raise RuntimeError("private technical failure")

    if failing_component == "reader":
        monkeypatch.setattr(get_ticket_repository(), "snapshot_for_metrics", broken)
    else:
        monkeypatch.setattr(_http(), "evaluate_frozen_resolution", broken)
    response = api.get(URL)

    assert response.status_code == 500
    assert "total_tickets" not in response.text
    assert "private technical failure" not in response.text
