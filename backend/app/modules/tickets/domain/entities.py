"""Entidades y reglas de dominio del modulo tickets (HU-02 y HU-03).

Cubre RF-12 (validacion de titulo y descripcion), RF-13 (identificador
opaco con formato UUID) y RF-19 (estado inicial `Abierto`) de HU-02, y de
HU-03: RF-21 (catalogos de prioridades y estados), RF-27.2/RF-27.3
(`priority` del ticket, vacia mientras no se fije) y RF-26 (entidad
`TicketModification` del registro de modificaciones).

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
- Estado inicial: `OPEN_STATUS`, fijo para todo ticket nuevo.
- Prioridad y estado (HU-03): coincidencia exacta con el catalogo, sin
  recorte, sin normalizar mayusculas ni Unicode. `priority` nace vacia
  (`None`) y todo ticket nuevo nace con `OPEN_STATUS`; la creacion no
  cambia (RF-27.3). El flujo del ciclo de vida es de HU-08: aqui no se
  imponen transiciones.
- Roles de gestion (RF-24): `MANAGEMENT_ROLES` fija que solo `tecnico` y
  `administrador` pueden fijar prioridad y estado; su aplicacion vive en
  la capa de aplicacion, no en la interfaz.
- Registro (RF-26): `TicketModification` es de solo datos; quien decide
  cuando se registra es el caso de uso (solo cambios efectivos).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 200
DESCRIPTION_MIN_LENGTH = 1
DESCRIPTION_MAX_LENGTH = 5000
OPEN_STATUS = "Abierto"
CLOSED_STATUS = "Cerrado"

# Catalogos de HU-03 (RF-21). El orden es el del RF y de la spec.
PRIORITIES = ("Crítica", "Alta", "Media", "Baja")
STATUSES = ("Abierto", "En progreso", "Resuelto", "Cerrado")

# Campos registrables en el registro de modificaciones (RF-26).
PRIORITY_FIELD = "priority"
STATUS_FIELD = "status"

# Roles con permisos de gestion sobre prioridad y estado (RF-24).
MANAGEMENT_ROLES = frozenset({"tecnico", "administrador"})


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


def _validate_catalog_value(
    raw: object, *, field: str, catalog: tuple[str, ...]
) -> str:
    """Aplica tipo estricto y coincidencia exacta con `catalog`.

    Devuelve el valor tal cual (sin recorte ni normalizacion alguna, RF-21).
    Lanza ValueError si el valor no es una cadena de texto (RF-29.1) o si
    no pertenece al catalogo (RF-29.3).
    """
    if not isinstance(raw, str):
        raise ValueError(f"{field} must be text")
    if raw not in catalog:
        raise ValueError(f"{field} must be one of {', '.join(catalog)}")
    return raw


def validate_priority(raw: object) -> str:
    """Devuelve la prioridad. Lanza ValueError si no es texto o no
    pertenece a `PRIORITIES` con coincidencia exacta (RF-21, RF-29.3)."""
    return _validate_catalog_value(raw, field="priority", catalog=PRIORITIES)


def validate_status(raw: object) -> str:
    """Devuelve el estado. Lanza ValueError si no es texto o no pertenece
    a `STATUSES` con coincidencia exacta (RF-21, RF-29.3)."""
    return _validate_catalog_value(raw, field="status", catalog=STATUSES)


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
    """Ticket de soporte (RF-11, RF-13, RF-14, RF-19, RF-27.2, RF-27.3).

    `id` es un UUID opaco, `requester_id` el identificador opaco del
    usuario autenticado que lo creo (contrato de `identity`, sin datos
    personales) y `status` nace en `OPEN_STATUS`. `priority` nace vacia
    (`None`) mientras no se fije (RF-27.2); los campos con valor por
    defecto van al final.
    """

    id: str
    title: str
    description: str
    requester_id: str
    created_at: datetime
    priority: str | None = None
    status: str = OPEN_STATUS


@dataclass
class TicketModification:
    """Registro de un cambio efectivo de prioridad o de estado (RF-26).

    `field` es `PRIORITY_FIELD` o `STATUS_FIELD`; `previous_value` es
    `None` en la primera asignacion de una prioridad; `new_value` el valor
    fijado; `actor_id` el identificador opaco del usuario responsable,
    obtenido de la sesion autenticada (nunca del cuerpo de la peticion);
    `changed_at` la fecha y hora UTC generada por el sistema. Los empates
    de `changed_at` no fijan orden entre registros. La entidad es de solo
    datos: el alta del registro corresponde al caso de uso.
    """

    ticket_id: str
    field: str
    previous_value: str | None
    new_value: str
    actor_id: str
    changed_at: datetime
