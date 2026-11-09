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
- `develop` con HU-01..HU-07, HU-10 y TSK-025 mergeadas (HEAD `ffdefb8`).
- HU-08 (ciclo de vida): rama `feature/Hu-08-ciclo-de-vida` en remoto, sin mergear.
- HU-14 (configuración de SLA): implementada en `feature/hu-14-sla-config`
  (misma base que `develop`); pendiente de commit y PR contra `develop`.
- HU-20 (frontend): spec/plan/tareas, sin código.
- Suite completa (Docker + `DATABASE_URL`): **1042 passed, 3 failed**. Los 3
  fallos son los preexistentes de precedencia 401/404 (`test_tickets_assign_access`,
  `test_tickets_modify_access`), ajenos a HU-14.

## Decisiones HU-14

- Configuración **global** de SLA, semilla 120/240/720/1440 min
  (Crítica/Alta/Media/Baja) en `sla/domain/policy_config.py`; el cálculo deja de
  leer la constante de HU-05 y consulta el repositorio en cada llamada.
- API solo backend: `GET` y `PUT /api/sla/policies` (reemplazo total con las 4
  prioridades) y solo rol `administrador`. Sin 403: 401 sin sesión, 404 uniforme
  `{"detail": "not found"}` para cliente/técnico y 422 de cuerpo.
- Precedencia 401 > 404 > 422: el cuerpo del `PUT` se lee en una dependencia
  declarada después de `require_sla_admin`.
- Se expone y edita en **horas** (`hours = minutos/60`; 150→2.5) pero se guarda en
  **minutos enteros**: `Decimal` + `ROUND_HALF_UP`, mínimo 1 min (`0.001`→422).
- Forma → 422 `detail` lista (Pydantic); regla de dominio (positivo, mínimo,
  claves) → 422 `detail` cadena. `NaN`/`Infinity` se sanean al serializar el 422.
- Persistencia **en memoria**: `InMemorySlaPolicyRepository` singleton, último
  escritor gana y `reset()` a la semilla al arrancar; contrato con `company_id`
  opcional preparado para multitenant (sin implementar).
- Tickets activos derivan el SLA en vivo de la configuración vigente.
  `Resuelto`/`Cerrado` se congelan con `Ticket.resolved_target_minutes` (interno,
  fuera de `TicketResponse`); al reabrir se limpia; al cambiar la prioridad de un
  resuelto se re-congela con la configuración vigente en ese momento.
- `get_ticket_sla(snapshot, now=None)` conserva su firma; `TicketSlaSnapshot`
  gana `resolved_target_minutes` opcional al final.

## Decisiones previas (resumen)

- Autorización desde la sesión (`get_current_user`); el proyecto no usa 403.
- Ticket sin prioridad: `sla: null`; el vencimiento parte de `created_at`.
- Al resolver se fija `resolved_at`; SLA `cumplido`/`incumplido` congelado.
- `GET /api/tickets/requiring-attention`: derivado en vivo con `get_ticket_sla`,
  umbral 20 %, solo `tecnico`/`administrador`, orden por `due_at`.
- HU-07: comentarios `POST/GET /api/tickets/{id}/comments`; escriben staff; el
  cliente recibe 404 uniforme; ticket cerrado → 409 al comentar.
- HU-06: `TicketResponse` añade `requester` y `resolved_at`; resúmenes sin cambios.
- TSK-025: una BD y un esquema; `company_id` en `users`, `tickets` y `sla_policies`.

## Entorno local

- `infra/.env` con `POSTGRES_PORT=55432`; `docker compose up -d` en `infra/`.
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`;
  sin él, 14 tests de BD se saltan. No usar el puerto 5432.

## Errores que se deben evitar

- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`.
- `codegraph` solo corre vía `cmd /c`.
- No poner lógica de negocio en los HTTP ni tocar tablas de otros módulos.
- Logout 204 devuelve cuerpo vacío (`b""`).
- `Ticket` y `TicketSlaSnapshot`: campos con default al final.
- 422 de Pydantic: `detail` lista; del dominio: `detail` cadena.
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.
- Los tests de contrato comparan el conjunto exacto de campos; envejecer tickets
  mutando `created_at` (nunca dormir).
- La configuración de SLA es un singleton: `reset()` en fixtures `autouse`.

## Próximos pasos

- Commit y PR de HU-14 contra `develop`.
- Commit/PR de HU-08 contra `develop`.
- Integrar los módulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos preexistentes de precedencia 401/404.
