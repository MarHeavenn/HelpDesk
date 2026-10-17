"""T1 — Dominio y adaptadores base de identity (RF-3, RF-9).

Verifica:
- RF-9: lo almacenado no es la contrasena original, `verify` acepta la
  correcta y rechaza la incorrecta, con biblioteca y version documentadas.
- RF-3: normalizacion de email (trim + case-insensitive) y limites
  (nombre 2-100, email <=254, contrasena 8-128 intacta).
- Ajuste aprobado: la entidad `Session` incluye `expires_at`.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from importlib.metadata import version as pkg_version

from app.modules.identity.domain.entities import (
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    Session,
    User,
    normalize_email,
    validate_name,
    validate_password,
)
from app.modules.identity.infrastructure.email_validator import (
    EMAIL_VALIDATOR_VERSION,
    EmailValidator,
)
from app.modules.identity.infrastructure.password_hasher import (
    HASHER_LIBRARY_NAME,
    HASHER_LIBRARY_VERSION,
    Argon2PasswordHasher,
)


# --- RF-9: hash Argon2id ---


def test_password_hash_is_not_plaintext_and_uses_argon2id():
    hasher = Argon2PasswordHasher()
    stored = hasher.hash("Secreta123")
    assert stored != "Secreta123"
    assert "Secreta123" not in stored
    assert stored.startswith("$argon2id$")


def test_password_verify_accepts_correct_and_rejects_wrong():
    hasher = Argon2PasswordHasher()
    stored = hasher.hash("Secreta123")
    assert hasher.verify(stored, "Secreta123") is True
    assert hasher.verify(stored, "secreta123") is False
    assert hasher.verify(stored, "OtraClave99") is False


def test_hash_library_and_version_are_documented():
    assert HASHER_LIBRARY_NAME == "argon2-cffi"
    assert HASHER_LIBRARY_VERSION == pkg_version("argon2-cffi")
    assert EMAIL_VALIDATOR_VERSION == pkg_version("email-validator")


# --- RF-3: normalizacion de email ---


def test_normalize_email_trims_and_lowercases():
    assert normalize_email("  Usuario@Ejemplo.COM  ") == "usuario@ejemplo.com"


def test_email_validator_accepts_normalized_and_rejects_malformed():
    validator = EmailValidator()
    assert validator.validate("  Usuario@Ejemplo.COM  ") == "usuario@ejemplo.com"
    for bad in ["", "no-es-email", "a@b", "user@"]:
        with pytest.raises(ValueError):
            validator.validate(bad)


def test_email_over_254_chars_is_rejected():
    too_long = "a" * 243 + "@ejemplo.com"  # 255 caracteres
    assert len(too_long) > EMAIL_MAX_LENGTH
    with pytest.raises(ValueError):
        normalize_email(too_long)
    with pytest.raises(ValueError):
        EmailValidator().validate(too_long)


# --- RF-3: limites de nombre y contrasena ---


def test_name_must_have_2_to_100_chars_after_trim():
    assert validate_name("  Ana  ") == "Ana"
    with pytest.raises(ValueError):
        validate_name("A")
    with pytest.raises(ValueError):
        validate_name("   ")
    with pytest.raises(ValueError):
        validate_name("")
    assert validate_name("ab") == "ab"
    assert validate_name("n" * NAME_MAX_LENGTH) == "n" * NAME_MAX_LENGTH
    with pytest.raises(ValueError):
        validate_name("n" * (NAME_MAX_LENGTH + 1))
    assert NAME_MIN_LENGTH == 2
    assert NAME_MAX_LENGTH == 100


def test_password_length_8_to_128_kept_intact_without_trim():
    assert validate_password("12345678") == "12345678"
    assert validate_password("p" * PASSWORD_MAX_LENGTH) == "p" * PASSWORD_MAX_LENGTH
    with pytest.raises(ValueError):
        validate_password("1234567")
    with pytest.raises(ValueError):
        validate_password("p" * (PASSWORD_MAX_LENGTH + 1))
    # Los espacios al inicio/final se respetan tal cual (sin recortar).
    assert validate_password("  secreta12  ") == "  secreta12  "
    assert PASSWORD_MIN_LENGTH == 8
    assert PASSWORD_MAX_LENGTH == 128


def test_password_with_spaces_verifies_exact_not_trimmed():
    hasher = Argon2PasswordHasher()
    stored = hasher.hash("  secreta12  ")
    assert hasher.verify(stored, "  secreta12  ") is True
    assert hasher.verify(stored, "secreta12") is False


# --- Ajuste aprobado: Session con expires_at ---


def test_session_includes_expires_at_and_expiration_rule():
    now = datetime.now(timezone.utc)
    session = Session(
        id="s1",
        user_id="u1",
        token_hash="abc",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert session.revoked_at is None
    assert session.is_expired(now) is False
    assert session.is_valid(now) is True
    assert session.is_expired(now + timedelta(hours=2)) is True
    assert session.is_valid(now + timedelta(hours=2)) is False


def test_revoked_session_is_invalid_even_if_not_expired():
    now = datetime.now(timezone.utc)
    session = Session(
        id="s1",
        user_id="u1",
        token_hash="abc",
        created_at=now,
        revoked_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert session.is_valid(now) is False


def test_user_entity_holds_normalized_email_and_hash():
    user = User(
        id="u1",
        name="Ana",
        email="usuario@ejemplo.com",
        password_hash="$argon2id$v=19$ejemplo",
        role="cliente",
    )
    assert user.email == "usuario@ejemplo.com"
    assert user.role == "cliente"
