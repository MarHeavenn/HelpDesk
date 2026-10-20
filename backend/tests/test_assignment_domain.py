"""T1 — Dominio de asignacion: tecnico responsable, roles y registro (RF-34, RF-35.3, RF-37, RF-38).

Verifica:
- RF-34: `Ticket` gana el tecnico responsable (`assignee_id` y
  `assignee_name`) y nace sin asignacion; la creacion sigue naciendo
  `Abierto`, sin prioridad y sin asignacion.
- RF-35.3: el tecnico responsable se compone con identificador y nombre;
  sin asignacion ambos campos son `None` (el `null` del contrato),
  inequivocamente distinguible de cualquier tecnico registrado. El nombre
  es la proyeccion guardada en el ticket al asignar (D8): se lee del
  propio ticket, sin consultar `identity`.
- RF-37: `AssignmentRecord` representa una asignacion efectiva con el
  ticket, el tecnico anterior (vacio en la primera asignacion), el tecnico
  nuevo, el usuario que asigna y la fecha y hora del sistema; es de solo
  datos, independiente del estado del ticket y no sustituye al registro de
  modificaciones de HU-03.
- RF-38: `ASSIGNMENT_ROLES` fija el unico rol con permiso de asignacion
  (`administrador`), su aplicacion vive en la capa de aplicacion; los
  roles de gestion de HU-03 (`MANAGEMENT_ROLES`) no cambian.
"""

import dataclasses
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.modules.tickets.application.create_ticket import create_ticket
from app.modules.tickets.domain.entities import (
    ASSIGNMENT_ROLES,
    MANAGEMENT_ROLES,
    OPEN_STATUS,
    STATUSES,
    Ticket,
    AssignmentRecord,
)
from app.modules.tickets.infrastructure.ticket_repository import (
    get_ticket_repository,
)

NOW = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_repository():
    get_ticket_repository().clear()
    yield
    get_ticket_repository().clear()


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


# --- RF-34: el ticket nace sin tecnico responsable ---


def test_new_ticket_is_born_without_assignee():
    ticket = _ticket()

    assert ticket.assignee_id is None
    assert ticket.assignee_name is None


def test_new_ticket_can_omit_the_assignee_fields_explicitly():
    ticket = Ticket(
        id=str(uuid.uuid4()),
        title="Titulo",
        description="Descripcion",
        requester_id=str(uuid.uuid4()),
        created_at=NOW,
    )

    assert ticket.assignee_id is None
    assert ticket.assignee_name is None


def test_assignee_fields_are_declared_without_assignment_by_default():
    """RF-34: omitir el tecnico en la construccion deja el ticket sin asignar."""
    declared = {field.name: field for field in dataclasses.fields(Ticket)}

    for name in ("assignee_id", "assignee_name"):
        assert name in declared
        assert declared[name].default is None


def test_new_ticket_keeps_hu02_and_hu03_values():
    ticket = _ticket()

    assert ticket.status == OPEN_STATUS
    assert ticket.status in STATUSES
    assert ticket.priority is None
    assert ticket.created_at == NOW
    assert ticket.requester_id


def test_created_ticket_is_still_born_open_without_priority_and_without_assignee():
    """RF-34: la creacion no cambia; ningun ticket se asigna por crearse."""
    created = create_ticket(
        title="Impresora rota",
        description="No imprime",
        requester_id=str(uuid.uuid4()),
        tickets=get_ticket_repository(),
        now=NOW,
    )

    assert created.status == OPEN_STATUS
    assert created.priority is None
    assert created.assignee_id is None
    assert created.assignee_name is None


# --- RF-35.3: composicion del tecnico responsable ---


def test_ticket_keeps_the_assignee_identifier_and_name():
    ticket = _ticket(assignee_id="u-tech", assignee_name="Ana Torres")

    assert ticket.assignee_id == "u-tech"
    assert ticket.assignee_name == "Ana Torres"


def test_ticket_reassignment_replaces_both_assignee_values():
    ticket = _ticket(assignee_id="u-tech", assignee_name="Ana Torres")

    ticket.assignee_id = "u-tech-2"
    ticket.assignee_name = "Luis Perez"

    assert ticket.assignee_id == "u-tech-2"
    assert ticket.assignee_name == "Luis Perez"


