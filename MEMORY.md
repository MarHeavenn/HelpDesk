# Memoria del proyecto

## Estado actual

- HU-01..HU-05 completas en `develop` (HU-05 mergeada, PR #10).
- HU-06 (detalle), HU-07 (comentarios) y HU-08 (ciclo de vida) **implementadas**
  en `feature/Hu-06-tickets-sla` (cambios sin commit). Specs, planes y `tasks.md`
  (HU-06/HU-07/HU-08 redactadas a posteriori, todas cerradas).
- Suite completa con `DATABASE_URL`: **935 passed, 14 skipped, 3 failed**. Los 3
  fallos son previos: precedencia 401/404 con cookie inválida por `starlette`/`httpx`.
- TSK-025 (PostgreSQL multitenant) mergeada (PR #9). Los módulos siguen con
  persistencia en memoria; integrarlos con PostgreSQL es una tarea aparte.
- `HU-20` (frontend) con spec/plan/tareas, sin código. HU-09..HU-19 definidas
  solo en el documento general.

## Decisiones HU-08

- Flujo estricto en `PUT /api/tickets/{id}/status`: `Abierto` → `En progreso` →
  `Resuelto` → `Cerrado`, más el retroceso `Resuelto` → `En progreso`.
- Transición inválida: `409 {"detail": "invalid status transition"}`. Mismo estado
  en ticket no cerrado: 200 sin cambio ni registro. Ticket `Cerrado`: 409
  `ticket is closed` antes de validar el cuerpo.
- Reapertura: `POST /api/tickets/{id}/reopen`, solo `administrador`, sin cuerpo
  (se ignora). Devuelve `Abierto`, descarta `resolved_at`, reanuda el SLA y registra
  `Cerrado` → `Abierto`. No administrador/inexistente/inválido: 404 uniforme;
  no cerrado: 409 `ticket is not closed`.
- Precedencia `PUT /status`: 401 > 404 > 409 cerrado > 422 cuerpo/catálogo > 409
  transición. Reapertura: 401 > 404 > 409.
- Sin campos nuevos ni `allowed_transitions`; `TicketResponse` y resúmenes intactos.
- La tabla vive en `tickets/domain`; la interfaz solo traduce errores. El registro
  reutiliza `TicketModification` (lo consumirá HU-09).
- Pruebas de HU-03..HU-07 actualizadas para recorrer el flujo válido, sin debilitar
  aserciones.

## Decisiones HU-07

- `POST/GET /api/tickets/{id}/comments`; no cambia `TicketResponse`. Escriben
  `tecnico` y `administrador`; cliente: 404 uniforme. Lee quien ve el ticket.
- Ticket `Cerrado`: 409 al comentar, 200 al listar. `body` 1-2000 code points,
  recortado; autor de sesión; listado ascendente estable.

## Decisiones HU-06

- Cliente solo sus tickets; staff cualquiera. `TicketResponse` añade
  `requester {id, name, email}` y `resolved_at`; resúmenes sin cambios.
- 404 uniforme para staff; 401 antes que 404.

## Decisiones HU-05

- Critica 120, Alta 240, Media 720, Baja 1440 min. Sin prioridad: `sla: null`.
- `Resuelto`/`Cerrado` fijan `resolved_at` y congelan el SLA; al reanudar se
  descarta. Cálculo puro en `sla/domain`; `sla` no importa `tickets`.

## Entorno local

- `.venv` en `backend/`; instalar `backend/requirements.txt`.
- `infra/.env` (ignorado) usa `POSTGRES_PORT=55432`; el 5432 lo ocupa PostgreSQL
  nativo. Arrancar Docker y `docker compose up -d` en `infra/`.
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.

## Errores que se deben evitar

- No usar el puerto 5432. No afirmar pruebas no ejecutadas.
- `codegraph` solo via `cmd /c` (la política bloquea el .ps1).
- Logout 204 devuelve cuerpo vacío. `Ticket` (dataclass): defaults al final.
- 422 de Pydantic: `detail` lista; los del dominio, string.
- Un `TestClient` tiene una sola cookie: uno por rol.
- Al cambiar el contrato de ticket, ajustar tests de composición exacta.
- `PUT /status` ya no acepta saltos ni retrocesos libres (HU-08).

## Próximos pasos

- Commit/PR de HU-06, HU-07 y HU-08 contra `develop`.
- HU-09: historial de modificaciones (consumirá el registro de HU-08).
- HU-14: configuración pública de SLA. Integrar PostgreSQL aparte.
- Revisar los 3 tests fallidos por dependencias actuales.
- PRs siempre contra `develop`; `main` solo recibe versiones estables.
