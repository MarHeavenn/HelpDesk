# Tareas HU-08 — Gestionar ciclo de vida del ticket

Orden de dependencia. Verificación con pytest + TestClient (sin frontend).

Redactado a posteriori (2026-11-09) para documentar el trabajo implementado en
`feature/Hu-06-tickets-sla`: todas las tareas quedan cerradas (`[x]`) con el criterio
que realmente se verificó. La spec está en `implementada` y el plan en
`implementado`. No hay cambios de persistencia (PostgreSQL sigue pendiente) ni de
frontend (HU-20); el estado y el registro de modificaciones viven en memoria.

- [x] **T1. Dominio del flujo del ciclo de vida y rol de reapertura.** RF-71, RF-74, RF-77
  - Hecho cuando: `tickets/domain/entities.py` añade `IN_PROGRESS_STATUS`, reconstruye
    `STATUSES` con las cuatro constantes, define `STATUS_TRANSITIONS`
    (`Abierto` → `En progreso`; `En progreso` → `Resuelto`; `Resuelto` →
    `Cerrado`/`En progreso`; `Cerrado` sin destinos), `is_allowed_status_transition`
    y `REOPEN_ROLES = {"administrador"}`. `test_ticket_lifecycle_domain.py` pasa con
    22 casos: catálogo y orden intactos, tabla exacta, cuatro transiciones válidas,
    doce pares inválidos o repetidos, `Cerrado` sin salidas, estado desconocido y
    único rol de reapertura.

- [x] **T2. Validación de transiciones en la actualización de estado.** RF-72, RF-73, RF-74, RF-80
  - Hecho cuando: `tickets/application/update_ticket_status.py` valida primero el
    catálogo (`TicketValidationError` → 422), devuelve el ticket sin cambio ni
    registro si el estado coincide con el vigente y lanza
    `InvalidStatusTransitionError("invalid status transition")` si el destino es
    válido pero no figura en `STATUS_TRANSITIONS`. En un cambio efectivo muta el
    estado, registra `TicketModification` con el actor y la fecha del sistema, fija
    `resolved_at` al resolver, lo conserva en `Resuelto` → `Cerrado` y lo descarta al
    volver a un estado no resuelto.
  - `test_ticket_lifecycle_status.py` verifica las cuatro transiciones válidas, las
    cinco inválidas, la repetición del estado, los 409 de transición y de ticket
    cerrado, los 422 de cuerpo/catálogo, el 404 uniforme del cliente, el 404 de
    ticket inexistente/inválido, el 401 sin sesión, la composición exacta de
    `TicketResponse` y la semántica de `resolved_at`/SLA.

- [x] **T3. Resolución autorizada del ticket y reapertura.** RF-76, RF-77, RF-80
  - Hecho cuando: `tickets/application/get_reopenable_ticket.py` comprueba en orden
    el rol (`REOPEN_ROLES`), el formato UUID, la existencia (los tres casos con
    `TicketNotFoundError`/404 uniforme) y el estado `Cerrado`
    (`TicketNotClosedError("ticket is not closed")`/409).
    `tickets/application/reopen_ticket.py` pasa el ticket a `Abierto`, descarta
    `resolved_at`, no toca prioridad, técnico, solicitante, título, descripción ni
    `created_at`, y registra `Cerrado` → `Abierto` con el actor de la sesión.
  - `test_ticket_lifecycle_reopen.py` pasa con 13 casos: éxito del administrador,
    `resolved_at: null`, SLA reanudado, registro y contrato exacto, 404 uniforme para
    técnico/cliente, 404 para inexistente/inválido, 409 para ticket no cerrado,
    401 antes que 404/409, cuerpo ignorado (JSON, campos extra y bytes no JSON),
    bloqueo del cierre por `PUT /status`, operaciones habilitadas tras reabrir y
    ausencia de campos/registro expuestos.

- [x] **T4. Router, precarga de errores y contrato OpenAPI.** RF-75, RF-78, RF-79
  - Hecho cuando: `tickets/interface/router.py` traduce
    `InvalidStatusTransitionError` a `409 {"detail": "invalid status transition"}`
    después del 422, añade la dependencia `_reopenable_ticket` (401 > 404 > 409) y la
    ruta `POST /api/tickets/{ticket_id}/reopen` sin cuerpo declarado. El ticket
    cerrado sigue respondiendo 409 `ticket is closed` en `PUT /status` antes de
    validar el cuerpo. Se comprueba en OpenAPI que la única ruta nueva es `reopen`,
    que `PUT /status` conserva su forma y que no se añade `allowed_transitions` ni
    ningún campo a `TicketResponse`.

- [x] **T5. Flujo completo e integración entre historias.** RF-71 a RF-80
  - Hecho cuando: `test_ticket_lifecycle_flow.py` recorre HU-02 (creación) → HU-04
    (asignación) → HU-03/HU-05 (prioridad y SLA) → `En progreso` → comentario HU-07
    → `Resuelto` → `En progreso` → `Resuelto` → `Cerrado` → bloqueo de estado,
    comentarios y reapertura no autorizada → reapertura del administrador →
    operaciones habilitadas de nuevo → nuevo avance. Intercala saltos y retrocesos
    inválidos y verifica el registro acumulativo de siete transiciones y el listado
    de comentarios intacto.

- [x] **T6. Actualización de las pruebas de HU-03 a HU-07 que hacían saltos.** RF-71, RF-80
  - Hecho cuando: se actualizan `test_tickets_update_status.py`,
    `test_tickets_modifications_sweep.py`, `test_tickets_modify_access.py`,
    `test_tickets_assign_access.py`, `test_tickets_assignment_sweep.py`,
    `test_tickets_assignee_responses.py`, `test_tickets_set_priority.py`,
    `test_tickets_invalid_utf8.py`, `test_tickets_detail_contract.py`,
    `test_ticket_comments_creation.py`, `test_ticket_comments_listing.py`,
    `test_ticket_comments_flow.py` y `test_sla_api.py`. Los tickets cerrados se crean
    recorriendo `En progreso` → `Resuelto` → `Cerrado`; los cambios de estado usan
    orígenes válidos; `Resuelto` → `Abierto` se sustituye por el retroceso permitido
    `Resuelto` → `En progreso` y por la reapertura real con `POST /reopen`. No se
    debilita ninguna aserción de estado, registro, SLA, visibilidad ni composición.

- [x] **T7. Verificación de la suite completa.**
  - Hecho cuando: con Docker (`infra-db-1` en el puerto 55432) y
    `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`, la
    suite completa queda en **935 passed, 14 skipped, 3 failed**; los 3 fallos son
    los preexistentes de precedencia 401/404 con cookie inválida
    (`test_tickets_assign_access`, `test_tickets_modify_access`), ajenos a HU-08.
    Las 70 pruebas nuevas pasan: 22 de dominio, 34 de estado, 13 de reapertura y 1 de
    flujo completo.

- [x] **T8. Índice, memoria y cierre documental.**
  - Hecho cuando: `specs/project.md` apunta a
    `specs/features/HU-08-ticket-lifecycle/` como implementada; la spec y el plan
    quedan en `implementada`/`implementado`; la nota de ampliación de
    `specs/features/HU-03-priority-status/spec.md` documenta que HU-08 sustituye la
    libertad de transiciones de RF-23; `MEMORY.md` recoge el estado, las decisiones y
    el resultado de la suite; se ejecuta `codegraph sync`. Los cambios quedan sin
    commit en `feature/Hu-06-tickets-sla` a la espera de confirmación para el PR
    contra `develop`.
