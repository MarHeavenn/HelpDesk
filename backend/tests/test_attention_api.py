"""HU-10 T3 — visibilidad del listado de tickets que requieren atencion
(RF-62, RF-63, RF-66).

Verifica sobre `GET /api/tickets/requiring-attention`:

- RF-62: un usuario con rol de gestion (`tecnico` o `administrador`) recibe
  200 con la coleccion de resumenes, con independencia de quien los creo.
- RF-63: un cliente recibe 404 uniforme (`{"detail": "ticket not found"}`)
  sin datos; sin sesion valida la respuesta es 401 antes que cualquier
  resolucion (precedencia 401 > 404).
- RF-66: no se declaran parametros de consulta; los desconocidos
  (`?status=Abierto&page=2`) se ignoran en silencio (200).
- Colocacion de la ruta: al ser estatica y estar declarada antes de
  `GET /{ticket_id}`, pedir el listado devuelve 200 (no el 404 que daria
  `get_ticket_detail` si capturara "requiring-attention" como `ticket_id`).

Cada usuario usa su propio `TestClient` con sesion real (login), porque un
cliente HTTP guarda una unica cookie de sesion.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.session_store import (
    get_session_store,
)
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)
from app.modules.sla.infrastructure.sla_policy_repository import (
    get_sla_policy_repository,
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

PASSWORD = "Secreta123"
NOT_FOUND_BODY = {"detail": "ticket not found"}

# Composición exacta del resumen (RF-64) y del objeto sla (HU-05, RF-44).
SUMMARY_FIELDS = {
    "id",
    "title",
    "priority",
    "status",
    "assignee",
    "sla",
    "created_at",
}
SLA_FIELDS = {
    "target_minutes",
    "started_at",
    "due_at",
    "elapsed_minutes",
    "remaining_minutes",
    "status",
    "near_due",
    "breached",
}
# ISO 8601/RFC 3339 con offset UTC y microsegundos (RF-69).
ISO_8601_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$"
)


@pytest.fixture(autouse=True)
def clean_state():
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()
    yield
    get_user_repository().clear()
    get_session_store().clear()
    get_ticket_repository().clear()
    get_sla_policy_repository().reset()


def _provision(role: str, name: str, email: str) -> dict[str, str]:
    user = provision_user(
        name=name,
        email=email,
        password=PASSWORD,
        role=role,
        users=get_user_repository(),
    )
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def _register_client(name: str, email: str) -> dict[str, str]:
    response = TestClient(app).post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "role": "cliente",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(email: str) -> TestClient:
    """Cliente HTTP propio con la sesion real del usuario indicado."""
    own = TestClient(app)
    response = own.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return own


def _attention_ticket(
    requester_id: str,
    title: str = "Incidente urgente",
    hours_ago: int = 3,
    priority: str = "Crítica",
) -> Ticket:
    """Ticket que requiere atencion (Critica creada hace 3 h -> incumplido)."""
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=title,
        description="Descripcion del incidente",
        requester_id=requester_id,
        created_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        priority=priority,
    )
    get_ticket_repository().add(ticket)
    return ticket


def _insert_ticket(
    requester_id: str,
    *,
    title: str = "Ticket de prueba",
    minutes_ago: int = 0,
    priority: str | None = None,
    status: str = "Abierto",
    resolved_at: datetime | None = None,
) -> Ticket:
    """Inserta un ticket directamente en el repositorio con datos controlados.

    Permite simular transiciones de prioridad y estado (y el paso del reloj
    envejeciendo `created_at`) sin depender del reloj real mas alla de un
    margen de minutos/horas, como recomienda el plan (RF-67, RF-68).
    """
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title=title,
        description="Descripcion",
        requester_id=requester_id,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        priority=priority,
        status=status,
        resolved_at=resolved_at,
    )
    get_ticket_repository().add(ticket)
    return ticket


def _attention_ids(api: TestClient) -> list[str]:
    """Identificadores del listado de atencion, en el orden devuelto."""
    response = api.get("/api/tickets/requiring-attention")
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def _repo_state() -> tuple:
    """Instantanea inmutable del repositorio y de los registros (RF-62).

    Captura todos los tickets (campos completos) y el numero de registros
    de modificaciones y de asignaciones, para comprobar que una consulta
    de solo lectura no muta nada.
    """
    tickets = tuple(
        sorted(
            (
                (
                    ticket.id,
                    ticket.title,
                    ticket.description,
                    ticket.requester_id,
                    ticket.created_at,
                    ticket.priority,
                    ticket.status,
                    ticket.assignee_id,
                    ticket.assignee_name,
                    ticket.resolved_at,
                )
                for ticket in get_ticket_repository().list_all()
            ),
            key=lambda row: row[0],
        )
    )
    return (
        tickets,
        get_ticket_modification_log().count(),
        get_assignment_log().count(),
    )


# --- RF-62: roles de gestion reciben 200 ---


def test_technician_gets_200_with_the_attention_collection():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_administrator_gets_200_with_the_attention_collection():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    admin = _provision("administrador", "Admin Uno", "admin@ejemplo.com")
    api = _login(admin["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


def test_management_role_gets_empty_collection_when_nothing_requires_attention():
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    assert response.json() == []


# --- RF-63: cliente 404 uniforme, sin sesion 401 ---


def test_client_gets_uniform_404_without_any_ticket_data():
    requester = _register_client("Dueno Uno", "dueno@ejemplo.com")
    _attention_ticket(requester["id"], title="Secreto del dueno")
    intruder = _register_client("Otro Dos", "otro@ejemplo.com")
    api = _login(intruder["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    # Ningun dato del ticket ajeno se filtra en el error.
    raw = response.text
    assert "Secreto del dueno" not in raw
    assert "Descripcion del incidente" not in raw
    assert requester["email"] not in raw


def test_missing_session_returns_401_before_any_resolution():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    anonymous = TestClient(app)

    response = anonymous.get("/api/tickets/requiring-attention")

    assert response.status_code == 401
    assert response.json() != NOT_FOUND_BODY


# --- Colocacion de la ruta: no colisiona con /{ticket_id} ---


def test_list_route_does_not_collide_with_ticket_id_route():
    # Con tickets que requieren atencion, pedir la ruta estatica devuelve
    # 200 (un listado), no el 404 que daria `get_ticket_detail` si
    # "requiring-attention" se capturase como un `ticket_id` no-UUID.
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    assert response.json() != NOT_FOUND_BODY


# --- RF-66: parametros de consulta desconocidos se ignoran ---


def test_unknown_query_parameters_are_ignored():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get(
        "/api/tickets/requiring-attention", params={"status": "Abierto", "page": 2}
    )

    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


# --- T4: contrato del listado (RF-64, RF-65, RF-69) ---


def test_each_element_has_exactly_the_summary_composition():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    item = items[0]
    assert set(item) == SUMMARY_FIELDS
    # Sin datos personales ni internos (RF-64): ni requester, ni descripcion
    # ni fecha de resolucion (identica a HU-04/HU-06).
    assert "requester" not in item
    assert "description" not in item
    assert "resolved_at" not in item


def test_sla_is_the_hu05_object_with_eight_fields_and_never_null():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 1
    sla = items[0]["sla"]
    # Todo elemento tiene prioridad (RF-61): sla nunca es null (RF-64).
    assert sla is not None
    assert set(sla) == SLA_FIELDS
    assert sla["target_minutes"] > 0
    assert sla["status"] in {"en_tiempo", "en_riesgo", "cumplido", "incumplido"}


def test_breached_come_first_then_near_due_by_due_at_ascending():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    # Dos incumplidos (vencidos) y un proximo a vencer, con vencimientos
    # bien separados en horas para no depender de los limites exactos.
    alta = _attention_ticket(
        requester["id"], title="Alta vencida", hours_ago=6, priority="Alta"
    )
    critica = _attention_ticket(
        requester["id"], title="Critica vencida", hours_ago=3, priority="Crítica"
    )
    baja = _attention_ticket(
        requester["id"], title="Baja en riesgo", hours_ago=23, priority="Baja"
    )
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    items = response.json()
    assert len(items) == 3
    # due_at ascendente (RF-65): Alta (vence 2 h antes), Critica (1 h antes)
    # y Baja (vence dentro de ~1 h).
    assert [item["id"] for item in items] == [alta.id, critica.id, baja.id]
    due_ats = [item["sla"]["due_at"] for item in items]
    assert due_ats == sorted(due_ats)
    # Los incumplidos primero; los proximos a vencer despues (RF-65).
    assert [item["sla"]["breached"] for item in items] == [True, True, False]
    assert [item["sla"]["near_due"] for item in items] == [False, False, True]


def test_dates_are_iso8601_rfc3339_utc_with_microseconds():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    # created_at con microsegundos fijos para que la serializacion los
    # conserve de forma determinista (RF-69).
    created_at = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(
        microsecond=123456
    )
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Incidente con microsegundos",
        description="Descripcion",
        requester_id=requester["id"],
        created_at=created_at,
        priority="Crítica",
    )
    get_ticket_repository().add(ticket)
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    response = api.get("/api/tickets/requiring-attention")

    assert response.status_code == 200, response.text
    item = response.json()[0]
    for value in (
        item["created_at"],
        item["sla"]["started_at"],
        item["sla"]["due_at"],
    ):
        assert ISO_8601_UTC_RE.match(value), value
        parsed = datetime.fromisoformat(value)
        assert parsed.utcoffset() == timedelta(0)
        assert parsed.microsecond != 0
    # started_at coincide con created_at y due_at conserva los microsegundos.
    assert item["sla"]["started_at"] == item["created_at"]
    assert item["sla"]["due_at"].endswith(".123456+00:00")


def test_listing_is_read_only_and_does_not_mutate_tickets_or_logs():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    _attention_ticket(requester["id"])
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    before = _repo_state()
    response = api.get("/api/tickets/requiring-attention")
    assert response.status_code == 200, response.text
    after = _repo_state()

    assert after == before


# --- T5: comportamiento (RF-67, RF-68) ---


def test_no_sla_threshold_configuration_endpoint_exists():
    # RF-67: el umbral de alerta es el 20 % de HU-05, interno y fijo; no hay
    # operacion publica para leerlo ni modificarlo. HU-14 añade
    # /api/sla/policies (configuracion de SLA): la ruta existe, pero para un
    # tecnico responde el 404 uniforme sin revelar datos; /api/sla y
    # /api/sla/threshold no existen.
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    for method in ("get", "put"):
        for path in ("/api/sla", "/api/sla/threshold"):
            response = getattr(api, method)(path)
            assert response.status_code == 404, (method, path, response.text)

    for method in ("get", "put"):
        response = getattr(api, method)("/api/sla/policies")
        assert response.status_code == 404, (method, response.text)
        assert response.json() == {"detail": "not found"}


def test_a_shorter_target_makes_a_ticket_enter_attention():
    # HU-14 RF-76: el listado se deriva de la configuracion vigente en cada
    # consulta, sin recalcular historial ni mutar el ticket.
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    ticket = _insert_ticket(
        requester["id"], title="Entra al acortar", minutes_ago=45, priority="Crítica"
    )
    before = (ticket.created_at, ticket.priority, ticket.status, ticket.resolved_at)

    assert ticket.id not in _attention_ids(api)

    get_sla_policy_repository().replace(
        {"Crítica": 30, "Alta": 240, "Media": 720, "Baja": 1440}
    )

    response = api.get("/api/tickets/requiring-attention")
    assert response.status_code == 200, response.text
    item = next(
        (entry for entry in response.json() if entry["id"] == ticket.id), None
    )
    assert item is not None
    assert item["sla"]["target_minutes"] == 30
    assert item["sla"]["remaining_minutes"] == 0
    assert item["sla"]["breached"] is True
    assert (ticket.created_at, ticket.priority, ticket.status, ticket.resolved_at) == before


def test_a_longer_target_makes_a_ticket_leave_attention():
    # HU-14 RF-76: al ampliar el objetivo el vencimiento se aleja y el
    # ticket sale del listado; la configuracion no toca su estado.
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    ticket = _attention_ticket(
        requester["id"], title="Sale al ampliar", hours_ago=23, priority="Baja"
    )
    before = (ticket.created_at, ticket.priority, ticket.status, ticket.resolved_at)

    assert ticket.id in _attention_ids(api)

    get_sla_policy_repository().replace(
        {"Crítica": 120, "Alta": 240, "Media": 720, "Baja": 2880}
    )

    assert ticket.id not in _attention_ids(api)
    assert (ticket.created_at, ticket.priority, ticket.status, ticket.resolved_at) == before


def test_the_attention_listing_re_derives_without_recalculating_history():
    # HU-14 RF-76: volver a la semilla devuelve el estado derivado original,
    # sin historial ni estado persistido en el ticket.
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    ticket = _attention_ticket(
        requester["id"], title="Vuelve con la semilla", hours_ago=23, priority="Baja"
    )

    get_sla_policy_repository().replace(
        {"Crítica": 120, "Alta": 240, "Media": 720, "Baja": 2880}
    )
    assert ticket.id not in _attention_ids(api)

    get_sla_policy_repository().reset()

    assert ticket.id in _attention_ids(api)


def test_listing_reuses_sla_contract_without_reimplementing_calculation():
    # RF-67: el caso de uso importa el contrato `get_ticket_sla` y no el
    # calculo, las politicas ni el umbral de HU-05 (sin logica de SLA nueva).
    import app.modules.tickets.application.list_attention_tickets as module

    assert hasattr(module, "get_ticket_sla")
    for forbidden in (
        "calculate_sla",
        "calculate_ticket_sla",
        "target_minutes_for",
        "RISK_THRESHOLD_RATIO",
    ):
        assert not hasattr(module, forbidden), forbidden


def test_ticket_enters_when_priority_is_set_leaving_it_at_risk():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    # Creado hace 100 min sin prioridad: fuera del listado (sla nulo, RF-61).
    ticket = _insert_ticket(
        requester["id"], title="Sin prioridad todavia", minutes_ago=100
    )

    assert ticket.id not in _attention_ids(api)

    # Al fijar Critica (120 min) nace en_riesgo: quedan 20 min <= 20 % (24).
    ticket.priority = "Crítica"

    assert ticket.id in _attention_ids(api)


def test_ticket_leaves_when_resolved_before_due():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    # Baja (1440 min) creada hace 23 h: en_riesgo (queda ~1 h <= 288 min).
    ticket = _attention_ticket(
        requester["id"], title="Baja en riesgo", hours_ago=23, priority="Baja"
    )

    assert ticket.id in _attention_ids(api)

    # Se resuelve antes del vencimiento (aun falta ~1 h): sale del listado.
    ticket.status = "Resuelto"
    ticket.resolved_at = datetime.now(timezone.utc)

    assert ticket.id not in _attention_ids(api)


def test_ticket_reappears_when_reopened():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    ticket = _attention_ticket(
        requester["id"], title="Baja en riesgo", hours_ago=23, priority="Baja"
    )

    assert ticket.id in _attention_ids(api)

    # Resuelto -> sale.
    ticket.status = "Resuelto"
    ticket.resolved_at = datetime.now(timezone.utc)
    assert ticket.id not in _attention_ids(api)

    # Reapertura (Resuelto -> Abierto, descarta resolved_at): vuelve a aparecer.
    ticket.status = "Abierto"
    ticket.resolved_at = None

    assert ticket.id in _attention_ids(api)


def test_ticket_appears_and_disappears_when_priority_changes():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])

    # (a) De en_tiempo a en_riesgo: Baja (1440) creada hace 100 min esta en
    #     tiempo; al pasar a Critica (120) quedan 20 min -> en_riesgo.
    out_to_in = _insert_ticket(
        requester["id"], title="Pasa a critica", minutes_ago=100, priority="Baja"
    )
    assert out_to_in.id not in _attention_ids(api)
    out_to_in.priority = "Crítica"
    assert out_to_in.id in _attention_ids(api)

    # (b) De incumplido a en_tiempo: Critica (120) creada hace 150 min esta
    #     incumplida; al pasar a Baja (1440) vuelve a estar en tiempo.
    in_to_out = _insert_ticket(
        requester["id"],
        title="Pasa a baja",
        minutes_ago=150,
        priority="Crítica",
    )
    assert in_to_out.id in _attention_ids(api)
    in_to_out.priority = "Baja"
    assert in_to_out.id not in _attention_ids(api)


def test_state_is_derived_from_the_clock_not_a_persisted_field():
    requester = _register_client("Cliente Uno", "cliente@ejemplo.com")
    technician = _provision("tecnico", "Tecnico Uno", "tec@ejemplo.com")
    api = _login(technician["email"])
    # Alta (240 min) creada ahora: en_tiempo, fuera del listado.
    ticket = _insert_ticket(
        requester["id"], title="Derivada en vivo", minutes_ago=0, priority="Alta"
    )

    assert ticket.id not in _attention_ids(api)

    # Sin escribir ningun campo de alerta (no existe), solo el paso del reloj
    # —modelado envejeciendo created_at (convencion de HU-05/HU-06 para no
    # dormir)— lo hace entrar: Alta creada hace 5 h -> incumplido (RF-68).
    ticket.created_at = datetime.now(timezone.utc) - timedelta(hours=5)

    assert ticket.id in _attention_ids(api)

    # No hay estado persistido: la entidad no guarda el resultado del calculo
    # (ni sla, ni indicadores); todo se deriva en cada consulta (RF-67, RF-68).
    assert not hasattr(ticket, "sla")
    assert not hasattr(ticket, "near_due")
    assert not hasattr(ticket, "breached")
