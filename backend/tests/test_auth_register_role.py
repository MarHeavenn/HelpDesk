"""T3 — Rechazo de rol no-cliente u omitido en autorregistro (RF-2).

Verifica:
- RF-2: rol tecnico, administrador u otro valor -> 422 sin crear usuario.
- RF-2: cuerpo sin campo de rol -> 422 sin crear usuario ni aplicar
  valor por defecto.
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


# --- RF-2: rol distinto de cliente -> 422 sin crear usuario ---


@pytest.mark.parametrize("role", ["tecnico", "administrador", "superuser"])
def test_register_non_client_role_returns_422_without_creating_user(role):
    response = client.post("/api/auth/register", json=_valid_payload(role=role))

    assert response.status_code == 422
    assert "detail" in response.json()
    assert get_user_repository().count() == 0


# --- RF-2: rol omitido -> 422 sin crear usuario ni valor por defecto ---


def test_register_missing_role_returns_422_without_creating_user():
    payload = {
        "name": "Ana Perez",
        "email": "ana@ejemplo.com",
        "password": "Secreta123",
    }
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()
    # Sin valor por defecto: ningun usuario debe haberse creado.
    assert get_user_repository().count() == 0
