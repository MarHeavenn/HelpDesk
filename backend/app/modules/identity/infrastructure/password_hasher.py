"""Adaptador de hash de contrasenas con Argon2id (RF-9).

Biblioteca: argon2-cffi (version en HASHER_LIBRARY_VERSION, Argon2id via
`PasswordHasher` por defecto `Type.ID`). Nunca se almacena ni se devuelve
texto plano: solo el hash PHC `$argon2id$...`.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

HASHER_LIBRARY_NAME = "argon2-cffi"
HASHER_LIBRARY_VERSION = "25.1.0"


class Argon2PasswordHasher:
    """Hashea con Argon2id y verifica sin distinguir el motivo del fallo."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        """Devuelve el hash Argon2id de la contrasena intacta."""
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """True si la contrasena coincide; False en caso contrario
        (incluido hash malformado)."""
        try:
            return self._hasher.verify(password_hash, password)
        except VerificationError:
            return False
