# Tareas HU-15 — Notificaciones de tickets

Orden de dependencia. 20-30 min por tarea. Verificación con pytest + TestClient
en backend y Vitest + Testing Library en frontend. Spec en
`specs/features/HU-15-ticket-notifications/spec.md` (aprobada) y plan en
`plan.md` (propuesto).

- [x] **T1. Dominio y repositorio de notificaciones.** RF-144, RF-146
  - Hecho cuando: `tickets/domain/entities.py` añade las constantes
    `NOTIFICATION_TYPE_*`, `NOTIFICATION_TYPES` y
    `NOTIFICATION_VIEW_ALL_ROLES`, y la entidad `TicketNotification` con
    `id`, `company_id`, `recipient_id`, `ticket_id`, `ticket_title`, `type`,
    `actor_id`, `previous_value`, `new_value`, `created_at` y `read_at`.
    `tickets/infrastructure/notification_repository.py` añade
    `InMemoryNotificationRepository` (`add`, `list_by_recipient`,
    `list_by_company`, `find_by_id`, `count`, `clear`) y su singleton.
    `test_notifications_domain.py` cubre constantes, campos, defaults y orden
    descendente con empates deterministas.

- [x] **T2. Generación de notificaciones y destinatarios.** RF-144, RF-145, RF-146
  - Hecho cuando: `tickets/application/notify_ticket_event.py` crea una
    notificación por destinatario (solicitante y técnico asignado), omite al
    actor, deduplica, respeta el ticket sin técnico y copia `company_id`,
    título, tipo, actor, valores anterior/nuevo y fecha UTC. Rechaza tipos
    desconocidos. Las pruebas unitarias cubren asignación, reasignación,
    solicitante == técnico, sin técnico, actor implicado y tipos correctos de
    estado, resolución y reapertura.

- [x] **T3. Visibilidad y lectura de notificaciones.** RF-147, RF-148, RF-149, RF-150, RF-151
  - Hecho cuando: `tickets/application/list_notifications.py` aplica la
    visibilidad por rol y empresa (admin/supervisor todas las de su
    `company_id`; técnico/cliente solo las dirigidas a ellos) y devuelve orden
    descendente. `tickets/application/notification_reads.py` implementa
    `count_unread`, `mark_notification_read` (idempotente, 404 uniforme para
    ajena/inexistente/id inválido) y `mark_all_notifications_read` (solo
    propias, idempotente). Las pruebas cubren cada rol, aislamiento por
    empresa y repetición de operaciones.

- [x] **T4. Esquemas, router y registro en la aplicación.** RF-147, RF-149, RF-150, RF-151, RF-154
  - Hecho cuando: `tickets/interface/schemas.py` añade
    `NotificationTicketResponse`, `NotificationUserResponse`,
    `NotificationResponse`, `UnreadCountResponse` y `MarkAllReadResponse`.
    `tickets/interface/notifications_router.py` expone las cuatro rutas con
    401 primero, 404 uniforme y nombres resueltos con `get_user_summary`.
    `main.py` registra el router. La prueba de contrato confirma las cuatro
    rutas, los campos exactos y la ausencia de `company_id`, `actor_id` y
    `recipient_id` en las respuestas.

- [x] **T5. Enganche en los casos de uso de ticket.** RF-144, RF-145
  - Hecho cuando: `assign_ticket`, `update_ticket_status` y `reopen_ticket`
    aceptan un colaborador opcional `notify` al final y lo invocan solo tras
    aplicar el cambio y registrar el evento de origen. `assign_ticket`
    distingue asignación de reasignación y conserva el nombre anterior;
    `update_ticket_status` distingue resolución, reapertura y cambio de
    estado; `reopen_ticket` emite reapertura. `tickets/interface/router.py`
    pasa `notify_ticket_event`. Las pruebas existentes de HU-03/04/08 siguen
    pasando sin inyectar el colaborador.

