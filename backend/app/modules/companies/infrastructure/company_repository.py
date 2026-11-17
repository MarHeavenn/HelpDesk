"""Repositorio de empresas (HU-19, RF-126, RF-128 y RF-139).

Sigue el patron de `InMemoryUserRepository`: el repositorio en memoria es
la vista rapida y PostgreSQL el almacen compartido. No hay unicidad de
nombre en el repositorio: D-2 tolera empresas heredadas duplicadas y la
resolucion de conflictos se hace en la aplicacion bajo el bloqueo
transaccional que expone `name_lock`.
"""

from contextlib import contextmanager
from threading import RLock
from typing import Iterator

from app.infrastructure.db import (
    connection,
    in_memory_fallback_enabled,
    postgres_configured,
)
from app.modules.companies.domain.entities import Company

_fallback_name_locks: dict[str, RLock] = {}
_fallback_name_locks_guard = RLock()


def _fallback_name_lock(name_normalized: str) -> RLock:
    """Devuelve el lock en memoria de una forma normalizada concreta."""
    with _fallback_name_locks_guard:
        return _fallback_name_locks.setdefault(name_normalized, RLock())


class InMemoryCompanyRepository:
    """Guarda empresas por identificador y las sincroniza con PostgreSQL."""

    def __init__(self) -> None:
        self._by_id: dict[str, Company] = {}
        self.lock = RLock()

    def add(self, company: Company, conn=None) -> None:
        """Guarda la empresa sin imponer unicidad de nombre (D-2).

        La unicidad se resuelve en la aplicacion dentro de `name_lock`. `conn`
        permite que el alta participe en la transaccion del bloqueo (RF-135).
        """
        with self.lock:
            self._by_id[company.id] = company
            try:
                self.sync_persistent(company, conn)
            except RuntimeError:
                if postgres_configured() or not in_memory_fallback_enabled():
                    raise

    def find_by_id(self, company_id: str) -> Company | None:
        """Busca por identificador; None si no existe o no es texto."""
        if not isinstance(company_id, str):
            return None
        return self._by_id.get(company_id)

    def list_all(self) -> list[Company]:
        """Devuelve una copia de todas las empresas almacenadas."""
        return list(self._by_id.values())

    def find_by_name_normalized(
        self, name_normalized: str, conn=None
    ) -> Company | None:
        """Primera empresa con esa forma normalizada, o `None` (RF-128).

        Con PostgreSQL consulta el almacen compartido (dentro de `conn` si se
        entrega) para que dos instancias con repositorios independientes
        detecten el conflicto bajo el bloqueo de `name_lock` (D-2). Sin
        PostgreSQL solo se admite el seam explicito en memoria: no hay
        fallback silencioso.
        """
        if not isinstance(name_normalized, str):
            return None
        if conn is not None:
            return self._find_persistent_by_name(name_normalized, conn)
        if postgres_configured():
            with connection() as owned:
                return self._find_persistent_by_name(name_normalized, owned)
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar empresas"
            )
        return next(
            (
                company
                for company in self._by_id.values()
                if company.name_normalized == name_normalized
            ),
            None,
        )

    def _find_persistent_by_name(self, name_normalized: str, conn) -> Company | None:
        row = conn.execute(
            """
            SELECT id, name, name_normalized, email, phone, contact_name,
                   status, created_at
            FROM companies
            WHERE name_normalized = %s
            ORDER BY created_at, id
            LIMIT 1
            """,
            (name_normalized,),
        ).fetchone()
        return self._company_from_row(row) if row else None

    def update(self, company: Company, conn=None) -> None:
        """Reemplaza la empresa almacenada y la persiste."""
        with self.lock:
            self._by_id[company.id] = company
            try:
                self.sync_persistent(company, conn)
            except RuntimeError:
                if postgres_configured() or not in_memory_fallback_enabled():
                    raise

    def remove(self, company_id: str) -> None:
        """Retira una empresa; se usa para compensar un alta fallida."""
        with self.lock:
            removed = self._by_id.pop(company_id, None)
            if removed is None:
                return
            if not postgres_configured():
                if in_memory_fallback_enabled():
                    return
                raise RuntimeError(
                    "Configura DATABASE_URL o POSTGRES_PASSWORD para persistir empresas"
                )
            with connection() as conn:
                conn.execute("DELETE FROM companies WHERE id = %s", (company_id,))

    def count(self) -> int:
        """Numero de empresas almacenadas."""
        return len(self._by_id)

    def clear(self) -> None:
        """Vacia el repositorio (apoyo para pruebas)."""
        with self.lock:
            self._by_id.clear()
        try:
            with connection() as conn:
                conn.execute("DELETE FROM companies")
        except Exception:
            # El repositorio en memoria sigue siendo utilizable en pruebas
            # unitarias sin PostgreSQL; produccion aplica la migracion antes.
            pass

    @staticmethod
    def _upsert_sql() -> str:
        return """
            INSERT INTO companies (
                id, name, name_normalized, email, phone, contact_name,
                status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                name_normalized = EXCLUDED.name_normalized,
                email = EXCLUDED.email,
                phone = EXCLUDED.phone,
                contact_name = EXCLUDED.contact_name,
                status = EXCLUDED.status
        """

    def sync_persistent(self, company: Company, conn=None) -> None:
        """Persiste la empresa en el almacen compartido."""
        if conn is None and not postgres_configured():
            if in_memory_fallback_enabled():
                return
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para persistir empresas"
            )
        if conn is None:
            with connection() as owned:
                self.sync_persistent(company, owned)
            return
        conn.execute(
            self._upsert_sql(),
            (
                company.id,
                company.name,
                company.name_normalized,
                company.email,
                company.phone,
                company.contact_name,
                company.status,
                company.created_at,
            ),
        )

    @staticmethod
    def _company_from_row(row) -> Company:
        return Company(
            id=str(row["id"]),
            name=row["name"],
            name_normalized=row["name_normalized"],
            email=row["email"],
            phone=row["phone"],
            contact_name=row["contact_name"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def load_persistent_for_update(self, company_id: str, conn) -> Company | None:
        """Relee la empresa dentro de la transaccion y la bloquea."""
        row = conn.execute(
            """
            SELECT id, name, name_normalized, email, phone, contact_name,
                   status, created_at
            FROM companies
            WHERE id = %s
            FOR UPDATE
            """,
            (company_id,),
        ).fetchone()
        return self._company_from_row(row) if row else None

    @contextmanager
    def name_lock(self, name_normalized: str) -> Iterator[object]:
        """Serializa altas y cambios de nombre por forma normalizada (D-2).

        Con PostgreSQL usa `pg_advisory_xact_lock` sobre la forma
        normalizada, por lo que la exclusion vale entre procesos e
        instancias. Sin PostgreSQL solo se admite el seam explicito
        `HELPDESK_ALLOW_IN_MEMORY=1`, que serializa en el proceso. En
        cualquier otro caso la operacion falla: no hay fallback silencioso.
        """
        if postgres_configured():
            with connection() as conn:
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (name_normalized,),
                )
                yield conn
            return

        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para bloquear empresas"
            )

        with _fallback_name_lock(name_normalized):
            yield None


_companies = InMemoryCompanyRepository()


def get_company_repository() -> InMemoryCompanyRepository:
    """Devuelve el repositorio compartido de empresas."""
    return _companies
