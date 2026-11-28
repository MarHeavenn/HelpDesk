"""B.I.9: composición existente; no acredita mutaciones ni despliegue."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import pytest

from app.modules.identity.interface.dependencies import SESSION_COOKIE_NAME
from app.modules.tickets.infrastructure import ticket_repository
import test_hu26_composition as composition
from test_hu26_ticket_create_http import (
    PASSWORD,
    VALID,
    clients,
    password_hash,
    sandbox,
    world,
)


def test_contracts_keep_their_own_dependencies():
    composition.test_contracts_never_import_another_modules_contract()
    # Incluir también contract.py de SLA, fuera del glob *_contract.py de A7.
    contracts = [
        *composition.MODULES_ROOT.glob("*/interface/*_contract.py"),
        *composition.MODULES_ROOT.glob("*/interface/contract.py"),
    ]
    for path in contracts:
        owner = path.relative_to(composition.MODULES_ROOT).parts[0]
        for imported in composition._contract_imports(path):
            parts = imported.split(".")
            if len(parts) >= 5 and parts[:2] == ["app", "modules"]:
                assert not (
                    parts[2] != owner and parts[3] == "interface"
                    and (parts[4] == "contract" or parts[4].endswith("_contract"))
                ), path


def test_ticket_sql_and_repository_dependencies_stay_with_the_owner():
    composition.test_no_module_reads_another_modules_tables()
    path = composition.MODULES_ROOT / "tickets/infrastructure/ticket_repository.py"
    source = path.read_text(encoding="utf-8")
    assert re.search(r"\bFROM\s+tickets\b", source, re.IGNORECASE)
    assert re.search(r"\bINSERT\s+INTO\s+tickets\b", source, re.IGNORECASE)
    for imported in composition._contract_imports(path):
        if imported.startswith("app.modules."):
            assert imported.startswith("app.modules.tickets.")


def test_main_remains_the_composition_and_migration_point():
    composition.test_main_is_the_only_router_composition_point()


# El hijo no recibe objetos/repositorios/seed. Solo configuración SQL scoped
# y expectativas sintéticas por stdin; las consultas son HTTP reales.
CHILD_PROGRAM = r"""
import json, os, sys
from datetime import datetime
from dataclasses import asdict

from app.infrastructure import db
from app.modules.identity.infrastructure.user_repository import get_user_repository
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.interface.dependencies import SESSION_COOKIE_NAME
from app.modules.companies.infrastructure.company_repository import get_company_repository
from app.modules.tickets.infrastructure.ticket_repository import get_ticket_repository
from app.modules.tickets.interface.company_ticket_contract import get_company_ticket_stats
from app.modules.tickets.interface.sla_contract import list_sla_tickets
from fastapi.testclient import TestClient

data = json.load(sys.stdin)
assert "POSTGRES_PASSWORD" not in os.environ
assert "HU26_TEST_DATABASE_URL" not in os.environ
assert "HELPDESK_ALLOW_IN_MEMORY" not in os.environ
assert get_user_repository().count() == get_company_repository().count() == 0
assert get_session_store().count() == 0
assert get_ticket_repository()._by_id == {}

# Validar TODAS las conexiones, incluido startup; no sustituir SQL ni casos de uso.
original_connect = db.connect
connections = []
def checked_connect():
    conn = original_connect()
    try:
        actual = conn.execute(
            "SELECT current_schema() AS name, current_schemas(false) AS path"
        ).fetchone()
        assert actual == {
            "name": data["schema"], "path": [data["schema"], "pg_catalog"]
        }
        conn.commit()
    except BaseException:
        conn.close()
        raise
    connections.append(actual)
    return conn
db.connect = checked_connect

from app.main import app
summary_keys = {
    "id", "title", "priority", "status", "assignee", "sla", "created_at", "requester"
}
expected_summaries = []
for body in data["bodies"]:
    summary = {key: body[key] for key in summary_keys}
    summary["requester"] = {"name": data["actor"]["name"]}
    expected_summaries.append(summary)

