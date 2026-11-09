"""HU-14 T4 — Casos de uso de la configuracion de SLA (RF-72..RF-75).

Mapa RF -> test:
- RF-72: `list_sla_policies` devuelve las cuatro prioridades en orden de
  catalogo y no muta el repositorio.
- RF-73: `replace_sla_policies` reemplaza por completo y devuelve la lista
  resultante.
- RF-74: la validacion es del dominio; un cuerpo invalido no escribe nada.
- RF-75: la guardia de rol vive en la aplicacion y se ejecuta antes de
  leer o escribir el repositorio, sin revelar datos.

Se usan repositorios locales para no compartir el singleton global.
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.application.manage_sla_policies import (
    SLA_POLICIES_NOT_FOUND_MESSAGE,
    SlaPolicyAccessDeniedError,
    ensure_sla_admin,
    list_sla_policies,
    replace_sla_policies,
)
from app.modules.sla.domain.entities import SlaPolicy
from app.modules.sla.domain.policy_config import (
    DEFAULT_SLA_TARGET_MINUTES,
    SlaPolicyValidationError,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    InMemorySlaPolicyRepository,
)

SEED_POLICIES = [
    SlaPolicy(priority="Crítica", target_minutes=120),
    SlaPolicy(priority="Alta", target_minutes=240),
    SlaPolicy(priority="Media", target_minutes=720),
    SlaPolicy(priority="Baja", target_minutes=1440),
]

VALID_HOURS = {
    "Crítica": Decimal("2"),
    "Alta": Decimal("4"),
    "Media": Decimal("12"),
    "Baja": Decimal("24"),
}

CUSTOM_TARGETS = {"Crítica": 60, "Alta": 30, "Media": 15, "Baja": 1}


class _UntouchableRepository(InMemorySlaPolicyRepository):
    """Repositorio que falla si el caso de uso lo lee o lo escribe."""

    def get_target_minutes(self, *args, **kwargs):
        raise AssertionError("repository read")

    def get_all(self, *args, **kwargs):
        raise AssertionError("repository read")

    def replace(self, *args, **kwargs):
        raise AssertionError("repository write")

    def reset(self, *args, **kwargs):
        raise AssertionError("repository write")


# --- RF-75: guardia de rol ---


def test_ensure_sla_admin_accepts_the_admin_role():
    assert ensure_sla_admin("administrador") is None


@pytest.mark.parametrize(
    "role", ["cliente", "tecnico", "", None, "Administrador"]
)
def test_ensure_sla_admin_rejects_any_other_role(role):
    with pytest.raises(SlaPolicyAccessDeniedError) as excinfo:
        ensure_sla_admin(role)

    assert str(excinfo.value) == SLA_POLICIES_NOT_FOUND_MESSAGE
    assert SLA_POLICIES_NOT_FOUND_MESSAGE == "not found"


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_list_rejects_before_touching_the_repository(role):
    with pytest.raises(SlaPolicyAccessDeniedError):
        list_sla_policies(role, _UntouchableRepository())


@pytest.mark.parametrize("role", ["cliente", "tecnico"])
def test_replace_rejects_before_touching_the_repository(role):
    with pytest.raises(SlaPolicyAccessDeniedError):
        replace_sla_policies(role, VALID_HOURS, _UntouchableRepository())


def test_a_rejected_replace_keeps_the_configuration_intact():
    repository = InMemorySlaPolicyRepository()
    repository.replace(CUSTOM_TARGETS)

    with pytest.raises(SlaPolicyAccessDeniedError):
        replace_sla_policies("tecnico", VALID_HOURS, repository)

    assert repository.get_all() == CUSTOM_TARGETS


# --- RF-72: consulta ordenada y de solo lectura ---


def test_list_returns_the_catalog_in_order():
    repository = InMemorySlaPolicyRepository()

    policies = list_sla_policies("administrador", repository)

    assert policies == SEED_POLICIES
    assert all(isinstance(policy, SlaPolicy) for policy in policies)


def test_list_does_not_mutate_the_repository():
    repository = InMemorySlaPolicyRepository()
    before = repository.get_all()

    policies = list_sla_policies("administrador", repository)
    policies.clear()

    assert repository.get_all() == before
    assert repository.get_all() == DEFAULT_SLA_TARGET_MINUTES


# --- RF-73 y RF-74: reemplazo total validado ---


def test_replace_validates_persists_and_returns_the_result():
    repository = InMemorySlaPolicyRepository()
    values = {
        "Crítica": Decimal("2.5"),
        "Alta": Decimal("4"),
        "Media": Decimal("12"),
        "Baja": Decimal("24"),
    }

    policies = replace_sla_policies("administrador", values, repository)

    assert repository.get_target_minutes("Crítica") == 150
    assert policies == [
        SlaPolicy(priority="Crítica", target_minutes=150),
        SlaPolicy(priority="Alta", target_minutes=240),
        SlaPolicy(priority="Media", target_minutes=720),
        SlaPolicy(priority="Baja", target_minutes=1440),
    ]
    assert list(policies[0].__dict__) == ["priority", "target_minutes"]


@pytest.mark.parametrize(
    "values",
    [
        {},
        {
            "Crítica": Decimal("2"),
            "Alta": Decimal("4"),
            "Media": Decimal("12"),
        },
        {
            "Crítica": Decimal("2"),
            "Alta": Decimal("4"),
            "Media": Decimal("12"),
            "Baja": Decimal("24"),
            "Urgente": Decimal("1"),
        },
        {
            "Crítica": Decimal("2"),
            "Alta": Decimal("4"),
            "Media": Decimal("12"),
            "Baja": Decimal("0"),
        },
        {
            "Crítica": Decimal("2"),
            "Alta": Decimal("4"),
            "Media": Decimal("12"),
            "Baja": Decimal("0.001"),
        },
    ],
)
def test_an_invalid_body_raises_and_does_not_write(values):
    repository = InMemorySlaPolicyRepository()
    repository.replace(CUSTOM_TARGETS)

    with pytest.raises(SlaPolicyValidationError):
        replace_sla_policies("administrador", values, repository)

    assert repository.get_all() == CUSTOM_TARGETS


def test_replacing_with_the_same_values_is_idempotent():
    repository = InMemorySlaPolicyRepository()

    first = replace_sla_policies("administrador", VALID_HOURS, repository)
    second = replace_sla_policies("administrador", VALID_HOURS, repository)

    assert first == second == SEED_POLICIES
    assert repository.get_all() == DEFAULT_SLA_TARGET_MINUTES


def test_a_later_replace_substitutes_the_previous_one():
    repository = InMemorySlaPolicyRepository()

    replace_sla_policies("administrador", VALID_HOURS, repository)
    policies = replace_sla_policies(
        "administrador",
        {
            "Crítica": Decimal("0.5"),
            "Alta": Decimal("1"),
            "Media": Decimal("2"),
            "Baja": Decimal("3"),
        },
        repository,
    )

    assert repository.get_all() == {
        "Crítica": 30,
        "Alta": 60,
        "Media": 120,
        "Baja": 180,
    }
    assert policies[0] == SlaPolicy(priority="Crítica", target_minutes=30)
