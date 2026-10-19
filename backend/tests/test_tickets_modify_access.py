"""T4/T7 (HU-03) — Resolucion, permiso y precedencia HTTP (RF-24, RF-25, RF-28, RF-30).

Mapa RF -> test:
- RF-24 (permiso de gestion sobre cualquier ticket del sistema):
  `test_management_roles_resolve_any_ticket`,
  `test_management_roles_resolve_tickets_they_did_not_create`,
  `test_client_role_gets_the_unified_not_found`,
  `test_client_role_is_rejected_before_resolving_the_ticket`,
  `test_client_role_with_invalid_identifier_gets_unified_not_found`,
  `test_client_role_never_reveals_a_closed_ticket`,
  `test_client_gets_the_unified_404_with_any_body_and_case`.
- RF-25 (identificador con formato invalido o ticket inexistente):
  `test_invalid_identifier_format_raises_unified_not_found`,
  `test_nonexistent_ticket_raises_unified_not_found`,
  `test_not_found_message_is_the_same_unified_message_as_hu02`,
  `test_nonexistent_or_invalid_id_with_invalid_input_returns_404`.
- RF-28 (ticket cerrado inmutable en HU-03):
  `test_closed_ticket_raises_ticket_closed_error`,
  `test_ticket_closed_message_is_fixed_by_the_contract`,
  `test_only_the_closed_status_is_immutable`,
  `test_closed_ticket_returns_409_for_any_input_including_current_value`.
- RF-30 (precedencia 401 > 404 > 409 > 422):
  `test_client_role_is_rejected_before_resolving_the_ticket`,
  `test_client_role_never_reveals_a_closed_ticket`,
  `test_management_role_resolution_precedes_the_closed_check`,
  `test_no_session_returns_401_before_identifier_and_body`,
  `test_no_session_returns_401_on_a_closed_ticket_even_with_invalid_body`,
  `test_invalid_session_token_returns_401_before_invalid_identifier_and_body`,
  `test_revoked_session_returns_401_before_invalid_identifier_and_body`,
  `test_expired_session_returns_401_before_invalid_identifier_and_body`,
  `test_open_ticket_with_management_session_returns_422_for_malformed_json`,
  `test_modification_rejections_never_use_400_or_403`.

La primera parte prueba el caso de uso (T4); la seccion HTTP (T7) comprueba
la tabla completa de precedencia y no revelacion sobre la API real,
incluido el cuerpo crudo sintacticamente invalido (`content=` con
`Content-Type: application/json`): la autenticacion, el permiso, la
resolucion y el estado cerrado se resuelven antes de decodificarlo.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.dependencies import SESSION_COOKIE_NAME
from app.modules.tickets.application.get_modifiable_ticket import (
    TICKET_CLOSED_MESSAGE,
    TicketClosedError,
    get_modifiable_ticket,
)
from app.modules.tickets.application.get_ticket import (
    TICKET_NOT_FOUND_MESSAGE,
    TicketNotFoundError,
    get_my_ticket,
)
from app.modules.tickets.domain.entities import STATUSES, Ticket
from app.modules.tickets.infrastructure.ticket_modification_log import (
    get_ticket_modification_log,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
PASSWORD = "Secreta123"

api = TestClient(app)
other_api = TestClient(app)

MODIFICATION_ENDPOINTS = ("priority", "status")

VALID_BODIES = {
    "priority": {"priority": "Alta"},
    "status": {"status": "Resuelto"},
}

# Entradas invalidas de la tabla de precedencia (JSON valido, esquema o
# catalogo invalido): valor ausente, tipos no textuales, campos extra y
# valores fuera del catalogo (RF-29).
INVALID_BODIES = {
    "priority": [
        {},
        {"priority": None},
        {"priority": 3},
        {"priority": True},
        {"priority": ["Alta"]},
        {"priority": {"valor": "Alta"}},
        {"priority": "Urgente"},
        {"priority": "alta"},
        {"priority": "Alta", "actor_id": "otro-usuario"},
        {"priority": "Alta", "status": "Resuelto"},
    ],
    "status": [
        {},
        {"status": None},
        {"status": 3},
        {"status": True},
        {"status": ["Resuelto"]},
        {"status": {"valor": "Resuelto"}},
        {"status": "Abierta"},
        {"status": "abierto"},
        {"status": "Resuelto", "actor_id": "otro-usuario"},
        {"status": "Resuelto", "priority": "Alta"},
    ],
}

OUT_OF_CATALOG = {
    "priority": {"priority": "Urgente"},
    "status": {"status": "Abierta"},
}

# Cuerpos crudos sintacticamente invalidos (JSON mal formado), enviados con
# `content=` y `Content-Type: application/json` (no con `json=`): la
# precedencia RF-30 debe resolverse antes de decodificarlos.
MALFORMED_BODIES = {
    "priority": b'{"priority": ',
    "status": b'{"status": ',
}

JSON_HEADERS = {"Content-Type": "application/json"}

# Centinela para enviar la peticion sin cuerpo (el valor es obligatorio,
# RF-29.1): la precedencia debe resolverse antes de validarlo.
NO_BODY = object()


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()
    other_api.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    api.cookies.clear()
    other_api.cookies.clear()


def _client_session(target=api, email="ana@ejemplo.com", name="Ana Perez"):
    registered = target.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    _login(email, target=target)
    return registered.json()


def _login(email, target=api):
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200


def _provision_and_login(
    role="tecnico",
    email="gestion@ejemplo.com",
    name="Equipo Soporte",
    target=api,
):
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    _login(email, target=target)
    return user


def _create_ticket(target=api, title="Titulo", description="Descripcion"):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201
    return created.json()


def _put(endpoint, ticket_id, body=NO_BODY, target=api):
    url = f"/api/tickets/{ticket_id}/{endpoint}"
    if body is NO_BODY:
        return target.put(url)
    if isinstance(body, bytes):
        # JSON sintacticamente invalido enviado crudo (no `json=`), para
        # reproducir el 422 de decodificacion de FastAPI.
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _close_ticket(ticket_id, target=api):
    closed = _put("status", ticket_id, {"status": "Cerrado"}, target=target)
    assert closed.status_code == 200
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
    )


def _record_count(ticket_id):
    return len(get_ticket_modification_log().list_by_ticket(ticket_id))


def _expire_session(token):
    session = get_session_store().find_by_token(token)
    assert session is not None
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)


class _SpyTicketRepository(InMemoryTicketRepository):
    """Repositorio que registra las resoluciones por identificador."""

    def __init__(self) -> None:
        super().__init__()
        self.find_calls: list[object] = []

    def find_by_id(self, ticket_id: str) -> Ticket | None:
        self.find_calls.append(ticket_id)
        return super().find_by_id(ticket_id)


def _ticket(**overrides) -> Ticket:
    values = {
        "id": str(uuid.uuid4()),
        "title": "Titulo",
        "description": "Descripcion",
        "requester_id": str(uuid.uuid4()),
        "created_at": NOW,
    }
    values.update(overrides)
    return Ticket(**values)


# --- RF-24: tecnicos y administradores resuelven cualquier ticket ---


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_management_roles_resolve_any_ticket(role):
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    assert get_modifiable_ticket(ticket.id, role, repo) is ticket


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_management_roles_resolve_tickets_they_did_not_create(role):
    repo = InMemoryTicketRepository()
    ajeno = _ticket(requester_id="otro-solicitante")
    repo.add(ajeno)

    # La autorizacion es por rol y no depende de quien creo el ticket ni de
    # que tenga asignacion (HU-04).
    assert get_modifiable_ticket(ajeno.id, role, repo) is ajeno


# --- RF-24: un cliente recibe el 404 uniforme, incluso antes de resolver ---


def test_client_role_gets_the_unified_not_found():
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(ticket.id, "cliente", repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_role_is_rejected_before_resolving_the_ticket():
    repo = _SpyTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(ticket.id, "cliente", repo)

    # La comprobacion de rol ocurre antes de resolver el recurso (RF-30).
    assert repo.find_calls == []
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


@pytest.mark.parametrize("bad_id", ["", "no-es-uuid", "123", "abc-123", None, 123])
def test_client_role_with_invalid_identifier_gets_unified_not_found(bad_id):
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(bad_id, "cliente", repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_role_never_reveals_a_closed_ticket():
    repo = InMemoryTicketRepository()
    cerrado = _ticket(status=STATUSES[-1])
    repo.add(cerrado)

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(cerrado.id, "cliente", repo)

    # El permiso (404 uniforme) precede a la inmutabilidad del cerrado
    # (409): el cliente nunca recibe TicketClosedError (RF-24, RF-30).
    assert not isinstance(exc.value, TicketClosedError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


@pytest.mark.parametrize(
    "role",
    [
        "cliente",
        "",
        "TECNICO",
        "Tecnico",
        "técnico",
        "admin",
        "administrador ",
        None,
        123,
    ],
)
def test_roles_without_management_permissions_are_rejected(role):
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(ticket.id, role, repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


# --- RF-25: identificador invalido o ticket inexistente ---


@pytest.mark.parametrize("bad_id", ["", "no-es-uuid", "123", "abc-123", None, 123])
@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_invalid_identifier_format_raises_unified_not_found(role, bad_id):
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(bad_id, role, repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_nonexistent_ticket_raises_unified_not_found(role):
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(str(uuid.uuid4()), role, repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_not_found_message_is_the_same_unified_message_as_hu02():
    hu02_repo = InMemoryTicketRepository()
    hu02_message = None
    try:
        get_my_ticket(str(uuid.uuid4()), "u-1", hu02_repo)
    except TicketNotFoundError as exc:
        hu02_message = str(exc)

    with pytest.raises(TicketNotFoundError) as exc:
        get_modifiable_ticket(str(uuid.uuid4()), "tecnico", InMemoryTicketRepository())

    assert hu02_message is not None
    assert str(exc.value) == hu02_message == TICKET_NOT_FOUND_MESSAGE


# --- RF-28: un ticket cerrado es inmutable en HU-03 ---


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
def test_closed_ticket_raises_ticket_closed_error(role):
    repo = InMemoryTicketRepository()
    cerrado = _ticket(status=STATUSES[-1])
    repo.add(cerrado)

    with pytest.raises(TicketClosedError) as exc:
        get_modifiable_ticket(cerrado.id, role, repo)

    assert not isinstance(exc.value, TicketNotFoundError)
    assert str(exc.value) == TICKET_CLOSED_MESSAGE


def test_ticket_closed_message_is_fixed_by_the_contract():
    assert TICKET_CLOSED_MESSAGE == "ticket is closed"


@pytest.mark.parametrize("role", ["tecnico", "administrador"])
@pytest.mark.parametrize("status", [value for value in STATUSES if value != "Cerrado"])
def test_only_the_closed_status_is_immutable(role, status):
    repo = InMemoryTicketRepository()
    ticket = _ticket(status=status)
    repo.add(ticket)

    assert get_modifiable_ticket(ticket.id, role, repo) is ticket


def test_management_role_resolution_precedes_the_closed_check():
    repo = _SpyTicketRepository()
    missing = str(uuid.uuid4())

    with pytest.raises(TicketNotFoundError):
        get_modifiable_ticket(missing, "tecnico", repo)

    # Si el ticket no existe, se resuelve (y falla) como 404 antes de
    # poder comprobar el estado (RF-30).
    assert repo.find_calls == [missing]


# --- T7 / RF-30: 401 antes que identificador, cuerpo y estado del ticket ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_no_session_returns_401_before_identifier_and_body(endpoint):
    _client_session()
    created = _create_ticket()
    api.cookies.clear()
    before = _ticket_state(created["id"])

    for ticket_id in (created["id"], str(uuid.uuid4()), "no-es-uuid", "123"):
        for body in (
            VALID_BODIES[endpoint],
            NO_BODY,
            MALFORMED_BODIES[endpoint],
            *INVALID_BODIES[endpoint],
        ):
            response = _put(endpoint, ticket_id, body)
            assert response.status_code == 401
            assert response.status_code not in (400, 403, 404, 409, 422)
            assert set(response.json()) == {"detail"}
            assert _ticket_state(created["id"]) == before
            assert _record_count(created["id"]) == 0


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_no_session_returns_401_on_a_closed_ticket_even_with_invalid_body(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    _provision_and_login(target=other_api)
    _close_ticket(created["id"], target=other_api)
    api.cookies.clear()

    before = _ticket_state(created["id"])
    records_before = _record_count(created["id"])
    assert records_before == 1

    for body in (
        VALID_BODIES[endpoint],
        NO_BODY,
        MALFORMED_BODIES[endpoint],
        *INVALID_BODIES[endpoint],
    ):
        response = _put(endpoint, created["id"], body)
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 409, 422)
        assert set(response.json()) == {"detail"}
        assert _ticket_state(created["id"]) == before
        assert _record_count(created["id"]) == records_before


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_invalid_session_token_returns_401_before_invalid_identifier_and_body(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    token = api.cookies.get(SESSION_COOKIE_NAME)
    assert token
    api.cookies.set(SESSION_COOKIE_NAME, "token-invalido")
    before = _ticket_state(created["id"])

    for ticket_id in (created["id"], "no-es-uuid"):
        response = _put(endpoint, ticket_id, INVALID_BODIES[endpoint][-1])
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 409, 422)
        assert set(response.json()) == {"detail"}
        assert _ticket_state(created["id"]) == before
        assert _record_count(created["id"]) == 0


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_revoked_session_returns_401_before_invalid_identifier_and_body(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    token = api.cookies.get(SESSION_COOKIE_NAME)
    assert token

    assert api.post("/api/auth/logout").status_code == 204
    # El logout revoca la sesion y borra la cookie; se reenvia el token
    # revocado para comprobar que el 401 sigue prevaleciendo (RF-30).
    api.cookies.set(SESSION_COOKIE_NAME, token)
    before = _ticket_state(created["id"])

    for ticket_id in (created["id"], "no-es-uuid"):
        response = _put(endpoint, ticket_id, INVALID_BODIES[endpoint][-1])
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 409, 422)
        assert set(response.json()) == {"detail"}
        assert _ticket_state(created["id"]) == before
        assert _record_count(created["id"]) == 0


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_expired_session_returns_401_before_invalid_identifier_and_body(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    token = api.cookies.get(SESSION_COOKIE_NAME)
    assert token
    # Con la sesion aun valida el endpoint protegido responde (no es un
    # falso 401).
    assert api.get("/api/auth/me").status_code == 200

    _expire_session(token)
    before = _ticket_state(created["id"])

    for ticket_id in (created["id"], "no-es-uuid"):
        response = _put(endpoint, ticket_id, INVALID_BODIES[endpoint][-1])
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 409, 422)
        assert set(response.json()) == {"detail"}
        assert _ticket_state(created["id"]) == before
        assert _record_count(created["id"]) == 0


# --- T7 / RF-24: 404 uniforme con cualquier cuerpo y en todos los supuestos ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_client_gets_the_unified_404_with_any_body_and_case(endpoint):
    _client_session(
        target=other_api, email="otra@ejemplo.com", name="Otra Persona"
    )
    foreign = _create_ticket(
        target=other_api, title="Ajeno", description="Secreto"
    )

    _client_session()
    own_open = _create_ticket(title="Propio abierto")
    own_closed = _create_ticket(title="Propio cerrado")

    _provision_and_login(target=other_api)
    _close_ticket(own_closed["id"], target=other_api)

    # 404 unificado de HU-02 con la misma sesion de cliente.
    unified = api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404

    records_before = get_ticket_modification_log().count()
    before_foreign = _ticket_state(foreign["id"])
    before_open = _ticket_state(own_open["id"])
    before_closed = _ticket_state(own_closed["id"])

    cases = (
        ("propio", own_open["id"]),
        ("ajeno", foreign["id"]),
        ("inexistente", str(uuid.uuid4())),
        ("cerrado", own_closed["id"]),
        ("id invalido", "no-es-uuid"),
        ("id invalido", "123"),
    )

    for _, ticket_id in cases:
        for body in (
            VALID_BODIES[endpoint],
            NO_BODY,
            MALFORMED_BODIES[endpoint],
            *INVALID_BODIES[endpoint],
        ):
            response = _put(endpoint, ticket_id, body)
            assert response.status_code == 404
            assert response.status_code not in (400, 403, 409, 422)
            assert response.text == unified.text
            assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
            assert _ticket_state(foreign["id"]) == before_foreign
            assert _ticket_state(own_open["id"]) == before_open
            assert _ticket_state(own_closed["id"]) == before_closed
            assert get_ticket_modification_log().count() == records_before

    # HU-02 no cambia: el cliente sigue consultando sus tickets.
    detail = api.get(f"/api/tickets/{own_open['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "Abierto"
    assert detail.json()["priority"] is None


# --- T7 / RF-28: cerrado con cualquier entrada -> 409 ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_closed_ticket_returns_409_for_any_input_including_current_value(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    _provision_and_login(target=other_api)

    # Se prepara una prioridad vigente y el estado cerrado; cada cambio
    # efectivo deja su registro.
    assert (
        _put(
            "priority",
            created["id"],
            {"priority": "Media"},
            target=other_api,
        ).status_code
        == 200
    )
    _close_ticket(created["id"], target=other_api)

    records_before = _record_count(created["id"])
    assert records_before == 2
    before = _ticket_state(created["id"])

    current_body = {
        "priority": {"priority": "Media"},
        "status": {"status": "Cerrado"},
    }[endpoint]

    for body in (
        VALID_BODIES[endpoint],
        NO_BODY,
        MALFORMED_BODIES[endpoint],
        current_body,
        *INVALID_BODIES[endpoint],
    ):
        response = _put(endpoint, created["id"], body, target=other_api)
        assert response.status_code == 409
        assert response.status_code not in (400, 403, 404, 422)
        assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
        assert _ticket_state(created["id"]) == before
        assert _record_count(created["id"]) == records_before

    assert get_ticket_modification_log().count() == records_before


# --- T7 / RF-25: inexistente o id invalido con entrada invalida -> 404 ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_nonexistent_or_invalid_id_with_invalid_input_returns_404(endpoint):
    _provision_and_login()

    unified = api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404

    for ticket_id in (str(uuid.uuid4()), "no-es-uuid", "123"):
        for body in (
            VALID_BODIES[endpoint],
            NO_BODY,
            MALFORMED_BODIES[endpoint],
            *INVALID_BODIES[endpoint],
        ):
            response = _put(endpoint, ticket_id, body)
            assert response.status_code == 404
            assert response.status_code not in (400, 403, 409, 422)
            assert response.text == unified.text
            assert response.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}
            assert get_ticket_modification_log().count() == 0


# --- T7 / RF-30: JSON invalido -> 422 solo con ticket abierto y gestion ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_open_ticket_with_management_session_returns_422_for_malformed_json(
    endpoint,
):
    _client_session()
    created = _create_ticket()
    _provision_and_login()

    before = _ticket_state(created["id"])
    response = _put(endpoint, created["id"], MALFORMED_BODIES[endpoint])

    # Unico supuesto que llega al 422: ticket existente, no cerrado y con
    # sesion de gestion (RF-29, RF-30), aqui con JSON sintacticamente
    # invalido.
    assert response.status_code == 422
    assert response.status_code not in (400, 403, 404, 409)
    assert set(response.json()) == {"detail"}
    assert _ticket_state(created["id"]) == before
    assert _record_count(created["id"]) == 0
    assert get_ticket_modification_log().count() == 0


# --- T7 / RF-30: ningun rechazo usa 400 ni 403 ---


@pytest.mark.parametrize("endpoint", MODIFICATION_ENDPOINTS)
def test_modification_rejections_never_use_400_or_403(endpoint):
    _client_session()
    open_ticket = _create_ticket(title="Abierto")
    to_close = _create_ticket(title="Para cerrar")

    _provision_and_login(target=other_api)
    _close_ticket(to_close["id"], target=other_api)

    client_rejection = _put(
        endpoint, open_ticket["id"], OUT_OF_CATALOG[endpoint]
    )
    closed_rejection = _put(
        endpoint,
        to_close["id"],
        OUT_OF_CATALOG[endpoint],
        target=other_api,
    )
    validation_rejection = _put(
        endpoint,
        open_ticket["id"],
        OUT_OF_CATALOG[endpoint],
        target=other_api,
    )

    api.cookies.clear()
    unauthenticated_rejection = _put(
        endpoint, open_ticket["id"], OUT_OF_CATALOG[endpoint]
    )

    responses = (
        client_rejection,
        closed_rejection,
        validation_rejection,
        unauthenticated_rejection,
    )
    assert {response.status_code for response in responses} == {
        401,
        404,
        409,
        422,
    }
    for response in responses:
        assert response.status_code not in (400, 403)
