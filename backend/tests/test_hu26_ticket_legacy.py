"""B.I.1: evidencia sintética de 007, sin reparar ni importar legado."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from migrations import run
from hu26_sql_support import IsolatedPostgres


@pytest.fixture
def legacy(monkeypatch):
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.1 requiere PostgreSQL aislado opt-in")
    through_007 = [p for p in run.migration_files() if p.name[:3] <= "007"]
    with monkeypatch.context() as setup:
        setup.setattr(run, "migration_files", lambda: through_007)
        with IsolatedPostgres(dsn) as sandbox:
            setup.undo()
            yield sandbox


@pytest.fixture
def evidence(legacy):
    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    updated = datetime(2024, 2, 1, tzinfo=timezone.utc)
    tickets = []
    with legacy.connect() as conn:
        for number in range(2):
            company = uuid4()
            requester = uuid4()
            conn.execute(
                "INSERT INTO companies (id, name, name_normalized) VALUES (%s,%s,%s)",
                (company, f"Empresa sintética {number}", f"empresa sintética {number}"),
            )
            conn.execute(
                "INSERT INTO users (id, company_id, name, email, password_hash, role) "
                "VALUES (%s,%s,%s,%s,%s,'cliente')",
                (requester, company, "Cuenta sintética", f"synthetic{number}@example.test",
                 "$argon2id$synthetic"),
            )
            for status in ("Abierto", "En progreso", "Resuelto", "Cerrado"):
                ticket = uuid4()
                conn.execute(
                    "INSERT INTO tickets (id, company_id, requester_id, title, description,"
                    " status, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (ticket, company, requester, "Sintético", "Descripción sintética",
                     status, created, updated),
                )
                tickets.append((ticket, company, requester, status))
        ticket, _, author, _ = tickets[2]
        for body in ("Primero hipotético", "Segundo hipotético"):
            conn.execute(
                "INSERT INTO ticket_comments (id,ticket_id,author_id,body,created_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid4(), ticket, author, body, updated),
            )
        # El objetivo de esta tabla no prueba el objetivo congelado del ticket.
        conn.execute(
            "INSERT INTO ticket_sla (id,ticket_id,target_minutes,started_at,due_at) "
            "VALUES (%s,%s,120,%s,%s)",
            (uuid4(), ticket, created, created),
        )
    return tickets, created, updated


def snapshot(sandbox):
    with sandbox.connect() as conn:
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in ("tickets", "ticket_comments", "ticket_sla")
        }


def test_007_preserves_rows_and_distinguishes_missing_columns_from_null(legacy, evidence):
    expected, created, updated = evidence
    before = snapshot(legacy)
    with legacy.connect() as conn:
        columns = {row["column_name"] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='tickets'"
        )}
        versions = {row["version"][:3] for row in conn.execute(
            "SELECT version FROM schema_migrations"
        )}
    assert "007" in versions
    assert {"assignee_name", "resolved_at", "resolved_target_minutes"}.isdisjoint(columns)
    assert {(r["id"], r["company_id"], r["requester_id"], r["status"])
            for r in before["tickets"]} == set(expected)
    assert all(r["created_at"] == created and r["updated_at"] == updated
               and r["assignee_id"] is None and r["priority"] is None
               for r in before["tickets"])
    assert snapshot(legacy) == before


def test_equal_comment_times_and_sla_do_not_prove_history(legacy, evidence):
    before = snapshot(legacy)
    comments = before["ticket_comments"]
    assert len(comments) == 2 and comments[0]["created_at"] == comments[1]["created_at"]
    assert comments[0]["id"] != comments[1]["id"]
    assert len(before["ticket_sla"]) == 1
    assert before["ticket_sla"][0]["resolved_at"] is None
    assert before["ticket_sla"][0]["target_minutes"] == 120
    # Orden por UUID o política SLA actual no es evidencia histórica.
    assert snapshot(legacy) == before


@pytest.mark.parametrize("target", [None, 120])
def test_future_known_resolution_cases_are_not_007_ticket_columns(legacy, evidence, target):
    # Casos para tareas posteriores, no escritura de columnas futuras ni backfill.
    hypothetical = {"resolved_at": evidence[2], "resolved_target_minutes": target}
    assert hypothetical["resolved_at"] is not None
    assert hypothetical["resolved_target_minutes"] == target
    before = snapshot(legacy)
    assert all("resolved_at" not in row and "resolved_target_minutes" not in row
               for row in before["tickets"])
    assert snapshot(legacy) == before
