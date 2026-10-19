"""Repositorio en memoria de usuarios (RF-4).

Almacena los usuarios por email ya normalizado (trim + minusculas), de
modo que la unicidad case-insensitive queda garantizada tambien en la
persistencia: `add` rechaza el duplicado aunque el caso de uso no lo
haya comprobado. Sustituible por un adaptador PostgreSQL sin cambiar
el contrato.
"""

from app.modules.identity.domain.entities import User, normalize_email


class EmailAlreadyStoredError(ValueError):
    """El email (normalizado) ya existe en la persistencia."""


class InMemoryUserRepository:
    """Guarda usuarios por id y por email normalizado."""

    def __init__(self) -> None:
        self._by_id: dict[str, User] = {}
        self._by_email: dict[str, User] = {}

    def add(self, user: User) -> None:
        """Guarda el usuario; lanza EmailAlreadyStoredError si el email
        normalizado ya existe."""
        key = normalize_email(user.email)
        if key in self._by_email:
            raise EmailAlreadyStoredError("email already registered")
        self._by_id[user.id] = user
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
        self._by_id.clear()
        self._by_email.clear()


_users = InMemoryUserRepository()


def get_user_repository() -> InMemoryUserRepository:
    """Devuelve el repositorio compartido de usuarios."""
    return _users
