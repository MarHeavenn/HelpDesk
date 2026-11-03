"""HU-14 T2 — Repositorio en memoria de la configuracion de SLA.

Mapa RF -> test:
- RF-71: una instancia nueva arranca con la semilla de HU-05.
- RF-77: configuracion en memoria, reemplazo atomico del mapa completo
  («ultimo escritor gana»), `reset()` por instancia, singleton compartido
  y contrato preparado para `company_id` sin usarlo en esta historia.

La validacion del reemplazo es previa (dominio, T1): el repositorio solo
almacena un mapa ya validado y completo.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.domain.policy_config import (
    DEFAULT_SLA_TARGET_MINUTES,
    SLA_PRIORITIES,
    SlaPolicyValidationError,
    validate_policy_targets,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    InMemorySlaPolicyRepository,
    get_sla_policy_repository,
)

CUSTOM_TARGETS = {
    "Crítica": 60,
    "Alta": 30,
    "Media": 15,
    "Baja": 1,
}


# --- RF-71: semilla inicial ---


def test_a_new_instance_starts_with_the_seed():
    repository = InMemorySlaPolicyRepository()

    assert repository.get_all() == DEFAULT_SLA_TARGET_MINUTES
    assert repository.get_all() is not DEFAULT_SLA_TARGET_MINUTES


@pytest.mark.parametrize(
    ("priority", "expected_minutes"),
    [
        ("Crítica", 120),
        ("Alta", 240),
        ("Media", 720),
        ("Baja", 1440),
    ],
)
def test_get_target_minutes_returns_each_priority_target(
    priority, expected_minutes
):
    repository = InMemorySlaPolicyRepository()

    assert repository.get_target_minutes(priority) == expected_minutes


@pytest.mark.parametrize("priority", [None, "Urgente", "", 3])
def test_get_target_minutes_returns_none_for_absent_or_unknown_priority(
    priority,
):
    repository = InMemorySlaPolicyRepository()

    assert repository.get_target_minutes(priority) is None


# --- RF-77: lectura y copia ordenada ---


def test_get_all_returns_a_copy_in_catalog_order():
    repository = InMemorySlaPolicyRepository()

    configuration = repository.get_all()

    assert list(configuration) == list(SLA_PRIORITIES)
    configuration["Crítica"] = 1
    assert repository.get_target_minutes("Crítica") == 120


# --- RF-77: reemplazo total y ultimo escritor gana ---


def test_replace_substitutes_the_complete_configuration():
    repository = InMemorySlaPolicyRepository()

    repository.replace(CUSTOM_TARGETS)

    assert repository.get_all() == {
        "Crítica": 60,
        "Alta": 30,
        "Media": 15,
        "Baja": 1,
    }
    assert repository.get_target_minutes("Crítica") == 60


def test_replace_copies_the_input_map():
    repository = InMemorySlaPolicyRepository()
    targets = dict(CUSTOM_TARGETS)

    repository.replace(targets)
    targets["Crítica"] = 999

    assert repository.get_target_minutes("Crítica") == 60


def test_two_consecutive_replaces_leave_only_the_last():
    repository = InMemorySlaPolicyRepository()

    repository.replace(CUSTOM_TARGETS)
    repository.replace(
        {"Crítica": 10, "Alta": 20, "Media": 30, "Baja": 40}
    )

    assert repository.get_all() == {
        "Crítica": 10,
        "Alta": 20,
        "Media": 30,
        "Baja": 40,
    }
    assert repository.get_all() != CUSTOM_TARGETS


def test_an_invalid_replacement_is_rejected_before_touching_the_repository():
    repository = InMemorySlaPolicyRepository()

    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets(
            {"Crítica": 60, "Alta": 30, "Media": 15}
        )

    assert repository.get_all() == DEFAULT_SLA_TARGET_MINUTES


# --- RF-77: reset ---


def test_reset_returns_to_the_seed():
    repository = InMemorySlaPolicyRepository()
    repository.replace(CUSTOM_TARGETS)

    repository.reset()

    assert repository.get_all() == DEFAULT_SLA_TARGET_MINUTES


def test_reset_of_one_instance_does_not_affect_another():
    first = InMemorySlaPolicyRepository()
    second = InMemorySlaPolicyRepository()
    second.replace(CUSTOM_TARGETS)

    first.replace({"Crítica": 10, "Alta": 20, "Media": 30, "Baja": 40})
    first.reset()

    assert first.get_all() == DEFAULT_SLA_TARGET_MINUTES
    assert second.get_all() == {
        "Crítica": 60,
        "Alta": 30,
        "Media": 15,
        "Baja": 1,
    }


# --- RF-77: singleton y contrato preparado para company_id ---


def test_get_sla_policy_repository_returns_the_same_singleton():
    assert get_sla_policy_repository() is get_sla_policy_repository()
    assert isinstance(
        get_sla_policy_repository(), InMemorySlaPolicyRepository
    )


def test_the_contract_accepts_company_id_none():
    repository = InMemorySlaPolicyRepository()

    assert repository.get_target_minutes("Crítica", company_id=None) == 120
    assert repository.get_all(company_id=None) == DEFAULT_SLA_TARGET_MINUTES

    repository.replace(CUSTOM_TARGETS, company_id=None)
    assert repository.get_target_minutes("Baja", company_id=None) == 1

    repository.reset(company_id=None)
    assert repository.get_all(company_id=None) == DEFAULT_SLA_TARGET_MINUTES
