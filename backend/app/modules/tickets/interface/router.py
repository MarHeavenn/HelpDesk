"""Rutas HTTP de tickets (RF-11, RF-13 a RF-16, RF-22, RF-23, RF-30).

Solo comunican: delegan en los casos de uso y traducen sus errores a
codigos HTTP con cuerpo consistente {"detail": <mensaje>}. La identidad
proviene de la dependencia `get_current_user` de `identity` (unico
contacto entre modulos; el ticket usa `current["id"]` como responsable y
`current["role"]` para autorizar).

Precedencia de rechazos (RF-30): `get_current_user` (401) y la dependencia
que invoca `get_modifiable_ticket` (404 de permiso/resolucion, 409 de
ticket cerrado) se resuelven antes que el cuerpo de la peticion, como en
HU-02 el 401 precede al 422. Para que la precedencia se cumpla tambien con
JSON sintacticamente invalido (o con bytes que no son UTF-8 valido), el
cuerpo de las modificaciones no se declara como parametro (FastAPI lo
decodificaria antes de las dependencias) sino en una dependencia declarada
en ultimo lugar, que lo lee y lo valida con los esquemas de `schemas.py`
una vez resueltas la autenticacion, el permiso, la resolucion y el estado
cerrado.
"""

import json
from collections.abc import Callable, Coroutine
from email.message import Message
from typing import Any, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError

from app.modules.identity.interface.dependencies import get_current_user
from app.modules.identity.interface.technicians_contract import (
    get_technician_summary,
)
from app.modules.tickets.application.assign_ticket import assign_ticket
from app.modules.tickets.application.create_ticket import (
    TicketValidationError,
    create_ticket,
)
from app.modules.tickets.application.get_assignable_ticket import (
    get_assignable_ticket,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TicketClosedError,
    get_modifiable_ticket,
)
from app.modules.tickets.application.get_ticket import (
    TicketNotFoundError,
    get_my_ticket,
)
from app.modules.tickets.application.list_tickets import list_my_tickets
from app.modules.tickets.application.set_ticket_priority import set_ticket_priority
from app.modules.tickets.application.update_ticket_status import (
    update_ticket_status,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)
from app.modules.tickets.interface.schemas import (
    AssigneeResponse,
    CreateTicketRequest,
    SetAssigneeRequest,
    SetPriorityRequest,
    SetStatusRequest,
    TicketResponse,
    TicketSummaryResponse,
)

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _assignee_response(ticket: Ticket) -> AssigneeResponse | None:
    """Compone el tecnico responsable o `None` si el ticket no esta asignado.

    La entidad mantiene `assignee_id` y `assignee_name` siempre ambos
    `None` o ambos con valor (D8); una proyeccion incompleta se trata como
    no asignada para no inventar un nombre (RF-35.3).
    """
    if ticket.assignee_id is None or ticket.assignee_name is None:
        return None
    return AssigneeResponse(id=ticket.assignee_id, name=ticket.assignee_name)


def _ticket_response(ticket: Ticket) -> TicketResponse:
    """Serializa el ticket completo (fecha con offset UTC y microsegundos)."""
    return TicketResponse(
        id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status=ticket.status,
        assignee=_assignee_response(ticket),
        created_at=ticket.created_at.isoformat(),
        requester_id=ticket.requester_id,
    )


def ticket_summary(ticket: Ticket) -> TicketSummaryResponse:
    """Serializa el resumen del listado (sin descripcion, RF-15, RF-35.1)."""
    return TicketSummaryResponse(
        id=ticket.id,
        title=ticket.title,
        priority=ticket.priority,
        status=ticket.status,
        assignee=_assignee_response(ticket),
        created_at=ticket.created_at.isoformat(),
    )


