"""HU-19 T4 — casos de uso y rutas de datos de empresa.

Cubre RF-125 a RF-131, RF-135, RF-137, RF-142 y RF-143:

- Las siete rutas de datos de empresa responden con la ficha exacta de
  RF-143 (doce claves, sin datos de cuentas ni tickets ajenos).
- `GET/PATCH /api/companies/me` se registran antes de `/{company_id}` y la
  empresa se deriva solo de la sesión; `me` nunca se resuelve como id.
- El catálogo ordena por forma normalizada en code points con desempate por
  `created_at` y luego `id`, y devuelve `[]` con 200.
- El alta sin administrador responde 201 `{company}` sin `email_status`; con
  administrador completo responde 201 `{company, email_status}` y crea la
  cuenta pendiente en la misma operación, con rollback completo si el correo
  está tomado (PostgreSQL y memoria).
- Errores estructurales con `detail` lista y de dominio con `detail` cadena,
  literal exacto, sin mutaciones.
- Precedencia 401 -> 404 -> 422 estructural -> 409 `empresa no disponible`
  -> 422 de dominio.
- Dos altas simultáneas con el mismo nombre normalizado producen un solo
  éxito gracias al bloqueo de T1.
- `PUT .../status` es idempotente y no produce 409.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.infrastructure import db
from app.main import app
from app.modules.companies.application.company_lifecycle import create_company
from app.modules.companies.application.errors import CompanyConflictError
from app.modules.identity.application.users import UserEmailConflictError
from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
    get_company_repository,
)
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    InMemoryUserRepository,
    get_user_repository,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

client = TestClient(app)

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
STATUS_KEYS = {"Abierto", "En progreso", "Resuelto", "Cerrado"}

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Fixtures y utilidades
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    get_user_repository().clear()
    get_company_repository().clear()
    get_ticket_repository().clear()
    get_session_store().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_company_repository().clear()
    get_ticket_repository().clear()
    get_session_store().clear()
    client.cookies.clear()


@pytest.fixture
def in_memory_environment(monkeypatch: pytest.MonkeyPatch):
    """Fuerza el seam en memoria y deja el repositorio global vacío."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    get_company_repository().clear()
    get_user_repository().clear()


def _company(
    name: str = "Acme",
    *,
    company_id: str | None = None,
    status: str = "active",
    email: str | None = "contacto@acme.com",
    phone: str | None = None,
    contact_name: str | None = None,
    created_at: datetime | None = None,
    normalized: str | None = None,
) -> Company:
    company = Company(
        id=company_id or str(uuid.uuid4()),
        name=name,
        name_normalized=(
            normalized if normalized is not None else name.strip().lower()
        ),
        email=email,
        phone=phone,
        contact_name=contact_name,
        status=status,
        created_at=created_at or datetime.now(UTC),
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
    user_id: str | None = None,
) -> User:
    user = User(
        id=user_id or str(uuid.uuid4()),
        name=name,
        email=email or f"{uuid.uuid4().hex}@ejemplo.com",
        password_hash=Argon2PasswordHasher().hash("Secreta123"),
        role=role,
        company_id=company_id,
        status=status,
        invitation_status=invitation_status,
    )
    get_user_repository().add(user)
    return user


def _platform_admin(email: str = "plataforma@example.com") -> User:
    return _user(role="administrador", company_id=None, email=email)


def _login(email: str) -> None:
    response = client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert response.status_code == 200, response.text


def _logout() -> None:
    client.cookies.clear()


def _company_count() -> int:
    return get_company_repository().count()


def _user_count() -> int:
    return get_user_repository().count()


def _persistent_row(normalized: str) -> dict | None:
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD")):
        return None
    with db.connection() as conn:
        return conn.execute(
            "SELECT id, name, name_normalized, email, phone, contact_name, status "
            "FROM companies WHERE name_normalized = %s",
            (normalized,),
        ).fetchone()


def _assert_ficha(body: dict) -> None:
    assert set(body) == FICHA_KEYS
    assert body["status"] in {"active", "inactive"}
    assert set(body["tickets_by_status"]) == STATUS_KEYS
    assert sum(body["tickets_by_status"].values()) == body["tickets_total"]
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.tzinfo is not None
    assert created_at.utcoffset() is not None


def _structural_locations(response) -> list[tuple[str, ...]]:
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    return [tuple(item["loc"]) for item in detail]


# ---------------------------------------------------------------------------
# RF-143 — ficha exacta
# ---------------------------------------------------------------------------


