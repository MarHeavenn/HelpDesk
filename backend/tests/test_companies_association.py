"""HU-19 T6 — asociación de cuentas y consulta de cuentas sin empresa.

Cubre RF-133, RF-134, RF-140 y RF-143:

- `PUT /api/companies/{company_id}/accounts/{user_id}` acepta cuerpo ausente y
  `{}`, y rechaza cualquier campo (incluidos `company_id` y `user_id`) con 422
  estructural sin mutar la cuenta.
- Los cuatro rechazos 409 `"asociación no permitida"` (cuenta con empresa,
  empresa inactiva, cuenta con rol `administrador` y la propia cuenta del
  actor) son idénticos entre sí y no mutan nada.
- Los 404 `"not found"` de cuenta inexistente, empresa inexistente y actor
  fuera de alcance son idénticos entre sí y nunca comparten cuerpo con los 409.
- La asociación conserva nombre, correo, rol, estado, credenciales e
  invitación, no crea ni revoca sesiones, surte efecto en la siguiente
  petición de una sesión vigente, retira la cuenta de `unassigned` y la hace
  visible al administrador de su empresa (RF-134, RF-143).
- `GET /api/users/unassigned` devuelve `{id, name, email, role, status}` con
  orden determinista (forma normalizada de RF-128 y desempate por id), `[]`
  con 200, 404 `"user not found"` para cualquier otro actor y excluye cuentas
  con empresa y con rol `administrador` (RF-140).
- No existe ninguna ruta ni cuerpo que mueva una cuenta o un ticket con
  empresa (RF-133).
"""

from __future__ import annotations

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
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository

client = TestClient(app)

UTC = timezone.utc
PASSWORD = "Secreta123"
# Un solo hash reutilizado acelera las pruebas y conserva la verificación real
# de la contraseña en el login.
PASSWORD_HASH = Argon2PasswordHasher().hash(PASSWORD)

ASSOCIATION_NOT_ALLOWED = {"detail": "asociación no permitida"}
ASSOCIATION_NOT_FOUND = {"detail": "not found"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _company(status: str = "active", name: str = "Acme") -> Company:
    company = Company(
        id=str(uuid.uuid4()),
        name=name,
        name_normalized=name.strip().lower(),
        email="contacto@acme.com",
        status=status,
    )
    get_company_repository().add(company)
    return company


def _user(
    *,
    user_id: str | None = None,
    email: str | None = None,
    role: str = "cliente",
    company_id: str | None = None,
    name: str = "Cuenta Test",
    phone: str | None = None,
    status: str = "active",
    invitation_status: str = "accepted",
    password_hash: str | None = PASSWORD_HASH,
    invitation_token_hash: str | None = None,
    invitation_expires_at: datetime | None = None,
) -> User:
    user = User(
        id=user_id or str(uuid.uuid4()),
        name=name,
        email=email or f"{uuid.uuid4().hex}@ejemplo.com",
        password_hash=password_hash,
        role=role,
        company_id=company_id,
        phone=phone,
        status=status,
        invitation_status=invitation_status,
        invitation_token_hash=invitation_token_hash,
        invitation_expires_at=invitation_expires_at,
    )
    get_user_repository().add(user)
    return user


def _client_for(email: str) -> TestClient:
    """Cliente HTTP propio por actor: cada `TestClient` tiene una cookie."""
    session = TestClient(app)
    response = session.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    return session


def _ticket(company_id: str, requester_id: str) -> Ticket:
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Ticket existente",
        description="Ticket creado para probar que no se puede mover",
        requester_id=requester_id,
        created_at=datetime.now(UTC),
        company_id=company_id,
    )
    get_ticket_repository().add(ticket)
    return ticket


@pytest.fixture(autouse=True)
def clean_state():
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


# ---------------------------------------------------------------------------
# RF-134 — cuerpo de la asociación
# ---------------------------------------------------------------------------


def test_association_accepts_absent_body_and_empty_object():
    platform = _user(
        email="platform@example.com", role="administrador", name="Plataforma"
    )
    company = _company()
    first = _user(email="primera@example.com", role="cliente", name="Primera Cuenta")
    second = _user(email="segunda@example.com", role="tecnico", name="Segunda Cuenta")
    platform_client = _client_for(platform.email)

    # Cuerpo ausente: se procesa y responde 200 {company}.
    absent = platform_client.put(
        f"/api/companies/{company.id}/accounts/{first.id}"
    )
    assert absent.status_code == 200
    assert set(absent.json().keys()) == {"company"}
    assert absent.json()["company"]["id"] == company.id
    assert absent.json()["company"]["users_total"] == 1
    assert get_user_repository().find_by_id(first.id).company_id == company.id

    # `{}` explícito: también se procesa.
    empty = platform_client.put(
        f"/api/companies/{company.id}/accounts/{second.id}", json={}
    )
    assert empty.status_code == 200
    assert set(empty.json().keys()) == {"company"}
    assert empty.json()["company"]["users_total"] == 2
    assert get_user_repository().find_by_id(second.id).company_id == company.id


