# Memoria del proyecto

## Estado actual

- HU-01..HU-04 completas en `develop` (**735 passed**). Los PRs #3 y #4 se mergearon por error
  en `main`; `main` se rebobino a `ca8eb69` (solo HU-01/HU-02) con force push.
- HU-03 validada (520 passed); HU-04 validada por el reviewer (**APROBADO, 720 passed**).
- Extra post-validacion en HU-04 (`ee2b19a`): UTF-8 invalido en los PUT de tickets -> 422
  `json_invalid` (antes 500); regresion en `backend/tests/test_tickets_invalid_utf8.py`.
- Suite: `pytest backend/tests/` -> **735 passed** (HU-01..HU-04; 10 del barrido T11; test extra
  de dos sesiones de administrador y 14 de regresion UTF-8).
- Modulos: `identity` (registro/login/sesion/provision y directorio de tecnicos), `tickets`
  (HU-02 + HU-03 + asignacion), `assignment` y `sla` sin implementar. Persistencia en memoria.

## Decisiones tomadas (HU-04)

- Asignacion en `tickets` (D1): `Ticket.assignee_id/assignee_name`, `ASSIGNMENT_ROLES` solo
  `administrador`, log `InMemoryAssignmentLog` append-only e interno. `assignment` queda para
  politicas futuras.
- Tecnico como objeto `assignee: {id, name} | null` en creacion, listado, detalle, asignacion,
  modificaciones HU-03 y tickets a cargo (D7); nombre proyectado al asignar (D8).
- `PUT /api/tickets/{id}/assignee` (cuerpo `{"assignee_id": StrictStr}`), `GET /api/technicians`
  (solo admin) y `GET /api/assignments/mine` (cualquier sesion). Sin desasignacion.
- Precedencia 401 > 404 > 409 > 422 con dependencia y cuerpo al final, tambien con JSON
  invalido; tecnico invalido 422 uniforme `assignee is not a valid technician`; cerrado 409
  `ticket is closed`; sin 400 ni 403.
- Repetir el tecnico vigente -> 200 sin cambio ni registro; solo cambios efectivos se registran.
- Reutiliza `provision_user`; sin dependencias nuevas ni concurrencia. Empates de fecha no fijan orden.

## Errores que se deben evitar

- No inventar reglas ambiguas; marcarlas como pendientes.
- No acceder a estructuras/tablas internas de otros modulos ni poner logica de negocio en los HTTP.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`: pytest sin tuberias.
- Barridos: verificar cuerpo crudo (`response.text`/`json.loads`), no solo claves del JSON.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default (`priority`, `status`, `assignee_*`) al final.
- Bytes no UTF-8 en `json.loads` -> `UnicodeDecodeError` (no `JSONDecodeError`): capturarlo -> 422.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string (aceptado desde HU-01).
- Un `TestClient` tiene una sola cookie: usar un cliente por rol cuando coexistan sesiones.
- Al comparar rutas OpenAPI, `logout` contiene "log": filtrar por ticket/assignment.

## Proximos pasos

- Trabajar siempre desde `develop`; los PR deben apuntar a `develop`, nunca a `main` (GitHub
  sugiere `main` por defecto: cambiar la base a mano).
- `main` solo recibe versiones estables con decision explicita; nunca abrir un PR contra `main`.
- El usuario indico que ya no necesita HU-05 (SLA).
