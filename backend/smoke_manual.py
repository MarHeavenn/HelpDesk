"""Smoke manual automatizado de las vistas de tickets (HU-22 y HU-23).

Arranca la aplicacion real (uvicorn en un hilo), siembra un administrador y
dos tecnicos, y recorre los flujos de las tres cuentas contra la API real
con cookies de sesion reales:

- Cliente: se registra, crea un ticket, lo consulta y comprueba que no
  puede ver el listado global ni modificar el ticket.
- Tecnico: ve el listado global, fija prioridad, cambia estado y comenta.
- Administrador: asigna y reasigna, cambia prioridad y estado, cierra,
  comprueba los 409 del ticket cerrado y lo reabre.

No usa mocks ni TestClient. Los datos viven en memoria y desaparecen al
terminar el proceso.

Uso (desde backend/):

    ..\\.venv\\Scripts\\python.exe smoke_manual.py

Variables opcionales: SMOKE_HOST y SMOKE_PORT (por defecto, 127.0.0.1 y un
puerto libre). Sale con codigo 0 si todas las comprobaciones pasan.
"""

import json
import os
import socket
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import uvicorn

from app.main import app
from app.modules.identity.application.provision import provision_user
from app.modules.identity.infrastructure.user_repository import (
    get_user_repository,
)

PASSWORD = "Demo12345"

ADMIN = {"name": "Ana Admin", "email": "admin@smoke.dev", "role": "administrador"}
TECH_ONE = {
    "name": "Tomas Tecnico",
    "email": "tecnico1@smoke.dev",
    "role": "tecnico",
}
TECH_TWO = {
    "name": "Teresa Tecnica",
    "email": "tecnico2@smoke.dev",
    "role": "tecnico",
}
CLIENT = {"name": "Carla Cliente", "email": "cliente@smoke.dev"}
OTHER_CLIENT = {"name": "Otto Otro", "email": "otro@smoke.dev"}


class SmokeError(AssertionError):
    """Una comprobacion del smoke fallo."""


def _parse(raw: bytes, content_type: str | None):
    """Decodifica el cuerpo de la respuesta (JSON cuando corresponde)."""
    if not raw:
        return None
    text = raw.decode("utf-8", "replace")
    if content_type and "application/json" in content_type:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


class Session:
    """Sesion HTTP de un usuario, con manejo manual de cookies."""

    def __init__(self, label: str, base_url: str) -> None:
        self.label = label
        self.base_url = base_url
        self.cookies: dict[str, str] = {}

    def request(self, method: str, path: str, body=None):
        """Devuelve `(status, data)` sin lanzar por codigos 4xx/5xx."""
        headers = {}
        if self.cookies:
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in self.cookies.items()
            )
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=15) as response:
                self._store_cookies(response.headers.get_all("Set-Cookie") or [])
                return response.status, _parse(
                    response.read(), response.headers.get("Content-Type")
                )
        except HTTPError as exc:
            self._store_cookies(exc.headers.get_all("Set-Cookie") or [])
            return exc.code, _parse(
                exc.read(), exc.headers.get("Content-Type")
            )

    def _store_cookies(self, headers: list[str]) -> None:
        for header in headers:
            pair = header.split(";", 1)[0].strip()
            if "=" not in pair:
                continue
            name, value = pair.split("=", 1)
            expired = "max-age=0" in header.lower()
            if not value or expired:
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = value


