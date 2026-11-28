"""A6: catálogo y ficha de empresas leídos desde PostgreSQL, sin caché.

Las lecturas de `companies` deben venir de la fila confirmada y no de la
memoria del proceso, de la caché ni de la semilla. Los agregados de cuentas
usan el contrato persistente de `identity` (A3/A4); los de tickets siguen en
memoria hasta el bloque B y aquí solo se comprueba su forma.
"""

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.modules.companies.application.company_lifecycle import list_companies
from app.modules.companies.domain.entities import Company
from app.modules.companies.infrastructure import company_repository
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
)
from app.modules.companies.interface.company_status_contract import (
    company_exists,
    get_company_status,
)
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from test_hu26_identity_atomic_storage import sandbox


PASSWORD = "ExistingCompanyPassword123"
FICHA_KEYS = {
    "id", "name", "email", "phone", "contact_name", "status", "created_at",
    "users_total", "tickets_total", "tickets_by_status",
    "has_administrator", "administrator_invitation_pending",
}
STATUS_KEYS = {"Abierto", "En progreso", "Resuelto", "Cerrado"}


@pytest.fixture(scope="module")
def password_hash():
    return Argon2PasswordHasher().hash(PASSWORD)


def _company_id(value: int) -> str:
    return str(uuid.UUID(int=value))


@pytest.fixture
def world(sandbox, password_hash):
    """Tres empresas y cuentas ordinarias insertadas solo en el esquema A1."""
    created = datetime(2025, 3, 1, tzinfo=timezone.utc)
    companies = {
        "a": {
            "id": _company_id(101), "name": "  Ácme Norte  ",
            "name_normalized": "ácme norte", "email": "contacto@acme.test",
            "phone": "+57 555 0101", "contact_name": "Ana Contacto",
            "status": "active", "created_at": created,
        },
        "b": {
            "id": _company_id(102), "name": "Beta Sur",
            "name_normalized": "beta sur", "email": None, "phone": None,
            "contact_name": None, "status": "inactive",
            "created_at": created + timedelta(days=1),
        },
        "c": {
            "id": _company_id(103), "name": "Cedro",
            "name_normalized": "cedro", "email": "cedro@example.test",
            "phone": None, "contact_name": None, "status": "active",
            "created_at": created - timedelta(days=1),
        },
    }
    users = {
        "platform": {
            "id": _company_id(201), "company_id": None,
            "name": "Plataforma", "email": "platform@ordinary.example.com",
            "role": "administrador", "status": "active",
            "invitation_status": "accepted",
        },
        "admin_a": {
            "id": _company_id(202), "company_id": companies["a"]["id"],
            "name": "Admin A", "email": "admin.a@ordinary.example.com",
            "role": "administrador", "status": "active",
            "invitation_status": "accepted",
        },
        "invited_a": {
            "id": _company_id(203), "company_id": companies["a"]["id"],
            "name": "Invitada A", "email": "invited.a@ordinary.example.com",
            "role": "administrador", "status": "active",
            "invitation_status": "pending",
        },
        "tech_a": {
            "id": _company_id(204), "company_id": companies["a"]["id"],
            "name": "Técnica A", "email": "tech.a@ordinary.example.com",
            "role": "tecnico", "status": "active",
            "invitation_status": "accepted",
        },
        "client_a": {
            "id": _company_id(205), "company_id": companies["a"]["id"],
            "name": "Cliente A", "email": "client.a@ordinary.example.com",
            "role": "cliente", "status": "active",
            "invitation_status": "accepted",
        },
        "admin_b": {
            "id": _company_id(206), "company_id": companies["b"]["id"],
            "name": "Admin B", "email": "admin.b@ordinary.example.com",
            "role": "administrador", "status": "active",
            "invitation_status": "accepted",
        },
        "client_b": {
            "id": _company_id(207), "company_id": companies["b"]["id"],
            "name": "Cliente B", "email": "client.b@ordinary.example.com",
            "role": "cliente", "status": "active",
            "invitation_status": "accepted",
        },
    }
    with sandbox.connect() as conn:
        # Orden físico deliberadamente distinto del orden contratado.
        for key in ("c", "a", "b"):
            conn.execute(
                """INSERT INTO companies
                   (id,name,name_normalized,email,phone,contact_name,status,created_at)
                   VALUES (%(id)s,%(name)s,%(name_normalized)s,%(email)s,%(phone)s,
                           %(contact_name)s,%(status)s,%(created_at)s)""",
                companies[key],
            )
        for key, row in users.items():
            accepted = row["invitation_status"] == "accepted"
            conn.execute(
                """INSERT INTO users
                   (id,company_id,name,email,password_hash,phone,role,status,
                    invitation_status,invitation_token_hash,invitation_expires_at,
                    invitation_used_at,created_at)
                   VALUES (%(id)s,%(company_id)s,%(name)s,%(email)s,%(password_hash)s,
                           NULL,%(role)s,%(status)s,%(invitation_status)s,
                           %(token)s,%(expires_at)s,%(used_at)s,%(created_at)s)""",
                {
                    **row,
                    "password_hash": password_hash if accepted else None,
                    "token": None if accepted else f"a6 invitation hash {key}",
                    "expires_at": None if accepted else created + timedelta(days=7),
                    "used_at": created if accepted else None,
                    "created_at": created,
                },
            )
    return {"companies": companies, "users": users}