- [x] **T6. Pruebas de API, flujo y suite backend.** RF-144 a RF-155
  - Hecho cuando: `test_notifications_api.py` cubre las cuatro rutas, 401,
    404, visibilidad por rol y empresa, contador, marcar una/todas,
    idempotencia, parámetros desconocidos y OpenAPI. `test_notifications_flow.py`
    recorre creación → asignación → estado → resolución → cierre → reapertura
    y verifica tipos, destinatarios, valores y ausencia de avisos por
    prioridad/comentario/no-op. La suite completa con `DATABASE_URL` queda en
    verde salvo los tres fallos preexistentes de precedencia 401/404.

- [x] **T7. Tipos, API y utilidades del frontend.** RF-146, RF-152
  - Hecho cuando: `types/notification.ts` define el contrato;
    `api/notifications.api.ts` implementa `list`, `unreadCount`, `markRead`
    y `markAllRead` con id codificado; `lib/notifications.ts` centraliza el
    mensaje por tipo y la clave de icono. Las pruebas de API y de utilidades
    cubren URLs, métodos y los cinco mensajes.

- [x] **T8. Hooks, campana y armazón.** RF-149, RF-152
  - Hecho cuando: `hooks/useNotifications.ts` expone listado y contador con
    `refetchInterval: 30_000` y `refetchOnWindowFocus: true`, y mutaciones que
    invalidan ambas consultas. `NotificationBell` muestra el badge (`9+`),
    enlaza a `/notificaciones` y tiene etiqueta accesible con el número.
    `Topbar` y `AppShell` aceptan `notificationsApi?` y lo propagan. Las
    pruebas cubren badge en 0, 3 y `9+`, enlace y etiqueta.

- [x] **T9. Página `/notificaciones`.** RF-152
  - Hecho cuando: `pages/NotificationsPage.tsx` muestra listado, punto de no
    leída, filtro «Todas / No leídas», marcar una, marcar todas, estados de
    carga, vacío, vacío por filtro, error/reintento y 401. `routes.tsx`
    sustituye el placeholder. Las pruebas cubren cada estado y las acciones
    contra una API falsa.

- [x] **T10. Panel de notificaciones en el dashboard.** RF-153
  - Hecho cuando: `components/dashboard/NotificationsCard.tsx` muestra las
    cinco notificaciones visibles más recientes con enlace «Ver todas»,
    estados de carga, vacío y error. `DashboardPage` acepta
    `notificationsApi?` y renderiza la tarjeta para administrador, supervisor
    y técnico. Las pruebas cubren el límite de cinco, el enlace y los estados.

- [x] **T11. Verificación frontend y ajuste de pruebas existentes.** RF-152, RF-153, RF-155
  - Hecho cuando: se ajustan `AppShell.test.tsx`, `DashboardPage.test.tsx` y
    el stub de `routes/guards.test.tsx` para inyectar/resolver notificaciones
    sin llamadas reales. `npm test`, `npm run build` y `npm run lint` quedan
    en verde.

- [x] **T12. Documentación, memoria e índice.** RF-144 a RF-155
  - Hecho cuando: la spec queda en `implementada`, el plan en `implementado`,
    todas las tareas marcadas; `specs/project.md` apunta a
    `specs/features/HU-15-ticket-notifications/` como implementada; `MEMORY.md`
    recoge decisiones, estado y resultado de las suites; y se ejecuta
    `codegraph sync`.

## Estado de verificación

- Backend (modo memoria, sin `DATABASE_URL`):
  `1536 passed, 39 skipped` con
  `backend/.venv/Scripts/python.exe -m pytest -q --ignore=tests/test_dev_server_seed.py`.
  Los 39 omitidos requieren PostgreSQL; Docker Desktop no estaba en ejecución,
  así que la corrida con `DATABASE_URL` queda pendiente.
- Frontend: `npm test` → 31 archivos y 214 pruebas en verde; `npm run build` y
  `npm run lint` en verde.
- `tests/test_dev_server_seed.py` es un archivo no rastreado del usuario que no
  compila (`DEMO_TICKETS`); se excluyó de la verificación sin modificarlo.