class Smoke:
    """Contador de comprobaciones con salida legible en consola."""

    def __init__(self) -> None:
        self.passed = 0

    def check(self, name: str, condition: object, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  OK   {name}")
            return
        message = f"FALLO {name}"
        if detail:
            message += f": {detail}"
        raise SmokeError(message)

    def status(self, name: str, result, expected: int):
        status, data = result
        self.check(
            f"{name} -> {expected}",
            status == expected,
            f"recibido {status}: {data}",
        )
        return data


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _seed_users() -> None:
    users = get_user_repository()
    for user in (ADMIN, TECH_ONE, TECH_TWO):
        provision_user(
            name=user["name"],
            email=user["email"],
            password=PASSWORD,
            role=user["role"],
            users=users,
        )


def _start_server(host: str, port: int) -> uvicorn.Server:
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def _wait_health(base_url: str, server: uvicorn.Server) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urlopen(base_url + "/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            time.sleep(0.1)
    raise SmokeError("la API no respondio en /health")


def _login(smoke: Smoke, session: Session, label: str, email: str) -> dict:
    data = smoke.status(
        f"{label} inicia sesion",
        session.request(
            "POST", "/api/auth/login", {"email": email, "password": PASSWORD}
        ),
        200,
    )
    smoke.check(
        f"{label} recibe su rol",
        data.get("role") in {"administrador", "tecnico", "cliente"},
        str(data),
    )
    smoke.check(f"{label} recibe cookie de sesion", bool(session.cookies))
    me = smoke.status(
        f"{label} consulta /api/auth/me",
        session.request("GET", "/api/auth/me"),
        200,
    )
    smoke.check(
        f"{label} mantiene la identidad",
        me.get("email") == email and me.get("role") == data.get("role"),
        str(me),
    )
    return me


def run(base_url: str, smoke: Smoke) -> None:
    """Recorre el flujo completo de las tres cuentas."""
    anonymous = Session("anonimo", base_url)
    smoke.status(
        "Sin sesion, el listado global rechaza",
        anonymous.request("GET", "/api/tickets/all"),
        401,
    )

    client = Session("cliente", base_url)
    other = Session("otro cliente", base_url)

    print("\n[Cliente]")
    registered = smoke.status(
        "Cliente se registra",
        client.request(
            "POST",
            "/api/auth/register",
            {
                "name": CLIENT["name"],
                "email": CLIENT["email"],
                "password": PASSWORD,
                "role": "cliente",
            },
        ),
        201,
    )
    smoke.check(
        "El registro asigna el rol cliente",
        registered.get("role") == "cliente",
        str(registered),
    )
    smoke.status(
        "Segundo cliente se registra",
        other.request(
            "POST",
            "/api/auth/register",
            {
                "name": OTHER_CLIENT["name"],
                "email": OTHER_CLIENT["email"],
                "password": PASSWORD,
                "role": "cliente",
            },
        ),
        201,
    )
    client_user = _login(smoke, client, "Cliente", CLIENT["email"])

    created = smoke.status(
        "Cliente crea un ticket",
        client.request(
            "POST",
            "/api/tickets",
            {
                "title": "No puedo entrar al portal",
                "description": "Desde ayer no puedo entrar al portal.",
            },
        ),
        201,
    )
    ticket_id = created.get("id")
    smoke.check("El ticket tiene identificador", bool(ticket_id), str(created))
    smoke.check(
        "Nace Abierto, sin prioridad y sin SLA",
        created.get("status") == "Abierto"
        and created.get("priority") is None
        and created.get("sla") is None,
        str(created),
    )
    smoke.check(
        "El solicitante es el cliente autenticado",
        created.get("requester_id") == client_user.get("id"),
        str(created),
    )

    mine = smoke.status(
        "Cliente consulta sus tickets",
        client.request("GET", "/api/tickets"),
        200,
    )
    smoke.check(
        "El listado propio contiene su ticket",
        [ticket["id"] for ticket in mine] == [ticket_id],
        str(mine),
    )
    smoke.check(
        "El resumen expone exactamente los campos acordados",
        set(mine[0]) == {
            "id",
            "title",
            "priority",
            "status",
            "assignee",
            "sla",
            "created_at",
        },
        str(mine[0]),
    )
    smoke.status(
        "Cliente no accede al listado global",
        client.request("GET", "/api/tickets/all"),
        404,
    )
    detail = smoke.status(
        "Cliente consulta el detalle de su ticket",
        client.request("GET", f"/api/tickets/{ticket_id}"),
        200,
    )
    smoke.check(
        "El detalle trae descripcion y solicitante",
        detail.get("description") == "Desde ayer no puedo entrar al portal."
        and detail.get("requester", {}).get("email") == CLIENT["email"],
        str(detail),
    )
    smoke.status(
        "Cliente no cambia la prioridad",
        client.request(
            "PUT", f"/api/tickets/{ticket_id}/priority", {"priority": "Alta"}
        ),
        404,
    )
    smoke.status(
        "Cliente no cambia el estado",
        client.request(
            "PUT",
            f"/api/tickets/{ticket_id}/status",
            {"status": "En progreso"},
        ),
        404,
    )
    smoke.status(
        "Cliente no asigna tecnico",
        client.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": "u-tech"},
        ),
        404,
    )
    smoke.status(
        "Cliente no comenta",
        client.request(
            "POST", f"/api/tickets/{ticket_id}/comments", {"body": "Hola"}
        ),
        404,
    )

    _login(smoke, other, "Otro cliente", OTHER_CLIENT["email"])
    smoke.status(
        "Otro cliente no ve un ticket ajeno",
        other.request("GET", f"/api/tickets/{ticket_id}"),
        404,
    )
    other_list = smoke.status(
        "Otro cliente consulta sus tickets",
        other.request("GET", "/api/tickets"),
        200,
    )
    smoke.check("El cliente ajeno no tiene tickets", other_list == [], str(other_list))

    tech = Session("tecnico", base_url)
    print("\n[Tecnico]")
    tech_user = _login(smoke, tech, "Tecnico", TECH_ONE["email"])

    all_tickets = smoke.status(
        "Tecnico consulta el listado global",
        tech.request("GET", "/api/tickets/all"),
        200,
    )
    smoke.check(
        "El listado global contiene el ticket del cliente",
        [ticket["id"] for ticket in all_tickets] == [ticket_id],
        str(all_tickets),
    )
    smoke.check(
        "El listado global no incluye la descripcion",
        "description" not in all_tickets[0],
        str(all_tickets[0]),
    )
    assigned = smoke.status(
        "Tecnico consulta sus asignados (antes de asignar)",
        tech.request("GET", "/api/assignments/mine"),
        200,
    )
    smoke.check("Todavia no tiene tickets asignados", assigned == [], str(assigned))
    smoke.status(
        "Tecnico consulta el detalle",
        tech.request("GET", f"/api/tickets/{ticket_id}"),
        200,
    )

    prioritized = smoke.status(
        "Tecnico fija la prioridad Alta",
        tech.request(
            "PUT", f"/api/tickets/{ticket_id}/priority", {"priority": "Alta"}
        ),
        200,
    )
    smoke.check(
        "El SLA se calcula con el objetivo de 240 minutos",
        prioritized.get("priority") == "Alta"
        and prioritized.get("sla", {}).get("target_minutes") == 240,
        str(prioritized),
    )

    in_progress = smoke.status(
        "Tecnico cambia el estado a En progreso",
        tech.request(
            "PUT",
            f"/api/tickets/{ticket_id}/status",
            {"status": "En progreso"},
        ),
        200,
    )
    smoke.check(
        "El ticket sigue sin resolved_at",
        in_progress.get("status") == "En progreso"
        and in_progress.get("resolved_at") is None,
        str(in_progress),
    )

    commented = smoke.status(
        "Tecnico deja seguimiento",
        tech.request(
            "POST",
            f"/api/tickets/{ticket_id}/comments",
            {"body": "  Revisando el caso.  "},
        ),
        201,
    )
    smoke.check(
        "El comentario se recorta y registra al autor",
        commented.get("body") == "Revisando el caso."
        and commented.get("author", {}).get("id") == tech_user.get("id"),
        str(commented),
    )
    smoke.status(
        "Tecnico no asigna tecnico",
        tech.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": tech_user.get("id")},
        ),
        404,
    )
    tech_mine = smoke.status(
        "Tecnico consulta sus tickets creados",
        tech.request("GET", "/api/tickets"),
        200,
    )
    smoke.check("El tecnico no creo tickets", tech_mine == [], str(tech_mine))

    admin = Session("administrador", base_url)
    print("\n[Administrador]")
    _login(smoke, admin, "Administrador", ADMIN["email"])

    admin_mine = smoke.status(
        "Administrador consulta sus tickets creados",
        admin.request("GET", "/api/tickets"),
        200,
    )
    smoke.check(
        "El listado propio del admin no es el global",
        admin_mine == [],
        str(admin_mine),
    )
    technicians = smoke.status(
        "Administrador consulta el directorio de tecnicos",
        admin.request("GET", "/api/technicians"),
        200,
    )
    smoke.check(
        "El directorio trae los dos tecnicos y solo id/nombre",
        {tech_user["id"]} <= {item["id"] for item in technicians}
        and all(set(item) == {"id", "name"} for item in technicians),
        str(technicians),
    )
    tech_one_id = next(
        item["id"] for item in technicians if item["name"] == TECH_ONE["name"]
    )
    tech_two_id = next(
        item["id"] for item in technicians if item["name"] == TECH_TWO["name"]
    )

    assigned_ticket = smoke.status(
        "Administrador asigna al primer tecnico",
        admin.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": tech_one_id},
        ),
        200,
    )
    smoke.check(
        "El ticket queda a cargo del tecnico",
        assigned_ticket.get("assignee", {}).get("id") == tech_one_id,
        str(assigned_ticket),
    )
    tech_assigned = smoke.status(
        "El tecnico ve el ticket en sus asignados",
        tech.request("GET", "/api/assignments/mine"),
        200,
    )
    smoke.check(
        "Mis tickets del tecnico contiene el ticket",
        [ticket["id"] for ticket in tech_assigned] == [ticket_id],
        str(tech_assigned),
    )

    reassigned = smoke.status(
        "Administrador reasigna al segundo tecnico",
        admin.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": tech_two_id},
        ),
        200,
    )
    smoke.check(
        "El reasignado es el segundo tecnico",
        reassigned.get("assignee", {}).get("id") == tech_two_id,
        str(reassigned),
    )
    smoke.status(
        "Administrador devuelve el ticket al primer tecnico",
        admin.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": tech_one_id},
        ),
        200,
    )

    reprioritized = smoke.status(
        "Administrador cambia la prioridad a Media",
        admin.request(
            "PUT", f"/api/tickets/{ticket_id}/priority", {"priority": "Media"}
        ),
        200,
    )
    smoke.check(
        "El SLA pasa al objetivo de 720 minutos",
        reprioritized.get("sla", {}).get("target_minutes") == 720,
        str(reprioritized),
    )
    resolved = smoke.status(
        "Administrador marca el ticket como Resuelto",
        admin.request(
            "PUT", f"/api/tickets/{ticket_id}/status", {"status": "Resuelto"}
        ),
        200,
    )
    smoke.check(
        "Resuelto fija resolved_at",
        resolved.get("status") == "Resuelto"
        and resolved.get("resolved_at") is not None,
        str(resolved),
    )
    smoke.status(
        "Administrador deja seguimiento",
        admin.request(
            "POST",
            f"/api/tickets/{ticket_id}/comments",
            {"body": "Solucion aplicada."},
        ),
        201,
    )
    closed = smoke.status(
        "Administrador cierra el ticket",
        admin.request(
            "PUT", f"/api/tickets/{ticket_id}/status", {"status": "Cerrado"}
        ),
        200,
    )
    smoke.check(
        "El ticket queda Cerrado",
        closed.get("status") == "Cerrado",
        str(closed),
    )
    smoke.status(
        "Un ticket cerrado rechaza cambios de estado",
        admin.request(
            "PUT", f"/api/tickets/{ticket_id}/status", {"status": "En progreso"}
        ),
        409,
    )
    smoke.status(
        "Un ticket cerrado rechaza cambios de prioridad",
        admin.request(
            "PUT", f"/api/tickets/{ticket_id}/priority", {"priority": "Alta"}
        ),
        409,
    )
    smoke.status(
        "Un ticket cerrado rechaza la asignacion",
        admin.request(
            "PUT",
            f"/api/tickets/{ticket_id}/assignee",
            {"assignee_id": tech_two_id},
        ),
        409,
    )
    smoke.status(
        "Un ticket cerrado rechaza comentarios",
        admin.request(
            "POST", f"/api/tickets/{ticket_id}/comments", {"body": "Tarde"}
        ),
        409,
    )

    comments = smoke.status(
        "Administrador lee el seguimiento",
        admin.request("GET", f"/api/tickets/{ticket_id}/comments"),
        200,
    )
    smoke.check(
        "Los comentarios llegan del mas antiguo al mas nuevo",
        [comment["body"] for comment in comments]
        == ["Revisando el caso.", "Solucion aplicada."],
        str(comments),
    )
    closed_detail = smoke.status(
        "Administrador consulta el detalle cerrado",
        admin.request("GET", f"/api/tickets/{ticket_id}"),
        200,
    )
    smoke.check(
        "El detalle conserva prioridad, tecnico y resolved_at",
        closed_detail.get("priority") == "Media"
        and closed_detail.get("assignee", {}).get("id") == tech_one_id
        and closed_detail.get("resolved_at") is not None,
        str(closed_detail),
    )
    reopened = smoke.status(
        "Administrador reabre el ticket cerrado",
        admin.request("POST", f"/api/tickets/{ticket_id}/reopen"),
        200,
    )
    smoke.check(
        "La reapertura deja el ticket Abierto y sin resolved_at",
        reopened.get("status") == "Abierto"
        and reopened.get("resolved_at") is None,
        str(reopened),
    )
    after_reopen = smoke.status(
        "El listado global refleja la reapertura",
        admin.request("GET", "/api/tickets/all"),
        200,
    )
    smoke.check(
        "El ticket reabierto aparece Abierto",
        after_reopen[0]["status"] == "Abierto",
        str(after_reopen[0]),
    )

    print("\n[Sesion y validacion]")
    smoke.status(
        "El cliente cierra sesion",
        client.request("POST", "/api/auth/logout"),
        204,
    )
    smoke.status(
        "Tras cerrar sesion, el listado responde 401",
        client.request("GET", "/api/tickets"),
        401,
    )
    smoke.status(
        "Un identificador invalido responde 404 uniforme",
        admin.request("GET", "/api/tickets/no-es-uuid"),
        404,
    )
    smoke.status(
        "Un comentario vacio responde 422",
        admin.request(
            "POST", f"/api/tickets/{ticket_id}/comments", {"body": "   "}
        ),
        422,
    )


def main() -> int:
    host = os.getenv("SMOKE_HOST", "127.0.0.1")
    port = int(os.getenv("SMOKE_PORT", "0")) or _free_port()
    base_url = f"http://{host}:{port}"

    _seed_users()
    server = _start_server(host, port)
    smoke = Smoke()
    try:
        _wait_health(base_url, server)
        print(f"Smoke manual de tickets contra {base_url}\n")
        run(base_url, smoke)
    except SmokeError as exc:
        print(f"\n{exc}")
        return 1
    finally:
        server.should_exit = True
        time.sleep(0.2)

    print(f"\nSmoke completado: {smoke.passed} comprobaciones en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
