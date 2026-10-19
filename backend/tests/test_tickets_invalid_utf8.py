"""Regresion post-validacion (HU-03/HU-04): bytes UTF-8 invalidos en los PUT.

Los tres endpoints de modificacion comparten el helper `_json_body` del
router de tickets. Un cuerpo con bytes que no forman UTF-8 valido hacia que
`json.loads` lanzara `UnicodeDecodeError` (que no es `json.JSONDecodeError`),
la excepcion escapaba y la peticion acababa en 500. Ahora se traduce al
mismo 422 de decodificacion que un JSON sintacticamente invalido (`detail`
como lista, tipo `json_invalid`, posicion del byte y `ctx.error` claro),
sin alterar el comportamiento de los cuerpos validos ni el de los rechazos
previos.

Los cuerpos crudos se envian con `content=` y `Content-Type: application/json`
(un cliente HTTP real puede enviar bytes invalidos; `json=` siempre
serializa UTF-8 valido).

Cubre:
- administrador + ticket abierto -> 422 (nunca 500), sin mutar el ticket ni
  generar registros (RF-29, RF-30, RF-40);
- precedencia 401 > 404 > 409 > 422 con el mismo cuerpo invalido: sin sesion
  -> 401; cliente -> 404 uniforme; inexistente o id invalido -> 404; cerrado
  -> 409; solo administrador + ticket abierto llega al 422;
- JSON valido (incluido un valor multibyte) sigue devolviendo 200, y un
  cuerpo con bytes invalidos que no declara JSON conserva su 422 de esquema;
- el 422 del JSON sintacticamente invalido mantiene exactamente la misma
  forma de error.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
)
from app.modules.tickets.application.get_ticket import TICKET_NOT_FOUND_MESSAGE
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

PASSWORD = "Secreta123"
ENDPOINTS = ("priority", "status", "assignee")

JSON_HEADERS = {"Content-Type": "application/json"}

# Cuerpos con un byte 0xff: ni UTF-8 valido ni JSON. Se envian crudos.
INVALID_UTF8_BODIES = {
    "priority": b'{"priority": "\xff"}',
    "status": b'{"status": "\xff"}',
    "assignee": b'{"assignee_id": "\xff"}',
}

VALID_BODIES = {
    "priority": {"priority": "Media"},
    "status": {"status": "Resuelto"},
}

# `raise_server_exceptions=False`: si la aplicacion volviera a lanzar el
# `UnicodeDecodeError`, la prueba falla con un 500 explicito en lugar de un
# traceback (la regresion exige 422, nunca 500).
anon_api = TestClient(app, raise_server_exceptions=False)
client_api = TestClient(app, raise_server_exceptions=False)
admin_api = TestClient(app, raise_server_exceptions=False)

CLIENTS = (anon_api, client_api, admin_api)


@pytest.fixture(autouse=True)
def clean_state():
    _clear_state()
    yield
    _clear_state()


def _clear_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    for target in CLIENTS:
        target.cookies.clear()


def _login(target, email):
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200, logged.text
    return logged


def _client_session(target=client_api, email=None, name="Cliente Uno"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    registered = target.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201, registered.text
    _login(target, email)
    return registered.json()


def _provision(role, email=None, name="Equipo Soporte"):
    email = email or f"{uuid.uuid4().hex}@ejemplo.com"
    return provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )


def _admin_session(target=admin_api):
    admin = _provision("administrador", name="Admin Uno")
    _login(target, admin.email)
    return admin


def _create_ticket(
    target=client_api, title="Titulo", description="Descripcion"
):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201, created.text
    return created.json()


def _put(endpoint, ticket_id, body, target):
    url = f"/api/tickets/{ticket_id}/{endpoint}"
    if isinstance(body, bytes):
        # Cuerpo crudo (no `json=`): permite bytes que no son UTF-8 valido.
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _close_ticket(ticket_id, target=admin_api):
    closed = _put("status", ticket_id, {"status": "Cerrado"}, target)
    assert closed.status_code == 200, closed.text
    return closed


def _ticket_state(ticket_id):
    stored = get_ticket_repository().find_by_id(ticket_id)
    assert stored is not None
    return (
        stored.title,
        stored.description,
        stored.priority,
        stored.status,
        stored.requester_id,
        stored.created_at,
        stored.assignee_id,
        stored.assignee_name,
    )


def _snapshot(*ticket_ids):
    """Estado de los tickets y numero de registros de ambos logs."""
    return (
        {ticket_id: _ticket_state(ticket_id) for ticket_id in ticket_ids},
        get_ticket_modification_log().count(),
        get_assignment_log().count(),
    )


def _assert_decode_error_shape(error):
    """Claves y valores comunes a todo 422 de decodificacion."""
    assert set(error) == {"type", "loc", "msg", "input", "ctx"}
    assert error["type"] == "json_invalid"
    assert error["msg"] == "JSON decode error"
    assert error["input"] == {}
    assert error["loc"][0] == "body"
    assert isinstance(error["loc"][1], int)


def _assert_invalid_utf8_422(response, raw):
    """Formato exacto del 422 por bytes invalidos, con la posicion del byte."""
    assert response.status_code == 422, response.text
    assert response.status_code not in (400, 403, 404, 409, 500)
    body = response.json()
    assert set(body) == {"detail"}
    [error] = body["detail"]
    _assert_decode_error_shape(error)
    # La posicion es el indice del primer byte que no forma UTF-8 valido.
    assert error["loc"][1] == raw.index(0xFF)
    assert error["ctx"] == {"error": "Invalid UTF-8"}


# --- Administrador + ticket abierto: 422 (nunca 500) sin mutacion ---


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_invalid_utf8_body_returns_422_without_mutation(endpoint):
    _client_session()
    created = _create_ticket()
    _admin_session()
    raw = INVALID_UTF8_BODIES[endpoint]

    before = _snapshot(created["id"])
    response = _put(endpoint, created["id"], raw, admin_api)

    _assert_invalid_utf8_422(response, raw)
    # Ningun rechazo modifica el ticket ni genera registros.
    assert _snapshot(created["id"]) == before
    assert get_ticket_modification_log().count() == 0
    assert get_assignment_log().count() == 0


# --- Precedencia 401 > 404 > 409 > 422 con el mismo cuerpo invalido ---


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_invalid_utf8_precedence_401_404_409_before_422(endpoint):
    _client_session()
    _admin_session()
    open_ticket = _create_ticket(title="Abierto")
    closed_ticket = _create_ticket(title="Cerrado")
    _close_ticket(closed_ticket["id"])

    raw = INVALID_UTF8_BODIES[endpoint]

    # Cuerpo 404 uniforme de HU-02, identico en todos los intentos.
    unified = client_api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert unified.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
    unified_text = unified.text

    before = _snapshot(open_ticket["id"], closed_ticket["id"])

    # Sin sesion valida -> 401 antes de leer el cuerpo.
    for ticket_id in (open_ticket["id"], closed_ticket["id"], "no-es-uuid"):
        response = _put(endpoint, ticket_id, raw, anon_api)
        assert response.status_code == 401, response.text
        assert set(response.json()) == {"detail"}
        assert response.status_code not in (400, 403)

    # Cliente -> 404 uniforme aunque el ticket exista y el cuerpo falle.
    client_response = _put(endpoint, open_ticket["id"], raw, client_api)
    assert client_response.status_code == 404
    assert client_response.text == unified_text

    # Administrador: ticket inexistente o identificador invalido -> mismo 404.
    for ticket_id in (str(uuid.uuid4()), "no-es-uuid", "123"):
        response = _put(endpoint, ticket_id, raw, admin_api)
        assert response.status_code == 404
        assert response.text == unified_text

    # Ticket cerrado -> 409 aunque el cuerpo no se pueda decodificar.
    closed_response = _put(endpoint, closed_ticket["id"], raw, admin_api)
    assert closed_response.status_code == 409
    assert closed_response.json() == {"detail": TICKET_CLOSED_MESSAGE}

    # Solo administrador + ticket abierto llega a decodificar el cuerpo.
    open_response = _put(endpoint, open_ticket["id"], raw, admin_api)
    _assert_invalid_utf8_422(open_response, raw)

    # Ningun rechazo (tampoco el 422) muto nada ni registro nada.
    assert _snapshot(open_ticket["id"], closed_ticket["id"]) == before


# --- Sin regresiones: JSON valido sigue devolviendo 200 ---


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_valid_json_still_returns_200(endpoint):
    _client_session()
    created = _create_ticket()
    _admin_session()

    if endpoint == "assignee":
        technician = _provision("tecnico", name="Ana Torres")
        body = {"assignee_id": technician.id}
    else:
        body = VALID_BODIES[endpoint]

    response = _put(endpoint, created["id"], body, admin_api)

    assert response.status_code == 200, response.text
    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    if endpoint == "priority":
        assert stored.priority == body["priority"]
    elif endpoint == "status":
        assert stored.status == body["status"]
    else:
        assert stored.assignee_id == technician.id
        assert stored.assignee_name == technician.name
        assert response.json()["assignee"] == {
            "id": technician.id,
            "name": technician.name,
        }


def test_valid_multibyte_utf8_body_is_accepted():
    _client_session()
    created = _create_ticket()
    _admin_session()
    # "Critica" con tilde en UTF-8 valido (varios bytes por code point).
    raw = '{"priority": "Crítica"}'.encode("utf-8")

    response = admin_api.put(
        f"/api/tickets/{created['id']}/priority",
        content=raw,
        headers=JSON_HEADERS,
    )

    assert response.status_code == 200, response.text
    stored = get_ticket_repository().find_by_id(created["id"])
    assert stored is not None
    assert stored.priority == "Crítica"


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_invalid_utf8_with_non_json_content_type_keeps_schema_422(endpoint):
    _client_session()
    created = _create_ticket()
    _admin_session()
    raw = INVALID_UTF8_BODIES[endpoint]

    # Sin declarar JSON el cuerpo no se decodifica de forma estricta: se
    # conserva el 422 de esquema de siempre (nunca 500).
    response = admin_api.put(
        f"/api/tickets/{created['id']}/{endpoint}",
        content=raw,
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 422, response.text
    assert response.status_code not in (400, 403, 404, 409, 500)
    [error] = response.json()["detail"]
    assert error["type"] == "model_attributes_type"
    assert error["loc"] == ["body"]


def test_syntactically_invalid_json_keeps_the_same_error_shape():
    _client_session()
    created = _create_ticket()
    _admin_session()
    malformed = b'{"priority": '

    response = _put("priority", created["id"], malformed, admin_api)

    assert response.status_code == 422, response.text
    [error] = response.json()["detail"]
    # Misma forma que el 422 por UTF-8 invalido: solo cambian el mensaje
    # del decodificador (`ctx`) y la posicion.
    _assert_decode_error_shape(error)
    assert error["ctx"] == {"error": "Expecting value"}
