"""B.I.2: campos aditivos del ticket, solo en esquemas aislados A1."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest

from hu26_sql_support import IsolatedPostgres
from migrations import run
from test_hu26_ticket_legacy import evidence, legacy, snapshot


VERSION = "008_ticket_persistence.sql"
FIELDS = {
    "assignee_name": "text",
    "resolved_at": "timestamp with time zone",
    "resolved_target_minutes": "integer",
}


@pytest.fixture(autouse=True)
def through_ticket_fields(monkeypatch):
    # Acotar esta prueba de migración, sin imponer una última versión al proyecto.
    installation = [p for p in run.migration_files() if p.name <= VERSION]
    monkeypatch.setattr(run, "migration_files", lambda: installation)


def migrate(sandbox):
    with sandbox.connect() as conn:
        return run.apply_migrations(conn)


def structure(sandbox):
    """Catálogo propio: detecta cambios no autorizados de columnas/FK/triggers."""
    with sandbox.connect() as conn:
        return {
            "columns": conn.execute(
                "SELECT table_name, column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns WHERE table_schema=current_schema() "
                "ORDER BY table_name, ordinal_position"
            ).fetchall(),
            "constraints": conn.execute(
                "SELECT c.relname, x.conname, pg_get_constraintdef(x.oid) AS definition "
                "FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid "
                "WHERE c.relnamespace=current_schema()::regnamespace "
                "ORDER BY c.relname, x.conname"
            ).fetchall(),
            "triggers": conn.execute(
                "SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid) AS definition "
                "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "WHERE c.relnamespace=current_schema()::regnamespace "
                "ORDER BY c.relname, t.tgname"
            ).fetchall(),
            "indexes": conn.execute(
                "SELECT tablename, indexname, indexdef FROM pg_indexes "
                "WHERE schemaname=current_schema() ORDER BY tablename,indexname"
            ).fetchall(),
        }


def versions(sandbox):
    with sandbox.connect() as conn:
        return conn.execute(
            "SELECT * FROM schema_migrations ORDER BY version"
        ).fetchall()


def assert_new_columns(sandbox):
    added = [
        row for row in structure(sandbox)["columns"]
        if row["table_name"] == "tickets" and row["column_name"] in FIELDS
    ]
    assert {row["column_name"]: row["data_type"] for row in added} == FIELDS
    assert all(row["is_nullable"] == "YES" and row["column_default"] is None
               for row in added)


def test_ticket_fields_have_a_new_incremental_migration():
    assert VERSION in [path.name for path in run.migration_files()]


def test_clean_install_has_nullable_fields_without_defaults():
    dsn = os.environ.get("HU26_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("B.I.2 requiere PostgreSQL aislado opt-in")
    with IsolatedPostgres(dsn) as sandbox:
        assert_new_columns(sandbox)
        assert VERSION in {row["version"] for row in versions(sandbox)}
        assert migrate(sandbox) == []


def test_upgrade_from_007_only_adds_fields_and_preserves_all_legacy_values(
    legacy, evidence
):
    before = snapshot(legacy)
    schema_before = structure(legacy)
    log_before = versions(legacy)
    assert migrate(legacy) == [VERSION]
    assert_new_columns(legacy)
    after = snapshot(legacy)
    assert after["ticket_sla"] == before["ticket_sla"]
    assert after["ticket_comments"] == before["ticket_comments"]
    assert [
        {key: value for key, value in row.items() if key not in FIELDS}
        for row in after["tickets"]
    ] == before["tickets"]
    assert all(row[field] is None for row in after["tickets"] for field in FIELDS)
    schema_after = structure(legacy)
    schema_after["columns"] = [
        row for row in schema_after["columns"]
        if not (row["table_name"] == "tickets" and row["column_name"] in FIELDS)
    ]
    assert schema_after == schema_before
    log_after = versions(legacy)
    assert log_after[:-1] == log_before
    assert log_after[-1]["version"] == VERSION


def test_runner_repetition_preserves_known_values_and_migration_timestamp(
    legacy, evidence
):
    assert migrate(legacy) == [VERSION]
    resolved = datetime(2024, 3, 1, 12, tzinfo=timezone.utc)
    with legacy.connect() as conn:
        conn.execute(
            "UPDATE tickets SET assignee_name=%s,resolved_at=%s,"
            "resolved_target_minutes=%s WHERE id=%s",
            ("Proyección sintética conservada", resolved, 137, evidence[0][2][0]),
        )
    before, schema_before, log_before = snapshot(legacy), structure(legacy), versions(legacy)
    assert migrate(legacy) == []
    assert snapshot(legacy) == before
    assert structure(legacy) == schema_before
    assert versions(legacy) == log_before
    known = next(row for row in before["tickets"] if row["id"] == evidence[0][2][0])
    assert (known["assignee_name"], known["resolved_at"], known["resolved_target_minutes"]) == (
        "Proyección sintética conservada", resolved, 137,
    )


def test_failed_migration_rolls_back_ddl_data_and_version(
    legacy, evidence, monkeypatch, tmp_path
):
    before, schema_before, log_before = snapshot(legacy), structure(legacy), versions(legacy)
    source = run.MIGRATIONS_DIR / VERSION
    assert source.is_file()
    failed = tmp_path / VERSION
    # Ejecutar el SQL real y fallar después de sus cambios, dentro del runner real.
    failed.write_text(
        source.read_text(encoding="utf-8")
        + "\nDO $$ BEGIN RAISE EXCEPTION 'B.I.2 synthetic migration failure'; END $$;",
        encoding="utf-8",
    )
    monkeypatch.setattr(run, "migration_files", lambda: [failed])
    with legacy.connect() as conn:
        with pytest.raises(psycopg.errors.RaiseException, match="synthetic migration failure"):
            run.apply_migrations(conn)
        # Capturar el error y confirmar luego no debe conservar cambios parciales.
        assert conn.execute(
            "SELECT count(*) AS n FROM schema_migrations WHERE version=%s", (VERSION,)
        ).fetchone()["n"] == 0
    assert snapshot(legacy) == before
    assert structure(legacy) == schema_before
    assert versions(legacy) == log_before


def test_existing_tenant_constraints_and_triggers_still_enforce_integrity(
    legacy, evidence
):
    assert migrate(legacy) == [VERSION]
    ticket, _, _, _ = evidence[0][0]
    foreign_user = evidence[0][4][2]
    for field in ("requester_id", "assignee_id"):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with legacy.connect() as conn:
                conn.execute(f"UPDATE tickets SET {field}=%s WHERE id=%s",
                             (foreign_user, ticket))
    with pytest.raises(psycopg.errors.CheckViolation):
        with legacy.connect() as conn:
            conn.execute(
                "INSERT INTO ticket_comments (id,ticket_id,author_id,body) "
                "VALUES (%s,%s,%s,'Comentario sintético ajeno')",
                (uuid4(), ticket, foreign_user),
            )
    with legacy.connect() as conn:
        changed = conn.execute(
            "UPDATE tickets SET title='Cambio sintético' WHERE id=%s "
            "RETURNING updated_at, now() AS transaction_time", (ticket,)
        ).fetchone()
    assert changed["updated_at"] == changed["transaction_time"]
    assert changed["updated_at"] > evidence[2]
