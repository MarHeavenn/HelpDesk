# Memoria del proyecto

## Estado actual

- HU-01..HU-10 y HU-14 **mergeadas en `develop`** (backend en memoria).
- Suite backend sin Docker: **760 passed, 14 skipped**; con Docker: 1154 passed,
  3 fallos preexistentes de precedencia 401/404 con cookie inválida.
- `HU-20` con ADR/spec/plan/tareas y sin código. `HU-21` (frontend shell)
  T1..T6 completas; `HU-11` T1..T8 y `HU-12` T6 completas en sus ramas.
- HU-11: dashboard real de tickets en `/` (`GET /api/dashboard/tickets`);
  administrador global, técnico asignados, cliente 404.
- HU-12: reutilizará el módulo `sla` de HU-05/HU-14 (estados, umbral 20 %,
  configuración vigente) y añadirá `GET /api/dashboard/sla` + panel en `/`.
- TSK-025 (PostgreSQL multitenant) mergeada (PR #9); la persistencia de los
  módulos sigue en memoria.

## Decisiones clave

- HU-09: historial derivado, no persistido; `GET /api/tickets/{id}/history`;
  admin/técnico, cliente 404; orden determinista; `Cerrado` conserva historial.
- HU-08: flujo `Abierto` → `En progreso` → `Resuelto` → `Cerrado` y retroceso
  `Resuelto` → `En progreso`; reapertura solo administrador.
- HU-07: comentarios `POST/GET /api/tickets/{id}/comments`; cuerpo 1-2000.
- HU-06: cliente solo sus tickets, staff cualquiera; detalle añade `requester`
  y `resolved_at`.
- HU-05/HU-14: SLA 120/240/720/1440 min; `Resuelto`/`Cerrado` congelan
  `resolved_at`; reabrir reanuda; `GET/PUT /api/sla/policies` solo admin.
- `sla` no importa `tickets`; `tickets` compone el SLA con `get_ticket_sla`.

## Entorno local

- `.venv` en la raíz; `infra/.env` usa `POSTGRES_PORT=55432` (el 5432 está ocupado).
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`;
  sin él, los tests de BD se saltan.
- Frontend: `cd frontend`, `npm install`, `npm run dev` en `localhost:5173`.

## Errores que se deben evitar

- No usar el puerto 5432. No afirmar pruebas no ejecutadas. En PowerShell no
  existe `tail`. `codegraph` solo vía `cmd /c`.
- No poner lógica de negocio en los HTTP ni tocar tablas de otros módulos.
- Logout 204 devuelve cuerpo vacío. `Ticket` y `TicketSlaSnapshot`: defaults
  al final. 422 de Pydantic: `detail` lista; del dominio: `detail` cadena.
- Un `TestClient` tiene una sola cookie: uno por rol.
- Tests de contrato comparan el conjunto exacto de campos; envejecer tickets
  mutando `created_at` (nunca dormir).
- La configuración de SLA es un singleton: `reset()` en fixtures `autouse`.
- Al añadir una ruta, revisar los barridos que afirman su ausencia.
- Vitest sin `globals`: registrar `cleanup()` de RTL en `tests/setup.ts`.
- Abrir el frontend en `localhost:5173`, no `127.0.0.1`, por la cookie.

## Próximos pasos

- Sincronizar HU-11 y HU-12 con `develop` y abrir PRs contra `develop`.
- HU-21 T7..T10: drawer, marcadores, logout y cierre.
- HU-12: contrato de tickets, agregación, endpoint y panel de SLA.
- Integrar los módulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos preexistentes de precedencia 401/404.
