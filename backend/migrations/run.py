"""Migraciones SQL de DeskHelp (TSK-025).

Runner minimo e idempotente: aplica en orden los archivos
`NNN_*.sql` que aun no esten registrados en `schema_migrations`.
Cada archivo se ejecuta dentro de su propia transaccion.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.db import database_url  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent


def migration_files() -> list[Path]:
    """Devuelve los archivos de migracion ordenados por nombre."""
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    """Aplica las migraciones pendientes y devuelve sus versiones.

    Es idempotente: una migracion ya registrada no se vuelve a ejecutar.
    """
    with conn.transaction():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )

    applied: list[str] = []
    for path in migration_files():
        version = path.name
        with conn.transaction():
            already_applied = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s",
                (version,),
            ).fetchone()
            if already_applied:
                continue

            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            applied.append(version)

    return applied


def main() -> int:
    with psycopg.connect(database_url()) as conn:
        applied = apply_migrations(conn)

    if applied:
        print("Migraciones aplicadas: " + ", ".join(applied))
    else:
        print("Sin migraciones pendientes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