def test_the_unassigned_technician_is_distinguishable_from_any_registered_technician():
    """RF-35.3: sin asignacion no hay identificador ni nombre; con
    asignacion ambos tienen valor (un tecnico registrado siempre tiene
    identificador y nombre)."""
    unassigned = _ticket()
    assigned = _ticket(assignee_id="u-tech", assignee_name="Ana Torres")

    assert unassigned.assignee_id is None
    assert unassigned.assignee_name is None
    assert assigned.assignee_id is not None
    assert assigned.assignee_name is not None


def test_ticket_assignee_is_independent_from_priority_and_status():
    ticket = _ticket(priority="Alta", status="En progreso")

    ticket.assignee_id = "u-tech"
    ticket.assignee_name = "Ana Torres"

    assert ticket.priority == "Alta"
    assert ticket.status == "En progreso"


def test_ticket_assignment_does_not_change_creation_data_or_requester():
    """RF-32 y RF-33: asignar no altera fecha, creador, titulo ni descripcion."""
    requester_id = str(uuid.uuid4())
    ticket = _ticket(requester_id=requester_id, title="Titulo", description="Descripcion")

    ticket.assignee_id = "u-tech"
    ticket.assignee_name = "Ana Torres"

    assert ticket.requester_id == requester_id
    assert ticket.created_at == NOW
    assert ticket.title == "Titulo"
    assert ticket.description == "Descripcion"


# --- RF-38: roles con permiso de asignacion ---


def test_assignment_roles_are_exactly_the_administrator():
    assert isinstance(ASSIGNMENT_ROLES, frozenset)
    assert ASSIGNMENT_ROLES == frozenset({"administrador"})
    assert "administrador" in ASSIGNMENT_ROLES


def test_assignment_roles_exclude_technicians_and_clients():
    assert "tecnico" not in ASSIGNMENT_ROLES
    assert "cliente" not in ASSIGNMENT_ROLES


def test_management_roles_of_hu03_do_not_change():
    assert MANAGEMENT_ROLES == frozenset({"tecnico", "administrador"})


# --- RF-37: entidad `AssignmentRecord` ---


def _record(**overrides) -> AssignmentRecord:
    values = {
        "ticket_id": "t-1",
        "previous_assignee_id": None,
        "new_assignee_id": "u-tech",
        "actor_id": "u-admin",
        "assigned_at": NOW,
    }
    values.update(overrides)
    return AssignmentRecord(**values)


def test_first_assignment_record_keeps_all_assignment_data():
    assigned_at = datetime(2026, 10, 19, 12, 30, 15, 123456, tzinfo=timezone.utc)
    record = _record(assigned_at=assigned_at)

    assert record.ticket_id == "t-1"
    assert record.previous_assignee_id is None
    assert record.new_assignee_id == "u-tech"
    assert record.actor_id == "u-admin"
    assert record.assigned_at == assigned_at


def test_reassignment_record_keeps_the_previous_technician():
    record = _record(previous_assignee_id="u-tech", new_assignee_id="u-tech-2")

    assert record.previous_assignee_id == "u-tech"
    assert record.new_assignee_id == "u-tech-2"


def test_assignment_record_declares_exactly_the_fields_of_the_plan():
    assert [field.name for field in dataclasses.fields(AssignmentRecord)] == [
        "ticket_id",
        "previous_assignee_id",
        "new_assignee_id",
        "actor_id",
        "assigned_at",
    ]


def test_assignment_record_is_data_only_and_independent_from_the_ticket_state():
    """RF-37: el registro no lleva estado, prioridad ni solicitante; es
    independiente del estado vigente del ticket y no sustituye al registro
    de modificaciones de HU-03."""
    record = _record()
    field_names = {field.name for field in dataclasses.fields(AssignmentRecord)}

    assert field_names.isdisjoint({"status", "priority", "requester_id", "title", "description"})
    assert not hasattr(record, "status")
    assert not hasattr(record, "priority")
