"""T6 — 404 unificado y precedencia 401 sobre 404. (RF-17, RF-18)

Mapa RF -> test:
- RF-17: ticket inexistente, identificador con formato invalido y ticket
  de otro usuario devuelven **404 identico** (mismo cuerpo de error) y un
  formato invalido nunca produce 422:
  `test_nonexistent_ticket_returns_404`,
  `test_invalid_identifier_format_returns_404_not_422`,
  `test_other_users_ticket_returns_404_without_leaking_data`,
  `test_the_three_404_cases_return_the_same_error_body`.
- RF-17 (nivel de caso de uso, incluye la cadena vacia):
  `test_use_case_rejects_invalid_identifier_format`,
  `test_use_case_treats_other_users_ticket_as_not_found`.
- RF-18 (precedencia 401 > 404): sin sesion valida esos mismos casos
  devuelven 401 y nunca 404 ni 422:
  `test_all_cases_without_session_return_401`,
  `test_invalid_session_token_takes_precedence_over_404`.
- RF-18 (sesion expirada): con la cookie presente pero la sesion caducada,
  los endpoints de tickets devuelven 401:
  `test_expired_session_returns_401_on_ticket_endpoints`.

El aislamiento con dos sesiones simultaneas es de T7 y no se cubre aqui:
el caso "ticket de otro usuario" se arma insertando el ticket por el
contrato publico del repositorio.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.infrastructure.session_store import get_session_store
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.identity.interface.router import SESSION_COOKIE_NAME
from app.modules.tickets.application.get_ticket import (
    TicketNotFoundError,
    get_my_ticket,
)
from app.modules.tickets.domain.entities import Ticket
from app.modules.tickets.infrastructure.ticket_repository import (
    InMemoryTicketRepository,
    get_ticket_repository,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    client.cookies.clear()


def _register_and_login(email="ana@ejemplo.com"):
    registered = client.post(
        "/api/auth/register",
        json={
            "name": "Ana Perez",
            "email": email,
            "password": "Secreta123",
            "role": "cliente",
        },
    )
    assert registered.status_code == 201
    logged = client.post(
        "/api/auth/login", json={"email": email, "password": "Secreta123"}
    )
    assert logged.status_code == 200
    return registered.json()


def _foreign_ticket():
    """Ticket de otro usuario, insertado por el contrato publico."""
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Ticket ajeno",
        description="contenido secreto ajeno",
        requester_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
    )
    get_ticket_repository().add(ticket)
    return ticket


def _expire_session(token: str) -> None:
    """Expira la sesion con el mecanismo de HU-01 (`test_auth_me.py`)."""
    session = get_session_store().find_by_token(token)
    assert session is not None
    assert session.revoked_at is None
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)


# --- RF-17: los tres casos devuelven 404 ---


def test_nonexistent_ticket_returns_404():
    _register_and_login()

    response = client.get(f"/api/tickets/{uuid.uuid4()}")

    assert response.status_code == 404
    assert set(response.json()) == {"detail"}


@pytest.mark.parametrize("bad_id", ["no-es-uuid", "123", "abc-123"])
def test_invalid_identifier_format_returns_404_not_422(bad_id):
    _register_and_login()

    response = client.get(f"/api/tickets/{bad_id}")

    assert response.status_code == 404
    assert response.status_code != 422
    assert set(response.json()) == {"detail"}


def test_other_users_ticket_returns_404_without_leaking_data():
    _register_and_login()
    ajeno = _foreign_ticket()

    response = client.get(f"/api/tickets/{ajeno.id}")

    assert response.status_code == 404
    assert set(response.json()) == {"detail"}
    # No revela ningun dato del ticket ajeno.
    assert "contenido secreto ajeno" not in response.text
    assert "Ticket ajeno" not in response.text


def test_the_three_404_cases_return_the_same_error_body():
    _register_and_login()
    ajeno = _foreign_ticket()

    bodies = [
        client.get(f"/api/tickets/{uuid.uuid4()}").json(),
        client.get("/api/tickets/no-es-uuid").json(),
        client.get(f"/api/tickets/{ajeno.id}").json(),
    ]

    assert bodies[0] == bodies[1] == bodies[2]
    assert set(bodies[0]) == {"detail"}


# --- RF-17: caso de uso (incluye la cadena vacia) ---


@pytest.mark.parametrize("bad_id", ["", "no-es-uuid", "123", None])
def test_use_case_rejects_invalid_identifier_format(bad_id):
    repo = InMemoryTicketRepository()

    with pytest.raises(TicketNotFoundError):
        get_my_ticket(ticket_id=bad_id, requester_id="u-1", tickets=repo)


def test_use_case_treats_other_users_ticket_as_not_found():
    repo = InMemoryTicketRepository()
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id="u-1",
        created_at=datetime.now(timezone.utc),
    )
    repo.add(ticket)

    assert get_my_ticket(ticket.id, "u-1", repo) is ticket
    with pytest.raises(TicketNotFoundError):
        get_my_ticket(ticket.id, "u-2", repo)


# --- RF-18: sin sesion valida -> 401 (nunca 404 ni 422) ---


def test_all_cases_without_session_return_401():
    ajeno = _foreign_ticket()

    for ticket_id in (str(uuid.uuid4()), "no-es-uuid", "123", ajeno.id):
        response = client.get(f"/api/tickets/{ticket_id}")
        assert response.status_code == 401
        assert response.status_code not in (404, 422)
        assert set(response.json()) == {"detail"}


def test_invalid_session_token_takes_precedence_over_404():
    # Sin iniciar sesion: la unica cookie es la invalida.
    _foreign_ticket()
    client.cookies.set("session", "token-invalido")

    response = client.get("/api/tickets/no-es-uuid")

    assert response.status_code == 401
    assert set(response.json()) == {"detail"}


def test_expired_session_returns_401_on_ticket_endpoints():
    _register_and_login()
    created = client.post(
        "/api/tickets", json={"title": "Titulo", "description": "Descripcion"}
    ).json()
    token = client.cookies.get(SESSION_COOKIE_NAME)
    assert token
    # Con la sesion aun valida los endpoints responden (no es un falso 401).
    assert client.get("/api/tickets").status_code == 200

    _expire_session(token)

    for response in (
        client.get("/api/tickets"),
        client.get(f"/api/tickets/{created['id']}"),
        client.post("/api/tickets", json={"title": "T", "description": "D"}),
    ):
        assert response.status_code == 401
        assert response.status_code not in (404, 422)
        assert set(response.json()) == {"detail"}
