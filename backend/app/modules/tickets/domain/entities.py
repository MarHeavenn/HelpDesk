"""Entidades y reglas de dominio del modulo tickets (HU-02, HU-03, HU-04, HU-07, HU-08 y HU-09).

Cubre RF-12 (validacion de titulo y descripcion), RF-13 (identificador
opaco con formato UUID) y RF-19 (estado inicial `Abierto`) de HU-02, de
HU-03: RF-21 (catalogos de prioridades y estados), RF-27.2/RF-27.3
(`priority` del ticket, vacia mientras no se fije) y RF-26 (entidad
`TicketModification` del registro de modificaciones), de HU-04:
RF-34/RF-35.3 (tecnico responsable del ticket, vacio mientras no se
asigne), RF-37 (entidad `AssignmentRecord` del registro de asignaciones)
y RF-38 (`ASSIGNMENT_ROLES`, unico rol con permiso de asignacion), de
HU-07: RF-62/RF-63 (entidad `TicketComment` y validacion del contenido
del seguimiento), de HU-08: RF-71 (flujo del ciclo de vida mediante
`STATUS_TRANSITIONS`) y RF-77 (`REOPEN_ROLES`, unico rol que reabre), y
de HU-09: RF-82/RF-83 (entidad `TicketHistoryEvent` y acciones del
historial derivado).

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
  cambia (RF-27.3). El flujo del ciclo de vida se define en HU-08 mediante
  `STATUS_TRANSITIONS` (RF-71); el estado `Cerrado` solo sale por la
  reapertura autorizada de RF-76.
- Roles de gestion (RF-24): `MANAGEMENT_ROLES` fija que solo `tecnico` y
  `administrador` pueden fijar prioridad y estado; su aplicacion vive en
  la capa de aplicacion, no en la interfaz.
- Roles de reapertura (RF-77): `REOPEN_ROLES` fija que solo el
  `administrador` reabre un ticket `Cerrado`; los demas roles reciben el
  404 uniforme.
- Registro (RF-26): `TicketModification` es de solo datos; quien decide
  cuando se registra es el caso de uso (solo cambios efectivos).
- Tecnico responsable (HU-04): `assignee_id` es el identificador opaco
  del tecnico y `assignee_name` la proyeccion de su nombre en el momento
  de asignar (D8); ambos nacen vacios (`None`) y permanecen asi mientras
  el ticket no se asigne (RF-34). Sin asignacion los dos son `None`,
  representacion inequivocamente distinguible de cualquier tecnico
  registrado (RF-35.3); el ticket se compone leyendo el propio ticket,
  sin consultar `identity`.
- Roles de asignacion (RF-38): `ASSIGNMENT_ROLES` fija que solo
  `administrador` puede asignar y reasignar; los roles de gestion de
  prioridad y estado no cambian.
- Registro de asignaciones (RF-37): `AssignmentRecord` es de solo datos
  (ticket, tecnico anterior —vacio en la primera asignacion—, tecnico
  nuevo, usuario que asigna y fecha y hora); quien decide cuando se
  registra es el caso de uso (solo cambios efectivos).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 200
DESCRIPTION_MIN_LENGTH = 1
DESCRIPTION_MAX_LENGTH = 5000
COMMENT_MIN_LENGTH = 1
COMMENT_MAX_LENGTH = 2000
OPEN_STATUS = "Abierto"
IN_PROGRESS_STATUS = "En progreso"
CLOSED_STATUS = "Cerrado"
RESOLVED_STATUS = "Resuelto"

# Estados que congelan el SLA del ticket (HU-05, RF-46).
RESOLVED_STATUSES = frozenset({RESOLVED_STATUS, CLOSED_STATUS})

# Catalogos de HU-03 (RF-21). El orden es el del RF y de la spec.
PRIORITIES = ("Crítica", "Alta", "Media", "Baja")
STATUSES = (OPEN_STATUS, IN_PROGRESS_STATUS, RESOLVED_STATUS, CLOSED_STATUS)

# Flujo del ciclo de vida (HU-08, RF-71): destinos permitidos por
# `PUT /api/tickets/{ticket_id}/status`. `Cerrado` no tiene destinos por
# esa ruta; su unica salida es la reapertura de RF-76.
STATUS_TRANSITIONS = {
    OPEN_STATUS: frozenset({IN_PROGRESS_STATUS}),
    IN_PROGRESS_STATUS: frozenset({RESOLVED_STATUS}),
    RESOLVED_STATUS: frozenset({CLOSED_STATUS, IN_PROGRESS_STATUS}),
    CLOSED_STATUS: frozenset(),
}

# Campos registrables en el registro de modificaciones (RF-26).
PRIORITY_FIELD = "priority"
STATUS_FIELD = "status"

# Acciones del historial derivado (HU-09, RF-82).
HISTORY_ACTION_CREATED = "ticket_created"
HISTORY_ACTION_ASSIGNED = "technician_assigned"
HISTORY_ACTION_REASSIGNED = "technician_reassigned"
HISTORY_ACTION_PRIORITY = "priority_changed"
HISTORY_ACTION_STATUS = "status_changed"
HISTORY_ACTION_COMMENT = "comment_added"

# Roles con permisos de gestion sobre prioridad y estado (RF-24).
MANAGEMENT_ROLES = frozenset({"tecnico", "administrador"})
TICKET_READ_ROLES = frozenset({"tecnico", "supervisor", "administrador"})
TICKET_MODIFICATION_ROLES = frozenset({"tecnico", "supervisor", "administrador"})

# Roles con permiso de asignacion y reasignacion (RF-38): solo el
# administrador; los tecnicos no asignan.
ASSIGNMENT_ROLES = frozenset({"administrador", "supervisor"})

# Roles con permiso de reapertura (HU-08, RF-77): solo el administrador.
REOPEN_ROLES = frozenset({"administrador"})


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


def validate_comment_body(raw: object) -> str:
    """Devuelve el cuerpo del comentario recortado (HU-07, RF-62).

    Exige texto estricto y 1-2000 code points tras el recorte. El valor
    devuelto es el que debe almacenarse y exponerse.
    """
    return _validate_text(
        raw,
        field="body",
        min_length=COMMENT_MIN_LENGTH,
        max_length=COMMENT_MAX_LENGTH,
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


def is_allowed_status_transition(current: str, new: str) -> bool:
    """True si `current` -> `new` es una transicion del flujo (RF-71).

    Solo cubre las transiciones de `PUT /api/tickets/{ticket_id}/status`;
    la reapertura de `Cerrado` es una operacion propia (RF-76) y no
    figura en la tabla.
    """
    return new in STATUS_TRANSITIONS.get(current, frozenset())


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
    (`None`) mientras no se fije (RF-27.2) y el tecnico responsable
    (`assignee_id`/`assignee_name`) nace vacio mientras el ticket no se
    asigne (RF-34); los campos con valor por defecto van al final. Sin
    asignacion ambos campos del tecnico son `None` (RF-35.3).
    `resolved_at` (HU-05) nace vacia y la fija el caso de uso al pasar a
    `Resuelto` o `Cerrado`; es el instante en que se congela el SLA.
    `resolved_target_minutes` (HU-14) guarda el objetivo aplicado en ese
    momento y es interno: no forma parte de las respuestas HTTP.
    """

    id: str
    title: str
    description: str
    requester_id: str
    created_at: datetime
    priority: str | None = None
    status: str = OPEN_STATUS
    assignee_id: str | None = None
    assignee_name: str | None = None
    # Fecha y hora de resolucion (HU-05, RF-46). Vacia mientras el ticket
    # no este `Resuelto` ni `Cerrado`; el SLA se congela en este instante.
    resolved_at: datetime | None = None
    # Objetivo de SLA aplicado al resolver (HU-14, RF-76). Vacio mientras
    # el ticket este activo y se limpia al reabrir.
    resolved_target_minutes: int | None = None
    # Tenant autoritativo del ticket (HU-13). El valor por defecto conserva
    # compatibilidad con tickets legacy no multitenant de las historias previas.
    company_id: str | None = None


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


