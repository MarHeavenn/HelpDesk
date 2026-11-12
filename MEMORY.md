# Memoria del proyecto

## Estado actual

- HU-01..HU-10 y HU-14 **mergeadas en `develop`** (backend en memoria).
- Suite backend sin Docker: **1183 passed, 14 skipped**; frontend: **104 passed**.
- `HU-20` con ADR/spec/plan/tareas y sin código. `HU-21` (frontend shell)
  T1..T9 completas (T10 pendiente del smoke manual); `HU-11` T1..T8 y
  `HU-12` T1..T7 completas en sus ramas y en `develop`.
- HU-11: dashboard real de tickets en `/` (`GET /api/dashboard/tickets`);
  administrador global, técnico asignados, cliente 404.
- HU-12: `GET /api/dashboard/sla` + panel «Cumplimiento de SLA» en `/`;
  reutiliza el módulo `sla` de HU-05/HU-14 (estados, umbral 20 %, política
  vigente) con contrato de lectura de `tickets`; periodos 7/30/90.
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
- HU-12: el agregado vive en `sla/application/dashboard.py`; `tickets/interface/
  sla_contract.py` expone la vista mínima; el panel consume datos reales y no
  duplica la política ni el umbral.
- HU-21: drawer móvil propio (sin librería) con foco atrapado, `aria-expanded`
  y cierre por Escape/capa/ruta/umbral 1024 px; el contenido de la barra lateral
  se comparte entre la versión fija y el panel. `/cuenta/perfil` es un perfil
  mínimo con identidad real y «Cerrar sesión»; el menú del encabezado muestra
  nombre, correo y rol.

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
- `Literal[int]` no convierte `?days=7` (cadena) en FastAPI: validar con
  `Annotated[int, AfterValidator]` y probar los valores válidos por HTTP.

## Próximos pasos

- Force-push de HU-21, HU-11 y HU-12; abrir PRs contra `develop`.
- HU-21 T10: smoke manual en 360/768/1024/1440 px con las tres cuentas y PR
  contra `develop`.
- Integrar los módulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos preexistentes de precedencia 401/404.