def _modifiable_ticket(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> Ticket:
    """Resuelve el ticket sobre el que el actor puede operar.

    Delega en `get_modifiable_ticket` (permiso de rol y resolucion 404,
    ticket cerrado 409) y traduce sus errores a HTTP. Al ser una
    dependencia, FastAPI la resuelve antes del cuerpo: un 404 o un 409
    prevalecen sobre el 422 de validacion (RF-30).
    """
    try:
        return get_modifiable_ticket(
            ticket_id=ticket_id,
            actor_role=current["role"],
            tickets=get_ticket_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _assignable_ticket(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> Ticket:
    """Resuelve el ticket sobre el que el actor puede asignar.

    Delega en `get_assignable_ticket` (permiso de asignacion y resolucion
    404, ticket cerrado 409) y traduce sus errores a HTTP. Al ser una
    dependencia, FastAPI la resuelve antes del cuerpo: un 404 o un 409
    prevalecen sobre el 422 de validacion (RF-40).
    """
    try:
        return get_assignable_ticket(
            ticket_id=ticket_id,
            actor_role=current["role"],
            tickets=get_ticket_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TicketClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# Error de cuerpo ausente con el mismo formato que usaba FastAPI al validar
# el cuerpo de forma declarativa (`detail` como lista de errores).
_MISSING_BODY_ERROR = {
    "type": "missing",
    "loc": ("body",),
    "msg": "Field required",
    "input": None,
}

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


def _request_validation_error(
    errors: list[Any], body: Any
) -> RequestValidationError:
    """Construye el 422 con el formato de error de validacion de FastAPI."""
    return RequestValidationError(errors, body=body)


def _declares_json(content_type: str | None) -> bool:
    """Indica si el cuerpo declara JSON (mismo criterio que FastAPI)."""
    if not content_type:
        return False
    message = Message()
    message["content-type"] = content_type
    if message.get_content_maintype() != "application":
        return False
    subtype = message.get_content_subtype()
    return subtype == "json" or subtype.endswith("+json")


def _non_json_body_error(raw: bytes) -> dict[str, Any]:
    """Rechazo de esquema que FastAPI daba a un cuerpo que no declara JSON."""
    return {
        "type": "model_attributes_type",
        "loc": ("body",),
        "msg": "Input should be a valid dictionary or object to extract fields from",
        "input": raw.decode("utf-8", errors="replace"),
    }


def _body_error(error: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un error de esquema al formato que usaba FastAPI."""
    normalized = {key: value for key, value in error.items() if key != "url"}
    normalized["loc"] = ("body", *error.get("loc", ()))
    return normalized


def _json_invalid_error(
    position: int, message: str, raw: bytes
) -> RequestValidationError:
    """422 de cuerpo que no es JSON decodificable.

    Comparte formato entre la sintaxis invalida (`JSONDecodeError`) y los
    bytes que no son UTF-8 valido (`UnicodeDecodeError`); `position` es el
    indice donde el decodificador se detuvo.
    """
    return _request_validation_error(
        [
            {
                "type": "json_invalid",
                "loc": ("body", position),
                "msg": "JSON decode error",
                "input": {},
                "ctx": {"error": message},
            }
        ],
        body=raw,
    )


def _json_body(
    schema: type[_SchemaT],
) -> Callable[[Request], Coroutine[Any, Any, _SchemaT]]:
    """Devuelve la dependencia que lee y valida el cuerpo JSON.

    Se declara en ultimo lugar en la firma para que se ejecute despues de
    `get_current_user` y `_modifiable_ticket`: solo un ticket existente, no
    cerrado y con sesion de gestion llega a decodificar el cuerpo, de modo
    que un JSON sintacticamente invalido no adelanta el 422 al 401/404/409
    (RF-30). Ausente, invalido (sintaxis o UTF-8) o fuera de esquema -> 422,
    sin cambios.
    """

    async def _read_body(request: Request) -> _SchemaT:
        raw = await request.body()
        if not raw:
            raise _request_validation_error([_MISSING_BODY_ERROR], body=None)
        if not _declares_json(request.headers.get("content-type")):
            raise _request_validation_error(
                [_non_json_body_error(raw)], body=raw
            )
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise _json_invalid_error(exc.pos, exc.msg, raw) from exc
        except UnicodeDecodeError as exc:
            # `json.loads` decodifica los `bytes` como UTF-8: un cuerpo con
            # bytes invalidos lanza `UnicodeDecodeError` (que no es
            # `JSONDecodeError`) y escaparia como 500. Se traduce al mismo
            # 422 de decodificacion, con la posicion del byte invalido.
            raise _json_invalid_error(
                exc.start, "Invalid UTF-8", raw
            ) from exc
        if decoded is None:
            raise _request_validation_error([_MISSING_BODY_ERROR], body=None)
        try:
            return schema.model_validate(decoded)
        except ValidationError as exc:
            raise _request_validation_error(
                [_body_error(error) for error in exc.errors()], body=decoded
            ) from exc

    return _read_body


_priority_body = _json_body(SetPriorityRequest)
_status_body = _json_body(SetStatusRequest)
_assignee_body = _json_body(SetAssigneeRequest)


def _json_body_documentation(schema: type[BaseModel]) -> dict[str, Any]:
    """Documenta en OpenAPI el cuerpo que se valida en una dependencia."""
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": schema.model_json_schema()}
            },
        }
    }


@router.post("", response_model=TicketResponse, status_code=201)
def create_ticket_endpoint(
    payload: CreateTicketRequest,
    current: dict = Depends(get_current_user),
) -> TicketResponse:
    """Crea un ticket del usuario autenticado (201) o rechaza con 422."""
    try:
        ticket = create_ticket(
            title=payload.title,
            description=payload.description,
            requester_id=current["id"],
            tickets=get_ticket_repository(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ticket_response(ticket)


@router.get("", response_model=list[TicketSummaryResponse])
def list_tickets_endpoint(
    current: dict = Depends(get_current_user),
) -> list[TicketSummaryResponse]:
    """Lista los tickets propios, mas recientes primero (RF-15)."""
    tickets = list_my_tickets(
        requester_id=current["id"],
        tickets=get_ticket_repository(),
    )
    return [ticket_summary(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket_endpoint(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> TicketResponse:
    """Detalle de un ticket propio (RF-16, RF-17).

    `ticket_id` se declara como `str` (no `uuid.UUID`) para que un
    identificador mal formado no devuelva 422 de FastAPI: el formato y la
    propiedad se resuelven en la logica y se traducen aqui a 404. Sin
    sesion valida, `get_current_user` responde 401 antes del handler
    (precedencia 401 > 404, RF-18).
    """
    try:
        ticket = get_my_ticket(
            ticket_id=ticket_id,
            requester_id=current["id"],
            tickets=get_ticket_repository(),
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ticket_response(ticket)


@router.put(
    "/{ticket_id}/priority",
    response_model=TicketResponse,
    openapi_extra=_json_body_documentation(SetPriorityRequest),
)
def set_priority_endpoint(
    ticket: Ticket = Depends(_modifiable_ticket),
    current: dict = Depends(get_current_user),
    payload: SetPriorityRequest = Depends(_priority_body),
) -> TicketResponse:
    """Fija la prioridad de un ticket (RF-22) o rechaza con 422.

    La autorizacion, la resolucion y el estado cerrado se resuelven en
    `_modifiable_ticket` antes de leer el cuerpo (401/404/409 > 422,
    tambien con JSON sintacticamente invalido, RF-30). El catalogo se
    valida en el caso de uso (RF-21, RF-29.3). El responsable procede de
    la sesion, nunca del cuerpo (RF-24, RF-26).
    """
    try:
        updated = set_ticket_priority(
            ticket=ticket,
            priority=payload.priority,
            actor_id=current["id"],
            modifications=get_ticket_modification_log(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ticket_response(updated)


@router.put(
    "/{ticket_id}/status",
    response_model=TicketResponse,
    openapi_extra=_json_body_documentation(SetStatusRequest),
)
def set_status_endpoint(
    ticket: Ticket = Depends(_modifiable_ticket),
    current: dict = Depends(get_current_user),
    payload: SetStatusRequest = Depends(_status_body),
) -> TicketResponse:
    """Actualiza el estado de un ticket (RF-23) o rechaza con 422.

    Mismas reglas de precedencia y autorizacion que la prioridad. HU-03 no
    impone secuencia entre estados (RF-23); el ticket cerrado ya se ha
    rechazado en `_modifiable_ticket` con 409 (RF-28).
    """
    try:
        updated = update_ticket_status(
            ticket=ticket,
            status=payload.status,
            actor_id=current["id"],
            modifications=get_ticket_modification_log(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ticket_response(updated)


@router.put(
    "/{ticket_id}/assignee",
    response_model=TicketResponse,
    openapi_extra=_json_body_documentation(SetAssigneeRequest),
)
def set_assignee_endpoint(
    ticket: Ticket = Depends(_assignable_ticket),
    current: dict = Depends(get_current_user),
    payload: SetAssigneeRequest = Depends(_assignee_body),
) -> TicketResponse:
    """Asigna o reasigna el tecnico de un ticket (RF-32, RF-33).

    La autorizacion de asignacion (solo administrador, 404 uniforme), la
    resolucion del ticket (404) y el estado cerrado (409) se resuelven en
    `_assignable_ticket` antes de leer el cuerpo (RF-40, tambien con JSON
    sintacticamente invalido). El tecnico se valida en el caso de uso con
    el contrato de `identity` (422 uniforme, RF-39.3); el actor procede de
    la sesion, nunca del cuerpo (RF-38).
    """
    try:
        updated = assign_ticket(
            ticket=ticket,
            technician_id=payload.assignee_id,
            actor_id=current["id"],
            resolve_technician=get_technician_summary,
            assignments=get_assignment_log(),
        )
    except TicketValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _ticket_response(updated)

