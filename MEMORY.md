# Memoria del proyecto

## Estado actual

- HU-01..HU-04 completas en `develop` (**735 passed**). Los PRs #3/#4 se mergearon por error
  en `main`, rebobinada a `ca8eb69` (HU-01/HU-02) con force push.
- HU-03 validada y HU-04 aprobada; extra UTF-8 (`ee2b19a`): PUT invalido -> 422 `json_invalid`.
- Rama `feature/localhost-setup` desde `develop`: `uvicorn==0.54.0` + `backend/dev_server.py`
  (admin/tecnico demo y arranque en `127.0.0.1:8000`). Verificado por HTTP real (health, auth,
  tickets, asignacion, prioridad, estado, CORS, logout 401) y **735 passed**.
- Modulos: `identity`, `tickets` (HU-02..HU-04), `assignment` y `sla` sin implementar.
  Persistencia en memoria; frontend vacio; PostgreSQL aun no conectado.

## Decisiones tomadas (HU-04)

- Asignacion en `tickets` (D1): `assignee_id/assignee_name`, solo `administrador` asigna,
  `InMemoryAssignmentLog` append-only; `assignment` queda para politicas futuras.
- `assignee: {id, name} | null` en creacion/listado/detalle/modificaciones/tickets a cargo;
  nombre proyectado al asignar. Sin desasignacion.
- `PUT /api/tickets/{id}/assignee`, `GET /api/technicians` (admin) y
  `GET /api/assignments/mine` (cualquier sesion).
- Precedencia 401 > 404 > 409 > 422; cerrado 409 `ticket is closed`; tecnico invalido 422;
  repetir tecnico vigente -> 200 sin registro; sin 400 ni 403.

## Decisiones locales

- `dev_server.py` siembra admin/tecnico (no hay endpoint publico): `admin@helpdesk.dev` y
  `tecnico@helpdesk.dev`; `.test`/`.localhost` los rechaza `email-validator`.
- Contrasenas: `DEV_ADMIN_PASSWORD`/`DEV_TECH_PASSWORD`; si faltan se generan y muestran.
  `HOST`/`PORT` configurables (por defecto `127.0.0.1:8000`).

## Errores que se deben evitar

- No inventar reglas ambiguas; marcarlas como pendientes.
- No acceder a tablas internas de otros modulos ni poner logica de negocio en los HTTP.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`: pytest sin tuberias.
- Barridos: verificar cuerpo crudo (`response.text`/`json.loads`), no solo claves JSON.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default (`priority`, `status`, `assignee_*`) al final.
- Bytes no UTF-8 en `json.loads` -> `UnicodeDecodeError`: capturarlo -> 422.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string (aceptado desde HU-01).
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.
- En OpenAPI, `logout` contiene "log": filtrar por ticket/assignment.

## Proximos pasos

- PR de `feature/localhost-setup` contra `develop` (nunca contra `main`).
- `main` solo recibe versiones estables con decision explicita.
- El usuario indico que ya no necesita HU-05 (SLA). Frontend pendiente.
