# Tareas HU-16 — Notificaciones de incumplimiento de SLA

Orden de dependencia. Verificación con pytest + `TestClient` en backend y
Vitest + Testing Library en frontend. Spec en
`specs/features/HU-16-sla-breach-notifications/spec.md` (aprobada) y plan en
`plan.md` (propuesto).

- [x] **Corrección: deduplicación concurrente en memoria.** RF-158
  - Inserción de alertas con clave bajo bloqueo del repositorio; prueba con
    12 hilos y suite focalizada de notificaciones y SLA: 44 aprobadas.

- [x] **Corrección: reutilización de cuentas demo en PostgreSQL.**
  - La semilla carga cuentas existentes sin sobrescribir contraseñas y avisa
    cuando la clave indicada no coincide. Pruebas focalizadas PostgreSQL:
    14 aprobadas; en memoria: 36 aprobadas y 1 omitida (requiere PostgreSQL).

- [x] **Corrección: documentación de tipos SLA en OpenAPI.** RF-161
  - La descripción de `NotificationResponse` documenta ambos tipos sin alterar
    la forma de la respuesta; 27 pruebas de API aprobadas en memoria.

- [ ] **T1. Dominio y repositorio de alertas.** RF-156, RF-158, RF-159
  - Hecho cuando: `tickets/domain/entities.py` añade
    `NOTIFICATION_TYPE_SLA_NEAR_DUE`, `NOTIFICATION_TYPE_SLA_BREACHED`,
    `SYSTEM_ACTOR_ID`, incorpora ambos tipos a `NOTIFICATION_TYPES` y añade
    `dedupe_key` (interno, opcional) a `TicketNotification`.
    `notification_repository.py` añade `find_by_dedupe_key`.
    `test_notifications_domain.py` cubre el catálogo de siete tipos, el valor
    por defecto de `dedupe_key` y la búsqueda por clave.

- [ ] **T2. Contrato de administradores y caso de uso.** RF-156, RF-157, RF-158, RF-163
  - Hecho cuando: `identity/application/administrators.py` filtra
    administradores activos por empresa y devuelve solo ids;
    `identity/interface/administrators_contract.py` expone
    `list_company_administrator_ids`;
    `tickets/application/generate_sla_alerts.py` implementa el análisis con un
    único `now`, ámbito por rol, descarte de resueltos/sin prioridad, cálculo por
    contrato de SLA, destinatarios (admins activos + técnico), deduplicación por
    `(ticket, tipo, destinatario, due_at)` y actor de sistema.
    `test_sla_notifications.py` cubre cada regla.

- [ ] **T3. Router y contrato HTTP.** RF-160, RF-161
  - Hecho cuando: `notifications_router.py` ejecuta el análisis antes de listar
    y antes de contar no leídas, sin tocar las acciones de lectura;
    `_user_response` resuelve `system` como `{id: "system", name: "Sistema"}`;
    las cuatro rutas conservan su forma y sus códigos.
    `test_sla_notifications_api.py` verifica generación, deduplicación,
    visibilidad por rol/empresa, 401 y OpenAPI.

- [ ] **T4. Flujo y suite backend.** RF-156 a RF-161
  - Hecho cuando: `test_sla_notifications_flow.py` recorre ticket activo en
    riesgo → alerta, paso a incumplido → segunda alerta sin duplicar, y ticket
    resuelto → sin alerta nueva. La suite completa en memoria queda en verde
    (salvo PostgreSQL omitido) y se ejecuta con
    `--ignore=tests/test_dev_server_seed.py` mientras ese archivo no rastreado
    siga en curso.

- [ ] **T5. Frontend.** RF-162
  - Hecho cuando: `types/notification.ts` incluye los dos tipos;
    `lib/notifications.ts` asigna icono y mensaje con fecha;
    `NotificationGlyph.tsx` muestra iconos distintos; `lib/strings.ts`
    centraliza etiquetas y mensajes; la página, la campana y el dashboard
    muestran las alertas con el actor «Sistema». `npm test` cubre los mensajes,
    iconos y render.

- [ ] **T6. Demostración, documentación y cierre.** RF-164
  - Hecho cuando: `dev_server.py` siembra un cliente y tickets de ejemplo
    (riesgo, incumplido, en tiempo y resuelto) de forma idempotente; el README
    explica el paso a paso; se ejecutan backend, frontend, `npm test`,
    `npm run build` y `npm run lint`; se actualizan `specs/project.md` y
    `MEMORY.md`; la spec y el plan pasan a implementada/implementado; se ejecuta
    `codegraph sync`; se verifica en el navegador con administrador y técnico.