@dataclass
class AssignmentRecord:
    """Registro de una asignacion o reasignacion efectiva (RF-37).

    `previous_assignee_id` es `None` en la primera asignacion y el tecnico
    vigente en una reasignacion; `new_assignee_id` el tecnico fijado;
    `actor_id` el identificador opaco del usuario que asigna, obtenido de
    la sesion autenticada (nunca del cuerpo de la peticion); `assigned_at`
    la fecha y hora UTC generada por el sistema. Los empates de
    `assigned_at` no fijan orden entre registros. La entidad es de solo
    datos: el alta del registro corresponde al caso de uso, y solo se
    registran cambios efectivos. Es independiente del estado del ticket y
    no sustituye al registro de modificaciones de HU-03.
    """

    ticket_id: str
    previous_assignee_id: str | None
    new_assignee_id: str
    actor_id: str
    assigned_at: datetime


@dataclass
class TicketComment:
    """Comentario de seguimiento de un ticket (HU-07, RF-61, RF-63).

    `id` es un UUID opaco, `ticket_id` el ticket al que pertenece,
    `author_id` el identificador opaco del usuario autenticado que lo
    registro (nunca un dato del cuerpo) y `body` el contenido ya recortado
    y validado. `created_at` lo genera el sistema; los empates no fijan
    un orden por identificador, sino que conservan el orden de registro.
    """

    id: str
    ticket_id: str
    author_id: str
    body: str
    created_at: datetime


@dataclass(frozen=True)
class TicketHistoryEvent:
    """Evento del historial derivado de un ticket (HU-09, RF-82, RF-83).

    `action` es una de las constantes `HISTORY_ACTION_*`; `actor_id` el
    identificador opaco del usuario responsable (nunca un dato del cuerpo);
    `occurred_at` la fecha y hora del registro de origen. Los campos
    `previous_value`/`new_value` se usan para prioridad y estado; los
    identificadores de tecnico anterior y nuevo, para asignaciones; y
    `comment`, para el contenido del seguimiento. La entidad es de solo
    datos y de solo lectura: el caso de uso la construye a partir de los
    registros existentes y no la persiste.
    """

    action: str
    actor_id: str
    occurred_at: datetime
    previous_value: str | None = None
    new_value: str | None = None
    previous_assignee_id: str | None = None
    new_assignee_id: str | None = None
    comment: str | None = None