def test_ficha_has_exact_representation_and_aggregates():
    company = _company(
        "Acme", email="contacto@acme.com", phone="555", contact_name="Ana"
    )
    other = _company("Otra")

    _user(company_id=company.id, role="administrador", invitation_status="pending")
    _user(company_id=company.id, role="cliente", status="deactivated")
    _user(company_id=company.id, role="supervisor")
    _user(company_id=other.id, role="administrador", invitation_status="accepted")

    for status, amount in (
        ("Abierto", 2),
        ("En progreso", 1),
        ("Resuelto", 0),
        ("Cerrado", 1),
    ):
        for _ in range(amount):
            get_ticket_repository().add(
                Ticket(
                    id=str(uuid.uuid4()),
                    title="Ticket",
                    description="Descripción",
                    requester_id=str(uuid.uuid4()),
                    created_at=datetime.now(UTC),
                    status=status,
                    company_id=company.id,
                )
            )
    # Ticket de otra empresa y ticket heredado sin empresa: fuera del reparto.
    get_ticket_repository().add(
        Ticket(
            id=str(uuid.uuid4()),
            title="Ajeno",
            description="Descripción",
            requester_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
            status="Abierto",
            company_id=other.id,
        )
    )
    get_ticket_repository().add(
        Ticket(
            id=str(uuid.uuid4()),
            title="Sin empresa",
            description="Descripción",
            requester_id=str(uuid.uuid4()),
            created_at=datetime.now(UTC),
            status="Abierto",
            company_id=None,
        )
    )

    platform = _platform_admin()
    _login(platform.email)

    response = client.get(f"/api/companies/{company.id}")

    assert response.status_code == 200
    body = response.json()
    _assert_ficha(body)
    assert body["id"] == company.id
    assert body["name"] == "Acme"
    assert body["email"] == "contacto@acme.com"
    assert body["phone"] == "555"
    assert body["contact_name"] == "Ana"
    assert body["status"] == "active"
    assert body["users_total"] == 3
    assert body["tickets_total"] == 4
    assert body["tickets_by_status"] == {
        "Abierto": 2,
        "En progreso": 1,
        "Resuelto": 0,
        "Cerrado": 1,
    }
    assert body["has_administrator"] is False
    assert body["administrator_invitation_pending"] is True


def test_ficha_created_at_is_utc_iso_with_offset():
    company = _company(
        "Hora", created_at=datetime(2026, 4, 5, 10, 30, tzinfo=timezone.utc)
    )
    _login(_platform_admin().email)

    body = client.get(f"/api/companies/{company.id}").json()

    assert body["created_at"].startswith("2026-04-05T10:30:00")
    assert body["created_at"].endswith("+00:00")


# ---------------------------------------------------------------------------
# RF-129 — catálogo
# ---------------------------------------------------------------------------


def test_catalog_orders_by_normalized_name_created_at_and_id():
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, tzinfo=UTC)
    t3 = datetime(2026, 1, 3, tzinfo=UTC)
    first_beta = _company(
        "  beta ",
        company_id="00000000-0000-0000-0000-000000000002",
        created_at=t1,
    )
    second_beta = _company(
        "Beta",
        company_id="00000000-0000-0000-0000-000000000001",
        created_at=t2,
    )
    third_beta = _company(
        "BETA",
        company_id="00000000-0000-0000-0000-000000000003",
        created_at=t2,
    )
    zeta = _company("Zeta", created_at=t3)
    # «á» (U+00E1) queda después de «z» (U+007A) en code points.
    angel = _company("Ángel", created_at=t1)

    _login(_platform_admin().email)
    response = client.get("/api/companies")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert [item["id"] for item in body] == [
        first_beta.id,
        second_beta.id,
        third_beta.id,
        zeta.id,
        angel.id,
    ]
    for item in body:
        _assert_ficha(item)


def test_catalog_empty_returns_200_with_empty_list():
    _login(_platform_admin().email)

    response = client.get("/api/companies")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# RF-126, RF-127, RF-135 — alta
# ---------------------------------------------------------------------------


def test_create_company_without_administrator_returns_company_only():
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "  Acme S.A.  ",
            "email": "  Contacto@Acme.COM ",
            "phone": "  555-0100  ",
            "contact_name": "  Ana Pérez  ",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"company"}
    company = body["company"]
    _assert_ficha(company)
    assert company["name"] == "Acme S.A."
    assert company["email"] == "contacto@acme.com"
    assert company["phone"] == "555-0100"
    assert company["contact_name"] == "Ana Pérez"
    assert company["status"] == "active"
    assert company["users_total"] == 0
    assert company["tickets_total"] == 0
    assert company["has_administrator"] is False
    assert company["administrator_invitation_pending"] is False

    stored = get_company_repository().find_by_id(company["id"])
    assert stored is not None
    assert stored.name_normalized == "acme s.a."
    if os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD"):
        assert _persistent_row("acme s.a.") is not None


def test_create_company_with_administrator_null_is_company_only():
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={"name": "Sin Admin", "email": "sin@admin.com", "administrator": None},
    )

    assert response.status_code == 201
    assert set(response.json()) == {"company"}
    assert response.json()["company"]["users_total"] == 0
    assert response.json()["company"]["has_administrator"] is False


