"""Esquemas HTTP de la configuracion de SLA (HU-14, RF-72..RF-74).

La respuesta es un array ordenado de `{priority, hours}`. `hours` es el
cociente exacto `target_minutes / 60` como numero (no cadena), de modo
que 150 minutos se exponen como 2.5 (RF-72, RF-73).

El reemplazo es un mapa con exactamente las cuatro prioridades. Aqui se
valida solo la **forma** (objeto con las cuatro claves, sin extras, y
valores que sean numeros JSON finitos); la positividad, el minimo de 1
minuto y la conversion a minutos pertenecen al dominio (RF-74).
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class SlaPolicyResponse(BaseModel):
    """Tiempo objetivo vigente de una prioridad, expresado en horas."""

    priority: str
    hours: float


class UpdateSlaPoliciesRequest(BaseModel):
    """Cuerpo del reemplazo total: las cuatro prioridades en horas."""

    model_config = ConfigDict(extra="forbid")

    Crítica: Decimal
    Alta: Decimal
    Media: Decimal
    Baja: Decimal

    @field_validator("*", mode="before")
    @classmethod
    def _must_be_a_finite_json_number(cls, value: object) -> Decimal:
        """Rechaza cadenas, booleanos, null, listas, objetos y no finitos.

        Un `bool` es un `int` en Python, pero no es un numero JSON valido
        para este campo. Las reglas de valor (positivo y >= 1 minuto) se
        dejan al dominio.
        """
        if isinstance(value, bool):
            raise ValueError("hours must be a finite number")
        if isinstance(value, Decimal):
            number = value
        elif isinstance(value, int):
            number = Decimal(value)
        elif isinstance(value, float):
            number = Decimal(str(value))
        else:
            raise ValueError("hours must be a finite number")
        if not number.is_finite():
            raise ValueError("hours must be a finite number")
        return number
