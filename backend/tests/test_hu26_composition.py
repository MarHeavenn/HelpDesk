"""A7: composición del bloque A y cierre de su cobertura.

Comprueba que PostgreSQL es obligatorio en producción, que la memoria es un
seam explícito solo para pruebas y que `interface/router.py`/`main.py`
componen los módulos sin que un contrato importe el de otro ni ningún módulo
lea tablas ajenas. La migración 007 y HTTP se verifican juntos en un esquema
aislado de PostgreSQL, y un proceso nuevo relee lo que otro escribió.

No implementa tickets, SLA ni semilla demo: solo valida la composición ya
existente del bloque A.
"""

import ast
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.infrastructure import db
from app.modules.companies.infrastructure import company_repository
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
)
from app.modules.identity.infrastructure import session_store, user_repository
from app.modules.identity.infrastructure.password_hasher import Argon2PasswordHasher
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository
from hu26_sql_support import IsolatedPostgres
from migrations import run
from test_hu26_identity_atomic_storage import sandbox  # noqa: F401  (fixture A5a)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"
MIGRATION = "007_reconcile_identity_accounts.sql"
PASSWORD = "CompositionPassword123"

# Tablas internas por módulo; ninguna otra puede aparecer en su SQL.
OWNED_TABLES = {
    "companies": {"companies"},
    "identity": {
        "users",
        "identity_invitation_accounts",
        "identity_active_admin_guard",
    },
    "tickets": {"tickets", "ticket_comments"},
    "sla": {"sla_policies", "ticket_sla"},
    "assignment": set(),
}

ROUTERS = (
    ("app.modules.identity.interface.router", ("router", "invitation_router")),
    ("app.modules.identity.interface.technicians_router", ("router",)),
    ("app.modules.identity.interface.users_router", ("router",)),
    ("app.modules.companies.interface.router", ("router",)),
    ("app.modules.tickets.interface.router", ("router",)),
    ("app.modules.tickets.interface.assignments_router", ("router",)),
    ("app.modules.tickets.interface.comments_router", ("router",)),
    ("app.modules.tickets.interface.history_router", ("router",)),
    ("app.modules.tickets.interface.notifications_router", ("router",)),
    ("app.modules.tickets.interface.metrics_router", ("router",)),
    ("app.modules.tickets.interface.dashboard_router", ("router",)),
    ("app.modules.sla.interface.router", ("router",)),
    ("app.modules.sla.interface.dashboard_router", ("router",)),
)


def _python_sources(directory: Path):
    return sorted(directory.rglob("*.py"))


def _module_names():
    return sorted(
        path.name
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )


