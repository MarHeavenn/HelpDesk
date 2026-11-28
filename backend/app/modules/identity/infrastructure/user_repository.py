"""Repositorio en memoria de usuarios (RF-4).

Almacena los usuarios por email ya normalizado (trim + minusculas), de
modo que la unicidad case-insensitive queda garantizada tambien en la
persistencia: `add` rechaza el duplicado aunque el caso de uso no lo
haya comprobado. Sustituible por un adaptador PostgreSQL sin cambiar
el contrato.
"""

from datetime import datetime
from threading import RLock
from app.infrastructure.db import (
    connection,
    in_memory_fallback_enabled,
    postgres_configured,
)
from contextlib import contextmanager
from uuid import UUID

from psycopg.pq import TransactionStatus

from app.modules.identity.domain.entities import User, normalize_email


class EmailAlreadyStoredError(ValueError):
    """El email (normalizado) ya existe en la persistencia."""


def _is_unique_violation(exc: BaseException) -> bool:
    """Detecta una violacion de restriccion unica de PostgreSQL (R2)."""
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate == "23505":
        return True
    if "UniqueViolation" in type(exc).__name__:
        return True
    message = str(exc).lower()
    return "unique" in message and "violat" in message


class LastActiveAdministratorPersistenceError(ValueError):
    """La persistencia compartida impediria retirar el ultimo administrador."""


@contextmanager
def _account_transaction(conn):
    """Savepoint indivisible, sin confirmar la transacción del llamador."""
    if conn.info.transaction_status == TransactionStatus.IDLE:
        # También funciona con autocommit: el llamador conserva el COMMIT final.
        conn.execute("BEGIN")
    with conn.transaction():
        yield


_fallback_admin_lock = RLock()
_fallback_active_admins: dict[str, set[str]] = {}


def _ensure_admin_guard_table(conn) -> None:
    """Crea el coordinador compartido sin alterar el versionado aprobado."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS identity_active_admin_guard (
            company_id text PRIMARY KEY,
            active_admin_ids text[] NOT NULL
        )
        """
    )