def test_create_company_with_administrator_returns_email_status_and_pending_account():
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "Con Admin",
            "email": "contacto@conadmin.com",
            "administrator": {
                "name": "Admin Inicial",
                "email": "Admin.Inicial@Example.COM",
            },
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"company", "email_status"}
    assert body["email_status"] == "not-attempted"
    company = body["company"]
    _assert_ficha(company)
    assert company["users_total"] == 1
    assert company["has_administrator"] is False
    assert company["administrator_invitation_pending"] is True

    admin = get_user_repository().find_by_email("admin.inicial@example.com")
    assert admin is not None
    assert admin.company_id == company["id"]
    assert admin.role == "administrador"
    assert admin.status == "active"
    assert admin.invitation_status == "pending"
    assert admin.password_hash is None
    assert admin.invitation_token_hash is not None
    assert admin.invitation_expires_at is not None


def test_create_company_email_status_does_not_change_success_code(monkeypatch):
    import app.modules.companies.application.company_lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "send_invitation", lambda user, token: "sent")
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "Enviada",
            "email": "env@example.com",
            "administrator": {"name": "Admin", "email": "admin@env.com"},
        },
    )

    assert response.status_code == 201
    assert response.json()["email_status"] == "sent"


def test_create_company_rolls_back_when_admin_email_is_taken_in_memory(
    in_memory_environment,
    monkeypatch,
):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    taken = _user(email="tomado@example.com", role="cliente", company_id=None)
    platform = _platform_admin("plataforma2@example.com")
    _login(platform.email)

    companies_before = _company_count()
    users_before = _user_count()

    response = client.post(
        "/api/companies",
        json={
            "name": "Rollback Memoria",
            "email": "rollback@example.com",
            "administrator": {"name": "Admin", "email": taken.email},
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "correo no disponible"}
    assert _company_count() == companies_before
    assert _user_count() == users_before
    assert get_company_repository().find_by_name_normalized("rollback memoria") is None


def test_create_company_rolls_back_when_admin_email_is_taken_in_postgres():
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD")):
        pytest.skip("PostgreSQL no configurado")
    taken = _user(email="tomado@example.com", role="cliente", company_id=None)
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "Rollback Postgres",
            "email": "rollback@example.com",
            "administrator": {"name": "Admin", "email": taken.email},
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "correo no disponible"}
    assert get_company_repository().find_by_name_normalized("rollback postgres") is None
    assert _persistent_row("rollback postgres") is None


# ---------------------------------------------------------------------------
# 422 estructural del alta (RF-143)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, expected_loc",
    [
        ({"email": "contacto@acme.com"}, ("body", "name")),
        ({"name": "Acme"}, ("body", "email")),
        ({"name": None, "email": "contacto@acme.com"}, ("body", "name")),
        ({"name": "Acme", "email": None}, ("body", "email")),
        (
            {
                "name": "Acme",
                "email": "contacto@acme.com",
                "administrator": {},
            },
            ("body", "administrator", "name"),
        ),
        (
            {
                "name": "Acme",
                "email": "contacto@acme.com",
                "administrator": {"name": "Admin"},
            },
            ("body", "administrator", "email"),
        ),
        (
            {
                "name": "Acme",
                "email": "contacto@acme.com",
                "administrator": {
                    "name": "Admin",
                    "email": "admin@acme.com",
                    "phone": "555",
                },
            },
            ("body", "administrator", "phone"),
        ),
        (
            {
                "name": "Acme",
                "email": "contacto@acme.com",
                "administrator": {
                    "name": "Admin",
                    "email": "admin@acme.com",
                    "company_id": "c1",
                },
            },
            ("body", "administrator", "company_id"),
        ),
        (
            {"name": "Acme", "email": "contacto@acme.com", "status": "active"},
            ("body", "status"),
        ),
        (
            {"name": 7, "email": "contacto@acme.com"},
            ("body", "name"),
        ),
    ],
)
def test_create_company_structural_errors_are_lists_without_mutation(
    payload, expected_loc
):
    _login(_platform_admin().email)
    companies_before = _company_count()

    response = client.post("/api/companies", json=payload)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    locations = _structural_locations(response)
    assert expected_loc in locations
    assert _company_count() == companies_before


# ---------------------------------------------------------------------------
# 422 de dominio del alta (RF-126, RF-127)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {"name": "  ", "email": "contacto@acme.com"},
            "name must have 2-100 characters",
        ),
        (
            {"name": "Acme", "email": ""},
            "email is required",
        ),
        (
            {"name": "Acme", "email": "no-es-un-correo"},
            None,  # mensaje del validador vigente de HU-13
        ),
        (
            {"name": "Acme", "email": "a" * 250 + "@example.com"},
            "email exceeds 254 characters",
        ),
        (
            {"name": "Acme", "email": "contacto@acme.com", "phone": "9" * 33},
            "phone exceeds 32 characters",
        ),
        (
            {"name": "Acme", "email": "contacto@acme.com", "contact_name": "A"},
            "contact name must have 2-100 characters",
        ),
    ],
)
def test_create_company_domain_errors_are_strings_without_mutation(payload, message):
    _login(_platform_admin().email)
    companies_before = _company_count()

    response = client.post("/api/companies", json=payload)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    if message is not None:
        assert detail == message
    else:
        assert detail
    assert _company_count() == companies_before