def _contract_imports(path: Path) -> set[str]:
    """Módulos `app.modules.*` importados por un archivo, con nombres completos."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            for alias in node.names:
                imported.add(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return imported


def _assert_no_sql_for(module: str, tables: set[str]):
    pattern = re.compile(
        r"\b(?:from|join|into|update|table)\s+(?:"
        + "|".join(sorted(re.escape(table) for table in tables))
        + r")\b",
        re.IGNORECASE,
    )
    for path in _python_sources(MODULES_ROOT / module):
        match = pattern.search(path.read_text(encoding="utf-8"))
        assert match is None, (
            f"{path.relative_to(BACKEND_ROOT)} accede a una tabla de otro módulo: "
            f"{match.group(0)!r}"
        )


# ---------------------------------------------------------------------------
# Composición estática: contratos, tablas y punto de composición
# ---------------------------------------------------------------------------


def test_contracts_never_import_another_modules_contract():
    contracts = sorted(MODULES_ROOT.glob("*/interface/*_contract.py"))
    assert len(contracts) >= 7
    for path in contracts:
        owner = path.relative_to(MODULES_ROOT).parts[0]
        imported = _contract_imports(path)
        assert any(
            module == f"app.modules.{owner}" or module.startswith(f"app.modules.{owner}.")
            for module in imported
        ), f"{path.relative_to(BACKEND_ROOT)} no importa su propio módulo"
        for imported_module in imported:
            parts = imported_module.split(".")
            if len(parts) < 4 or parts[:2] != ["app", "modules"]:
                continue
            target, layer = parts[2], parts[3]
            if target != owner and layer == "interface":
                assert not imported_module.endswith("_contract"), (
                    f"{path.relative_to(BACKEND_ROOT)} importa el contrato de "
                    f"{target}: {imported_module}"
                )


def test_no_module_reads_another_modules_tables():
    modules = _module_names()
    assert {"identity", "companies", "tickets", "sla", "assignment"} <= set(modules)
    for module in modules:
        foreign = set().union(
            *(
                tables
                for other, tables in OWNED_TABLES.items()
                if other != module
            )
        )
        _assert_no_sql_for(module, foreign)

    # El escaneo ve SQL real en los módulos que hoy leen PostgreSQL.
    for module in ("identity", "companies"):
        source = "".join(
            path.read_text(encoding="utf-8")
            for path in _python_sources(MODULES_ROOT / module)
        )
        own = "|".join(sorted(OWNED_TABLES[module]))
        assert re.search(
            rf"\b(?:from|join|into|update|table)\s+(?:{own})\b",
            source,
            re.IGNORECASE,
        ), f"{module} no mostró SQL propio al escanear"


def test_main_is_the_only_router_composition_point():
    from app.main import app, startup_database

    # Ningún módulo incluye routers ni aplica migraciones por su cuenta.
    for path in _python_sources(MODULES_ROOT):
        source = path.read_text(encoding="utf-8")
        assert "include_router(" not in source, path.relative_to(BACKEND_ROOT)
        assert "apply_migrations(" not in source, path.relative_to(BACKEND_ROOT)

    # El arranque aplica migraciones y la composición HTTP vive en main.py.
    assert startup_database in app.router.on_startup
    main_source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "apply_migrations" in main_source
    assert "include_router(" in main_source

    # Cada router de módulo está registrado en la aplicación compuesta.
    import importlib

    registered = set(app.openapi()["paths"])
    for module_name, attributes in ROUTERS:
        module = importlib.import_module(module_name)
        for attribute in attributes:
            router = getattr(module, attribute)
            router_paths = {route.path for route in router.routes}
            assert router_paths, f"{module_name}.{attribute} no declara rutas"
            assert router_paths <= registered, (
                f"Rutas sin componer en main.py: {router_paths - registered}"
            )


# ---------------------------------------------------------------------------
# PostgreSQL obligatorio y seam en memoria explícito
# ---------------------------------------------------------------------------


def _clear_database_environment(monkeypatch):
    for name in (
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "HELPDESK_ALLOW_IN_MEMORY",
        "SMTP_HOST",
    ):
        monkeypatch.delenv(name, raising=False)


def test_production_startup_requires_postgresql(monkeypatch):
    _clear_database_environment(monkeypatch)
    from app.main import initialize_database

    assert db.postgres_configured() is False
    assert db.in_memory_fallback_enabled() is False
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        initialize_database()
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        db.database_url()
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        InMemoryUserRepository().find_by_id(str(uuid.uuid4()))
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        InMemoryCompanyRepository().find_by_id(str(uuid.uuid4()))


def test_memory_seam_is_explicit_and_accepts_only_one(monkeypatch):
    _clear_database_environment(monkeypatch)
    from app.main import initialize_database

    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "true")
    assert db.in_memory_fallback_enabled() is False
    with pytest.raises(RuntimeError, match="Configura DATABASE_URL"):
        initialize_database()

    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    assert db.in_memory_fallback_enabled() is True
    assert initialize_database() is None
    assert InMemoryUserRepository().find_by_id(str(uuid.uuid4())) is None
    assert InMemoryCompanyRepository().find_by_id(str(uuid.uuid4())) is None

    # Con PostgreSQL configurado el seam no sustituye la ruta SQL.
    monkeypatch.setenv("DATABASE_URL", "postgresql://helpdesk@127.0.0.1:1/helpdesk")
    assert db.postgres_configured() is True


def test_configured_database_never_falls_back_to_memory(monkeypatch):
    _clear_database_environment(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://helpdesk@127.0.0.1:1/helpdesk?connect_timeout=1",
    )
    monkeypatch.setenv("HELPDESK_ALLOW_IN_MEMORY", "1")
    from app.main import initialize_database

    assert db.postgres_configured() is True
    with pytest.raises(psycopg.OperationalError):
        initialize_database()
    with pytest.raises(psycopg.OperationalError):
        InMemoryUserRepository().find_by_id(str(uuid.uuid4()))
    with pytest.raises(psycopg.OperationalError):
        InMemoryCompanyRepository().find_by_id(str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Migración 007 + HTTP en PostgreSQL aislado
# ---------------------------------------------------------------------------


def _use_isolated(monkeypatch, isolated):
    monkeypatch.setenv("DATABASE_URL", isolated.scoped_dsn)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("HELPDESK_ALLOW_IN_MEMORY", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setattr(db, "connect", isolated.connect)


def _reset_process_repositories(monkeypatch):
    monkeypatch.setattr(user_repository, "_users", InMemoryUserRepository())
    monkeypatch.setattr(
        session_store, "_sessions", session_store.InMemorySessionStore()
    )
    monkeypatch.setattr(
        company_repository, "_companies", InMemoryCompanyRepository()
    )


@pytest.fixture
def legacy_sandbox(monkeypatch):
    """Esquema aislado en el estado 001–006, listo para aplicar 007."""
    dsn = os.getenv("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("A7 SQL requiere HU26_TEST_DATABASE_URL en infra-db-1:55432")
    previous = [path for path in run.migration_files() if path.name < MIGRATION]
    with monkeypatch.context() as setup:
        setup.setattr(run, "migration_files", lambda: previous)
        with IsolatedPostgres(dsn) as isolated:
            setup.undo()
            _use_isolated(monkeypatch, isolated)
            yield isolated


def test_migration_and_http_compose_on_isolated_postgres(legacy_sandbox, monkeypatch):
    # Conservar la comprobación histórica 006→007 antes del tramo HTTP actual.
    current_migration_files = run.migration_files
    historical = [path for path in run.migration_files() if path.name <= MIGRATION]
    monkeypatch.setattr(run, "migration_files", lambda: historical)
    isolated = legacy_sandbox
    created = datetime(2025, 5, 1, tzinfo=timezone.utc)
    account_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    email = "reconciled.admin@ordinary.example.com"
    password_hash = Argon2PasswordHasher().hash(PASSWORD)

    with isolated.connect() as conn:
        conn.execute(
            "INSERT INTO companies (id,name,name_normalized) "
            "VALUES (%s,'Empresa compuesta','empresa compuesta')",
            (company_id,),
        )
        conn.execute(
            """INSERT INTO identity_invitation_accounts
               (account_id,company_id,name,email,phone,role,status,
                invitation_status,password_hash,invitation_token_hash,
                invitation_expires_at,invitation_used_at,created_at)
               VALUES (%s,%s,'Admin compuesta',%s,NULL,'administrador','active',
                       'accepted',%s,NULL,NULL,%s,%s)""",
            (account_id, company_id, email, password_hash, created, created),
        )
        projection_before = conn.execute(
            "SELECT * FROM identity_invitation_accounts ORDER BY account_id"
        ).fetchall()
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0

    with isolated.connect() as conn:
        assert run.apply_migrations(conn) == [MIGRATION]

    with isolated.connect() as conn:
        canonical = conn.execute(
            "SELECT id::text AS id, company_id::text AS company_id, email, role, "
            "status, invitation_status FROM users"
        ).fetchall()
        projection_after = conn.execute(
            "SELECT * FROM identity_invitation_accounts ORDER BY account_id"
        ).fetchall()
    assert canonical == [
        {
            "id": account_id,
            "company_id": company_id,
            "email": email,
            "role": "administrador",
            "status": "active",
            "invitation_status": "accepted",
        }
    ]
    # La tabla operativa anterior se conserva como proyección, no se reescribe.
    assert projection_after == projection_before

    # Autorizado en B.I.4: actualizar solo este esquema A1 antes del HTTP actual.
    monkeypatch.setattr(run, "migration_files", current_migration_files)
    with isolated.connect() as conn:
        assert run.apply_migrations(conn) == [
            path.name for path in current_migration_files() if path.name > MIGRATION
        ]

    _reset_process_repositories(monkeypatch)
    from app.main import app

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        )
        assert login.status_code == 200, login.text
        assert "password_hash" not in login.text and "invitation_token" not in login.text

        own = client.get("/api/companies/me")
        assert own.status_code == 200, own.text
        body = own.json()
        assert body["id"] == company_id
        assert body["name"] == "Empresa compuesta"
        assert body["users_total"] == 1
        assert body["has_administrator"] is True
        assert body["administrator_invitation_pending"] is False
        assert "password_hash" not in own.text

        # Una instancia de repositorio independiente relee lo confirmado.
        assert InMemoryUserRepository().find_by_email(email).id == account_id
        assert InMemoryCompanyRepository().find_by_id(company_id).name == (
            "Empresa compuesta"
        )
        assert InMemoryUserRepository().count() == 0
        assert InMemoryCompanyRepository().count() == 0


# ---------------------------------------------------------------------------
# Nuevo proceso: relee lo que otro proceso escribió por HTTP
# ---------------------------------------------------------------------------


def test_new_process_reads_what_http_wrote(sandbox, monkeypatch):
    _reset_process_repositories(monkeypatch)
    created = datetime(2025, 5, 2, tzinfo=timezone.utc)
    platform_email = "platform.compose@ordinary.example.com"
    with sandbox.connect() as conn:
        conn.execute(
            """INSERT INTO users
               (id,name,email,password_hash,role,status,invitation_status,
                invitation_used_at,created_at)
               VALUES (%s,'Plataforma',%s,%s,'administrador','active','accepted',
                       %s,%s)""",
            (
                str(uuid.uuid4()),
                platform_email,
                Argon2PasswordHasher().hash(PASSWORD),
                created,
                created,
            ),
        )

    invited_email = "invited.compose@ordinary.example.com"
    from app.main import app

    with TestClient(app) as client:
        assert client.post(
            "/api/auth/login",
            json={"email": platform_email, "password": PASSWORD},
        ).status_code == 200
        response = client.post(
            "/api/companies",
            json={
                "name": "Empresa durable",
                "email": "contacto@durable.example.com",
                "administrator": {"name": "Invitada", "email": invited_email},
            },
        )
        assert response.status_code == 201, response.text
        company_id = response.json()["company"]["id"]
        assert client.get(f"/api/companies/{company_id}").status_code == 200

    with sandbox.connect() as conn:
        account_id = str(
            conn.execute(
                "SELECT id::text AS id FROM users WHERE lower(email)=lower(%s)",
                (invited_email,),
            ).fetchone()["id"]
        )

    program = """
