"""B.I.8: DTO y visibilidad SQL mediante la aplicación HTTP real."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.modules.tickets.infrastructure import ticket_repository
from app.modules.tickets.interface import router as ticket_router
from test_hu26_ticket_create_http import (
    DETAIL_KEYS, SUMMARY_KEYS, clients, password_hash, sandbox,
)


@pytest.fixture
def world(sandbox, password_hash):
    companies = [str(uuid4()), str(uuid4())]
    actors = {}
    with sandbox.connect() as conn:
        for index, company in enumerate(companies):
            conn.execute(
                "INSERT INTO companies(id,name,name_normalized) VALUES (%s,%s,%s)",
                (company, f"Consulta {index}", f"consulta {index}"),
            )
        for key, role, company in (
            ("client", "cliente", companies[0]),
            ("other", "cliente", companies[0]),
            ("client_b", "cliente", companies[1]),
            ("admin", "administrador", companies[0]),
            ("admin_b", "administrador", companies[1]),
            ("tech", "tecnico", companies[0]),
            ("tech_other", "tecnico", companies[0]),
            ("tech_b", "tecnico", companies[1]),
            ("supervisor", "supervisor", companies[0]),
            ("platform", "administrador", None),
            ("unassociated", "cliente", None),
            ("tech_no_company", "tecnico", None),
        ):
            actor = {
                "id": str(uuid4()), "name": f"Cuenta {key}",
                "email": f"{key}@ordinary.example.com", "company_id": company,
            }
            conn.execute(
                "INSERT INTO users(id,company_id,name,email,password_hash,role,"
                "invitation_status) VALUES (%s,%s,%s,%s,%s,%s,'accepted')",
                (actor["id"], company, actor["name"], actor["email"], password_hash, role),
            )
            actors[key] = actor
    return actors


@pytest.fixture
def rows(sandbox, world):
    created = datetime(2020, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
    data = {}
    for index, (key, requester, assignee, name, status, resolution, target) in enumerate((
        ("legacy", "client", "tech", None, "En progreso", None, None),
        ("known", "client", "tech", "Nombre conservado", "Cerrado", created + timedelta(hours=1), 17),
        ("other", "other", None, None, "Abierto", None, None),
        ("final", "client", "tech", None, "Resuelto", None, None),
        ("foreign", "client_b", "tech_b", None, "En progreso", None, None),
    )):
        row = {
            "id": str(uuid4()), "company_id": world[requester]["company_id"],
            "requester_id": world[requester]["id"],
            "assignee_id": world[assignee]["id"] if assignee else None,
            "assignee_name": name, "title": f"Título {key}", "description": f"Descripción {key}",
            "created_at": created + timedelta(minutes=index), "priority": "Alta",
            "status": status, "resolved_at": resolution, "resolved_target_minutes": target,
        }
        with sandbox.connect() as conn:
            conn.execute(
                "INSERT INTO tickets(id,company_id,requester_id,assignee_id,assignee_name,"
                "title,description,created_at,priority,status,resolved_at,resolved_target_minutes)"
                " VALUES (%(id)s,%(company_id)s,%(requester_id)s,%(assignee_id)s,%(assignee_name)s,"
                "%(title)s,%(description)s,%(created_at)s,%(priority)s,%(status)s,"
                "%(resolved_at)s,%(resolved_target_minutes)s)", row,
            )
        data[key] = row
    return data


def _stored(sandbox):
    with sandbox.connect() as conn:
        return conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()


def _observe_composition(monkeypatch):
    """Espías que delegan en los contratos reales; no sustituyen datos SQL."""
    calls = {"users": [], "sla": []}
    real_user, real_sla = ticket_router.get_user_summary, ticket_router.get_ticket_sla

    def user(user_id):
        calls["users"].append(user_id)
        return real_user(user_id)

    def sla(snapshot, now=None):
        calls["sla"].append(snapshot)
        return real_sla(snapshot, now=now)

    monkeypatch.setattr(ticket_router, "get_user_summary", user)
    monkeypatch.setattr(ticket_router, "get_ticket_sla", sla)
    return calls


def _assert_dto(body, row, world, *, detail=False):
    assert set(body) == (DETAIL_KEYS if detail else SUMMARY_KEYS)
    for key in ("id", "title", "priority", "status"):
        assert body[key] == row[key]
    assert datetime.fromisoformat(body["created_at"]) == row["created_at"]
    actor = next(actor for actor in world.values() if actor["id"] == row["requester_id"])
    assert body["requester"] == (
        {"id": actor["id"], "name": actor["name"], "email": actor["email"]}
        if detail else {"name": actor["name"]}
    )
    if row["assignee_id"] is None:
        assert body["assignee"] is None
    else:
        assignee = next(actor for actor in world.values() if actor["id"] == row["assignee_id"])
        assert body["assignee"] == {
            "id": row["assignee_id"], "name": row["assignee_name"] or assignee["name"],
        }
    if detail:
        assert body["description"] == row["description"]
        assert body["requester_id"] == row["requester_id"]
        assert (
            datetime.fromisoformat(body["resolved_at"]) if body["resolved_at"] else None
        ) == row["resolved_at"]
    assert set(body["sla"]) == {
        "target_minutes", "started_at", "due_at", "elapsed_minutes",
        "remaining_minutes", "status", "near_due", "breached",
    }


@pytest.mark.parametrize("actor,key,expected", [
    ("client", "legacy", 200), ("other", "legacy", 404),
    ("client", "other", 404), ("admin", "legacy", 200),
    ("tech", "legacy", 200), ("tech_other", "legacy", 200),
    ("supervisor", "legacy", 200), ("platform", "legacy", 404),
    ("unassociated", "legacy", 404), ("tech_no_company", "legacy", 404),
    ("admin_b", "legacy", 404), ("admin", "foreign", 404),
    ("client_b", "foreign", 200), ("admin_b", "foreign", 200),
    ("anonymous", "legacy", 401),
])
def test_detail_authorizes_before_composition_and_preserves_dto(
    sandbox, world, rows, clients, monkeypatch, actor, key, expected,
):
    client = clients(actor)
    before = _stored(sandbox)
    calls = _observe_composition(monkeypatch)
    response = client.get(f"/api/tickets/{rows[key]['id']}")
    assert response.status_code == expected
    if expected == 200:
        _assert_dto(response.json(), rows[key], world, detail=True)
        assert calls["sla"]
        assert set(calls["users"]) <= {rows[key]["requester_id"], rows[key]["assignee_id"]}
    else:
        if expected == 404:
            assert response.json() == {"detail": "ticket not found"}
        assert calls == {"users": [], "sla": []}
    assert _stored(sandbox) == before
    assert ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("actor,route,keys,expected", [
    ("client", "/api/tickets", {"legacy", "known", "final"}, 200),
    ("other", "/api/tickets", {"other"}, 200),
    ("client_b", "/api/tickets", {"foreign"}, 200),
    ("admin", "/api/tickets", {"legacy", "known", "other", "final"}, 200),
    ("tech_other", "/api/tickets", {"legacy", "known", "other", "final"}, 200),
    ("admin_b", "/api/tickets/all", {"foreign"}, 200),
    ("admin", "/api/tickets/all", {"legacy", "known", "other", "final"}, 200),
    ("tech_other", "/api/tickets/all", {"legacy", "known", "other", "final"}, 200),
    ("supervisor", "/api/tickets/all", {"legacy", "known", "other", "final"}, 200),
    ("client", "/api/tickets/all", set(), 404),
    ("tech", "/api/assignments/mine", {"legacy", "known", "final"}, 200),
    ("tech_other", "/api/assignments/mine", set(), 200),
    ("client", "/api/assignments/mine", set(), 200),
    ("admin", "/api/assignments/mine", set(), 200),
    ("admin", "/api/tickets/requiring-attention", {"legacy", "other"}, 200),
    ("tech_other", "/api/tickets/requiring-attention", {"legacy", "other"}, 200),
    ("admin_b", "/api/tickets/requiring-attention", {"foreign"}, 200),
    ("client", "/api/tickets/requiring-attention", set(), 404),
] + [
    (actor, route, set(), 401 if actor == "anonymous" else 404)
    for actor in ("anonymous", "platform", "unassociated", "tech_no_company")
    for route in ("/api/tickets", "/api/tickets/all",
                  "/api/assignments/mine", "/api/tickets/requiring-attention")
])
def test_lists_scope_before_composition_and_keep_eight_keys(
    sandbox, world, rows, clients, monkeypatch, actor, route, keys, expected,
):
    client = clients(actor)
    before = _stored(sandbox)
    calls = _observe_composition(monkeypatch)
    response = client.get(route)
    assert response.status_code == expected
    if expected == 200:
        by_id = {row["id"]: row for row in rows.values()}
        assert {body["id"] for body in response.json()} == {rows[key]["id"] for key in keys}
        for body in response.json():
            _assert_dto(body, by_id[body["id"]], world)
        allowed = {rows[key]["requester_id"] for key in keys} | {
            rows[key]["assignee_id"] for key in keys
        }
        assert set(calls["users"]) <= allowed
        assert len(calls["sla"]) == len(keys)
        if route != "/api/tickets/requiring-attention":
            dates = [body["created_at"] for body in response.json()]
            assert dates == sorted(dates, reverse=True)
    else:
        if expected == 404:
            assert response.json() == {"detail": "ticket not found"}
        assert calls == {"users": [], "sla": []}
    assert _stored(sandbox) == before
    assert ticket_repository.get_ticket_repository()._by_id == {}


@pytest.mark.parametrize("actor", ["admin", "client", "platform", "anonymous"])
@pytest.mark.parametrize("ticket_id", ["not-a-uuid", str(uuid4())])
def test_invalid_or_absent_ids_with_malformed_get_body_keep_401_404(
    rows, clients, monkeypatch, actor, ticket_id,
):
    client = clients(actor)
    calls = _observe_composition(monkeypatch)
    response = client.request(
        "GET", f"/api/tickets/{ticket_id}", content="{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == (401 if actor == "anonymous" else 404)
    if actor != "anonymous":
        assert response.json() == {"detail": "ticket not found"}
    assert calls == {"users": [], "sla": []}


@pytest.mark.parametrize("role,status", [
    ("tecnico", "deactivated"), ("cliente", "active"), ("administrador", "deactivated"),
])
def test_historical_assignment_uses_current_name_without_current_eligibility_filter(
    sandbox, world, rows, clients, monkeypatch, role, status,
):
    client = clients("admin")
    with sandbox.connect() as conn:
        conn.execute(
            "UPDATE users SET name='Nombre actual',role=%s,status=%s WHERE id=%s",
            (role, status, world["tech"]["id"]),
        )
    world["tech"]["name"] = "Nombre actual"
    before = _stored(sandbox)
    calls = _observe_composition(monkeypatch)
    monkeypatch.setattr(
        ticket_repository, "_tickets", ticket_repository.InMemoryTicketRepository()
    )
    for key in ("legacy", "known", "final"):
        calls["users"].clear()
        response = client.get(f"/api/tickets/{rows[key]['id']}")
        assert response.status_code == 200
        _assert_dto(response.json(), rows[key], world, detail=True)
        if key == "known":
            assert world["tech"]["id"] not in calls["users"]
    listing = client.get("/api/tickets/all")
    assert listing.status_code == 200
    by_id = {row["id"]: row for row in rows.values()}
    for body in listing.json():
        _assert_dto(body, by_id[body["id"]], world)
    assert _stored(sandbox) == before  # Ni nombre actual ni fechas se escriben como historia.
