# Memoria del proyecto

## Estado actual

- HU-01..HU-10 y HU-14 **mergeadas en `develop`**.
- HU-09 (historial y trazabilidad) **implementada** en
  `feature/Hu-09-trazabilidad-del-ticket` (cambios sin commit), con 44 pruebas
  nuevas (dominio, acceso, caso de uso, contrato, API y flujo completo).
- Suite completa con Docker (`DATABASE_URL`): **1154 passed, 3 failed**. Los 3
  fallos son preexistentes: precedencia 401/404 con cookie inválida
  (`test_tickets_assign_access`, `test_tickets_modify_access`).
- Corregida la integración HU-08/HU-14: `reopen_ticket` ahora limpia también
  `resolved_target_minutes`, de modo que la reapertura reanuda el SLA con la
  configuración vigente.
- TSK-025 (PostgreSQL multitenant) mergeada (PR #9). Los módulos siguen con
  persistencia en memoria; integrarlos con PostgreSQL es una tarea aparte.
- `HU-20` (frontend) con spec/plan/tareas, sin código. HU-11..HU-13 y
  HU-15..HU-19 definidas solo en el documento general.

## Decisiones HU-09

- Historial **derivado**, no persistido: reúne creación, modificaciones de
  prioridad/estado, asignaciones y comentarios ya registrados. No duplica
  datos ni toca los casos de uso de HU-03/04/07/08.
- `GET /api/tickets/{ticket_id}/history`, solo lectura. Visibilidad:
  `administrador` y `tecnico`; cliente → 404 uniforme; sin sesión → 401.
- Eventos: `ticket_created`, `technician_assigned`, `technician_reassigned`,
  `priority_changed`, `status_changed` (incluye reapertura) y
  `comment_added`. Solo cambios efectivos; no-ops y rechazos no generan evento.
- Orden ascendente determinista: `(occurred_at, source_rank, insertion_index)`
  con creación=0, asignación=1, prioridad=2, estado=3, comentario=4.
- Respuesta: `action`, `actor {id, name|null}`, `occurred_at` ISO 8601 UTC,
  `previous_value`/`new_value`, `previous_assignee`/`new_assignee` y
  `comment`; todos los campos presentes (null cuando no aplican).
- Ticket `Cerrado` conserva el historial (200, sin 409). Sin paginación,
  filtros, exportación ni edición. Nombres resueltos con `get_user_summary`;
  un usuario no resoluble conserva su id y `name: null`.
- RF-81..RF-90 (HU-08 y HU-14 ya solaparon RF-71..RF-80).

## Decisiones HU-08

- Flujo `Abierto` → `En progreso` → `Resuelto` → `Cerrado` y retroceso
  `Resuelto` → `En progreso`. Transición inválida → 409
  `invalid status transition`; mismo estado → 200 sin registro; `Cerrado` →
  409 `ticket is closed`.
- Reapertura `POST /api/tickets/{id}/reopen`: solo administrador, sin cuerpo,
  `Cerrado` → `Abierto`, descarta `resolved_at`, reanuda SLA; no cerrado →
  409 `ticket is not closed`; no admin/inexistente → 404 uniforme.

## Decisiones HU-07, HU-06, HU-05 y HU-14

- HU-07: `POST/GET /api/tickets/{id}/comments`; escriben `tecnico` y
  `administrador`; cliente → 404; cerrado → 409 al comentar, 200 al listar;
  `body` 1-2000 code points recortado.
- HU-06: cliente solo sus tickets, staff cualquiera; `TicketResponse` añade
  `requester {id, name, email}` y `resolved_at`; resúmenes sin cambios.
- HU-05: SLA por prioridad (120/240/720/1440 min); `Resuelto`/`Cerrado`
  congelan `resolved_at`; reabrir reanuda; `sla` no importa `tickets`.
- HU-14: `GET/PUT /api/sla/policies` solo administrador; reemplazo total en
  horas, guardado en minutos; 401 > 404 > 422; configuración global en memoria.

## Entorno local

- `.venv` en `backend/`; instalar `backend/requirements.txt`.
- `infra/.env` usa `POSTGRES_PORT=55432`; el 5432 lo ocupa PostgreSQL nativo.
  `docker compose up -d` en `infra/`.
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`;
  sin él, los tests de BD se saltan.

## Errores que se deben evitar

- No usar el puerto 5432. No afirmar pruebas no ejecutadas. En PowerShell no
  existe `tail`.
- `codegraph` solo vía `cmd /c`.
- No poner lógica de negocio en los HTTP ni tocar tablas de otros módulos.
- Logout 204 devuelve cuerpo vacío. `Ticket` y `TicketSlaSnapshot`: defaults
  al final.
- 422 de Pydantic: `detail` lista; del dominio: `detail` cadena.
- Un `TestClient` tiene una sola cookie: uno por rol.
- Los tests de contrato comparan el conjunto exacto de campos; envejecer
  tickets mutando `created_at` (nunca dormir).
- La configuración de SLA es un singleton: `reset()` en fixtures `autouse`.
- Al añadir una ruta, revisar los barridos que afirman su ausencia (HU-09).

## Próximos pasos

- Commit y PR de HU-09 contra `develop`.
- Integrar los módulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos preexistentes de precedencia 401/404.
- PRs siempre contra `develop`; `main` solo recibe versiones estables.