def test_create_company_empty_phone_and_contact_name_become_null():
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "Sin Contacto",
            "email": "contacto@sin.com",
            "phone": "   ",
            "contact_name": "   ",
        },
    )

    assert response.status_code == 201
    body = response.json()["company"]
    assert body["phone"] is None
    assert body["contact_name"] is None


# ---------------------------------------------------------------------------
# RF-128 — unicidad del nombre
# ---------------------------------------------------------------------------


def test_duplicate_normalized_name_returns_409_without_mutation():
    _company("Acme S.A.", email="contacto@acme.com")
    _login(_platform_admin().email)
    companies_before = _company_count()

    response = client.post(
        "/api/companies",
        json={"name": "  acme s.a.  ", "email": "otro@acme.com"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "empresa no disponible"}
    assert _company_count() == companies_before


def test_duplicate_normalized_name_ignores_unicode_composition():
    _company("Ácme", email="contacto@acme.com")
    _login(_platform_admin().email)

    # «a´» descompuesto no es igual literalmente, pero sí tras NFC.
    response = client.post(
        "/api/companies",
        json={"name": "a\u0301cme", "email": "otro@acme.com"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "empresa no disponible"}


def test_duplicate_name_takes_precedence_over_invalid_admin_email():
    _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)

    response = client.post(
        "/api/companies",
        json={
            "name": "acme",
            "email": "contacto@nuevo.com",
            "administrator": {"name": "Admin", "email": "no-es-correo"},
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "empresa no disponible"}


def test_structural_error_takes_precedence_over_duplicate_name():
    _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)

    response = client.post("/api/companies", json={"name": "Acme"})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


# ---------------------------------------------------------------------------
# RF-131 — actualización
# ---------------------------------------------------------------------------


def test_patch_company_updates_fields_and_preserves_relations():
    company = _company("Acme", email="contacto@acme.com")
    other = _company("Otra")
    account = _user(company_id=company.id, role="cliente")
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Ticket",
        description="Descripción",
        requester_id=account.id,
        created_at=datetime.now(UTC),
        status="Abierto",
        company_id=company.id,
    )
    get_ticket_repository().add(ticket)
    created_at = company.created_at
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{company.id}",
        json={
            "name": "  Acme Renovada  ",
            "email": "  Nuevo@Acme.COM  ",
            "phone": " 555 ",
            "contact_name": "  Ana  ",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    _assert_ficha(body)
    assert body["name"] == "Acme Renovada"
    assert body["email"] == "nuevo@acme.com"
    assert body["phone"] == "555"
    assert body["contact_name"] == "Ana"
    assert body["status"] == "active"
    assert datetime.fromisoformat(body["created_at"]) == created_at
    assert body["users_total"] == 1
    assert body["tickets_total"] == 1
    assert account.company_id == company.id
    assert ticket.company_id == company.id
    stored = get_company_repository().find_by_id(company.id)
    assert stored is not None
    assert stored.name_normalized == "acme renovada"
    assert other.name_normalized == "otra"


def test_patch_company_partial_update_and_null_clears_optional_fields():
    company = _company(
        "Acme", email="contacto@acme.com", phone="555", contact_name="Ana"
    )
    _login(_platform_admin().email)

    response = client.patch(f"/api/companies/{company.id}", json={"phone": None})

    assert response.status_code == 200
    body = response.json()
    assert body["phone"] is None
    assert body["contact_name"] == "Ana"
    assert body["name"] == "Acme"
    assert body["email"] == "contacto@acme.com"

    response = client.patch(
        f"/api/companies/{company.id}", json={"contact_name": "   "}
    )
    assert response.status_code == 200
    assert response.json()["contact_name"] is None


def test_patch_company_same_values_succeeds_without_side_effects():
    company = _company("Acme", email="contacto@acme.com")
    _user(company_id=company.id, role="cliente")
    _login(_platform_admin().email)
    users_before = _user_count()

    response = client.patch(
        f"/api/companies/{company.id}",
        json={"name": "Acme", "email": "contacto@acme.com"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Acme"
    assert _user_count() == users_before


def test_patch_company_accepts_case_and_space_only_name_change():
    company = _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{company.id}", json={"name": "  ACME  "}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "ACME"


def test_patch_company_accepts_unchanged_inherited_out_of_range_name():
    inherited = _company("x", normalized="x", email=None)
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{inherited.id}", json={"name": "  X  "}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "X"

    # Editar otros campos de una empresa heredada sin correo sigue permitido.
    response = client.patch(
        f"/api/companies/{inherited.id}", json={"phone": "555"}
    )
    assert response.status_code == 200
    assert response.json()["email"] is None

    # Un cambio efectivo de nombre sí exige 2-100 caracteres.
    response = client.patch(f"/api/companies/{inherited.id}", json={"name": "y"})
    assert response.status_code == 422
    assert response.json() == {"detail": "name must have 2-100 characters"}


def test_patch_company_empty_body_is_domain_error():
    company = _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)

    response = client.patch(f"/api/companies/{company.id}", json={})

    assert response.status_code == 422
    assert response.json() == {"detail": "at least one field is required"}


@pytest.mark.parametrize(
    "payload, expected_loc",
    [
        ({"status": "inactive"}, ("body", "status")),
        ({"id": "x"}, ("body", "id")),
        ({"created_at": "2026-01-01T00:00:00+00:00"}, ("body", "created_at")),
        ({"company_id": "c1"}, ("body", "company_id")),
        ({"administrator": {}}, ("body", "administrator")),
    ],
)
def test_patch_company_rejects_non_editable_and_extra_fields(payload, expected_loc):
    company = _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)
    before = (company.name, company.email, company.phone, company.contact_name)

    response = client.patch(f"/api/companies/{company.id}", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert expected_loc in _structural_locations(response)
    assert (company.name, company.email, company.phone, company.contact_name) == before


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"name": None}, "name must have 2-100 characters"),
        ({"name": ""}, "name must have 2-100 characters"),
        ({"email": None}, "email is required"),
        ({"email": ""}, "email is required"),
        ({"email": "no-es-correo"}, None),
        ({"phone": "9" * 33}, "phone exceeds 32 characters"),
        ({"contact_name": "A"}, "contact name must have 2-100 characters"),
    ],
)
def test_patch_company_domain_errors_do_not_mutate(payload, message):
    company = _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)
    before = (company.name, company.email, company.phone, company.contact_name)

    response = client.patch(f"/api/companies/{company.id}", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    if message is not None:
        assert detail == message
    else:
        assert detail
    assert (company.name, company.email, company.phone, company.contact_name) == before


def test_patch_company_duplicate_name_returns_409_without_mutation():
    _company("Acme", email="contacto@acme.com")
    other = _company("Otra", email="otra@example.com")
    _login(_platform_admin().email)

    response = client.patch(f"/api/companies/{other.id}", json={"name": "acme"})

    assert response.status_code == 409
    assert response.json() == {"detail": "empresa no disponible"}
    assert other.name == "Otra"
    assert other.name_normalized == "otra"


def test_patch_company_duplicate_name_precedes_invalid_email_domain():
    _company("Acme", email="contacto@acme.com")
    other = _company("Otra", email="otra@example.com")
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{other.id}", json={"name": "acme", "email": "no-es-correo"}
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "empresa no disponible"}


