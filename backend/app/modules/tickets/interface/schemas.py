"""Esquemas HTTP del modulo tickets (RF-11, RF-13, RF-14, RF-22, RF-23).

La validacion semantica (recorte, longitudes, catalogos, sin coercion)
vive en el dominio y el caso de uso; aqui solo se exige presencia, tipo
cadena estricto (`StrictStr`) y se rechazan campos extra. Las respuestas
de ticket incluyen el campo `priority` (RF-27.2) y el tecnico responsable
`assignee` (RF-35.3, RF-35.5): `{id, name}` o `null`; las peticiones de
modificacion admiten unicamente el valor a fijar (RF-29.2).
"""

from pydantic import BaseModel, ConfigDict, StrictStr
from uuid import UUID


class CreateTicketRequest(BaseModel):
    """Cuerpo de POST /api/tickets: solo titulo y descripcion (RF-12)."""

    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    description: StrictStr


class SetPriorityRequest(BaseModel):
    """Cuerpo de PUT /api/tickets/{ticket_id}/priority (RF-22, RF-29)."""

    model_config = ConfigDict(extra="forbid")

    priority: StrictStr


class SetStatusRequest(BaseModel):
    """Cuerpo de PUT /api/tickets/{ticket_id}/status (RF-23, RF-29)."""

    model_config = ConfigDict(extra="forbid")

    status: StrictStr


class SetAssigneeRequest(BaseModel):
    """Cuerpo de PUT /api/tickets/{ticket_id}/assignee (RF-39.1, RF-39.2).

    Admite unicamente el identificador del tecnico, obligatorio y textual
    estricto (sin coercion); cualquier campo adicional se rechaza.
    """

    model_config = ConfigDict(extra="forbid")

    assignee_id: UUID


class CreateCommentRequest(BaseModel):
    """Cuerpo de POST /api/tickets/{ticket_id}/comments (HU-07, RF-62).

    Admite unicamente el contenido del comentario, obligatorio y textual
    estricto (sin coercion); el autor y la fecha se obtienen de la sesion
    y del sistema, nunca del cuerpo.
    """

    model_config = ConfigDict(extra="forbid")

    body: StrictStr


class AuthorResponse(BaseModel):
    """Autor de un comentario de seguimiento (HU-07, RF-67).

    Solo identificador opaco y nombre: nunca correo, rol, credenciales ni
    hash.
    """

    id: str
    name: str


class CommentResponse(BaseModel):
    """Comentario de seguimiento devuelto por la API (HU-07, RF-61).

    Incluye el ticket al que pertenece, el cuerpo ya recortado, el autor
    resuelto por `identity` (o `None` si no se resuelve) y la fecha y hora
    en ISO 8601 con offset UTC.
    """

    id: str
    ticket_id: str
    body: str
    author: AuthorResponse | None
    created_at: str


class AssigneeResponse(BaseModel):
    """Tecnico responsable de un ticket (RF-35.3, RF-35.4).

    Solo identificador opaco y nombre: nunca correo, credenciales ni rol.
    """

    id: str
    name: str


class HistoryUserResponse(BaseModel):
    """Usuario de un evento de historial (HU-09, RF-83, RF-88).

    Solo identificador opaco y nombre visible. `name` es `None` si el
    usuario ya no se puede resolver, pero el identificador se conserva para
    no perder la trazabilidad. Nunca incluye correo, rol ni credenciales.
    """

    id: str
    name: str | None


class HistoryEventResponse(BaseModel):
    """Evento del historial de un ticket (HU-09, RF-81, RF-83).

    Todos los campos se serializan siempre; los que no aplican a un tipo de
    evento van a `null`. `previous_value`/`new_value` describen prioridad y
    estado; `previous_assignee`/`new_assignee`, asignaciones; y `comment`,
    el contenido del seguimiento. `occurred_at` va en ISO 8601 con offset
    UTC, igual que el resto de fechas del contrato.
    """

    action: str
    actor: HistoryUserResponse
    occurred_at: str
    previous_value: str | None
    new_value: str | None
    previous_assignee: HistoryUserResponse | None
    new_assignee: HistoryUserResponse | None
    comment: str | None


class RequesterResponse(BaseModel):
    """Solicitante de un ticket (HU-06, RF-53).

    Identificador opaco, nombre y correo, resueltos por el contrato de
    `identity`. Nunca incluye rol, contrasena, hash ni otros datos de
    credenciales (RF-59).
    """

    id: str
    name: str
    email: str


class SlaResponse(BaseModel):
    """SLA calculado de un ticket (HU-05, RF-44).

    Se anula cuando el ticket no tiene prioridad (RF-42). Los tiempos van
    en minutos enteros y las fechas en ISO 8601 con offset UTC, igual que
    `created_at`. `near_due` y `breached` son los indicadores de SLA
    proximo a vencer e incumplido (RF-45.4).
    """

    target_minutes: int
    started_at: str
    due_at: str
    elapsed_minutes: int
    remaining_minutes: int
    status: str
    near_due: bool
    breached: bool


class TicketResponse(BaseModel):
    """Ticket completo devuelto por creacion, detalle y modificacion.

    `priority` es `None` mientras no se fije (RF-27.2). `assignee` es
    `None` mientras el ticket no tenga responsable (RF-35.3). `requester`
    es la vista del solicitante (HU-06, RF-53) o `None` si no se resuelve.
    `resolved_at` es `None` mientras el ticket no este resuelto (HU-05,
    RF-46). `sla` es `None` mientras no haya prioridad (HU-05, RF-42).
    Las fechas se serializan en ISO 8601/RFC 3339 con offset UTC y
    microsegundos (contrato de la planificacion, D6).
    """

    id: str
    title: str
    description: str
    priority: str | None
    status: str
    assignee: AssigneeResponse | None
    requester: RequesterResponse | None
    sla: SlaResponse | None
    created_at: str
    resolved_at: str | None
    requester_id: str


class TicketSummaryResponse(BaseModel):
    """Resumen de un ticket para el listado (RF-15, RF-27.2, RF-35.1).

    Exactamente `{id, title, priority, status, assignee, sla, created_at}`:
    no incluye la descripcion ni el identificador del solicitante. `sla`
    es `None` mientras el ticket no tenga prioridad (HU-05, RF-42).
    """

    id: str
    title: str
    priority: str | None
    status: str
    assignee: AssigneeResponse | None
    sla: SlaResponse | None
    created_at: str