import json, sys
from app.modules.companies.infrastructure.company_repository import (
    InMemoryCompanyRepository,
)
from app.modules.identity.infrastructure.user_repository import InMemoryUserRepository

data = json.load(sys.stdin)
company = InMemoryCompanyRepository().find_by_id(data["company_id"])
account = InMemoryUserRepository().find_by_email(data["email"])
assert company is not None and company.name == data["name"]
assert account is not None and account.id == data["account_id"]
assert account.company_id == data["company_id"]
assert (account.role, account.status, account.invitation_status) == (
    "administrador", "active", "pending",
)
assert InMemoryCompanyRepository().count() == 0
assert InMemoryUserRepository().count() == 0
print("composition durable")
"""
    env = dict(os.environ)
    env["DATABASE_URL"] = sandbox.scoped_dsn
    env["PYTHONPATH"] = os.pathsep.join(
        [str(BACKEND_ROOT), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    env.pop("POSTGRES_PASSWORD", None)
    env.pop("HU26_TEST_DATABASE_URL", None)
    env.pop("HELPDESK_ALLOW_IN_MEMORY", None)
    result = subprocess.run(
        [sys.executable, "-c", program],
        env=env,
        input=json.dumps(
            {
                "company_id": company_id,
                "account_id": account_id,
                "email": invited_email,
                "name": "Empresa durable",
            }
        ),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "composition durable"