def test_patch_company_structural_error_precedes_duplicate_name():
    _company("Acme", email="contacto@acme.com")
    other = _company("Otra", email="otra@example.com")
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{other.id}", json={"name": "acme", "status": "inactive"}
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_patch_company_404_precedes_structural_error():
    _login(_platform_admin().email)

    response = client.patch(
        f"/api/companies/{uuid.uuid4()}", json={"status": "inactive"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "company not found"}


# ---------------------------------------------------------------------------
# RF-142 — propia empresa
# ---------------------------------------------------------------------------


def test_company_admin_gets_and_updates_own_company():
    company = _company("Acme", email="contacto@acme.com")
    admin = _user(role="administrador", company_id=company.id)
    _company("Otra", email="otra@example.com")
    _login(admin.email)

    response = client.get("/api/companies/me")
    assert response.status_code == 200
    _assert_ficha(response.json())
    assert response.json()["id"] == company.id

    response = client.patch(
        "/api/companies/me", json={"phone": "555", "contact_name": "Ana"}
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "555"
    assert response.json()["contact_name"] == "Ana"

    # La ruta por identificador no está disponible para el administrador de
    # empresa, ni siquiera con su propio identificador.
    assert client.get(f"/api/companies/{company.id}").status_code == 404
    assert client.patch(
        f"/api/companies/{company.id}", json={"phone": "777"}
    ).status_code == 404


def test_me_is_not_resolved_as_a_company_id(in_memory_environment):
    company = _company("Acme", email="contacto@acme.com")
    # Empresa con identificador literal «me»: la ruta debe seguir siendo
    # literal y no resolverla como identificador.
    _company("Marca Me", company_id="me", normalized="marca me")
    admin = _user(role="administrador", company_id=company.id)
    platform = _platform_admin("plataforma3@example.com")

    _login(admin.email)
    response = client.get("/api/companies/me")
    assert response.status_code == 200
    assert response.json()["id"] == company.id

    _logout()
    _login(platform.email)
    # Sin empresa en la sesión: 404 aunque exista la empresa «me».
    assert client.get("/api/companies/me").status_code == 404
    assert client.patch("/api/companies/me", json={"phone": "555"}).status_code == 404


def test_company_admin_with_missing_company_gets_404():
    admin = _user(role="administrador", company_id=str(uuid.uuid4()))
    _login(admin.email)

    assert client.get("/api/companies/me").status_code == 404
    assert client.get("/api/companies/me").json() == {"detail": "company not found"}
    assert client.patch("/api/companies/me", json={"phone": "555"}).status_code == 404


# ---------------------------------------------------------------------------
# RF-136 — cambio de estado
# ---------------------------------------------------------------------------


def test_put_status_is_idempotent_and_never_conflicts():
    company = _company("Acme", email="contacto@acme.com")
    account = _user(company_id=company.id, role="cliente")
    _login(_platform_admin().email)

    first = client.put(
        f"/api/companies/{company.id}/status", json={"status": "inactive"}
    )
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "inactive"
    assert first.json()["users_total"] == 1

    second = client.put(
        f"/api/companies/{company.id}/status", json={"status": "inactive"}
    )
    assert second.status_code == 200
    assert second.json()["status"] == "inactive"

    third = client.put(
        f"/api/companies/{company.id}/status", json={"status": "active"}
    )
    assert third.status_code == 200
    assert third.json()["status"] == "active"

    # La desactivación conserva cuentas existentes.
    assert get_user_repository().find_by_id(account.id) is not None
    assert account.status == "active"


@pytest.mark.parametrize(
    "payload, expected_loc",
    [
        ({"status": "operativa"}, ("body", "status")),
        ({"status": None}, ("body", "status")),
        ({"status": "active", "extra": 1}, ("body", "extra")),
        ({}, ("body", "status")),
    ],
)
def test_put_status_structural_errors(payload, expected_loc):
    company = _company("Acme", email="contacto@acme.com")
    _login(_platform_admin().email)

    response = client.put(f"/api/companies/{company.id}/status", json=payload)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert expected_loc in _structural_locations(response)
    assert company.status == "active"


def test_invalid_company_identifier_resolves_to_uniform_404():
    _login(_platform_admin().email)

    responses = [
        client.get("/api/companies/not-a-uuid"),
        client.patch("/api/companies/not-a-uuid", json={"phone": "555"}),
        client.put(
            "/api/companies/not-a-uuid/status", json={"status": "inactive"}
        ),
    ]

    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}


def test_put_status_404_for_missing_company_and_wrong_scope():
    company = _company("Acme", email="contacto@acme.com")
    admin = _user(role="administrador", company_id=company.id)
    _login(_platform_admin().email)
    assert client.put(
        f"/api/companies/{uuid.uuid4()}/status", json={"status": "inactive"}
    ).status_code == 404

    _logout()
    _login(admin.email)
    response = client.put(
        f"/api/companies/{company.id}/status", json={"status": "inactive"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "company not found"}
    assert company.status == "active"


# ---------------------------------------------------------------------------
# RF-125 / RF-137 — autorización uniforme y precedencia
# ---------------------------------------------------------------------------


def _actor_for(role: str, company: Company) -> User:
    if role == "plataforma":
        return _platform_admin(f"actor-{uuid.uuid4().hex}@example.com")
    if role == "administrador_empresa":
        return _user(
            role="administrador",
            company_id=company.id,
            email=f"actor-{uuid.uuid4().hex}@example.com",
        )
    return _user(
        role=role,
        company_id=company.id if role in {"supervisor", "tecnico"} else None,
        email=f"actor-{uuid.uuid4().hex}@example.com",
    )


@pytest.mark.parametrize(
    "role",
    ["supervisor", "tecnico", "cliente", "administrador_empresa"],
)
def test_platform_routes_deny_uniform_404_for_other_actors(role):
    company = _company("Acme", email="contacto@acme.com")
    actor = _actor_for(role, company)
    _login(actor.email)

    requests = [
        client.get("/api/companies"),
        client.get(f"/api/companies/{company.id}"),
        client.post("/api/companies", json={"name": "Nueva", "email": "n@x.com"}),
        client.patch(f"/api/companies/{company.id}", json={"phone": "555"}),
        client.put(
            f"/api/companies/{company.id}/status", json={"status": "inactive"}
        ),
    ]

    for response in requests:
        assert response.status_code == 404, (role, response.request.url, response.text)
        assert response.json() == {"detail": "company not found"}


@pytest.mark.parametrize(
    "role", ["plataforma", "supervisor", "tecnico", "cliente"]
)
def test_me_routes_deny_uniform_404_for_other_actors(role):
    company = _company("Acme", email="contacto@acme.com")
    actor = _actor_for(role if role != "plataforma" else "plataforma", company)
    _login(actor.email)

    for response in (
        client.get("/api/companies/me"),
        client.patch("/api/companies/me", json={"phone": "555"}),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("get", "/api/companies", None),
        ("get", "/api/companies/me", None),
        ("patch", "/api/companies/me", {"phone": "555"}),
        ("get", "/api/companies/x", None),
        ("post", "/api/companies", {"name": "Acme", "email": "a@b.com"}),
        ("patch", "/api/companies/x", {"phone": "555"}),
        ("put", "/api/companies/x/status", {"status": "inactive"}),
    ],
)
def test_every_route_requires_a_session(method, path, body):
    _logout()

    response = getattr(client, method)(path, json=body) if body is not None else getattr(
        client, method
    )(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_401_precedes_structural_422_without_session():
    _logout()

    response = client.post("/api/companies", json={"unexpected": 1})

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_404_precedes_structural_422_for_denied_actor():
    company = _company("Acme", email="contacto@acme.com")
    client_user = _user(role="cliente", company_id=None)
    _login(client_user.email)

    response = client.post("/api/companies", json={"unexpected": 1})

    assert response.status_code == 404
    assert response.json() == {"detail": "company not found"}


# ---------------------------------------------------------------------------
# RF-128 — concurrencia por nombre normalizado
# ---------------------------------------------------------------------------


def _run_two_creations(name: str, make_repository):
    results: list = []
    errors: list[BaseException] = []
    guard = threading.Lock()
    barrier = threading.Barrier(2)

    def worker() -> None:
        companies, users = make_repository()
        barrier.wait(timeout=5)
        try:
            outcome = create_company(
                name=name,
                email=f"{uuid.uuid4().hex}@example.com",
                companies=companies,
                users=users,
            )
            with guard:
                results.append(outcome)
        except BaseException as exc:  # noqa: BLE001 - se comprueba el tipo abajo
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    return results, errors


def test_concurrent_creations_in_memory_produce_exactly_one_success(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    shared_companies = InMemoryCompanyRepository()
    shared_users = InMemoryUserRepository()
    name = "Concurrente Memoria"

    results, errors = _run_two_creations(
        name, lambda: (shared_companies, shared_users)
    )

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], CompanyConflictError)
    assert errors[0].detail == "empresa no disponible"
    assert shared_companies.count() == 1


def test_concurrent_creations_in_postgres_produce_exactly_one_success():
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD")):
        pytest.skip("PostgreSQL no configurado")
    name = f"Concurrente {uuid.uuid4()}"
    normalized = name.strip().lower()

    results, errors = _run_two_creations(
        name, lambda: (InMemoryCompanyRepository(), InMemoryUserRepository())
    )

    assert len(results) == 1, [str(error) for error in errors]
    assert len(errors) == 1
    assert isinstance(errors[0], CompanyConflictError)
    assert errors[0].detail == "empresa no disponible"
    with db.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS total FROM companies WHERE name_normalized = %s",
            (normalized,),
        ).fetchone()["total"]
    assert count == 1