@pytest.mark.parametrize(
    "payload",
    [
        {"company_id": "otra-empresa"},
        {"user_id": "otra-cuenta"},
        {"company_id": "otra-empresa", "user_id": "otra-cuenta"},
        {"empresa": "otra-empresa"},
        {"name": "Nombre"},
        {"foo": 1},
        {"company": {"id": "otra-empresa"}},
    ],
)
def test_association_rejects_any_field_with_422_and_no_change(payload):
    platform = _user(
        email="platform@example.com", role="administrador", name="Plataforma"
    )
    company = _company()
    account = _user(email="cuenta@example.com", role="cliente", name="Cuenta Libre")
    platform_client = _client_for(platform.email)

    response = platform_client.put(
        f"/api/companies/{company.id}/accounts/{account.id}", json=payload
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert all(error["loc"][0] == "body" for error in detail)
    # Sin cambios: la cuenta sigue sin empresa y no se cuenta en la ficha.
    assert get_user_repository().find_by_id(account.id).company_id is None
    ficha = platform_client.get(f"/api/companies/{company.id}").json()
    assert ficha["users_total"] == 0
    unassigned = platform_client.get("/api/users/unassigned").json()
    assert any(item["id"] == account.id for item in unassigned)


def test_association_bodies_with_company_and_user_id_name_the_extra_field():
    platform = _user(email="platform@example.com", role="administrador")
    company = _company()
    account = _user(email="cuenta@example.com", role="cliente")
    platform_client = _client_for(platform.email)

    for field, value in (
        ("company_id", company.id),
        ("user_id", account.id),
    ):
        response = platform_client.put(
            f"/api/companies/{company.id}/accounts/{account.id}",
            json={field: value},
        )
        assert response.status_code == 422
        assert any(
            error["type"] == "extra_forbidden" and field in error["loc"]
            for error in response.json()["detail"]
        )


# ---------------------------------------------------------------------------
# RF-134 — grupo 409 idéntico
# ---------------------------------------------------------------------------


def test_association_409_group_is_identical_and_leaves_state_untouched():
    platform = _user(
        email="platform@example.com", role="administrador", name="Plataforma"
    )
    company = _company(name="Activa")
    inactive = _company(status="inactive", name="Inactiva")
    with_company = _user(
        email="con-empresa@example.com", role="cliente", company_id=company.id
    )
    platform_account = _user(
        email="otro-admin@example.com", role="administrador", name="Otro Admin"
    )
    candidate = _user(email="candidata@example.com", role="cliente")
    platform_client = _client_for(platform.email)

    responses = [
        # 1) cuenta con empresa
        platform_client.put(
            f"/api/companies/{company.id}/accounts/{with_company.id}", json={}
        ),
        # 2) empresa inactiva
        platform_client.put(
            f"/api/companies/{inactive.id}/accounts/{candidate.id}", json={}
        ),
        # 3) cuenta con rol administrador (no asociable)
        platform_client.put(
            f"/api/companies/{company.id}/accounts/{platform_account.id}", json={}
        ),
        # 4) la propia cuenta del actor
        platform_client.put(
            f"/api/companies/{company.id}/accounts/{platform.id}", json={}
        ),
    ]

    assert [response.status_code for response in responses] == [409, 409, 409, 409]
    bodies = [response.json() for response in responses]
    assert all(body == ASSOCIATION_NOT_ALLOWED for body in bodies)
    assert len({repr(sorted(body.items())) for body in bodies}) == 1

    # Ningún rechazo mutó nada.
    assert with_company.company_id == company.id
    assert candidate.company_id is None
    assert platform_account.company_id is None
    assert platform.company_id is None
    assert (
        platform_client.get(f"/api/companies/{company.id}").json()["users_total"]
        == 1
    )
    assert (
        platform_client.get(f"/api/companies/{inactive.id}").json()["users_total"]
        == 0
    )


# ---------------------------------------------------------------------------
# RF-134 — grupo 404 idéntico y distinto del 409
# ---------------------------------------------------------------------------


def test_association_404_group_is_identical_and_distinct_from_409():
    platform = _user(email="platform@example.com", role="administrador")
    company = _company()
    company_admin = _user(
        email="admin-empresa@example.com",
        role="administrador",
        company_id=company.id,
    )
    supervisor = _user(email="supervisor@example.com", role="supervisor")
    account = _user(email="cuenta@example.com", role="cliente")
    platform_client = _client_for(platform.email)

    responses = [
        # cuenta inexistente
        platform_client.put(
            f"/api/companies/{company.id}/accounts/{uuid.uuid4()}", json={}
        ),
        # empresa inexistente
        platform_client.put(
            f"/api/companies/{uuid.uuid4()}/accounts/{account.id}", json={}
        ),
        # actor fuera de alcance: administrador de empresa
        _client_for(company_admin.email).put(
            f"/api/companies/{company.id}/accounts/{account.id}", json={}
        ),
        # actor fuera de alcance: supervisor
        _client_for(supervisor.email).put(
            f"/api/companies/{company.id}/accounts/{account.id}", json={}
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404]
    bodies = [response.json() for response in responses]
    assert all(body == ASSOCIATION_NOT_FOUND for body in bodies)
    assert len({repr(sorted(body.items())) for body in bodies}) == 1
    # Los dos grupos nunca comparten cuerpo.
    assert bodies[0] != ASSOCIATION_NOT_ALLOWED
    # El intento no asoció la cuenta.
    assert account.company_id is None


def test_association_resolves_the_route_company_before_reading_the_body():
    """RF-137: un identificador de empresa de la ruta inexistente da 404 siempre.

    Aunque el cuerpo sea inválido (422 si se evaluara primero), la empresa de
    la ruta se resuelve antes de leerlo para que el 404 uniforme no dependa
    del cuerpo.
    """
    platform = _user(email="platform@example.com", role="administrador")
    account = _user(email="cuenta@example.com", role="cliente")
    platform_client = _client_for(platform.email)

    for payload in ({"foo": 1}, {"company_id": "otra"}, {"user_id": "otra"}):
        response = platform_client.put(
            f"/api/companies/{uuid.uuid4()}/accounts/{account.id}", json=payload
        )
        assert response.status_code == 404, response.text
        assert response.json() == ASSOCIATION_NOT_FOUND

    malformed = platform_client.put(
        f"/api/companies/{uuid.uuid4()}/accounts/{account.id}",
        content="{incompleto",
        headers={"content-type": "application/json"},
    )
    assert malformed.status_code == 404, malformed.text
    assert malformed.json() == ASSOCIATION_NOT_FOUND
    assert account.company_id is None


# ---------------------------------------------------------------------------
# RF-134 — conservación del agregado y de las sesiones
# ---------------------------------------------------------------------------


def test_association_preserves_account_data_and_sessions():
    platform = _user(email="platform@example.com", role="administrador")
    company = _company()
    accepted = _user(
        email="aceptada@example.com",
        role="tecnico",
        name="Cuenta Aceptada",
        phone="555-1234",
    )
    expires_at = datetime.now(UTC) + timedelta(hours=168)
    pending = _user(
        email="pendiente@example.com",
        role="supervisor",
        name="Cuenta Pendiente",
        invitation_status="pending",
        password_hash=None,
        invitation_token_hash="hash-de-invitacion",
        invitation_expires_at=expires_at,
    )

    accepted_before = dict(accepted.__dict__)
    pending_before = dict(pending.__dict__)

    accepted_client = _client_for(accepted.email)
    session_token = accepted_client.cookies.get("session")
    assert session_token
    platform_client = _client_for(platform.email)
    sessions_before = get_session_store().count()
    assert sessions_before == 2

    for account in (accepted, pending):
        response = platform_client.put(
            f"/api/companies/{company.id}/accounts/{account.id}", json={}
        )
        assert response.status_code == 200
        assert response.json()["company"]["users_total"] == (
            1 if account is accepted else 2
        )

    # Único campo alterado: `company_id`; credenciales e invitación intactas.
    assert dict(accepted.__dict__) == {
        **accepted_before,
        "company_id": company.id,
    }
    assert dict(pending.__dict__) == {
        **pending_before,
        "company_id": company.id,
    }
    assert accepted.password_hash == PASSWORD_HASH
    assert pending.password_hash is None
    assert pending.invitation_status == "pending"
    assert pending.invitation_token_hash == "hash-de-invitacion"
    assert pending.invitation_expires_at == expires_at

    # No se creó ni revocó ninguna sesión y la vigente sigue operando.
    assert get_session_store().count() == sessions_before
    session = get_session_store().find_by_token(session_token)
    assert session is not None and session.revoked_at is None
    assert accepted_client.get("/api/auth/me").status_code == 200


# ---------------------------------------------------------------------------
# RF-134 — efecto en la siguiente petición y alcance de la empresa
# ---------------------------------------------------------------------------


def test_association_takes_effect_on_next_request_and_scopes_visibility():
    platform = _user(email="platform@example.com", role="administrador")
    company_a = _company(name="Alfa")
    company_b = _company(name="Beta")
    account = _user(email="cliente@example.com", role="cliente", name="Cliente Alfa")
    admin_a = _user(
        email="admin-alfa@example.com", role="administrador", company_id=company_a.id
    )
    admin_b = _user(
        email="admin-beta@example.com", role="administrador", company_id=company_b.id
    )

    # La sesión de la cuenta se abre antes de la asociación y no se renueva.
    account_client = _client_for(account.email)
    ticket_payload = {
        "title": "No carga la pantalla",
        "description": "La pantalla queda en blanco",
    }
    before = account_client.post("/api/tickets", json=ticket_payload)
    assert before.status_code == 404
    assert before.json() == {"detail": "ticket not found"}

    platform_client = _client_for(platform.email)
    association = platform_client.put(
        f"/api/companies/{company_a.id}/accounts/{account.id}", json={}
    )
    assert association.status_code == 200

    # Misma cookie, siguiente petición: ya opera con la empresa asociada.
    after = account_client.post("/api/tickets", json=ticket_payload)
    assert after.status_code == 201
    assert after.json()["requester"]["id"] == account.id
    created_id = after.json()["id"]
    mine = account_client.get("/api/tickets")
    assert mine.status_code == 200
    assert [ticket["id"] for ticket in mine.json()] == [created_id]

    # La cuenta queda visible para el administrador de su empresa...
    visible = _client_for(admin_a.email).get("/api/users")
    assert visible.status_code == 200
    visible_account = next(
        item for item in visible.json() if item["id"] == account.id
    )
    assert visible_account["company_id"] == company_a.id

    # ...y no para el de otra empresa ni para el administrador de plataforma.
    other_admin = _client_for(admin_b.email)
    assert other_admin.get(f"/api/users/{account.id}").status_code == 404
    assert (
        other_admin.get(f"/api/users/{account.id}").json()
        == {"detail": "user not found"}
    )
    assert platform_client.get(f"/api/users/{account.id}").status_code == 404
    assert platform_client.get("/api/users").status_code == 404


def test_association_retires_account_from_unassigned():
    platform = _user(email="platform@example.com", role="administrador")
    company = _company()
    account = _user(email="cuenta@example.com", role="cliente")
    remaining = _user(email="resto@example.com", role="cliente")
    platform_client = _client_for(platform.email)

    before = platform_client.get("/api/users/unassigned").json()
    assert {item["id"] for item in before} == {account.id, remaining.id}

    assert (
        platform_client.put(
            f"/api/companies/{company.id}/accounts/{account.id}", json={}
        ).status_code
        == 200
    )

    after = platform_client.get("/api/users/unassigned").json()
    assert [item["id"] for item in after] == [remaining.id]


# ---------------------------------------------------------------------------
# RF-140 — consulta de cuentas sin empresa
# ---------------------------------------------------------------------------


def test_unassigned_returns_exact_shape_and_deterministic_order():
    platform = _user(email="platform@example.com", role="administrador")
    # Forma normalizada de RF-128: recorte, NFC y minúsculas; desempate por id.
    _user(user_id="u-zeta", email="zeta@example.com", name="Zeta")
    _user(user_id="u-beta", email="beta@example.com", name="  beta  ")
    _user(user_id="u-alpha-2", email="alpha2@example.com", name=" ALPHA ")
    _user(user_id="u-alpha-1", email="alpha1@example.com", name="Alpha")
    _user(
        user_id="u-delta",
        email="delta@example.com",
        name="Delta",
        role="tecnico",
        status="deactivated",
    )
    _user(user_id="u-nandu", email="nandu@example.com", name="Ñandú")
    # Excluidas: con empresa y con rol administrador.
    _user(
        user_id="u-con-empresa",
        email="empresa@example.com",
        name="Alfa",
        company_id="c1",
    )
    _user(
        user_id="u-admin",
        email="otro-admin@example.com",
        name="Aaaa",
        role="administrador",
    )
    platform_client = _client_for(platform.email)

    response = platform_client.get("/api/users/unassigned")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [
        "u-alpha-1",
        "u-alpha-2",
        "u-beta",
        "u-delta",
        "u-zeta",
        "u-nandu",
    ]
    for item in data:
        assert set(item.keys()) == {"id", "name", "email", "role", "status"}
    assert data[3] == {
        "id": "u-delta",
        "name": "Delta",
        "email": "delta@example.com",
        "role": "tecnico",
        "status": "deactivated",
    }
    # `unassigned` es una ruta literal y nunca se resuelve como identificador.
    assert isinstance(data, list)


def test_unassigned_empty_list_is_200():
    platform = _user(email="platform@example.com", role="administrador")
    platform_client = _client_for(platform.email)

    response = platform_client.get("/api/users/unassigned")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "role,company_id",
    [
        ("administrador", "c1"),
        ("supervisor", "c1"),
        ("tecnico", "c1"),
        ("cliente", "c1"),
    ],
)
def test_unassigned_returns_user_not_found_for_every_other_actor(role, company_id):
    actor = _user(
        email=f"{role}@example.com", role=role, company_id=company_id, name=role
    )

    response = _client_for(actor.email).get("/api/users/unassigned")

    assert response.status_code == 404
    assert response.json() == {"detail": "user not found"}


def test_unassigned_requires_session():
    response = TestClient(app).get("/api/users/unassigned")

    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_association_requires_session():
    company = _company()
    account = _user(email="cuenta@example.com", role="cliente")
    anonymous = TestClient(app)

    association = anonymous.put(
        f"/api/companies/{company.id}/accounts/{account.id}", json={}
    )
    assert association.status_code == 401
    assert association.json() == {"detail": "not authenticated"}
    assert account.company_id is None


# ---------------------------------------------------------------------------
# RF-133 — no existe ruta ni cuerpo para mover cuentas o tickets
# ---------------------------------------------------------------------------


def test_no_route_or_body_allows_moving_account_or_ticket_between_companies():
    platform = _user(email="platform@example.com", role="administrador")
    company_a = _company(name="Alfa")
    company_b = _company(name="Beta")
    admin_a = _user(
        email="admin-alfa@example.com", role="administrador", company_id=company_a.id
    )
    account = _user(
        email="cuenta@example.com",
        role="cliente",
        company_id=company_a.id,
        name="Cuenta Alfa",
    )
    ticket = _ticket(company_a.id, account.id)
    platform_client = _client_for(platform.email)

    # Rutas de movimiento inexistentes: 404/405 estándar, sin efecto.
    assert (
        platform_client.put(
            f"/api/users/{account.id}/company", json={"company_id": company_b.id}
        ).status_code
        == 404
    )
    assert (
        platform_client.post(
            f"/api/companies/{company_b.id}/accounts/{account.id}/move"
        ).status_code
        == 404
    )
    assert (
        platform_client.patch(
            f"/api/companies/{company_b.id}/accounts/{account.id}"
        ).status_code
        == 405
    )
    assert (
        platform_client.put(
            f"/api/tickets/{ticket.id}/company", json={"company_id": company_b.id}
        ).status_code
        == 404
    )
    assert (
        platform_client.post(
            f"/api/tickets/{ticket.id}/move", json={"company_id": company_b.id}
        ).status_code
        == 404
    )
    # La asociación tampoco mueve una cuenta que ya tiene empresa.
    move_attempt = platform_client.put(
        f"/api/companies/{company_b.id}/accounts/{account.id}", json={}
    )
    assert move_attempt.status_code == 409
    assert move_attempt.json() == ASSOCIATION_NOT_ALLOWED

    # Dato de empresa en el cuerpo: 422 estructural, sin cambios.
    admin_client = _client_for(admin_a.email)
    patch_user = admin_client.patch(
        f"/api/users/{account.id}", json={"company_id": company_b.id}
    )
    assert patch_user.status_code == 422
    assert isinstance(patch_user.json()["detail"], list)

    create_user = admin_client.post(
        "/api/users",
        json={
            "name": "Nueva Persona",
            "email": "nueva@example.com",
            "role": "cliente",
            "company_id": company_b.id,
        },
    )
    assert create_user.status_code == 422
    assert get_user_repository().find_by_email("nueva@example.com") is None

    status_user = admin_client.put(
        f"/api/users/{account.id}/status",
        json={"status": "active", "company_id": company_b.id},
    )
    assert status_user.status_code == 422

    status_ticket = admin_client.put(
        f"/api/tickets/{ticket.id}/status",
        json={"status": "En progreso", "company_id": company_b.id},
    )
    assert status_ticket.status_code == 422

    # Nada se movió: cuenta y ticket conservan su empresa original.
    assert get_user_repository().find_by_id(account.id).company_id == company_a.id
    assert get_ticket_repository().find_by_id(ticket.id).company_id == company_a.id