with TestClient(app) as client:
    # Ni una cookie del padre ni una petición anónima son una sesión del hijo.
    assert client.get("/api/tickets").status_code == 401
    denied = client.get(
        "/api/tickets/" + data["bodies"][0]["id"],
        headers={"Cookie": SESSION_COOKIE_NAME + "=" + data["old_cookie"]},
    )
    assert denied.status_code == 401
    assert get_session_store().count() == 0
    login = client.post("/api/auth/login", json={
        "email": data["actor"]["email"], "password": data["password"],
    })
    assert login.status_code == 200
    assert login.json()["id"] == data["actor"]["id"]
    for body in data["bodies"]:
        response = client.get("/api/tickets/" + body["id"])
        assert response.status_code == 200 and response.json() == body
        assert datetime.fromisoformat(response.json()["created_at"]) == (
            datetime.fromisoformat(body["created_at"])
        )
        stored = get_ticket_repository().find_by_id(body["id"])
        assert stored.company_id == data["actor"]["company_id"]
        assert stored.requester_id == data["actor"]["id"]
        for field in (
            "priority", "assignee_id", "assignee_name", "resolved_at",
            "resolved_target_minutes",
        ):
            assert getattr(stored, field) is None
    listing = client.get("/api/tickets")
    assert listing.status_code == 200
    assert sorted(listing.json(), key=lambda row: row["id"]) == (
        sorted(expected_summaries, key=lambda row: row["id"])
    )
    assert client.get("/api/tickets/" + data["ghost_id"]).status_code == 404

with TestClient(app) as admin:
    assert admin.post("/api/auth/login", json={
        "email": data["admin"]["email"], "password": data["password"],
    }).status_code == 200
    listing = admin.get("/api/tickets/all")
    assert listing.status_code == 200
    assert sorted(listing.json(), key=lambda row: row["id"]) == (
        sorted(expected_summaries, key=lambda row: row["id"])
    )

# Fronteras existentes recuperan SQL sin importar contratos ajenos.
stats = get_company_ticket_stats(data["actor"]["company_id"])
assert stats.tickets_total == 2
assert dict(stats.by_status) == {
    "Abierto": 2, "En progreso": 0, "Resuelto": 0, "Cerrado": 0,
}
views = {view.id: view for view in list_sla_tickets()}
assert set(views) == {body["id"] for body in data["bodies"]}
for body in data["bodies"]:
    view = views[body["id"]]
    assert view.company_id == data["actor"]["company_id"]
    assert view.created_at == datetime.fromisoformat(body["created_at"])
    assert view.status == "Abierto" and not view.is_resolved
    assert view.priority is view.assignee_id is view.resolved_at is (
        view.resolved_target_minutes
    ) is None
assert connections
assert get_ticket_repository().count() == 2
assert get_ticket_repository()._by_id == {}
assert get_user_repository().count() == get_company_repository().count() == 0
print("ticket base durable; scoped startup/http; reauthenticated; no seed/cache")
"""


@pytest.mark.parametrize("actor_key", ["client", "admin"])
def test_http_created_tickets_survive_a_fresh_app_process(
    sandbox, world, clients, actor_key,
):
    client = clients(actor_key)
    bodies = []
    for _ in range(2):
        response = client.post("/api/tickets", json=VALID)
        assert response.status_code == 201
        bodies.append(response.json())
    assert bodies[0]["id"] != bodies[1]["id"]
    assert bodies[0]["title"] == bodies[1]["title"]
    with sandbox.connect() as conn:
        before = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    assert len(before) == 2

    # Cambios EXCLUSIVAMENTE locales de una referencia y una caché fantasma:
    # no llamar mutaciones aún no persistidas ni prometer recuperarlas.
    repository = ticket_repository.get_ticket_repository()
    retained = repository.find_by_id(bodies[0]["id"])
    retained.title = "Solo memoria, no es un cambio confirmado"
    retained.status = "Cerrado"
    retained.resolved_target_minutes = 987
    repository._by_id[retained.id] = retained
    ghost_id = str(uuid4())
    repository._by_id[ghost_id] = retained

    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("DEMO_", "PLATFORM_ADMIN_", "SMTP_")) or key in {
            "POSTGRES_PASSWORD", "HU26_TEST_DATABASE_URL", "HELPDESK_ALLOW_IN_MEMORY",
            "SESSION_COOKIE_SECURE", "SESSION_COOKIE_SAMESITE",
        }:
            env.pop(key, None)
    env["DATABASE_URL"] = sandbox.scoped_dsn
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run(
        [sys.executable, "-c", CHILD_PROGRAM],
        env=env,
        input=json.dumps({
            "schema": sandbox.schema, "actor": world[actor_key],
            "admin": world["admin"], "password": PASSWORD, "bodies": bodies,
            "ghost_id": ghost_id, "old_cookie": client.cookies.get(SESSION_COOKIE_NAME),
        }),
        text=True, capture_output=True, timeout=60,
    )
    # No propagar stdout/stderr con posibles datos de conexión.
    assert result.returncode == 0, (
        f"El hijo no superó las aserciones SQL/HTTP (exit {result.returncode})"
    )
    assert result.stdout.strip() == (
        "ticket base durable; scoped startup/http; reauthenticated; no seed/cache"
    )
    with sandbox.connect() as conn:
        assert conn.execute("SELECT * FROM tickets ORDER BY id").fetchall() == before
