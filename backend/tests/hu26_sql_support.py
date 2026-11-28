"""Infraestructura de pruebas A1; nunca se utiliza en el arranque operativo."""

import re
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from migrations.run import apply_migrations


ACCOUNT_CASES = (
    "identical",
    "operational_only",
    "conflicting_hash",
    "conflicting_email",
    "conflicting_company",
    "invalid_id",
    "missing_company",
)


class IsolatedPostgres:
    """Esquema aleatorio propio, sin public en la resolución de nombres.

    El DSN debe entregarse explícitamente desde el entorno de pruebas. No lee
    archivos .env, no migra public ni acepta el nombre de un esquema existente.
    No es un sandbox para ejecutar SQL arbitrario cualificado por un esquema.
    """

    def __init__(self, dsn: str):
        params = conninfo_to_dict(dsn)
        if (
            params.get("host") not in {"127.0.0.1", "localhost"}
            or params.get("port") != "55432"
            or params.get("hostaddr") not in {None, "", "127.0.0.1"}
            or params.get("service")
        ):
            raise ValueError("Solo se autoriza PostgreSQL local en 127.0.0.1:55432")
        self.base_dsn = dsn
        self._schema = f"hu26_test_{uuid.uuid4().hex}"
        self._owns_schema = False
        self.scoped_dsn = make_conninfo(
            dsn, options=f"-c search_path={self._schema},pg_catalog"
        )

    @property
    def schema(self) -> str:
        return self._schema

    def __enter__(self):
        with psycopg.connect(self.base_dsn, row_factory=dict_row) as admin:
            # 001 requiere pgcrypto. No instalar extensiones globales en pruebas.
            if not admin.execute(
                "SELECT 1 FROM pg_extension WHERE extname='pgcrypto'"
            ).fetchone():
                raise RuntimeError("pgcrypto debe existir antes de ejecutar A1")
            admin.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self._schema))
            )
        self._owns_schema = True
        try:
            with self.connect() as conn:
                apply_migrations(conn)
        except BaseException:
            self.close()
            raise
        return self

    def connect(self):
        if not self._owns_schema:
            raise RuntimeError("El esquema de prueba no está abierto")
        conn = psycopg.connect(
            self.scoped_dsn, row_factory=dict_row, connect_timeout=5
        )
        try:
            actual = conn.execute(
                "SELECT current_schema() AS name, current_schemas(false) AS path"
            ).fetchone()
            if actual != {
                "name": self._schema,
                "path": [self._schema, "pg_catalog"],
            }:
                raise RuntimeError("La conexión no está aislada del esquema operativo")
            conn.commit()
        except BaseException:
            conn.close()
            raise
        return conn

    def close(self):
        if not self._owns_schema:
            return
        if not re.fullmatch(r"hu26_test_[0-9a-f]{32}", self._schema):
            raise RuntimeError("Se rechaza limpiar un esquema no generado por A1")
        with psycopg.connect(self.base_dsn) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self._schema))
            )
        self._owns_schema = False

    def __exit__(self, *exc):
        self.close()


def seed_account_case(sandbox: IsolatedPostgres, case: str) -> dict:
    """Filas para la futura reconciliación, sin reconciliar ni modificar public."""
    if case not in ACCOUNT_CASES:
        raise ValueError("Caso de caracterización desconocido")
    account_id = str(uuid.uuid4())
    canonical = {
        "id": account_id,
        "email": "account@example.test",
        "password_hash": "$argon2id$test-only-original",
        "role": "cliente",
        "status": "active",
        "company_id": None,
    }
    operational = dict(canonical)
    if case == "conflicting_hash":
        operational["password_hash"] = "$argon2id$test-only-different"
    elif case == "conflicting_email":
        operational["email"] = "other@example.test"
    elif case == "invalid_id":
        operational["id"] = "legacy-not-a-uuid"
    elif case == "missing_company":
        operational["company_id"] = str(uuid.uuid4())
    with sandbox.connect() as conn:
        if case == "conflicting_company":
            for account, name in (
                (canonical, "Empresa original"),
                (operational, "Empresa distinta"),
            ):
                account["company_id"] = str(conn.execute(
                    "INSERT INTO companies (name, name_normalized) "
                    "VALUES (%s, %s) RETURNING id",
                    (name, name.lower()),
                ).fetchone()["id"])
        if case != "operational_only":
            conn.execute(
                "INSERT INTO users (id, name, email, password_hash, role, status, "
                "company_id) VALUES (%(id)s, 'Cuenta original', %(email)s, "
                "%(password_hash)s, %(role)s, %(status)s, %(company_id)s)",
                canonical,
            )
        conn.execute(
            "INSERT INTO identity_invitation_accounts "
            "(account_id, name, email, password_hash, role, status, company_id, "
            "invitation_status) VALUES (%(id)s, 'Cuenta original', %(email)s, "
            "%(password_hash)s, %(role)s, %(status)s, %(company_id)s, 'accepted')",
            operational,
        )
    return {
        "canonical_id": account_id,
        "operational_id": operational["id"],
        "canonical": canonical if case != "operational_only" else None,
        "operational": operational,
    }
