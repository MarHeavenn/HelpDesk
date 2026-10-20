"""T5/T8 (HU-04) — Resolucion y permiso de asignacion (RF-38, RF-39.4, RF-40).

Mapa RF -> test:
- RF-38 (solo el administrador asigna y reasigna; cliente y tecnico
  reciben el 404 uniforme de HU-02, sin revelar nada):
  `test_assignment_roles_resolve_any_ticket`,
  `test_administrator_resolves_tickets_they_did_not_create`,
  `test_client_role_gets_the_unified_not_found`,
  `test_technician_role_gets_the_unified_not_found`,
  `test_client_and_technician_get_the_identical_rejection`,
  `test_roles_without_assignment_permission_are_rejected`,
  `test_client_role_is_rejected_before_resolving_the_ticket`,
  `test_technician_role_is_rejected_before_resolving_the_ticket`,
  `test_real_users_are_authorized_by_their_role`,
  `test_technician_can_still_modify_but_cannot_assign`.
- RF-39.4 (ticket existente y con formato valido; `Cerrado` inmutable):
  `test_invalid_identifier_format_raises_unified_not_found`,
  `test_nonexistent_ticket_raises_unified_not_found`,
  `test_nonexistent_ticket_is_not_reported_as_closed`,
  `test_closed_ticket_raises_ticket_closed_error`,
  `test_ticket_closed_message_is_fixed_by_the_contract`,
  `test_only_the_closed_status_is_immutable`.
- RF-40 (precedencia del permiso y de la resolucion antes de la
  validacion de la solicitud; sin mecanismos de autenticacion nuevos):
  `test_client_role_is_rejected_before_resolving_the_ticket`,
  `test_technician_role_is_rejected_before_resolving_the_ticket`,
  `test_permission_precedes_invalid_identifier_and_existence`,
  `test_client_role_never_reveals_a_closed_ticket`,
  `test_technician_role_never_reveals_a_closed_ticket`,
  `test_nonexistent_ticket_is_resolved_before_the_closed_check`.
- RF-40 (HTTP, T8: 401 > 404 > 409 > 422, tambien con JSON
  sintacticamente invalido; ningun rechazo usa 400 ni 403):
  `test_no_session_returns_401_before_identifier_body_and_ticket_state`,
  `test_non_valid_session_returns_401_before_invalid_identifier_and_body`,
  `test_client_and_technician_get_the_unified_404_with_any_body_and_case`,
  `test_administrator_gets_404_for_nonexistent_or_invalid_ticket_with_any_body`,
  `test_closed_ticket_returns_409_for_any_input_including_current_technician`,
  `test_open_ticket_with_administrator_session_returns_422_for_invalid_request`,
  `test_assignment_rejections_never_use_400_or_403`.

Este archivo prueba el caso de uso `get_assignable_ticket` (T5) y, desde
T8, la seccion HTTP con la tabla completa de precedencia 401 > 404 > 409
> 422 sobre la API real, incluido el cuerpo crudo sintacticamente invalido
(`content=` con `Content-Type: application/json`). Un tecnico ya no tiene
permiso de asignacion (RF-38): recibe el mismo 404 uniforme que un
cliente.
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
from app.modules.tickets.application.get_assignable_ticket import (
    get_assignable_ticket,
)
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
from app.modules.tickets.domain.entities import (
    ASSIGNMENT_ROLES,
    CLOSED_STATUS,
    STATUSES,
    Ticket,
)
from app.modules.tickets.infrastructure.assignment_log import (
    get_assignment_log,
)
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

JSON_HEADERS = {"Content-Type": "application/json"}
# Cuerpo crudo con JSON sintacticamente invalido: se envia con `content=`
# para que la precedencia se resuelva antes de decodificarlo (RF-40).
MALFORMED_ASSIGNEE_BODY = b'{"assignee_id": '
# Centinela para enviar la peticion sin cuerpo.
NO_BODY = object()

# Roles sin permiso de asignacion (RF-38): el tecnico se comporta igual
# que un cliente; el resto son variantes de rol que no pertenecen al
# catalogo exacto.
ROLES_WITHOUT_ASSIGNMENT_PERMISSION = [
    "cliente",
    "tecnico",
    "",
    "Administrador",
    "ADMINISTRADOR",
    "administrador ",
    " admin",
    "admin",
    None,
    123,
]


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    api.cookies.clear()
    other_api.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_ticket_modification_log().clear()
    get_assignment_log().clear()
    api.cookies.clear()
    other_api.cookies.clear()


def _provision(role, email="gestion@ejemplo.com", name="Equipo Soporte"):
    return provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )


def _login(email, target=api):
    logged = target.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert logged.status_code == 200, logged.text


def _client_session(target=api, email="cliente@ejemplo.com", name="Cliente"):
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
    _login(email, target=target)
    return registered.json()


def _provision_and_login(
    role="administrador",
    email="admin@ejemplo.com",
    name="Admin Uno",
    target=api,
):
    user = _provision(role, email=email, name=name)
    _login(email, target=target)
    return user


def _create_ticket(target=api, title="Titulo", description="Descripcion"):
    created = target.post(
        "/api/tickets", json={"title": title, "description": description}
    )
    assert created.status_code == 201, created.text
    return created.json()


def _put_assignee(ticket_id, body=NO_BODY, target=api):
    url = f"/api/tickets/{ticket_id}/assignee"
    if body is NO_BODY:
        return target.put(url)
    if isinstance(body, bytes):
        return target.put(url, content=body, headers=JSON_HEADERS)
    return target.put(url, json=body)


def _close_ticket(ticket_id, target=api):
    closed = target.put(
        f"/api/tickets/{ticket_id}/status", json={"status": "Cerrado"}
    )
    assert closed.status_code == 200, closed.text
    return closed


def _assignee_state(ticket_id):
    stored = get_ticket_repository().find_by_id(ticket_id)
    assert stored is not None
    return (
        stored.title,
        stored.description,
        stored.priority,
        stored.status,
        stored.requester_id,
        stored.assignee_id,
        stored.assignee_name,
    )


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


# --- RF-38: el administrador resuelve cualquier ticket ---


@pytest.mark.parametrize("role", sorted(ASSIGNMENT_ROLES))
def test_assignment_roles_resolve_any_ticket(role):
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    assert get_assignable_ticket(ticket.id, role, repo) is ticket


def test_administrator_resolves_tickets_they_did_not_create():
    repo = InMemoryTicketRepository()
    ajeno = _ticket(requester_id="otro-solicitante")
    repo.add(ajeno)

    # La autorizacion es por rol y no depende de quien creo el ticket ni
    # de que ya tenga un tecnico responsable (RF-38).
    assert get_assignable_ticket(ajeno.id, "administrador", repo) is ajeno


# --- RF-38: un cliente o un tecnico reciben el 404 uniforme ---


def test_client_role_gets_the_unified_not_found():
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, "cliente", repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_technician_role_gets_the_unified_not_found():
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, "tecnico", repo)

    # En HU-04 el tecnico no asigna: mismo rechazo que un cliente (RF-38).
    assert not isinstance(exc.value, TicketClosedError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_and_technician_get_the_identical_rejection():
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    messages = []
    for role in ("cliente", "tecnico"):
        with pytest.raises(TicketNotFoundError) as exc:
            get_assignable_ticket(ticket.id, role, repo)
        messages.append(str(exc.value))

    assert messages == [TICKET_NOT_FOUND_MESSAGE, TICKET_NOT_FOUND_MESSAGE]


@pytest.mark.parametrize("role", ROLES_WITHOUT_ASSIGNMENT_PERMISSION)
def test_roles_without_assignment_permission_are_rejected(role):
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, role, repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_client_role_is_rejected_before_resolving_the_ticket():
    repo = _SpyTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, "cliente", repo)

    # El permiso se comprueba antes de resolver el recurso (RF-40): el
    # repositorio no se consulta y no se revela ningun dato.
    assert repo.find_calls == []
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_technician_role_is_rejected_before_resolving_the_ticket():
    repo = _SpyTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, "tecnico", repo)

    assert repo.find_calls == []
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_real_users_are_authorized_by_their_role():
    admin = _provision("administrador", email="admin@ejemplo.com")
    technician = _provision("tecnico", email="tecnico@ejemplo.com")

    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    # El rol real de un usuario de `identity` es el que autoriza.
    assert get_assignable_ticket(ticket.id, admin.role, repo) is ticket
    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, technician.role, repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_technician_can_still_modify_but_cannot_assign():
    repo = InMemoryTicketRepository()
    ticket = _ticket()
    repo.add(ticket)

    # HU-03 no cambia (D9): el tecnico conserva el permiso de gestion y
    # solo pierde el de asignacion.
    assert get_modifiable_ticket(ticket.id, "tecnico", repo) is ticket
    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(ticket.id, "tecnico", repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


# --- RF-39.4: identificador invalido o ticket inexistente -> 404 ---


@pytest.mark.parametrize("bad_id", ["", "no-es-uuid", "123", "abc-123", None, 123])
def test_invalid_identifier_format_raises_unified_not_found(bad_id):
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(bad_id, "administrador", repo)

    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_nonexistent_ticket_raises_unified_not_found():
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(str(uuid.uuid4()), "administrador", repo)

    assert not isinstance(exc.value, TicketClosedError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_nonexistent_ticket_is_not_reported_as_closed():
    repo = _SpyTicketRepository()
    missing = str(uuid.uuid4())

    with pytest.raises(TicketNotFoundError):
        get_assignable_ticket(missing, "administrador", repo)

    assert repo.find_calls == [missing]


def test_not_found_message_is_the_same_unified_message_as_hu02():
    hu02_message = None
    try:
        get_my_ticket(str(uuid.uuid4()), "u-1", InMemoryTicketRepository())
    except TicketNotFoundError as exc:
        hu02_message = str(exc)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(
            str(uuid.uuid4()), "administrador", InMemoryTicketRepository()
        )

    assert hu02_message is not None
    assert str(exc.value) == hu02_message == TICKET_NOT_FOUND_MESSAGE


# --- RF-39.4: un ticket cerrado no admite asignacion ni reasignacion ---


def test_closed_ticket_raises_ticket_closed_error():
    repo = InMemoryTicketRepository()
    cerrado = _ticket(status=CLOSED_STATUS)
    repo.add(cerrado)

    with pytest.raises(TicketClosedError) as exc:
        get_assignable_ticket(cerrado.id, "administrador", repo)

    assert not isinstance(exc.value, TicketNotFoundError)
    assert str(exc.value) == TICKET_CLOSED_MESSAGE


def test_ticket_closed_message_is_fixed_by_the_contract():
    assert TICKET_CLOSED_MESSAGE == "ticket is closed"


@pytest.mark.parametrize(
    "status", [value for value in STATUSES if value != CLOSED_STATUS]
)
def test_only_the_closed_status_is_immutable(status):
    repo = InMemoryTicketRepository()
    ticket = _ticket(status=status)
    repo.add(ticket)

    assert get_assignable_ticket(ticket.id, "administrador", repo) is ticket


# --- RF-40: precedencia del permiso y de la resolucion ---


def test_permission_precedes_invalid_identifier_and_existence():
    repo = _SpyTicketRepository()

    for ticket_id in ("no-es-uuid", "123", str(uuid.uuid4())):
        with pytest.raises(TicketNotFoundError) as exc:
            get_assignable_ticket(ticket_id, "cliente", repo)

        assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE

    assert repo.find_calls == []


def test_client_role_never_reveals_a_closed_ticket():
    repo = InMemoryTicketRepository()
    cerrado = _ticket(status=CLOSED_STATUS)
    repo.add(cerrado)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(cerrado.id, "cliente", repo)

    # El permiso (404 uniforme) precede a la inmutabilidad del cerrado
    # (409): el cliente nunca recibe TicketClosedError (RF-40).
    assert not isinstance(exc.value, TicketClosedError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_technician_role_never_reveals_a_closed_ticket():
    repo = InMemoryTicketRepository()
    cerrado = _ticket(status=CLOSED_STATUS)
    repo.add(cerrado)

    with pytest.raises(TicketNotFoundError) as exc:
        get_assignable_ticket(cerrado.id, "tecnico", repo)

    assert not isinstance(exc.value, TicketClosedError)
    assert str(exc.value) == TICKET_NOT_FOUND_MESSAGE


def test_closed_check_comes_after_the_resolution():
    repo = _SpyTicketRepository()
    cerrado = _ticket(status=CLOSED_STATUS)
    repo.add(cerrado)

    with pytest.raises(TicketClosedError):
        get_assignable_ticket(cerrado.id, "administrador", repo)

    assert repo.find_calls == [cerrado.id]


# --- T8 / RF-40: la API real respeta 401 > 404 > 409 > 422 ---


def _precedence_bodies(technician_id, actor_id="otro-usuario"):
    """Cuerpos de la tabla de precedencia (validos e invalidos)."""
    return (
        {"assignee_id": technician_id},
        NO_BODY,
        MALFORMED_ASSIGNEE_BODY,
        {},
        {"assignee_id": None},
        {"assignee_id": 3},
        {"assignee_id": True},
        {"assignee_id": ["id"]},
        {"assignee_id": {"id": "x"}},
        {
            "assignee_id": technician_id,
            "actor_id": actor_id,
            "assigned_at": "2026-10-19T12:00:00+00:00",
        },
        {"assignee_id": "no-es-uuid"},
    )


def test_no_session_returns_401_before_identifier_body_and_ticket_state():
    client_api = TestClient(app)
    _client_session(target=client_api)
    open_ticket = _create_ticket(target=client_api, title="Abierto")

    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    closed_ticket = _create_ticket(target=client_api, title="Cerrado")
    technician = _provision("tecnico", email="tecnico@ejemplo.com")
    _close_ticket(closed_ticket["id"], target=admin_api)

    before_open = _assignee_state(open_ticket["id"])
    before_closed = _assignee_state(closed_ticket["id"])

    anonymous = TestClient(app)
    for ticket_id in (
        open_ticket["id"],
        closed_ticket["id"],
        str(uuid.uuid4()),
        "no-es-uuid",
    ):
        for body in _precedence_bodies(technician.id):
            response = _put_assignee(ticket_id, body, target=anonymous)
            assert response.status_code == 401
            assert response.status_code not in (400, 403, 404, 409, 422)
            assert set(response.json()) == {"detail"}
            assert _assignee_state(open_ticket["id"]) == before_open
            assert _assignee_state(closed_ticket["id"]) == before_closed
            assert get_assignment_log().count() == 0


@pytest.mark.parametrize("session_state", ["invalid", "revoked", "expired"])
def test_non_valid_session_returns_401_before_invalid_identifier_and_body(
    session_state,
):
    client_api = TestClient(app)
    _client_session(target=client_api)
    created = _create_ticket(target=client_api)
    token = client_api.cookies.get(SESSION_COOKIE_NAME)
    assert token

    if session_state == "invalid":
        client_api.cookies.set(SESSION_COOKIE_NAME, "token-invalido")
    elif session_state == "revoked":
        assert client_api.post("/api/auth/logout").status_code == 204
        client_api.cookies.set(SESSION_COOKIE_NAME, token)
    else:
        _expire_session(token)

    before = _assignee_state(created["id"])
    for body in (MALFORMED_ASSIGNEE_BODY, {"assignee_id": "no-es-uuid"}, NO_BODY):
        response = _put_assignee("no-es-uuid", body, target=client_api)
        assert response.status_code == 401
        assert response.status_code not in (400, 403, 404, 409, 422)
        assert set(response.json()) == {"detail"}
        assert _assignee_state(created["id"]) == before
        assert get_assignment_log().count() == 0


def test_client_and_technician_get_the_unified_404_with_any_body_and_case():
    other_client_api = TestClient(app)
    _client_session(
        target=other_client_api, email="otra@ejemplo.com", name="Otra Persona"
    )
    foreign = _create_ticket(target=other_client_api, title="Ajeno")

    client_api = TestClient(app)
    _client_session(target=client_api, email="cliente@ejemplo.com")
    own_open = _create_ticket(target=client_api, title="Propio abierto")
    own_closed = _create_ticket(target=client_api, title="Propio cerrado")

    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    technician = _provision("tecnico", email="tecnico@ejemplo.com")
    _close_ticket(own_closed["id"], target=admin_api)

    technician_api = TestClient(app)
    _login(technician.email, target=technician_api)

    # Mismo 404 unificado de HU-02 (se comprueba contra el detalle).
    unified = client_api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert unified.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}

    cases = (
        own_open["id"],
        foreign["id"],
        own_closed["id"],
        str(uuid.uuid4()),
        "no-es-uuid",
        "123",
    )
    before = {
        ticket_id: _assignee_state(ticket_id)
        for ticket_id in (own_open["id"], foreign["id"], own_closed["id"])
    }
    bodies = _precedence_bodies(technician.id)

    for target in (client_api, technician_api):
        for ticket_id in cases:
            for body in bodies:
                response = _put_assignee(ticket_id, body, target=target)
                assert response.status_code == 404
                assert response.status_code not in (400, 403, 409, 422)
                assert response.text == unified.text
                assert response.json() == {
                    "detail": TICKET_NOT_FOUND_MESSAGE
                }
                for stored_id, state in before.items():
                    assert _assignee_state(stored_id) == state
                assert get_assignment_log().count() == 0


def test_administrator_gets_404_for_nonexistent_or_invalid_ticket_with_any_body():
    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    technician = _provision("tecnico", email="tecnico@ejemplo.com")

    unified = admin_api.get(f"/api/tickets/{uuid.uuid4()}")
    assert unified.status_code == 404
    assert unified.json() == {"detail": TICKET_NOT_FOUND_MESSAGE}

    for ticket_id in (str(uuid.uuid4()), "no-es-uuid", "123"):
        for body in _precedence_bodies(technician.id):
            response = _put_assignee(ticket_id, body, target=admin_api)
            assert response.status_code == 404
            assert response.status_code not in (400, 403, 409, 422)
            assert response.text == unified.text
            assert get_assignment_log().count() == 0


def test_closed_ticket_returns_409_for_any_input_including_current_technician():
    client_api = TestClient(app)
    _client_session(target=client_api)
    created = _create_ticket(target=client_api)

    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    current = _provision("tecnico", name="Ana Torres", email="ana@ejemplo.com")
    other = _provision("tecnico", name="Luis Perez", email="luis@ejemplo.com")

    assigned = _put_assignee(
        created["id"], {"assignee_id": current.id}, target=admin_api
    )
    assert assigned.status_code == 200
    _close_ticket(created["id"], target=admin_api)

    records_before = get_assignment_log().count()
    assert records_before == 1
    before = _assignee_state(created["id"])

    bodies = _precedence_bodies(current.id)
    # Repeticion del tecnico vigente y reasignacion a otro tecnico valido.
    bodies = (
        {"assignee_id": current.id},
        {"assignee_id": other.id},
        *bodies,
    )
    for body in bodies:
        response = _put_assignee(created["id"], body, target=admin_api)
        assert response.status_code == 409
        assert response.status_code not in (400, 403, 404, 422)
        assert response.json() == {"detail": TICKET_CLOSED_MESSAGE}
        assert _assignee_state(created["id"]) == before
        assert get_assignment_log().count() == records_before


def test_open_ticket_with_administrator_session_returns_422_for_invalid_request():
    client_api = TestClient(app)
    _client_session(target=client_api)
    created = _create_ticket(target=client_api)

    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    technician = _provision("tecnico", email="tecnico@ejemplo.com")

    before = _assignee_state(created["id"])
    # Se excluye el cuerpo valido (index 0): con un ticket abierto y un
    # administrador seria un 200, no un rechazo.
    bodies = _precedence_bodies(technician.id)[1:]
    for body in bodies:
        response = _put_assignee(created["id"], body, target=admin_api)
        assert response.status_code == 422
        assert response.status_code not in (400, 403, 404, 409)
        assert set(response.json()) == {"detail"}
        assert _assignee_state(created["id"]) == before
        assert get_assignment_log().count() == 0


def test_assignment_rejections_never_use_400_or_403():
    client_api = TestClient(app)
    _client_session(target=client_api)
    open_ticket = _create_ticket(target=client_api, title="Abierto")
    to_close = _create_ticket(target=client_api, title="Para cerrar")

    admin_api = TestClient(app)
    _provision_and_login(target=admin_api)
    technician = _provision("tecnico", email="tecnico@ejemplo.com")
    _close_ticket(to_close["id"], target=admin_api)

    anonymous = TestClient(app)
    responses = (
        _put_assignee(
            open_ticket["id"],
            {"assignee_id": technician.id},
            target=anonymous,
        ),
        _put_assignee(
            open_ticket["id"],
            {"assignee_id": technician.id},
            target=client_api,
        ),
        _put_assignee(
            to_close["id"],
            {"assignee_id": technician.id},
            target=admin_api,
        ),
        _put_assignee(
            open_ticket["id"], MALFORMED_ASSIGNEE_BODY, target=admin_api
        ),
    )

    assert {response.status_code for response in responses} == {
        401,
        404,
        409,
        422,
    }
    for response in responses:
        assert response.status_code not in (400, 403)