@pytest.fixture
def client(sandbox, monkeypatch):
    from app.main import app

    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    monkeypatch.setattr(
        session_store, "_sessions", session_store.InMemorySessionStore()
    )
    # Instancia vacía: ninguna lectura puede depender del proceso previo.
    monkeypatch.setattr(
        company_repository, "_companies", InMemoryCompanyRepository()
    )
    with TestClient(app) as test_client:
        yield test_client


def _login(client, email):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


def _by_id(repository, companies):
    return {key: repository.find_by_id(row["id"]) for key, row in companies.items()}


# ---------------------------------------------------------------------------
# Repositorio: lecturas canónicas por ID y listado
# ---------------------------------------------------------------------------


def test_independent_readers_recover_every_confirmed_company_field(world):
    first_id = world["companies"]["a"]["id"]
    for reader in (InMemoryCompanyRepository(), InMemoryCompanyRepository()):
        for expected in world["companies"].values():
            company = reader.find_by_id(expected["id"])
            assert company is not None
            assert company.__dict__ == expected
        # Cada lectura devuelve un agregado nuevo, no una referencia retenida.
        assert reader.find_by_id(first_id) is not reader.find_by_id(first_id)
        assert {item.id for item in reader.list_all()} == {
            row["id"] for row in world["companies"].values()
        }
        assert reader.count() == 0  # No hidratar la caché al consultar.


def test_reads_ignore_stale_memory_and_reread_confirmed_commits(world, sandbox):
    repository = InMemoryCompanyRepository()
    stale = Company(**world["companies"]["a"])
    repository._by_id[stale.id] = stale
    ghost = Company(
        id=str(uuid.uuid4()), name="Solo memoria",
        name_normalized="solo memoria",
        created_at=datetime(2025, 3, 2, tzinfo=timezone.utc),
    )
    repository._by_id[ghost.id] = ghost

    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE companies SET name='Ácme Norte Renombrada', "
            "name_normalized='ácme norte renombrada', status='inactive', email=NULL "
            "WHERE id=%s",
            (stale.id,),
        )

    for reader in (repository, InMemoryCompanyRepository()):
        fresh = reader.find_by_id(stale.id)
        assert (fresh.name, fresh.status, fresh.email) == (
            "Ácme Norte Renombrada", "inactive", None,
        )
        assert reader.find_by_id(ghost.id) is None
        assert ghost.id not in {item.id for item in reader.list_all()}

    # El objeto retenido por el proceso previo no se muta ni se reutiliza.
    assert (stale.name, stale.status, stale.email) == (
        "  Ácme Norte  ", "active", "contacto@acme.test",
    )


def test_repository_and_catalog_keep_their_contracted_orders(world):
    expected = sorted(
        world["companies"].values(),
        key=lambda row: (row["created_at"], row["id"]),
    )
    assert [item.id for item in InMemoryCompanyRepository().list_all()] == [
        row["id"] for row in expected
    ]

    catalog = list_companies(InMemoryCompanyRepository())
    assert [item.id for item in catalog] == [
        row["id"] for row in sorted(
            world["companies"].values(),
            key=lambda row: (row["name_normalized"], row["created_at"], row["id"]),
        )
    ]
    # `list_companies` incluye activas e inactivas.
    assert {item.status for item in catalog} == {"active", "inactive"}


