"""Esquemas HTTP del modulo tickets (RF-11, RF-13, RF-14).

La validacion semantica (recorte, longitudes, sin coercion) vive en el
dominio y el caso de uso; aqui solo se exige presencia, tipo cadena
estricto (`StrictStr`) y se rechazan campos extra. La respuesta de
creacion incluye los seis campos del ticket.
"""

from pydantic import BaseModel, ConfigDict, StrictStr


class CreateTicketRequest(BaseModel):
    """Cuerpo de POST /api/tickets: solo titulo y descripcion (RF-12)."""

    model_config = ConfigDict(extra="forbid")

    title: StrictStr
    description: StrictStr


class TicketResponse(BaseModel):
    """Ticket devuelto por la creacion (RF-13, RF-14, RF-16).

    `created_at` se serializa en ISO 8601/RFC 3339 con offset UTC y
    microsegundos (contrato de la planificacion, D6).
    """

    id: str
    title: str
    description: str
    status: str
    created_at: str
    requester_id: str


class TicketSummaryResponse(BaseModel):
    """Resumen de un ticket para el listado (RF-15).

    Exactamente `{id, title, status, created_at}`: no incluye la
    descripcion ni el identificador del solicitante.
    """

    id: str
    title: str
    status: str
    created_at: str
