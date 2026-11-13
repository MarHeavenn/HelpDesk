# Memoria del proyecto

## Estado actual

- HU-01..HU-12, HU-14 y HU-21 **mergeadas en `develop`**; la persistencia de
  los módulos sigue en memoria (TSK-025 deja PostgreSQL preparado).
- HU-22 (creación y detalle) y HU-23 (listados) en la rama
  `feature/HU-20-tickets-frontend`, sin commit ni PR todavía.
- Suites al 2026-11-13: backend **1191 passed, 14 skipped**; frontend
  **22 archivos / 155 pruebas**; `lint` y `build` en verde.
- HU-23: `/tickets` y `/mis-tickets` reales sobre un `TicketListPage` común;
  filtros, orden y paginación en cliente con la URL como fuente de verdad.
  El técnico ve sus asignados en «Mis tickets»; admin y cliente, los suyos.
- HU-23: nuevo `GET /api/tickets/all` (administrador y técnico; cliente 404,
  sin sesión 401), declarado antes de `GET /{ticket_id}`.
- HU-22: detalle en modal accesible desde la tabla, con prioridad/estado,
  asignación (solo admin) y comentarios; título y descripción inmutables.
- Smoke manual ejecutado el 2026-11-13 con las tres cuentas: API real (90
  comprobaciones) e interfaz real en Chrome headless (27), en verde.
- HU-11 y HU-12: dashboard real de tickets y de SLA en `/`.

## Decisiones clave

- HU-09: historial derivado, no persistido; admin/técnico, cliente 404.
- HU-08: `Abierto` → `En progreso` → `Resuelto` → `Cerrado`; retroceso
  `Resuelto` → `En progreso`; reapertura solo administrador.
- HU-07: comentarios de 1–2000 code points; admin y técnico escriben.
- HU-06: cliente solo sus tickets; el detalle añade `requester` y `resolved_at`.
- HU-05/HU-14: SLA 120/240/720/1440 min; `Resuelto`/`Cerrado` congelan
  `resolved_at`; `GET/PUT /api/sla/policies` solo admin.
- `sla` no importa `tickets`; `tickets` compone el SLA con `get_ticket_sla`.
- HU-23: el filtro de técnico se deriva de los tickets cargados, porque el
  directorio completo (`/api/technicians`) es solo del administrador.
- HU-22/HU-23: `TicketListPage` sirve ambos listados; «Mis tickets» no consulta
  hasta resolver el rol, para no pedir el alcance equivocado.

## Entorno local

- `.venv` en la raíz; `infra/.env` usa `POSTGRES_PORT=55432` (5432 ocupado).
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`;
  sin él, los tests de BD se saltan.
- Frontend: `cd frontend`, `npm install`, `npm run dev` en `localhost:5173`.
- Smoke de API reproducible: `cd backend` y `..\.venv\Scripts\python.exe
  smoke_manual.py` (levanta uvicorn real y siembra las tres cuentas).

## Errores que se deben evitar

- No usar el puerto 5432. No afirmar pruebas no ejecutadas. En PowerShell no
  existe `tail`. `codegraph` solo vía `cmd /c`.
- No poner lógica de negocio en los HTTP ni tocar tablas de otros módulos.
- Logout 204 devuelve cuerpo vacío. 422 de Pydantic: `detail` lista; del
  dominio: `detail` cadena. Un `TestClient` tiene una sola cookie: uno por rol.
- Tests de contrato comparan campos exactos; envejecer tickets mutando
  `created_at` (nunca dormir). La config de SLA es un singleton con `reset()`.
- Al añadir una ruta, revisar los barridos que afirman su ausencia.
- Vitest sin `globals`: registrar `cleanup()` de RTL en `tests/setup.ts`.
- Abrir el frontend en `localhost:5173`, no `127.0.0.1`, por la cookie.
- Las vistas de tickets usan la API real: en pruebas hay que inyectar el fake o
  stubear `fetch`; si no, el 401 global desmonta la vista.

## Próximos pasos

- PR de HU-22/HU-23 contra `develop` (los cambios siguen sin commit).
- Revisión visual manual de HU-21 en 360/768/1024/1440 px, aún pendiente.
- Conectar las vistas restantes: técnicos, SLA, usuarios y empresas.
- Integrar los módulos con PostgreSQL en una tarea aparte.
