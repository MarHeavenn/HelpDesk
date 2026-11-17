"""HU-19 T7 — estado de la empresa y bloqueo por empresa inactiva.

Cubre RF-136, RF-137 y RF-139 de extremo a extremo:

- Con empresa inactiva, crear una cuenta responde 409 `"empresa no activa"`
  después de validar el cuerpo (422 estructural y de dominio primero).
- Crear un ticket responde 409 antes de validar la entrada (dependencia de
  ruta), también con un cuerpo inválido; 401 y 404 de HU-13 preceden.
- Aceptar una invitación pendiente responde 404 `"invitation not found"`,
  idéntico al token inválido, sin consumir el token ni establecer contraseña;
  el reenvío de la pendiente sigue admitido.
- Inicio de sesión, sesiones vigentes, comentarios, cambios de estado,
  historial y dashboards siguen funcionando.
- Reactivar restaura las altas nuevas sin revivir cuentas desactivadas ni
  tokens vencidos o ya usados.
- Desactivar no elimina ni altera cuentas, tickets ni políticas.
- Una cuenta heredada con `company_id` sin fila en `companies` (estado
  desconocido) no se bloquea (RF-139).
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
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_comment_repository import (
    get_ticket_comment_repository,
)
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

UTC = timezone.utc
PASSWORD = "Secreta123"
# Un solo hash reutilizado acelera la suite sin saltarse la verificación.
PASSWORD_HASH = Argon2PasswordHasher().hash(PASSWORD)
PLATFORM_EMAIL = "plataforma@example.com"
INACTIVE = {"detail": "empresa no activa"}
INVITATION_NOT_FOUND = {"detail": "invitation not found"}
TICKET_PAYLOAD = {
    "title": "No carga la pantalla",
    "description": "La pantalla queda en blanco",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_company_repository().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()
    get_session_store().clear()
    yield
    get_user_repository().clear()
    get_company_repository().clear()
    get_ticket_repository().clear()
    get_ticket_comment_repository().clear()
    get_session_store().clear()


def _company(*, status: str = "active", name: str = "Acme") -> Company:
    company = Company(
        id=str(uuid.uuid4()),
        name=name,
        name_normalized=name.strip().lower(),
        email="contacto@acme.com",
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
    password_hash: str | None = PASSWORD_HASH,
    invitation_token: str | None = None,
    invitation_expires_at: datetime | None = None,
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        name=name,
        email=email or f"{uuid.uuid4().hex}@ejemplo.com",
        password_hash=password_hash,
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
        created_at=datetime.now(UTC),
    )
    get_user_repository().add(user)
    return user


def _platform_admin() -> User:
    return _user(role="administrador", company_id=None, email=PLATFORM_EMAIL)


def _login(email: str) -> TestClient:
    """Cliente HTTP propio por actor: cada `TestClient` tiene una cookie."""
    session = TestClient(app)
    response = session.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return session


def _ticket(company_id: str, requester_id: str) -> Ticket:
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Ticket existente",
        description="Ticket creado antes de desactivar la empresa",
        requester_id=requester_id,
        created_at=datetime.now(UTC),
        company_id=company_id,
    )
    get_ticket_repository().add(ticket)
    return ticket


def _set_status(client: TestClient, company_id: str, status: str) -> None:
    response = client.put(
        f"/api/companies/{company_id}/status", json={"status": status}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == status


# ---------------------------------------------------------------------------
# RF-136 — alta de cuentas bloqueada después de validar el cuerpo
# ---------------------------------------------------------------------------


def test_inactive_company_rejects_new_account_after_validating_the_body():
    company = _company(status="inactive")
    admin = _user(
        role="administrador", company_id=company.id, email="admin@example.com"
    )
    admin_client = _login(admin.email)
    before = len(get_user_repository().list_all())

    valid = admin_client.post(
        "/api/users",
        json={"name": "Nueva Cuenta", "email": "nueva@example.com", "role": "cliente"},
    )
    assert valid.status_code == 409, valid.text
    assert valid.json() == INACTIVE

    # Un cuerpo estructuralmente inválido conserva el 422 estructural de HU-13.
    structural = admin_client.post(
        "/api/users",
        json={"name": "Nueva Cuenta", "role": "cliente"},
    )
    assert structural.status_code == 422, structural.text
    assert isinstance(structural.json()["detail"], list)

    # Un cuerpo válido con datos de dominio inválidos conserva el 422 de dominio.
    domain = admin_client.post(
        "/api/users",
        json={"name": "x", "email": "nueva@example.com", "role": "cliente"},
    )
    assert domain.status_code == 422, domain.text
    assert domain.json() == {"detail": "name must have 2-100 characters"}

    assert len(get_user_repository().list_all()) == before
    assert get_user_repository().find_by_email("nueva@example.com") is None


# ---------------------------------------------------------------------------
# RF-136 / RF-137 — alta de tickets bloqueada antes de validar la entrada
# ---------------------------------------------------------------------------


def test_inactive_company_rejects_new_ticket_before_input_validation():
    company = _company(status="inactive")
    admin = _user(
        role="administrador", company_id=company.id, email="admin@example.com"
    )
    cliente = _user(
        role="cliente", company_id=company.id, email="cliente@example.com"
    )
    supervisor = _user(
        role="supervisor", company_id=company.id, email="supervisor@example.com"
    )
    before = get_ticket_repository().count()
    cliente_client = _login(cliente.email)

    attempts = [
        # Cuerpo ausente y cuerpo fuera de esquema.
        cliente_client.post("/api/tickets", json={}),
        # JSON sintácticamente inválido: el 409 llega antes que el 422.
        cliente_client.post(
            "/api/tickets",
            content="{incompleto",
            headers={"content-type": "application/json"},
        ),
        # Cuerpo válido: también se rechaza.
        cliente_client.post("/api/tickets", json=TICKET_PAYLOAD),
    ]
    for response in attempts:
        assert response.status_code == 409, response.text
        assert response.json() == INACTIVE

    # El administrador de la empresa queda igualmente bloqueado.
    assert (
        _login(admin.email).post("/api/tickets", json={}).status_code == 409
    )
    assert get_ticket_repository().count() == before

    # La precedencia de HU-13 se mantiene: 401 y 404 antes del 409.
    assert TestClient(app).post("/api/tickets", json={}).status_code == 401
    out_of_scope = _login(supervisor.email).post("/api/tickets", json={})
    assert out_of_scope.status_code == 404
    assert out_of_scope.json() == {"detail": "ticket not found"}


# ---------------------------------------------------------------------------
# RF-136 / RF-137 — aceptación bloqueada y reenvío admitido
# ---------------------------------------------------------------------------


def test_inactive_company_acceptance_is_uniform_404_and_resend_stays_allowed():
    _platform_admin()
    company = _company(status="inactive")
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    pending = _user(
        role="administrador",
        company_id=company.id,
        email="pendiente@example.com",
        invitation_status="pending",
        password_hash=None,
        invitation_token="token-empresa-inactiva",
        invitation_expires_at=expires_at,
    )
    before = pending.__dict__.copy()

    blocked = TestClient(app).post(
        "/api/invitations/token-empresa-inactiva/accept",
        json={"password": "validpass"},
    )
    invalid = TestClient(app).post(
        "/api/invitations/token-inexistente/accept",
        json={"password": "validpass"},
    )
    assert blocked.status_code == invalid.status_code == 404
    assert blocked.json() == invalid.json() == INVITATION_NOT_FOUND
    # Sin consumir el token, sin establecer contraseña y sin tocar la cuenta.
    assert pending.__dict__ == before

    # El reenvío de una invitación pendiente no crea cuentas y sigue admitido.
    platform_client = _login(PLATFORM_EMAIL)
    resent = platform_client.post(
        f"/api/companies/{company.id}/administrator/invitation"
    )
    assert resent.status_code == 200, resent.text
    assert resent.json()["company"]["status"] == "inactive"
    assert resent.json()["company"]["administrator_invitation_pending"] is True
    assert pending.invitation_token != "token-empresa-inactiva"
    assert pending.invitation_token
    assert pending.invitation_status == "pending"
    assert pending.password_hash is None
    remaining = pending.invitation_expires_at - datetime.now(UTC)
    assert timedelta(hours=167) < remaining <= timedelta(hours=168)


# ---------------------------------------------------------------------------
# RF-136 / D11 — todo lo demás sigue funcionando
# ---------------------------------------------------------------------------


def test_inactive_company_keeps_login_sessions_comments_status_history_and_dashboards():
    _platform_admin()
    company = _company()
    admin = _user(
        role="administrador",
        company_id=company.id,
        email="admin@example.com",
        name="Admin Empresa",
    )
    cliente = _user(
        role="cliente",
        company_id=company.id,
        email="cliente@example.com",
        name="Cliente Empresa",
    )
    ticket = _ticket(company.id, cliente.id)
    platform_client = _login(PLATFORM_EMAIL)
    admin_client = _login(admin.email)
    cliente_client = _login(cliente.email)

    policies_before = platform_client.get("/api/sla/policies")
    assert policies_before.status_code == 200
    ficha_before = platform_client.get(f"/api/companies/{company.id}").json()

    _set_status(platform_client, company.id, "inactive")

    # Inicio de sesión y sesiones vigentes.
    relogin = _login(cliente.email)
    assert relogin.get("/api/auth/me").status_code == 200
    assert cliente_client.get("/api/auth/me").status_code == 200
    listed = cliente_client.get("/api/tickets")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [ticket.id]

    # Comentarios, cambios de estado de tickets e historial.
    comment = admin_client.post(
        f"/api/tickets/{ticket.id}/comments", json={"body": "Seguimos revisando"}
    )
    assert comment.status_code == 201, comment.text
    status_change = admin_client.put(
        f"/api/tickets/{ticket.id}/status", json={"status": "En progreso"}
    )
    assert status_change.status_code == 200, status_change.text
    history = admin_client.get(f"/api/tickets/{ticket.id}/history")
    assert history.status_code == 200, history.text
    assert len(history.json()) >= 1

    # Dashboards.
    assert admin_client.get("/api/dashboard/tickets").status_code == 200

    # Desactivar no elimina ni altera cuentas, tickets ni políticas.
    policies_after = platform_client.get("/api/sla/policies")
    assert policies_after.status_code == 200
    assert policies_after.json() == policies_before.json()
    ficha_after = platform_client.get(f"/api/companies/{company.id}").json()
    assert ficha_after["status"] == "inactive"
    assert ficha_after["users_total"] == ficha_before["users_total"]
    assert ficha_after["tickets_total"] == ficha_before["tickets_total"]
    stored_ticket = get_ticket_repository().find_by_id(ticket.id)
    assert stored_ticket is not None
    assert stored_ticket.company_id == company.id
    assert stored_ticket.title == ticket.title
    assert get_user_repository().find_by_id(admin.id).status == "active"
    assert get_user_repository().find_by_id(cliente.id).status == "active"
    stored_comments = get_ticket_comment_repository().list_by_ticket(ticket.id)
    assert [item.body for item in stored_comments] == ["Seguimos revisando"]


# ---------------------------------------------------------------------------
# RF-136 — reactivar restaura altas sin revivir cuentas ni tokens
# ---------------------------------------------------------------------------


def test_reactivation_restores_creations_without_reviving_accounts_or_tokens():
    _platform_admin()
    company = _company()
    admin = _user(
        role="administrador", company_id=company.id, email="admin@example.com"
    )
    deactivated = _user(
        role="cliente",
        company_id=company.id,
        email="desactivada@example.com",
        status="deactivated",
    )
    expired = _user(
        role="cliente",
        company_id=company.id,
        email="vencida@example.com",
        invitation_status="pending",
        password_hash=None,
        invitation_token="token-vencido",
        invitation_expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    pending = _user(
        role="cliente",
        company_id=company.id,
        email="pendiente@example.com",
        invitation_status="pending",
        password_hash=None,
        invitation_token="token-valido",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    used = _user(
        role="cliente",
        company_id=company.id,
        email="usada@example.com",
        invitation_status="pending",
        password_hash=None,
        invitation_token="token-usado",
        invitation_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    # El token se usa una vez mientras la empresa está activa.
    accepted_first = TestClient(app).post(
        "/api/invitations/token-usado/accept", json={"password": "validpass"}
    )
    assert accepted_first.status_code == 200, accepted_first.text

    platform_client = _login(PLATFORM_EMAIL)
    admin_client = _login(admin.email)
    _set_status(platform_client, company.id, "inactive")

    # Mientras está inactiva: sin altas nuevas y sin consumir la invitación.
    assert (
        admin_client.post(
            "/api/users",
            json={
                "name": "Cuenta Nueva",
                "email": "nueva@example.com",
                "role": "cliente",
            },
        ).status_code
        == 409
    )
    assert admin_client.post("/api/tickets", json=TICKET_PAYLOAD).status_code == 409
    blocked_acceptance = TestClient(app).post(
        "/api/invitations/token-valido/accept", json={"password": "validpass"}
    )
    assert blocked_acceptance.status_code == 404
    assert pending.invitation_token == "token-valido"
    assert pending.invitation_status == "pending"
    assert pending.password_hash is None

    _set_status(platform_client, company.id, "active")

    # Las altas nuevas vuelven a funcionar.
    created = admin_client.post(
        "/api/users",
        json={
            "name": "Cuenta Nueva",
            "email": "nueva@example.com",
            "role": "cliente",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["company_id"] == company.id
    assert admin_client.post("/api/tickets", json=TICKET_PAYLOAD).status_code == 201

    # La cuenta desactivada sigue desactivada y no puede iniciar sesión.
    assert get_user_repository().find_by_id(deactivated.id).status == "deactivated"
    assert (
        TestClient(app)
        .post(
            "/api/auth/login",
            json={"email": deactivated.email, "password": PASSWORD},
        )
        .status_code
        == 401
    )
    # Los tokens vencidos y ya usados no reviven.
    assert (
        TestClient(app)
        .post("/api/invitations/token-vencido/accept", json={"password": "validpass"})
        .status_code
        == 404
    )
    assert (
        TestClient(app)
        .post("/api/invitations/token-usado/accept", json={"password": "validpass"})
        .status_code
        == 404
    )
    # La invitación pendiente no se consumió: el mismo token sigue siendo
    # aceptable si no ha expirado.
    resumed = TestClient(app).post(
        "/api/invitations/token-valido/accept", json={"password": "validpass"}
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["invitation_status"] == "accepted"
    assert get_user_repository().find_by_id(expired.id).invitation_status == "pending"


# ---------------------------------------------------------------------------
# RF-139 — datos heredados: empresa desconocida no bloquea
# ---------------------------------------------------------------------------


def test_legacy_company_id_without_a_company_row_is_not_blocked():
    # Fixtures de HU-13 usan `company_id="c1"` sin fila en `companies`: el
    # estado es desconocido (`None`) y NO debe bloquear ninguna alta.
    admin = _user(
        role="administrador", company_id="c1", email="admin@example.com"
    )
    cliente = _user(role="cliente", company_id="c1", email="cliente@example.com")
    assert get_company_repository().find_by_id("c1") is None

    admin_client = _login(admin.email)
    created = admin_client.post(
        "/api/users",
        json={"name": "Cuenta Nueva", "email": "nueva@example.com", "role": "cliente"},
    )
    assert created.status_code == 201, created.text

    cliente_client = _login(cliente.email)
    ticket = cliente_client.post("/api/tickets", json=TICKET_PAYLOAD)
    assert ticket.status_code == 201, ticket.text

    invited = get_user_repository().find_by_email("nueva@example.com")
    assert invited is not None and invited.invitation_token
    accepted = TestClient(app).post(
        f"/api/invitations/{invited.invitation_token}/accept",
        json={"password": "validpass"},
    )
    assert accepted.status_code == 200, accepted.text
