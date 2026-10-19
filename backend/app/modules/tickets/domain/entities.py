"""Entidades y reglas de dominio del modulo tickets (HU-02).

Cubre RF-12 (validacion de titulo y descripcion), RF-13 (identificador
opaco con formato UUID) y RF-19 (estado inicial `Abierto`, informativo y
de solo lectura en esta historia).

Reglas:
- Titulo: obligatorio, tipo cadena de texto, 1-200 code points tras el
  recorte y el recorte se aplica tambien al almacenar.
- Descripcion: obligatorio, tipo cadena de texto, 1-5000 code points tras
  el recorte, con el mismo recorte almacenado.
- Recorte: semantica de `strip()` sin argumentos (espacios, tabuladores,
  saltos de linea y separadores Unicode); NO elimina U+200B.
- Tipo estricto: cualquier valor JSON de otro tipo (numero, booleano,
  objeto, lista o nulo) se rechaza sin coercion a texto.
- Sin deduplicacion: el dominio no impone unicidad de titulo/descripcion.
- Estado inicial: `OPEN_STATUS`, fijo para todo ticket nuevo. HU-02 no
  define catalogo de estados ni transiciones (HU-03 y HU-08).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 200
DESCRIPTION_MIN_LENGTH = 1
DESCRIPTION_MAX_LENGTH = 5000
OPEN_STATUS = "Abierto"


def _validate_text(raw: object, *, field: str, min_length: int, max_length: int) -> str:
    """Aplica tipo estricto, recorte `strip()` y limites de longitud.

    Devuelve el valor recortado (el que debe almacenarse). Lanza
    ValueError si el valor no es una cadena de texto o queda fuera de los
    limites contados en code points.
    """
    if not isinstance(raw, str):
        raise ValueError(f"{field} must be text")
    value = raw.strip()
    if not (min_length <= len(value) <= max_length):
        raise ValueError(f"{field} must have {min_length}-{max_length} characters")
    return value


def validate_title(raw: object) -> str:
    """Devuelve el titulo recortado. Lanza ValueError si no es texto o
    queda fuera de 1-200 code points tras el recorte."""
    return _validate_text(
        raw,
        field="title",
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
    )


def validate_description(raw: object) -> str:
    """Devuelve la descripcion recortada. Lanza ValueError si no es texto
    o queda fuera de 1-5000 code points tras el recorte."""
    return _validate_text(
        raw,
        field="description",
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
    )


def is_valid_uuid_format(value: object) -> bool:
    """True si `value` es una cadena con formato UUID valido (RF-13, RF-17)."""
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


@dataclass
class Ticket:
    """Ticket de soporte (RF-11, RF-13, RF-14, RF-19).

    `id` es un UUID opaco, `requester_id` el identificador opaco del
    usuario autenticado que lo creo (contrato de `identity`, sin datos
    personales) y `status` nace en `OPEN_STATUS` y no lo modifica HU-02.
    """

    id: str
    title: str
    description: str
    requester_id: str
    created_at: datetime
    status: str = OPEN_STATUS
