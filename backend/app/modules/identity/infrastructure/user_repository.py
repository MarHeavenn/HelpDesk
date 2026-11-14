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
from app.modules.identity.domain.entities import User, normalize_email


class EmailAlreadyStoredError(ValueError):
    """El email (normalizado) ya existe en la persistencia."""


class LastActiveAdministratorPersistenceError(ValueError):
    """La persistencia compartida impediria retirar el ultimo administrador."""


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
    """Guarda usuarios por id y por email normalizado."""

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, User] = {}
        self.lock = RLock()

    def add(self, user: User) -> None:
        """Guarda el usuario; lanza EmailAlreadyStoredError si el email
        normalizado ya existe."""
        key = normalize_email(user.email)
        with self.lock:
            if key in self._by_email:
                raise EmailAlreadyStoredError("email already registered")
            self._by_id[user.id] = user
            self._by_email[key] = user
            try:
                self.sync_persistent(user)
            except RuntimeError:
                if postgres_configured() or not in_memory_fallback_enabled():
                    raise
            if user.company_id is not None and user.role == "administrador" and user.status == "active":
                if postgres_configured():
                    self._register_active_admin_if_guarded(user)
                elif in_memory_fallback_enabled():
                    with _fallback_admin_lock:
                        _fallback_active_admins.setdefault(user.company_id, set()).add(user.id)

    def update_email(self, user: User, email: str) -> None:
        key = normalize_email(email)
        with self.lock:
            existing = self._by_email.get(key)
            if existing is not None and existing is not user:
                raise EmailAlreadyStoredError("email already registered")
            self._by_email.pop(normalize_email(user.email), None)
            user.email = key
            self._by_email[key] = user

    def find_by_email(self, email: str) -> User | None:
        """Busca por email (se normaliza de forma defensiva); None si no existe."""
        try:
            key = normalize_email(email)
        except (ValueError, AttributeError):
            return None
        return self._by_email.get(key)

    def find_by_id(self, user_id: str) -> User | None:
        """Busca por id; None si no existe."""
        return self._by_id.get(user_id)

    def list_all(self) -> list[User]:
        """Devuelve una copia de todos los usuarios almacenados.

        Lectura para el directorio de tecnicos (RF-31); el orden no se
        exige.
        """
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
    def _upsert_sql():
        return """
            INSERT INTO identity_invitation_accounts (
                account_id, company_id, name, email, phone, role, status,
                invitation_status, password_hash, invitation_token_hash,
                invitation_expires_at, invitation_used_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (account_id) DO UPDATE SET
                company_id = EXCLUDED.company_id, name = EXCLUDED.name,
                email = EXCLUDED.email, phone = EXCLUDED.phone,
                role = EXCLUDED.role, status = EXCLUDED.status,
                invitation_status = EXCLUDED.invitation_status,
                password_hash = EXCLUDED.password_hash,
                invitation_token_hash = EXCLUDED.invitation_token_hash,
                invitation_expires_at = EXCLUDED.invitation_expires_at,
                invitation_used_at = EXCLUDED.invitation_used_at
        """

    def sync_persistent(self, user: User, conn=None) -> None:
        """Persiste el agregado de invitación en el almacén compartido."""
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
        conn.execute(
            self._upsert_sql(),
            (
                user.id, user.company_id, user.name, user.email, user.phone,
                user.role, user.status, user.invitation_status,
                user.password_hash, user.invitation_token_hash,
                user.invitation_expires_at, user.invitation_used_at,
            ),
        )

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
        )

    def load_persistent_for_update(self, account_id: str, conn):
        row = conn.execute(
            """SELECT account_id, company_id, name, email, phone, role, status,
                      invitation_status, password_hash, invitation_token_hash,
                      invitation_expires_at, invitation_used_at
               FROM identity_invitation_accounts
               WHERE account_id = %s
               FOR UPDATE""",
            (account_id,),
        ).fetchone()
        return self._user_from_row(row) if row else None

    def find_persistent_account_by_token(self, token_hash: str):
        """Resuelve la cuenta desde el token cuando el repositorio local está obsoleto."""
        with connection() as conn:
            row = conn.execute(
                "SELECT account_id FROM identity_invitation_accounts "
                "WHERE invitation_token_hash = %s",
                (token_hash,),
            ).fetchone()
        return str(row["account_id"]) if row else None

    @staticmethod
    def copy_state(target: User, source: User) -> User:
        target.__dict__.update(source.__dict__)
        return target

    def _register_active_admin_if_guarded(self, user: User) -> None:
        """Añade un admin nuevo a una coordinación ya inicializada."""
        with connection() as conn:
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
        fila se inicializa desde el repositorio local solo una vez; desde ese
        momento todas las instancias comparten el conjunto de admins activos.
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
            row = conn.execute(
                """
                SELECT active_admin_ids
                FROM identity_active_admin_guard
                WHERE company_id = %s
                FOR UPDATE
                """,
                (user.company_id,),
            ).fetchone()
            if row is None:
                active_ids = [
                    candidate.id for candidate in self.list_all()
                    if candidate.company_id == user.company_id
                    and candidate.role == "administrador"
                    and candidate.status == "active"
                ]
                conn.execute(
                    """
                    INSERT INTO identity_active_admin_guard
                        (company_id, active_admin_ids)
                    VALUES (%s, %s)
                    """,
                    (user.company_id, active_ids),
                )
            else:
                active_ids = list(row["active_admin_ids"])

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
                UPDATE identity_active_admin_guard
                SET active_admin_ids = %s
                WHERE company_id = %s
                """,
                (sorted(active_set), user.company_id),
            )


_users = InMemoryUserRepository()


def get_user_repository() -> InMemoryUserRepository:
    """Devuelve el repositorio compartido de usuarios."""
    return _users