def test_invalid_identifier_returns_none_without_querying(world, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Un identificador inválido no debe consultar PostgreSQL")

    monkeypatch.setattr(company_repository, "connection", forbidden)
    reader = InMemoryCompanyRepository()
    assert reader.find_by_id("not-a-uuid") is None
    assert reader.find_by_id(None) is None


def test_status_contract_reads_the_canonical_state(world):
    companies = world["companies"]
    assert get_company_status(companies["a"]["id"]) == "active"
    assert get_company_status(companies["b"]["id"]) == "inactive"
    assert get_company_status(str(uuid.uuid4())) is None
    assert get_company_status("legacy-company") is None
    assert get_company_status(None) is None
    assert company_exists(companies["c"]["id"]) is True
    assert company_exists(str(uuid.uuid4())) is False


def test_sql_errors_are_propagated_without_silent_fallback(world, sandbox):
    repository = InMemoryCompanyRepository()
    company_id = world["companies"]["a"]["id"]
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE companies RENAME TO unavailable_companies")

    calls = (
        lambda: repository.find_by_id(company_id),
        repository.list_all,
        lambda: list_companies(repository),
        lambda: get_company_status(company_id),
        lambda: company_exists(company_id),
    )
    for call in calls:
        with pytest.raises(psycopg.errors.UndefinedTable):
            call()


def test_missing_configuration_requires_the_explicit_memory_seam(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    reader = InMemoryCompanyRepository()
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        reader.find_by_id(str(uuid.uuid4()))
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        reader.list_all()


def test_explicit_memory_seam_keeps_legacy_references_and_order(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    reader = InMemoryCompanyRepository()
    second = Company(
        id="legacy-z", name="Segunda", name_normalized="segunda",
        created_at=datetime(2025, 3, 2, tzinfo=timezone.utc),
    )
    first = Company(
        id="legacy-a", name="Primera", name_normalized="primera",
        created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    reader.add(second)
    reader.add(first)
    assert reader.find_by_id(first.id) is first
    assert reader.find_by_id(None) is None
    listing = reader.list_all()
    assert listing == [second, first]
    assert listing[0] is second


# ---------------------------------------------------------------------------
# HTTP: catálogo, ficha y aislamiento
# ---------------------------------------------------------------------------


def test_http_catalog_and_detail_come_from_confirmed_rows(client, world):
    companies = world["companies"]
    _login(client, world["users"]["platform"]["email"])

    catalog = client.get("/api/companies")
    assert catalog.status_code == 200
    bodies = catalog.json()
    assert all(set(body) == FICHA_KEYS for body in bodies)
    # Orden contratado por forma normalizada: beta sur, cedro, ácme norte.
    assert [body["id"] for body in bodies] == [
        companies["b"]["id"], companies["c"]["id"], companies["a"]["id"],
    ]
    by_id = {body["id"]: body for body in bodies}
    own = by_id[companies["a"]["id"]]
    assert {
        key: own[key]
        for key in ("name", "email", "phone", "contact_name", "status")
    } == {
        "name": "  Ácme Norte  ", "email": "contacto@acme.test",
        "phone": "+57 555 0101", "contact_name": "Ana Contacto",
        "status": "active",
    }
    assert own["users_total"] == 4
    assert own["has_administrator"] is True
    assert own["administrator_invitation_pending"] is True
    assert by_id[companies["b"]["id"]]["status"] == "inactive"
    assert by_id[companies["b"]["id"]]["users_total"] == 2
    assert by_id[companies["c"]["id"]]["users_total"] == 0
    assert set(own["tickets_by_status"]) == STATUS_KEYS
    assert sum(own["tickets_by_status"].values()) == own["tickets_total"]

    detail = client.get(f"/api/companies/{companies['a']['id']}")
    assert detail.status_code == 200
    assert detail.json() == own
    for unknown in (str(uuid.uuid4()), "not-a-uuid"):
        response = client.get(f"/api/companies/{unknown}")
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}


def test_http_reads_reflect_an_external_commit_without_relogin(
    client, world, sandbox, monkeypatch
):
    company = world["companies"]["b"]
    _login(client, world["users"]["platform"]["email"])
    assert client.get(f"/api/companies/{company['id']}").json()["name"] == "Beta Sur"

    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE companies SET name='Beta Renombrada', "
            "name_normalized='beta renombrada', contact_name='Contacto nuevo', "
            "status='active' WHERE id=%s",
            (company["id"],),
        )
    # Nuevo repositorio en el proceso; la sesión sigue siendo la misma.
    monkeypatch.setattr(
        company_repository, "_companies", InMemoryCompanyRepository()
    )
    detail = client.get(f"/api/companies/{company['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert (body["name"], body["contact_name"], body["status"]) == (
        "Beta Renombrada", "Contacto nuevo", "active",
    )
    catalog = client.get("/api/companies").json()
    assert {item["id"]: item["name"] for item in catalog}[company["id"]] == (
        "Beta Renombrada"
    )


@pytest.mark.parametrize("actor, scope", [("admin_a", "a"), ("admin_b", "b")])
def test_http_session_company_scope_and_inactive_state(client, world, actor, scope):
    companies = world["companies"]
    other = "b" if scope == "a" else "a"
    _login(client, world["users"][actor]["email"])

    own = client.get("/api/companies/me")
    assert own.status_code == 200
    body = own.json()
    assert set(body) == FICHA_KEYS
    assert body["id"] == companies[scope]["id"]
    assert body["status"] == companies[scope]["status"]
    assert body["users_total"] == sum(
        1 for user in world["users"].values()
        if user["company_id"] == companies[scope]["id"]
    )
    assert companies[other]["id"] not in {body["id"]}

    for path in (
        "/api/companies",
        f"/api/companies/{companies[other]['id']}",
        f"/api/companies/{companies[scope]['id']}",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}


@pytest.mark.parametrize("actor", ["tech_a", "client_a", "client_b"])
def test_http_company_reads_keep_existing_role_denials(client, world, actor):
    _login(client, world["users"][actor]["email"])
    company_id = world["companies"]["a"]["id"]
    for path in ("/api/companies", "/api/companies/me", f"/api/companies/{company_id}"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}


def test_http_company_endpoints_preserve_401_404_422_409_precedence(client, world):
    companies = world["companies"]
    company_id = companies["a"]["id"]

    # Sin sesión: 401 antes de cualquier lectura o validación del cuerpo.
    assert client.get("/api/companies").status_code == 401
    assert client.get(f"/api/companies/{company_id}").status_code == 401
    assert client.patch(f"/api/companies/{company_id}", json={}).status_code == 401

    _login(client, world["users"]["platform"]["email"])

    # 404 de la ruta antes del 422 estructural del cuerpo.
    for unknown in (str(uuid.uuid4()), "not-a-uuid"):
        response = client.patch(f"/api/companies/{unknown}", json={"extra": 1})
        assert response.status_code == 404
        assert response.json() == {"detail": "company not found"}

    # 422 estructural con empresa existente.
    structural = client.patch(f"/api/companies/{company_id}", json={"extra": 1})
    assert structural.status_code == 422
    assert isinstance(structural.json()["detail"], list)

    # 422 de dominio por nombre inválido.
    domain = client.patch(f"/api/companies/{company_id}", json={"name": ""})
    assert domain.status_code == 422
    assert isinstance(domain.json()["detail"], str)

    # 409 por nombre normalizado ya usado por otra empresa.
    conflict = client.patch(
        f"/api/companies/{company_id}", json={"name": companies["b"]["name"]}
    )
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "empresa no disponible"}

    # La empresa no cambió tras los rechazos.
    current = client.get(f"/api/companies/{company_id}").json()
    assert current["name"] == companies["a"]["name"]


def test_http_sql_errors_are_not_hidden_behind_memory_fallback(client, world, sandbox):
    _login(client, world["users"]["platform"]["email"])
    with sandbox.connect() as conn:
        conn.execute("ALTER TABLE companies RENAME TO unavailable_companies")
    with pytest.raises(psycopg.errors.UndefinedTable):
        client.get("/api/companies")
