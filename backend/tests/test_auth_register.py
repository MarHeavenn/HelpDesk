"""T2 — POST /api/auth/register camino feliz (RF-1, RF-3).

Verifica:
- RF-1: registro valido responde 201 con {id, name, email, role=cliente}
  y ningun campo de contrasena/hash.
- RF-3: entradas invalidas (nombre/email/contrasena) responden 422
  sin crear ningun usuario.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.user_repository import (
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


# --- RF-1: camino feliz ---


def test_register_valid_client_returns_201_without_password_or_hash():
    response = client.post("/api/auth/register", json=_valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ana Perez"
    assert body["email"] == "ana@ejemplo.com"
    assert body["role"] == "cliente"
    assert "id" in body and body["id"]
    assert "password" not in body
    assert "password_hash" not in body
    assert "hash" not in "".join(body.keys()).lower()
    assert set(body.keys()) == {"id", "name", "email", "role"}


# --- RF-3: matriz de validacion -> 422 sin crear usuario ---


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "A"),  # 1 caracter
        ("name", "   "),  # solo espacios
        ("name", ""),  # vacio
        ("name", "n" * 101),  # mas de 100
        ("email", ""),  # vacio
        ("email", "no-es-email"),  # malformado
        ("email", "a@b"),  # malformado
        ("email", "user@"),  # malformado
        ("email", "a" * 243 + "@ejemplo.com"),  # mas de 254
        ("password", "1234567"),  # menos de 8
        ("password", "p" * 129),  # mas de 128
    ],
)
def test_register_invalid_fields_return_422_without_creating_user(field, value):
    response = client.post("/api/auth/register", json=_valid_payload(**{field: value}))

    assert response.status_code == 422
    assert get_user_repository().count() == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "ana@ejemplo.com", "password": "Secreta123", "role": "cliente"},
        {"name": "Ana Perez", "password": "Secreta123", "role": "cliente"},
        {"name": "Ana Perez", "email": "ana@ejemplo.com", "role": "cliente"},
    ],
)
def test_register_missing_required_fields_returns_422(payload):
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert get_user_repository().count() == 0
