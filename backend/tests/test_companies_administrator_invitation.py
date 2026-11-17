"""HU-19 T5 — invitación y reenvío del administrador (RF-135, RF-141, RO-02).

Cubre la operación única `POST /api/companies/{company_id}/administrator/invitation`:

- La rama se resuelve antes de leer el cuerpo, con `list_company_administrators`
  ordenado por `created_at` y luego `id`: con administradora `active`/`accepted`
  responde 409 `"la empresa ya tiene administrador"` aunque el cuerpo sea
  inválido.
- Rama de reenvío: 200 sobre la pendiente activa más antigua, rotación del
  token, reinicio de 168 h y 422 de dominio
  `"resend does not accept name or email"` si el cuerpo trae nombre o correo.
- Rama de invitación: 201 con cuenta `active`/`pending`, 422 estructural si
  faltan campos y 422 de dominio `"name and email are required"` cuando no hay
  valores utilizables.
- Correo ya usado → 409 `"correo no disponible"`, también con empresa inactiva
  (el correo se evalúa antes que el estado); empresa inactiva sin conflicto →
  409 `"empresa no activa"` solo en la rama de invitación.
- `email_status` sale de `send_invitation` (`sent`, `failed`, `not-attempted`)
  sin cambiar el código de éxito, con doble de envío y sin `SMTP_HOST`.
- Ninguna respuesta expone token, enlace ni hash.
- La aceptación bloqueada por empresa inactiva responde 404 `"invitation not
  found"`, idéntico al token inválido y sin consumir el token (T7).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure.company_repository import (
    get_company_repository,
)
from app.modules.identity.application import invitations
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository

UTC = timezone.utc
ENDPOINT = "/api/companies/{company_id}/administrator/invitation"

FICHA_KEYS = {
    "id",
    "name",
    "email",
    "phone",
    "contact_name",
    "status",
    "created_at",
    "users_total",
    "tickets_total",
    "tickets_by_status",
    "has_administrator",
    "administrator_invitation_pending",
}

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures y utilidades
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    get_user_repository().clear()
    get_company_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_company_repository().clear()
    get_session_store().clear()
    client.cookies.clear()


def _company(
    name: str = "Acme",
    *,
    company_id: str | None = None,
    status: str = "active",
) -> Company:
    company = Company(
        id=company_id or str(uuid.uuid4()),
        name=name,
        name_normalized=name.strip().lower(),
        email="contacto@acme.com",
        phone=None,
        contact_name=None,
        status=status,
        created_at=datetime.now(UTC),
    )
    get_company_repository().add(company)
    return company


def _user(
    *,
    role: str = "cliente",
    company_id: str | None = None,
    email: str | None = None,
    name: str = "Cuenta Test",
    status: str = "active",
    invitation_status: str = "accepted",
    created_at: datetime | None = None,
    invitation_token: str | None = None,
    invitation_expires_at: datetime | None = None,
    password_hash: str | None = None,
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email or f"{uuid.uuid4().hex}@ejemplo.com",
        password_hash=(
            password_hash
            if password_hash is not None
            else Argon2PasswordHasher().hash("Secreta123")
        ),
        role=role,
        company_id=company_id,
        status=status,
        invitation_status=invitation_status,
        invitation_token=invitation_token,
        invitation_token_hash=(
            hashlib.sha256(invitation_token.encode("utf-8")).hexdigest()
            if invitation_token
            else None
        ),
        invitation_expires_at=invitation_expires_at,
        created_at=created_at or datetime.now(UTC),
    )
    get_user_repository().add(user)
    return user


def _platform_admin(email: str = "plataforma@example.com") -> User:
    return _user(role="administrador", company_id=None, email=email)


def _login(email: str) -> TestClient:
    new_client = TestClient(app)
    response = new_client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert response.status_code == 200, response.text
    return new_client


def _assert_168_hour_lifetime(expires_at: datetime | None) -> None:
    assert expires_at is not None
    remaining = expires_at - datetime.now(UTC)
    assert timedelta(hours=167) < remaining <= timedelta(hours=168)


def _administrators(company_id: str) -> list[User]:
    return [
        user
        for user in get_user_repository().list_all()
        if user.company_id == company_id and user.role == "administrador"
    ]


def _assert_no_secret(payload_text: str, *users: User) -> None:
    lowered = payload_text.lower()
    assert "token" not in lowered
    assert "hash" not in lowered
    assert "/invitations/" not in lowered
    for user in users:
        if user.invitation_token:
            assert user.invitation_token not in payload_text
        if user.invitation_token_hash:
            assert user.invitation_token_hash not in payload_text


# ---------------------------------------------------------------------------
# Resolución de la rama antes del cuerpo
# ---------------------------------------------------------------------------


def test_accepted_administrator_returns_409_before_reading_an_invalid_body():
    _platform_admin()
    active = _company("Activa")
    _user(
        role="administrador",
        company_id=active.id,
        email="admin.activa@example.com",
        invitation_status="accepted",
    )
    inactive = _company("Inactiva", status="inactive")
    _user(
        role="administrador",
        company_id=inactive.id,
        email="admin.inactiva@example.com",
        invitation_status="accepted",
    )
    admin_client = _login("plataforma@example.com")
    before = len(get_user_repository().list_all())

    for company in (active, inactive):
        for body in ({}, {"name": 1, "email": ["no-es-texto"]}, [1, 2, 3]):
            response = admin_client.post(
                ENDPOINT.format(company_id=company.id), json=body
            )
            assert response.status_code == 409, response.text
            assert response.json() == {"detail": "la empresa ya tiene administrador"}

        malformed = admin_client.post(
            ENDPOINT.format(company_id=company.id),
            content="{incompleto",
            headers={"content-type": "application/json"},
        )
        assert malformed.status_code == 409, malformed.text
        assert malformed.json() == {"detail": "la empresa ya tiene administrador"}

    assert len(get_user_repository().list_all()) == before


def test_invitation_branch_ignores_deactivated_accepted_administrator():
    _platform_admin()
    company = _company("Acme")
    _user(
        role="administrador",
        company_id=company.id,
        email="antiguo@example.com",
        status="deactivated",
        invitation_status="accepted",
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        json={"name": "Nueva Admin", "email": "nueva@example.com"},
    )

    assert response.status_code == 201, response.text
    created = get_user_repository().find_by_email("nueva@example.com")
    assert created is not None
    assert created.role == "administrador"
    assert created.status == "active"
    assert created.invitation_status == "pending"


# ---------------------------------------------------------------------------
# Rama de reenvío
# ---------------------------------------------------------------------------


def test_resend_rotates_oldest_pending_token_and_restarts_168_hours():
    _platform_admin()
    company = _company("Acme")
    old_expiry = datetime.now(UTC) - timedelta(hours=1)
    oldest = _user(
        role="administrador",
        company_id=company.id,
        email="oldest@example.com",
        invitation_status="pending",
        created_at=datetime.now(UTC) - timedelta(days=2),
        invitation_token="token-mas-antiguo",
        invitation_expires_at=old_expiry,
    )
    newest = _user(
        role="administrador",
        company_id=company.id,
        email="newest@example.com",
        invitation_status="pending",
        created_at=datetime.now(UTC) - timedelta(days=1),
        invitation_token="token-mas-reciente",
        invitation_expires_at=old_expiry,
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(ENDPOINT.format(company_id=company.id))

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"company", "email_status"}
    assert set(body["company"]) == FICHA_KEYS
    assert body["company"]["id"] == company.id
    assert body["company"]["has_administrator"] is False
    assert body["company"]["administrator_invitation_pending"] is True
    assert body["company"]["users_total"] == 2
    assert body["email_status"] == "not-attempted"
    _assert_no_secret(response.text, oldest, newest)

    assert oldest.invitation_token != "token-mas-antiguo"
    assert oldest.invitation_token
    _assert_168_hour_lifetime(oldest.invitation_expires_at)
    # La pendiente más reciente no se toca.
    assert newest.invitation_token == "token-mas-reciente"
    assert newest.invitation_expires_at == old_expiry

    # El token anterior queda invalidado y el nuevo sigue siendo de un solo uso.
    assert (
        TestClient(app)
        .post(
            "/api/invitations/token-mas-antiguo/accept",
            json={"password": "validpass"},
        )
        .status_code
        == 404
    )
    accepted = TestClient(app).post(
        f"/api/invitations/{oldest.invitation_token}/accept",
        json={"password": "validpass"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["invitation_status"] == "accepted"


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Otra Persona"},
        {"email": "otra@example.com"},
        {"name": None},
        {"email": None},
        {"name": "Otra Persona", "email": "otra@example.com"},
    ],
)
def test_resend_rejects_name_or_email_with_domain_422_without_mutating(body):
    _platform_admin()
    company = _company("Acme")
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pending@example.com",
        invitation_status="pending",
        invitation_token="token-pendiente",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(ENDPOINT.format(company_id=company.id), json=body)

    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "resend does not accept name or email"}
    assert pending.invitation_token == "token-pendiente"
    assert pending.invitation_status == "pending"


@pytest.mark.parametrize(
    "body",
    [
        {"company_id": "otra-empresa"},
        {"company": "otra-empresa"},
        {"empresa": "otra-empresa"},
        {"phone": "555"},
        {"status": "active"},
        {"company_id": "otra-empresa", "phone": "555"},
    ],
)
def test_resend_rejects_other_fields_with_structural_422_without_mutating(body):
    _platform_admin()
    company = _company("Acme")
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pending@example.com",
        invitation_status="pending",
        invitation_token="token-pendiente",
        invitation_expires_at=expires_at,
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(ENDPOINT.format(company_id=company.id), json=body)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    for error in detail:
        assert error["loc"][0] == "body"
        assert "url" not in error
        assert "input" not in error
    # Sin efectos secundarios: ni rota el token ni toca la invitación.
    assert pending.invitation_token == "token-pendiente"
    assert pending.invitation_expires_at == expires_at
    assert pending.invitation_status == "pending"


def test_resend_structural_rejection_precedes_the_domain_message_without_mutating():
    _platform_admin()
    company = _company("Acme")
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pending@example.com",
        invitation_status="pending",
        invitation_token="token-pendiente",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        json={"name": "Otra Persona", "phone": "555"},
    )

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any(error["type"] == "extra_forbidden" for error in detail)
    assert pending.invitation_token == "token-pendiente"


def test_resend_rejects_malformed_json_with_structural_422_without_mutating():
    _platform_admin()
    company = _company("Acme")
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pending@example.com",
        invitation_status="pending",
        invitation_token="token-pendiente",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        content="{incompleto",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422, response.text
    assert isinstance(response.json()["detail"], list)
    assert pending.invitation_token == "token-pendiente"


# ---------------------------------------------------------------------------
# Rama de invitación
# ---------------------------------------------------------------------------


def test_invitation_creates_pending_administrator_and_returns_201():
    _platform_admin()
    company = _company("Acme")
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        json={"name": "  Ana López ", "email": "ANA@Example.COM"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"company", "email_status"}
    assert body["email_status"] == "not-attempted"
    assert set(body["company"]) == FICHA_KEYS
    assert body["company"]["users_total"] == 1
    assert body["company"]["has_administrator"] is False
    assert body["company"]["administrator_invitation_pending"] is True
    assert body["company"]["status"] == "active"
    _assert_no_secret(response.text)

    created = get_user_repository().find_by_email("ana@example.com")
    assert created is not None
    assert created.name == "Ana López"
    assert created.company_id == company.id
    assert created.role == "administrador"
    assert created.status == "active"
    assert created.invitation_status == "pending"
    assert created.password_hash is None
    assert created.invitation_token
    _assert_168_hour_lifetime(created.invitation_expires_at)
    _assert_no_secret(response.text, created)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Ana"},
        {"email": "ana@example.com"},
        {"name": None, "email": None},
    ],
)
def test_invitation_missing_fields_are_structural_422(body):
    _platform_admin()
    company = _company("Acme")
    admin_client = _login("plataforma@example.com")
    before = len(get_user_repository().list_all())

    response = admin_client.post(ENDPOINT.format(company_id=company.id), json=body)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    for error in detail:
        assert error["loc"][0] == "body"
        assert "url" not in error
        assert "input" not in error
    assert len(get_user_repository().list_all()) == before
    assert _administrators(company.id) == []


@pytest.mark.parametrize(
    "body",
    [
        {"name": "   ", "email": "   "},
        {"name": "   ", "email": "ana@example.com"},
        {"name": "Ana", "email": "   "},
    ],
)
def test_invitation_without_usable_values_is_domain_422(body):
    _platform_admin()
    company = _company("Acme")
    admin_client = _login("plataforma@example.com")

    response = admin_client.post(ENDPOINT.format(company_id=company.id), json=body)

    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "name and email are required"}
    assert _administrators(company.id) == []


# ---------------------------------------------------------------------------
# Conflictos de correo y estado de la empresa
# ---------------------------------------------------------------------------


def test_email_conflict_is_409_before_company_status_in_both_companies():
    _platform_admin()
    active = _company("Activa")
    inactive = _company("Inactiva", status="inactive")
    other = _company("Otra")
    _user(role="cliente", company_id=other.id, email="tomado@example.com")
    admin_client = _login("plataforma@example.com")
    before = len(get_user_repository().list_all())

    for company in (active, inactive):
        response = admin_client.post(
            ENDPOINT.format(company_id=company.id),
            json={"name": "Admin Tomada", "email": "tomado@example.com"},
        )
        assert response.status_code == 409, response.text
        assert response.json() == {"detail": "correo no disponible"}

    assert len(get_user_repository().list_all()) == before
    assert _administrators(active.id) == []
    assert _administrators(inactive.id) == []


def test_inactive_company_blocks_only_the_invitation_branch_and_allows_resend():
    _platform_admin()
    company = _company("Inactiva", status="inactive")
    admin_client = _login("plataforma@example.com")

    blocked = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        json={"name": "Admin Nueva", "email": "nueva@example.com"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json() == {"detail": "empresa no activa"}
    assert _administrators(company.id) == []

    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pendiente@example.com",
        invitation_status="pending",
        invitation_token="token-inactiva",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    resent = admin_client.post(ENDPOINT.format(company_id=company.id))

    assert resent.status_code == 200, resent.text
    assert set(resent.json()) == {"company", "email_status"}
    assert resent.json()["company"]["status"] == "inactive"
    assert pending.invitation_token != "token-inactiva"


# ---------------------------------------------------------------------------
# email_status (RO-02)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("email_status", ["sent", "failed", "not-attempted"])
def test_email_status_comes_from_send_invitation_without_changing_success_code(
    monkeypatch: pytest.MonkeyPatch, email_status: str
):
    _platform_admin()
    company = _company("Acme")
    if email_status == "not-attempted":
        monkeypatch.delenv("SMTP_HOST", raising=False)
    else:
        monkeypatch.setenv("SMTP_HOST", "smtp.example.test")

        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                if email_status == "failed":
                    raise OSError("delivery failed")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def starttls(self):
                pass

            def send_message(self, message):
                pass

        monkeypatch.setattr(invitations.smtplib, "SMTP", FakeSMTP)

    admin_client = _login("plataforma@example.com")

    created = admin_client.post(
        ENDPOINT.format(company_id=company.id),
        json={"name": "Ana Admin", "email": "ana@example.com"},
    )
    pending = get_user_repository().find_by_email("ana@example.com")
    assert pending is not None
    resent = admin_client.post(ENDPOINT.format(company_id=company.id))

    assert created.status_code == 201, created.text
    assert resent.status_code == 200, resent.text
    assert created.json()["email_status"] == email_status
    assert resent.json()["email_status"] == email_status
    assert "Invitation-Delivery" not in created.headers
    assert "Invitation-Delivery" not in resent.headers
    assert pending.invitation_status == "pending"
    _assert_no_secret(created.text, pending)
    _assert_no_secret(resent.text, pending)


# ---------------------------------------------------------------------------
# Alcance y precedencia 401 -> 404
# ---------------------------------------------------------------------------


def test_sessions_outside_platform_scope_get_401_and_uniform_404():
    company = _company("Acme")
    url = ENDPOINT.format(company_id=company.id)

    anonymous = TestClient(app)
    assert anonymous.post(url, json={}).status_code == 401

    _platform_admin()
    accounts = {
        "company-admin@example.com": dict(role="administrador", company_id=company.id),
        "supervisor@example.com": dict(role="supervisor", company_id=company.id),
        "tecnico@example.com": dict(role="tecnico", company_id=company.id),
        "cliente@example.com": dict(role="cliente", company_id=company.id),
    }
    for email, scope in accounts.items():
        _user(email=email, **scope)

    for email in accounts:
        scoped_client = _login(email)
        response = scoped_client.post(url, json={"name": 1})
        assert response.status_code == 404, (email, response.text)
        assert response.json() == {"detail": "company not found"}

    platform_client = _login("plataforma@example.com")
    missing = platform_client.post(
        ENDPOINT.format(company_id="no-existe"), json={"name": 1}
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "company not found"}


# ---------------------------------------------------------------------------
# Aceptación bloqueada por empresa inactiva (RF-136, RF-137)
# ---------------------------------------------------------------------------


def test_acceptance_of_inactive_company_invitation_is_404_without_consuming_token():
    _platform_admin()
    company = _company("Inactiva", status="inactive")
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pendiente@example.com",
        invitation_status="pending",
        invitation_token="token-empresa-inactiva",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
        password_hash=None,
    )
    before_hash = pending.password_hash
    before_token = pending.invitation_token

    response = TestClient(app).post(
        "/api/invitations/token-empresa-inactiva/accept",
        json={"password": "validpass"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "invitation not found"}
    assert pending.invitation_status == "pending"
    assert pending.password_hash == before_hash
    assert pending.invitation_token == before_token
    assert pending.invitation_token_hash is not None
