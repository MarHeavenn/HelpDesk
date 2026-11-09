# Tareas HU-09 — Registrar historial y trazabilidad del ticket

Orden de dependencia. 20-30 min por tarea. Verificación con pytest + TestClient
(sin frontend). Spec en `specs/features/HU-09-ticket-history/spec.md` (aprobada)
y plan en `plan.md` (propuesto).

- [x] **T1. Modelo de evento y acciones del historial.** RF-82, RF-83
  - Hecho cuando: `tickets/domain/entities.py` añade `TicketHistoryEvent`
    (inmutable, con `action`, `actor_id`, `occurred_at`, `previous_value`,
    `new_value`, `previous_assignee_id`, `new_assignee_id` y `comment`) y las
    constantes `HISTORY_ACTION_CREATED`, `HISTORY_ACTION_ASSIGNED`,
    `HISTORY_ACTION_REASSIGNED`, `HISTORY_ACTION_PRIORITY`,
    `HISTORY_ACTION_STATUS` y `HISTORY_ACTION_COMMENT`.
    `test_ticket_history_domain.py` verifica la forma de la entidad, los
    valores exactos de las constantes y que no se expone ningún campo interno
    adicional.

- [x] **T2. Resolución autorizada del ticket para el historial.** RF-84, RF-85
  - Hecho cuando: `tickets/application/get_historyable_ticket.py` comprueba
    primero el rol de gestión (`tecnico`/`administrador`) y delega en
    `get_ticket_detail` el formato UUID y la existencia, con
    `TicketNotFoundError`/404 uniforme. No comprueba el estado `Cerrado`.
    Las pruebas cubren administrador, técnico, cliente con ticket propio,
    ticket inexistente, identificador inválido y ticket cerrado.

- [x] **T3. Caso de uso del historial y orden determinista.** RF-82, RF-86, RF-87
  - Hecho cuando: `tickets/application/list_ticket_history.py` reúne creación,
    modificaciones, asignaciones y comentarios en `TicketHistoryEvent`, mapea
    cada `field` a su acción, distingue asignación de reasignación y ordena por
    `(occurred_at, source_rank, insertion_index)` con creación=0, asignación=1,
    prioridad=2, estado=3 y comentario=4. No muta ninguna fuente. Las pruebas
    unitarias cubren el orden con empates, la estabilidad al repetir y la
    ausencia de eventos para no-ops (la lista se construye solo con los
    registros existentes).

- [x] **T4. Esquemas HTTP, router y registro en la aplicación.** RF-81, RF-83, RF-89
  - Hecho cuando: `tickets/interface/schemas.py` añade `HistoryUserResponse`
    (`id`, `name` opcional) y `HistoryEventResponse` con los ocho campos del
    plan, siempre presentes. `tickets/interface/history_router.py` expone
    `GET /api/tickets/{ticket_id}/history`, traduce `TicketNotFoundError` a
    404, resuelve actor y técnicos con `get_user_summary` (nombre `null` si no
    se resuelve), serializa fechas en ISO 8601 UTC e ignora parámetros
    desconocidos. `main.py` incluye el router. La prueba de OpenAPI confirma
    que la única ruta nueva es la de historial y que `TicketResponse` y los
    resúmenes no cambian.

- [x] **T5. Pruebas de contenido de eventos en la API.** RF-82, RF-83, RF-87
  - Hecho cuando: `test_ticket_history_api.py` verifica creación (un solo
    evento), asignación inicial y reasignación (técnicos anterior/nuevo),
    prioridad inicial y cambio, secuencia de estados y reapertura, comentario
    con autor/contenido/fecha, y que repetir prioridad, repetir estado,
    repetir técnico, transición inválida, ticket cerrado y comentario inválido
    no añaden eventos. Se comprueba el conjunto exacto de campos de cada
    evento y que los valores anteriores/nuevos son los esperados.

- [x] **T6. Pruebas de visibilidad, errores y lectura de tickets cerrados.** RF-84, RF-85, RF-88, RF-89
  - Hecho cuando: las pruebas cubren 401 sin sesión antes de 404; 404 uniforme
    para cliente, ticket inexistente e identificador inválido; 200 con
    historial completo en ticket `Cerrado` sin 409 ni mutación; evento
    conservado con `name: null` cuando el usuario no se resuelve; parámetros
    de consulta desconocidos ignorados; y ausencia de campos internos
    (`actor_id`, `changed_at`, `assigned_at`) en las respuestas.

- [x] **T7. Flujo completo entre historias.** RF-82, RF-86, RF-87
  - Hecho cuando: `test_ticket_history_flow.py` recorre HU-02 (creación) →
    HU-04 (asignación) → HU-03/HU-05 (prioridad) → HU-07 (comentario) →
    HU-08 (avance, resolución, cierre, reapertura y nuevo avance) y comprueba
    la secuencia exacta de acciones, actores, valores y fechas, sin duplicados,
    sin eventos de operaciones rechazadas y sin que la consulta mute el
    ticket ni los registros.

- [x] **T8. Ajuste de pruebas existentes y suite completa.** RF-89
  - Hecho cuando: se actualizan
    `test_assignment_log.py::test_no_public_route_exposes_the_assignment_log`,
    `test_tickets_modifications_domain.py::test_no_public_route_exposes_the_modification_log`
    y el barrido de `test_tickets_assignment_sweep.py` para permitir
    exactamente `GET /api/tickets/{ticket_id}/history`, manteniendo la
    prohibición de `log`/`record`, de rutas de historial no documentadas y de
    los campos internos (`actor_id`, `changed_at`, `assigned_at`,
    `previous_assignee_id`, `new_assignee_id`) en los esquemas. También se
    ajusta `test_sla_live_config.py` para recorrer el flujo válido de HU-08 y
    reabrir con `POST /reopen`, y se corrige `reopen_ticket` para limpiar
    `resolved_target_minutes` (interacción HU-08/HU-14). La suite completa con
    `DATABASE_URL` queda en **1154 passed, 3 failed**, con solo los tres
    fallos preexistentes de precedencia 401/404 con cookie inválida, ajenos a
    HU-09.

- [x] **T9. Documentación, memoria e índice.** RF-81 a RF-90
  - Hecho cuando: la spec queda en `implementada`, el plan en `implementado`,
    todas las tareas marcadas; `specs/project.md` apunta a
    `specs/features/HU-09-ticket-history/` como implementada; `MEMORY.md`
    recoge el estado, las decisiones y el resultado de la suite; y se ejecuta
    `codegraph sync`.