def _run_two_admin_email_creations(admin_email: str, make_repository):
    results: list = []
    errors: list[BaseException] = []
    guard = threading.Lock()
    barrier = threading.Barrier(2)
    names = [f"ConcEmail {uuid.uuid4()} A", f"ConcEmail {uuid.uuid4()} B"]
    normalized = [name.strip().lower() for name in names]

    def worker(index: int) -> None:
        companies, users = make_repository()
        barrier.wait(timeout=5)
        try:
            outcome = create_company(
                name=names[index],
                email=f"{uuid.uuid4().hex}@example.com",
                administrator={"name": "Admin", "email": admin_email},
                companies=companies,
                users=users,
            )
            with guard:
                results.append(outcome)
        except BaseException as exc:  # noqa: BLE001
            with guard:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    return results, errors, names, normalized


def test_concurrent_admin_email_in_postgres_produces_exactly_one_success():
    if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_PASSWORD")):
        pytest.skip("PostgreSQL no configurado")
    admin_email = f"admin-{uuid.uuid4()}@example.com"

    results, errors, names, normalized = _run_two_admin_email_creations(
        admin_email, lambda: (InMemoryCompanyRepository(), InMemoryUserRepository())
    )

    assert len(results) == 1, [str(error) for error in errors]
    assert len(errors) == 1
    assert isinstance(errors[0], UserEmailConflictError)
    with db.connection() as conn:
        account_count = conn.execute(
            "SELECT count(*) AS total FROM identity_invitation_accounts "
            "WHERE lower(email) = %s",
            (admin_email,),
        ).fetchone()["total"]
        company_count = conn.execute(
            "SELECT count(*) AS total FROM companies WHERE name_normalized = ANY(%s)",
            (normalized,),
        ).fetchone()["total"]
    assert account_count == 1
    assert company_count == 1


