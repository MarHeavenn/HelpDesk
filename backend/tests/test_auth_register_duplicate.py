"""T4 — Unicidad de correo case-insensitive (RF-4).

Verifica:
- RF-4: registrar un correo y reintentarlo con distintas mayusculas
  (y con espacios) devuelve 409 con cuerpo {"detail": ...} sin crear
  un segundo usuario.
- RF-4: la persistencia rechaza el duplicado aunque se intente por
  debajo del caso de uso (add directo al repositorio, incluso con
  distintas mayusculas).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.user_repository import (
    EmailAlreadyStoredError,
    InMemoryUserRepository,
    get_user_repository,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_repository():
    get_user_repository().clear()
    yield
    get_user_repository().clear()


def _valid_payload(**overrides):
    payload = {
        "name": "Ana Perez",
        "email": "ana@ejemplo.com",
        "password": "Secreta123",
        "role": "cliente",
    }
    payload.update(overrides)
    return payload


# --- RF-4: duplicado con distintas mayusculas -> 409 sin crear usuario ---


@pytest.mark.parametrize("duplicate", ["ANA@EJEMPLO.COM", "Ana@Ejemplo.Com"])
def test_register_duplicate_email_case_insensitive_returns_409(duplicate):
    first = client.post("/api/auth/register", json=_valid_payload())
    assert first.status_code == 201

    retry = client.post("/api/auth/register", json=_valid_payload(email=duplicate))

    assert retry.status_code == 409
    assert "detail" in retry.json()
    assert get_user_repository().count() == 1


def test_register_duplicate_email_with_spaces_and_case_returns_409():
    first = client.post("/api/auth/register", json=_valid_payload())
    assert first.status_code == 201

    retry = client.post(
        "/api/auth/register", json=_valid_payload(email="  ANA@Ejemplo.COM  ")
    )

    assert retry.status_code == 409
    assert "detail" in retry.json()
    assert get_user_repository().count() == 1


# --- RF-4: la persistencia rechaza el duplicado por debajo del caso de uso ---


def test_repository_rejects_duplicate_below_use_case():
    repo = InMemoryUserRepository()
    repo.add(
        User(
            id="u-1",
            name="Ana Perez",
            email="ana@ejemplo.com",
            password_hash="hash",
            role="cliente",
        )
    )

    with pytest.raises(EmailAlreadyStoredError):
        repo.add(
            User(
                id="u-2",
                name="Otra Persona",
                email="ana@ejemplo.com",
                password_hash="hash",
                role="cliente",
            )
        )
    assert repo.count() == 1


def test_repository_rejects_duplicate_with_different_case_below_use_case():
    repo = InMemoryUserRepository()
    repo.add(
        User(
            id="u-1",
            name="Ana Perez",
            email="ana@ejemplo.com",
            password_hash="hash",
            role="cliente",
        )
    )

    with pytest.raises(EmailAlreadyStoredError):
        repo.add(
            User(
                id="u-2",
                name="Otra Persona",
                email="ANA@EJEMPLO.COM",
                password_hash="hash",
                role="cliente",
            )
        )
    assert repo.count() == 1