class InMemoryUserRepository:
    """Repositorio transitorio: lecturas SQL o seam explícito en memoria.

    Las escrituras se migran en A5; no desplegar esta
    transición parcialmente. Con PostgreSQL, la caché no autoriza lecturas.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, User] = {}
        self.lock = RLock()

    def add(self, user: User, conn=None) -> None:
        """Guarda el usuario; lanza EmailAlreadyStoredError si el email
        normalizado ya existe.

        `conn` permite que el alta participe en la transaccion del llamador
        (HU-19 RF-135: empresa y administrador inicial en una sola operacion).
        """
        if conn is not None or postgres_configured():
            if conn is None:
                with connection() as owned:
                    self.add(user, owned)
                return
            with _account_transaction(conn):
                self.sync_persistent(user, conn)
                if (
                    user.company_id is not None
                    and user.role == "administrador"
                    and user.status == "active"
                ):
                    self._register_active_admin_if_guarded(user, conn)
            # Las lecturas SQL son autoritativas; nunca publicar un agregado
            # antes del commit (incluido el commit externo del llamador).
            return
        key = normalize_email(user.email)
        with self.lock:
            if key in self._by_email:
                raise EmailAlreadyStoredError("email already registered")
            self.sync_persistent(user)
            self._by_id[user.id] = user
            self._by_email[key] = user
            if (
                user.company_id is not None
                and user.role == "administrador"
                and user.status == "active"
            ):
                with _fallback_admin_lock:
                    _fallback_active_admins.setdefault(user.company_id, set()).add(user.id)

    def update_email(self, user: User, email: str) -> None:
        key = normalize_email(email)
        if postgres_configured():
            # El guardado explícito valida la unicidad en PostgreSQL.
            user.email = key
            return
        with self.lock:
            existing = self._by_email.get(key)
            if existing is not None and existing is not user:
                raise EmailAlreadyStoredError("email already registered")
            self._by_email.pop(normalize_email(user.email), None)
            user.email = key
            self._by_email[key] = user

    def remove(self, user_id: str) -> None:
        """Retira una cuenta del repositorio del proceso.

        Se usa para compensar un alta fallida (RO-01): si la persistencia
        rechaza la cuenta, no debe quedar una cuenta parcial en la vista en
        memoria. No elimina cuentas ya persistidas: el rollback de la
        transacción de PostgreSQL deshace su propia inserción.
        """
        with self.lock:
            removed = self._by_id.pop(user_id, None)
            if removed is None:
                return
            self._by_email.pop(normalize_email(removed.email), None)
            if removed.company_id is not None:
                with _fallback_admin_lock:
                    admins = _fallback_active_admins.get(removed.company_id)
                    if admins is not None:
                        admins.discard(removed.id)
                        if not admins:
                            _fallback_active_admins.pop(removed.company_id, None)

    def find_by_email(self, email: str) -> User | None:
        """Busca en users con PostgreSQL; memoria solo mediante seam explícito."""
        try:
            key = normalize_email(email)
        except (ValueError, AttributeError):
            return None
        if postgres_configured():
            return self._find_canonical(key, by_email=True)
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar usuarios"
            )
        return self._by_email.get(key)

    def find_by_email_persistent(self, email: str) -> User | None:
        """Alias compatible: el correo se resuelve siempre por la misma autoridad."""
        return self.find_by_email(email)

    def _find_canonical(self, value: str, *, by_email: bool = False) -> User | None:
        # Solo estas dos cláusulas fijas; el valor siempre viaja como parámetro.
        predicate = "lower(email) = %s" if by_email else "id = %s"
        with connection() as conn:
            row = conn.execute(
                """SELECT id::text AS account_id, company_id::text AS company_id,
                          name, email, phone, role, status, invitation_status,
                          password_hash, invitation_token_hash,
                          invitation_expires_at, invitation_used_at, created_at
                   FROM users WHERE """ + predicate,
                (value,),
            ).fetchone()
        return self._user_from_row(row) if row else None

    def cache_persistent_user(self, user: User) -> User:
        """Incorpora una cuenta ya leida de PostgreSQL sin modificarla."""
        key = normalize_email(user.email)
        with self.lock:
            existing = self._by_email.get(key)
            if existing is not None:
                return existing
            self._by_email[key] = user
            self._by_id[user.id] = user
            return user

    def find_by_id(self, user_id: str) -> User | None:
        """Recupera el agregado canónico sin reutilizar objetos del proceso."""
        if postgres_configured():
            if not isinstance(user_id, str):
                return None
            try:
                canonical_id = str(UUID(user_id))
            except ValueError:
                return None
            return self._find_canonical(canonical_id)
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar usuarios"
            )
        return self._by_id.get(user_id)

    def list_all(self) -> list[User]:
        """Recupera todas las cuentas canónicas sin hidratar la caché.

        Los consumidores conservan sus filtros y ordenaciones de dominio.
        El seam de memoria mantiene el orden y las referencias heredadas.
        """
        if postgres_configured():
            with connection() as conn:
                rows = conn.execute(
                    """SELECT id::text AS account_id, company_id::text AS company_id,
                              name, email, phone, role, status, invitation_status,
                              password_hash, invitation_token_hash,
                              invitation_expires_at, invitation_used_at, created_at
                       FROM users ORDER BY created_at, id"""
                ).fetchall()
            return [self._user_from_row(row) for row in rows]
        if not in_memory_fallback_enabled():
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para consultar usuarios"
            )
        return list(self._by_id.values())

    def count(self) -> int:
        """Numero de usuarios almacenados."""
        return len(self._by_id)

    def clear(self) -> None:
        """Vacia el repositorio (apoyo para pruebas)."""
        with self.lock:
            for user in self._by_id.values():
                if user.company_id is not None:
                    with _fallback_admin_lock:
                        admins = _fallback_active_admins.get(user.company_id)
                        if admins is not None:
                            admins.discard(user.id)
                            if not admins:
                                _fallback_active_admins.pop(user.company_id, None)
            self._by_id.clear()
            self._by_email.clear()
        try:
            with connection() as conn:
                conn.execute("DELETE FROM identity_active_admin_guard")
                conn.execute("DELETE FROM identity_invitation_accounts")
        except Exception:
            # The in-memory repository remains usable in unit tests that do
            # not configure PostgreSQL; production runs the migration first.
            pass

    @staticmethod
    def _upsert_sql(canonical: bool = False):
        # Identificadores internos fijos; ningún nombre procede de una petición.
        table, key = ("users", "id") if canonical else ("identity_invitation_accounts", "account_id")
        return f"""
            INSERT INTO {table} (
                {key}, company_id, name, email, phone, role, status,
                invitation_status, password_hash, invitation_token_hash,
                invitation_expires_at, invitation_used_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ({key}) DO UPDATE SET
                company_id = EXCLUDED.company_id, name = EXCLUDED.name,
                email = EXCLUDED.email, phone = EXCLUDED.phone,
                role = EXCLUDED.role, status = EXCLUDED.status,
                invitation_status = EXCLUDED.invitation_status,
                password_hash = EXCLUDED.password_hash,
                invitation_token_hash = EXCLUDED.invitation_token_hash,
                invitation_expires_at = EXCLUDED.invitation_expires_at,
                invitation_used_at = EXCLUDED.invitation_used_at,
                created_at = EXCLUDED.created_at
        """

    def sync_persistent(self, user: User, conn=None) -> None:
        """Guarda users y su proyección en la misma transacción.

        Con conexión propia solo retorna después del commit; con conexión del
        llamador no confirma ni publica caché. Un fallo revierte el savepoint.
        """
        if conn is None and not postgres_configured():
            if in_memory_fallback_enabled():
                return
            raise RuntimeError(
                "Configura DATABASE_URL o POSTGRES_PASSWORD para persistir usuarios"
            )
        if conn is None:
            with connection() as owned:
                self.sync_persistent(user, owned)
            return
        try:
            values = (
                user.id, user.company_id, user.name, user.email, user.phone,
                user.role, user.status, user.invitation_status,
                user.password_hash, user.invitation_token_hash,
                user.invitation_expires_at, user.invitation_used_at,
                user.created_at,
            )
            with _account_transaction(conn):
                conn.execute(self._upsert_sql(canonical=True), values)
                conn.execute(self._upsert_sql(), values)
        except Exception as exc:
            if _is_unique_violation(exc):
                raise EmailAlreadyStoredError("email already registered") from exc
            raise

    @staticmethod
    def _user_from_row(row) -> User:
        return User(
            id=str(row["account_id"]), company_id=row["company_id"],
            name=row["name"], email=row["email"], phone=row["phone"],
            role=row["role"], status=row["status"],
            invitation_status=row["invitation_status"],
            password_hash=row["password_hash"],
            invitation_token_hash=row["invitation_token_hash"],
            invitation_expires_at=row["invitation_expires_at"],
            invitation_used_at=row["invitation_used_at"],
            created_at=row["created_at"],
        )

    def load_persistent_for_update(self, account_id: str, conn):
        row = conn.execute(
            """SELECT id::text AS account_id, company_id::text AS company_id,
                      name, email, phone, role, status,
                      invitation_status, password_hash, invitation_token_hash,
                      invitation_expires_at, invitation_used_at, created_at
               FROM users
               WHERE id = %s
               FOR UPDATE""",
            (account_id,),
        ).fetchone()
        return self._user_from_row(row) if row else None

    def find_persistent_account_by_token(self, token_hash: str):
        """Resuelve la cuenta desde el token cuando el repositorio local está obsoleto."""
        with connection() as conn:
            row = conn.execute(
                "SELECT id::text AS account_id FROM users "
                "WHERE invitation_token_hash = %s",
                (token_hash,),
            ).fetchone()
        return str(row["account_id"]) if row else None

    @staticmethod
    def copy_state(target: User, source: User) -> User:
        target.__dict__.update(source.__dict__)
        return target

    def restore_state(self, user: User, before: dict) -> None:
        """Compensa el agregado y sus índices locales tras un aborto."""
        with self.lock:
            for email, candidate in list(self._by_email.items()):
                if candidate is user:
                    self._by_email.pop(email)
            user.__dict__.clear()
            user.__dict__.update(before)
            if self._by_id.get(user.id) is user:
                self._by_email[normalize_email(user.email)] = user

    @contextmanager
    def locked_account(self, account_id: str, conn):
        """Exclusión de cuenta en la transacción externa, sin confirmarla."""
        with _account_transaction(conn):
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"identity:account:{account_id}",),
            )
            yield conn

    def _register_active_admin_if_guarded(self, user: User, conn=None) -> None:
        """Añade un admin nuevo usando la transacción del alta."""
        if conn is None:
            with connection() as owned:
                self._register_active_admin_if_guarded(user, owned)
            return
        _ensure_admin_guard_table(conn)
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (user.company_id,),
        )
        conn.execute(
            """
            UPDATE identity_active_admin_guard
            SET active_admin_ids = array_append(active_admin_ids, %s)
            WHERE company_id = %s AND NOT (%s = ANY(active_admin_ids))
            """,
            (user.id, user.company_id, user.id),
        )

    def commit_admin_mutation(
        self,
        user: User,
        *,
        new_role: str | None = None,
        new_status: str | None = None,
        conn=None,
    ) -> None:
        """Reserva de forma atomica el cambio de un administrador.

        El lock es una transaccion PostgreSQL, no el RLock del proceso. La
        elegibilidad se relee de users bajo el lock de empresa en cada cambio;
        el coordinador previo solo refleja la reserva de esta transacción.
        """
        if user.company_id is None:
            return
        if conn is None and not postgres_configured():
            if not in_memory_fallback_enabled():
                raise RuntimeError(
                    "Configura DATABASE_URL o POSTGRES_PASSWORD para persistir usuarios"
                )
            removes = (
                user.role == "administrador"
                and user.status == "active"
                and (
                    new_role is not None and new_role != "administrador"
                    or new_status is not None and new_status != "active"
                )
            )
            adds = (
                (new_role == "administrador" and user.status == "active")
                or (new_status == "active" and user.role == "administrador")
            )
            with _fallback_admin_lock:
                active_ids = _fallback_active_admins.setdefault(user.company_id, set())
                if removes:
                    if user.id not in active_ids or len(active_ids) <= 1:
                        raise LastActiveAdministratorPersistenceError(
                            "at least one active administrator is required"
                        )
                    active_ids.remove(user.id)
                if adds:
                    active_ids.add(user.id)
            return
        removes = (
            user.role == "administrador"
            and user.status == "active"
            and (new_role is not None and new_role != "administrador"
                 or new_status is not None and new_status != "active")
        )
        adds = (
            (new_role == "administrador" and user.status == "active")
            or (new_status == "active" and user.role == "administrador")
        )
        if conn is None:
            with connection() as owned:
                return self.commit_admin_mutation(
                    user, new_role=new_role, new_status=new_status, conn=owned
                )
        else:
            _ensure_admin_guard_table(conn)
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (user.company_id,),
            )
            # El advisory lock de empresa serializa retiros/altas. La autoridad
            # es users confirmado, no el coordinador previo ni una caché local.
            active_ids = [
                str(row["id"]) for row in conn.execute(
                    "SELECT id FROM users WHERE company_id=%s "
                    "AND role='administrador' AND status='active'",
                    (user.company_id,),
                ).fetchall()
            ]

            active_set = set(active_ids)
            if removes and user.id in active_set:
                if len(active_set) <= 1:
                    raise LastActiveAdministratorPersistenceError(
                        "at least one active administrator is required"
                    )
                active_set.remove(user.id)
            if adds:
                active_set.add(user.id)
            conn.execute(
                """
                INSERT INTO identity_active_admin_guard(company_id,active_admin_ids)
                VALUES (%s,%s)
                ON CONFLICT (company_id) DO UPDATE
                SET active_admin_ids = EXCLUDED.active_admin_ids
                """,
                (user.company_id, sorted(active_set)),
            )


_users = InMemoryUserRepository()


def get_user_repository() -> InMemoryUserRepository:
    """Devuelve el repositorio compartido de usuarios."""
    return _users
