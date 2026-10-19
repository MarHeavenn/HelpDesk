"""Esquemas HTTP del modulo tickets (RF-11, RF-13, RF-14, RF-22, RF-23).

La validacion semantica (recorte, longitudes, catalogos, sin coercion)
vive en el dominio y el caso de uso; aqui solo se exige presencia, tipo
cadena estricto (`StrictStr`) y se rechazan campos extra. Las respuestas
de ticket incluyen el campo `priority` (RF-27.2) y las peticiones de
modificacion admiten unicamente el valor a fijar (RF-29.2).
"""

from pydantic import BaseModel, ConfigDict, StrictStr


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


class TicketResponse(BaseModel):
    """Ticket completo devuelto por creacion, detalle y modificacion.

    `priority` es `None` mientras no se fije (RF-27.2). `created_at` se
    serializa en ISO 8601/RFC 3339 con offset UTC y microsegundos
    (contrato de la planificacion, D6).
    """

    id: str
    title: str
    description: str
    priority: str | None
    status: str
    created_at: str
    requester_id: str


class TicketSummaryResponse(BaseModel):
    """Resumen de un ticket para el listado (RF-15, RF-27.2).

    Exactamente `{id, title, priority, status, created_at}`: no incluye la
    descripcion ni el identificador del solicitante.
    """

    id: str
    title: str
    priority: str | None
    status: str
    created_at: str