# ---------------------------------------------------------------------------
# Ningún rechazo muta datos
# ---------------------------------------------------------------------------


def test_rejections_leave_companies_and_accounts_untouched():
    existing = _company("Acme", email="contacto@acme.com")
    other = _company("Otra", email="otra@example.com")
    account = _user(company_id=existing.id, role="cliente")
    _login(_platform_admin().email)
    companies_before = _company_count()
    users_before = _user_count()
    snapshot = (
        existing.name,
        existing.email,
        existing.phone,
        existing.contact_name,
        existing.status,
        existing.created_at,
    )

    rejected = [
        # Nombre duplicado.
        client.post("/api/companies", json={"name": "Acme", "email": "x@y.com"}),
        # Correo de contacto inválido (dominio).
        client.post("/api/companies", json={"name": "Nueva", "email": ""}),
        # Estructura inválida del administrador.
        client.post(
            "/api/companies",
            json={"name": "Nueva", "email": "n@x.com", "administrator": {}},
        ),
        # Campo no editable en la actualización.
        client.patch(f"/api/companies/{existing.id}", json={"status": "inactive"}),
        # Estado inválido en el cambio de estado.
        client.put(
            f"/api/companies/{existing.id}/status", json={"status": "operativa"}
        ),
        # Ficha inexistente.
        client.get(f"/api/companies/{uuid.uuid4()}"),
        # Nombre en conflicto en la actualización.
        client.patch(f"/api/companies/{other.id}", json={"name": " acme "}),
        # Correo de contacto nulo (dominio).
        client.patch(f"/api/companies/{existing.id}", json={"email": None}),
    ]

    assert [response.status_code for response in rejected] == [
        409,
        422,
        422,
        422,
        422,
        404,
        409,
        422,
    ]

    assert _company_count() == companies_before
    assert _user_count() == users_before
    assert account.company_id == existing.id
    assert other.name == "Otra"
    assert other.name_normalized == "otra"
    assert (
        existing.name,
        existing.email,
        existing.phone,
        existing.contact_name,
        existing.status,
        existing.created_at,
    ) == snapshot


