# Memoria del proyecto

## Estado actual

- HU-01 y HU-02 completas y mergeadas a `develop`. HU-03 validada por el reviewer (520 passed);
  rama `feature/hu-03-priority-status` publicada, PR a `develop` pendiente a mano.
- HU-04 (asignacion): completa y validada por el reviewer (**APROBADO, 720 passed**); rama
  `feature/hu-04-assignment` publicada en `origin` (commit `df7a195`; apilada sobre HU-03). PR a
  `develop` pendiente de abrir a mano y **despues del merge de HU-03**.
- Suite actual: `pytest backend/tests/` -> **721 passed** (HU-01..HU-04; 10 del barrido T11;
  test extra de dos sesiones de administrador en HU-04).
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
- 422 de Pydantic devuelven `detail` lista; los del dominio, string (aceptado desde HU-01).
- Un `TestClient` tiene una sola cookie: usar un cliente por rol cuando coexistan sesiones.
- Al comparar rutas OpenAPI, `logout` contiene "log": filtrar por ticket/assignment.

## Proximos pasos

- Abrir a mano el PR de HU-03 -> `develop` (no hay `gh`).
- HU-04: abrir su PR a `develop` a mano, despues del merge de HU-03 (rama apilada).
- Pendiente opcional (no bloqueante): bytes UTF-8 invalidos en cuerpos JSON de HU-03 devuelven 500 en
  vez de 422; el usuario decidio dejarlo pendiente.
- El usuario indico que ya no necesita HU-05 (SLA).
