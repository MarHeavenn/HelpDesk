"""HU-14 T1 — Dominio de la configuracion de SLA (RF-71, RF-74).

Mapa RF -> test:
- RF-71: catalogo ordenado identico al de `tickets` y semilla inicial con
  los valores fijos de HU-05, reexportada desde `application/policies.py`.
- RF-74: conversion horas -> minutos enteros con `Decimal` y
  `ROUND_HALF_UP`, minimo de 1 minuto, valores finitos y estrictamente
  positivos, y mapa completo con exactamente las cuatro prioridades.
"""

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.sla.application.policies import (
    DEFAULT_SLA_TARGET_MINUTES as APPLICATION_SEED,
)
from app.modules.sla.domain.policy_config import (
    DEFAULT_SLA_TARGET_MINUTES,
    SLA_PRIORITIES,
    SlaPolicyValidationError,
    hours_to_minutes,
    validate_policy_targets,
)
from app.modules.tickets.domain.entities import PRIORITIES


# --- RF-71: catalogo y semilla ---


def test_catalog_is_the_exact_ordered_tuple():
    assert SLA_PRIORITIES == ("Crítica", "Alta", "Media", "Baja")
    assert isinstance(SLA_PRIORITIES, tuple)


def test_catalog_matches_the_tickets_priorities():
    assert SLA_PRIORITIES == PRIORITIES


def test_seed_is_the_initial_hu05_values_in_catalog_order():
    assert DEFAULT_SLA_TARGET_MINUTES == {
        "Crítica": 120,
        "Alta": 240,
        "Media": 720,
        "Baja": 1440,
    }
    assert list(DEFAULT_SLA_TARGET_MINUTES) == list(SLA_PRIORITIES)


def test_seed_is_still_importable_from_application_policies():
    assert APPLICATION_SEED == DEFAULT_SLA_TARGET_MINUTES
    assert APPLICATION_SEED is DEFAULT_SLA_TARGET_MINUTES


# --- RF-74: conversion horas -> minutos ---


@pytest.mark.parametrize(
    ("hours", "expected_minutes"),
    [
        (Decimal("2"), 120),
        (Decimal("0.5"), 30),
        (Decimal("0.25"), 15),
        (Decimal("0.02"), 1),
    ],
)
def test_hours_to_minutes_converts_the_reference_examples(
    hours, expected_minutes
):
    assert hours_to_minutes(hours) == expected_minutes


@pytest.mark.parametrize(
    ("hours", "expected_minutes"),
    [
        (Decimal("0.025"), 2),  # 1.5 min -> 2 (HALF_UP, no HALF_EVEN)
        (Decimal("0.075"), 5),  # 4.5 min -> 5 (HALF_EVEN daria 4)
    ],
)
def test_hours_to_minutes_rounds_half_up(hours, expected_minutes):
    assert hours_to_minutes(hours) == expected_minutes


@pytest.mark.parametrize(
    "hours",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("-0.5"),
        Decimal("0.001"),  # 0.06 min -> 0: no alcanza el minimo
        Decimal("0.008"),  # 0.48 min -> 0
    ],
)
def test_hours_to_minutes_rejects_non_positive_or_below_one_minute(hours):
    with pytest.raises(SlaPolicyValidationError):
        hours_to_minutes(hours)


@pytest.mark.parametrize(
    "hours",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_hours_to_minutes_rejects_non_finite_values(hours):
    with pytest.raises(SlaPolicyValidationError):
        hours_to_minutes(hours)


# --- RF-74: mapa completo de prioridades ---


def test_validate_policy_targets_returns_minutes_in_catalog_order():
    result = validate_policy_targets(
        {
            "Baja": Decimal("24"),
            "Media": Decimal("0.5"),
            "Alta": Decimal("4"),
            "Crítica": Decimal("2.5"),
        }
    )

    assert result == {
        "Crítica": 150,
        "Alta": 240,
        "Media": 30,
        "Baja": 1440,
    }
    assert list(result) == list(SLA_PRIORITIES)


def test_validate_policy_targets_rejects_an_empty_map():
    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets({})


def test_validate_policy_targets_rejects_a_missing_priority():
    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets(
            {
                "Crítica": Decimal("2"),
                "Alta": Decimal("4"),
                "Media": Decimal("12"),
            }
        )


def test_validate_policy_targets_rejects_an_extra_key():
    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets(
            {
                "Crítica": Decimal("2"),
                "Alta": Decimal("4"),
                "Media": Decimal("12"),
                "Baja": Decimal("24"),
                "Urgente": Decimal("1"),
            }
        )


def test_validate_policy_targets_rejects_a_rule_violation():
    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets(
            {
                "Crítica": Decimal("2"),
                "Alta": Decimal("4"),
                "Media": Decimal("12"),
                "Baja": Decimal("0"),
            }
        )


def test_validate_policy_targets_rejects_non_finite_values():
    with pytest.raises(SlaPolicyValidationError):
        validate_policy_targets(
            {
                "Crítica": Decimal("NaN"),
                "Alta": Decimal("4"),
                "Media": Decimal("12"),
                "Baja": Decimal("24"),
            }
        )
