# Tareas HU-12 — Dashboard de cumplimiento de SLA

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde.
Verificación backend: `backend\.venv\Scripts\python.exe -m pytest` desde `backend/`. Verificación frontend: `npm run test` y `npm run build` desde `frontend/`.
Prerrequisitos: HU-21 (scaffold, cliente HTTP, AppShell y `/`) y HU-11 (dashboard de tickets en `/`).

- [ ] **T1. Fecha de resolución del ticket.** RF-97
  - Hecho cuando: `Ticket` añade `resolved_at` con `None` por defecto; `update_ticket_status` lo fija al pasar a `Resuelto`/`Cerrado` y lo limpia al volver a `Abierto`/`En progreso`, usando el mismo `now` del registro; un estado repetido no lo altera; tests de transiciones y reapertura en verde.
- [ ] **T2. Dominio de SLA.** RF-95, RF-96, RF-97
  - Hecho cuando: `sla/domain/sla.py` define la política 120/240/720/1440, el umbral del 20 %, `evaluate_sla` y los cuatro estados; tests de en tiempo, en riesgo en el límite, incumplido abierto, cumplido, incumplido cerrado, sin prioridad y cerrado sin fecha en verde.
- [ ] **T3. Contrato de tickets para SLA.** RF-100
  - Hecho cuando: `tickets/interface/sla_contract.py` expone la vista mínima (id, prioridad, estado, `created_at`, `resolved_at`, técnico) sin descripción ni datos personales; tests del contrato y de la instantánea en verde.
- [ ] **T4. Agregación de SLA.** RF-94, RF-98, RF-99, RF-101
  - Hecho cuando: `sla/application/dashboard.py` filtra por rol y periodo, evalúa cada ticket, calcula totales, `sin_sla`, `closed_without_resolved_at`, porcentajes y `by_priority` con ceros; una sola pasada; tests de fórmulas, ceros, periodos 7/30/90 y dataset vacío en verde.
- [ ] **T5. Router y validación.** RF-93, RF-94
  - Hecho cuando: `GET /api/dashboard/sla` responde 401 sin sesión, 404 para cliente, 200 para administrador/técnico y 422 para `days` fuera de 7/30/90; esquemas Pydantic con la composición del plan; tests de API en verde.
- [x] **T6. Tipos, servicio y hook del frontend.** RF-98 a RF-101
  - Hecho cuando: `types/dashboard.ts` incluye el contrato de SLA; `dashboard.api.ts` consume el endpoint con `days`; `useSlaDashboard(days)` usa TanStack Query; tests con `FakeApiClient` de éxito, cambio de periodo, 401, 404 y error de red en verde.
- [ ] **T7. Panel de cumplimiento.** RF-102
  - Hecho cuando: `/` muestra el panel con donut SVG, porcentaje al centro, leyenda de en tiempo/en riesgo/cumplido/incumplido, selector 7/30/90 con 30 por defecto y nota de `sin_sla`/`closed_without_resolved_at`; al cambiar el periodo se recarga con esqueleto; tests de valores, leyenda y selector en verde.
- [ ] **T8. Estados, accesibilidad e integración.** RF-100, RF-103, RF-104
  - Hecho cuando: el panel cubre carga, vacío y error con «Reintentar»; un 401 cierra sesión; la leyenda no depende solo del color; es responsive; convive con el dashboard de HU-11 sin romper sus pruebas; no usa `DemoBadge`; tests de estados, accesibilidad y consistencia `total_evaluated + sin_sla` en verde.
- [ ] **T9. Cierre, build y smoke.** RF-93 a RF-104
  - Hecho cuando: `pytest` del backend y `npm run test`/`npm run build` pasan; smoke manual con administrador y técnico en 7/30/90 días; `MEMORY.md` actualizado; no hay RF sin cubrir o se documenta la brecha.