# ---------------------------------------------------------------------------
# R6 (criterio 17) — la actualización de una empresa no altera el SLA de
# otras empresas ni de la propia.
# ---------------------------------------------------------------------------


def test_patch_company_does_not_change_sla_policies():
    _platform_admin()
    first = _company("Alpha", email="a@acme.com")
    second = _company("Beta", email="b@acme.com")

    _login("plataforma@example.com")

    from app.modules.sla.infrastructure.sla_policy_repository import (
        get_sla_policy_repository,
    )

    before_endpoint = client.get("/api/sla/policies").json()
    before_first = get_sla_policy_repository().get_all(company_id=first.id)
    before_second = get_sla_policy_repository().get_all(company_id=second.id)

    response = client.patch(
        f"/api/companies/{first.id}",
        json={"name": "Alpha Renombrada", "phone": "555-0001", "contact_name": "Ana"},
    )
    assert response.status_code == 200, response.text

    after_endpoint = client.get("/api/sla/policies").json()
    after_first = get_sla_policy_repository().get_all(company_id=first.id)
    after_second = get_sla_policy_repository().get_all(company_id=second.id)

    assert before_endpoint == after_endpoint
    assert before_first == after_first
    assert before_second == after_second

    # La segunda empresa también se puede editar sin tocar el SLA de la primera.
    response2 = client.patch(
        f"/api/companies/{second.id}",
        json={"email": "nuevo@acme.com"},
    )
    assert response2.status_code == 200, response2.text
    assert client.get("/api/sla/policies").json() == before_endpoint


# ---------------------------------------------------------------------------
# R7 (criterio 8) — tolerancia de datos heredados en la actualización.
# ---------------------------------------------------------------------------


def test_update_inherited_duplicate_name_other_fields_returns_200():
    # Dos empresas preexistentes con el mismo nombre normalizado (datos heredados).
    first = _company("Duplicada")
    second = _company("Duplicada")

    _platform_admin()
    _login("plataforma@example.com")

    response = client.patch(
        f"/api/companies/{first.id}",
        json={"phone": "999", "contact_name": "Contacto", "email": "dup@acme.com"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["phone"] == "999"
    assert response.json()["contact_name"] == "Contacto"
    assert response.json()["email"] == "dup@acme.com"

    # La otra empresa sigue intacta.
    other = get_company_repository().find_by_id(second.id)
    assert other is not None
    assert other.phone is None


def test_update_effective_name_length_101_returns_422():
    company = _company("Empresa", email="e@acme.com")

    _platform_admin()
    _login("plataforma@example.com")

    long_name = "a" * 101
    response = client.patch(
        f"/api/companies/{company.id}",
        json={"name": long_name},
    )
    assert response.status_code == 422, response.text
    assert response.json() == {"detail": "name must have 2-100 characters"}
