"""Configuracion administrable de tiempos objetivo de SLA (HU-14).

Cubre RF-71 (catalogo y semilla inicial) y RF-74 (validacion y
conversion de horas a minutos).

Reglas:
- El catalogo de prioridades es el de HU-03, con coincidencia exacta y
  sin prioridad por defecto. `sla` no importa `tickets`: el catalogo se
  replica aqui y una prueba comprueba que ambas tuplas coinciden.
- La semilla conserva los valores fijos de HU-05 y es solo el estado de
  arranque de la configuracion (RF-71); ya no es el valor de calculo.
- Los valores se expresan en horas, con decimales permitidos, y se
  convierten a minutos enteros con aritmetica `Decimal` y redondeo
  `ROUND_HALF_UP` (RF-74).
- Cada valor debe ser un numero finito estrictamente positivo y la
  conversion debe alcanzar al menos 1 minuto (RF-74).
- El mapa de reemplazo debe contener exactamente las cuatro prioridades;
  cualquier ausencia o clave extra es un error de regla (RF-74).
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Catalogo ordenado de HU-03 (RF-21). Mismo orden que `PRIORITIES`.
SLA_PRIORITIES = ("Crítica", "Alta", "Media", "Baja")

# Semilla inicial de la configuracion (RF-71): valores fijos de HU-05.
DEFAULT_SLA_TARGET_MINUTES: dict[str, int] = {
    "Crítica": 120,
    "Alta": 240,
    "Media": 720,
    "Baja": 1440,
}

MINUTES_PER_HOUR = Decimal(60)
MIN_TARGET_MINUTES = 1


class SlaPolicyValidationError(ValueError):
    """Error de regla de la configuracion de SLA (RF-74)."""


def _as_finite_decimal(hours: object) -> Decimal:
    """Convierte un numero a `Decimal` finito o lanza si no lo es (RF-74)."""
    if isinstance(hours, bool):
        raise SlaPolicyValidationError("hours must be a finite number")
    if isinstance(hours, Decimal):
        value = hours
    elif isinstance(hours, int):
        value = Decimal(hours)
    elif isinstance(hours, float):
        value = Decimal(str(hours))
    else:
        raise SlaPolicyValidationError("hours must be a finite number")
    if not value.is_finite():
        raise SlaPolicyValidationError("hours must be a finite number")
    return value


def hours_to_minutes(hours: Decimal | int | float) -> int:
    """Convierte horas a minutos enteros (RF-74).

    Exige un valor finito y estrictamente positivo y que el resultado
    alcance al menos 1 minuto; en caso contrario lanza
    `SlaPolicyValidationError`. El redondeo es `ROUND_HALF_UP`.
    """
    value = _as_finite_decimal(hours)
    if value <= 0:
        raise SlaPolicyValidationError("hours must be greater than zero")
    try:
        minutes = int(
            (value * MINUTES_PER_HOUR).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    except InvalidOperation as exc:
        raise SlaPolicyValidationError("hours out of range") from exc
    if minutes < MIN_TARGET_MINUTES:
        raise SlaPolicyValidationError(
            "hours must convert to at least one minute"
        )
    return minutes


def validate_policy_targets(values: Mapping[str, object]) -> dict[str, int]:
    """Valida el mapa de horas y devuelve los minutos en orden de catalogo.

    Exige que el conjunto de claves sea exactamente `SLA_PRIORITIES` y
    convierte cada valor con `hours_to_minutes` (RF-74). No muta la
    entrada. El mapa devuelto respeta el orden del catalogo.
    """
    if not isinstance(values, Mapping):
        raise SlaPolicyValidationError("policies must be an object")
    if set(values) != set(SLA_PRIORITIES):
        raise SlaPolicyValidationError(
            "policies must contain exactly the catalog priorities"
        )
    return {
        priority: hours_to_minutes(values[priority])
        for priority in SLA_PRIORITIES
    }
