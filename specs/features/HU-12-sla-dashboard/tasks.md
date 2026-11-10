# Tareas HU-12 — Dashboard de cumplimiento de SLA

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde.
Verificación backend: `& ".venv\Scripts\python.exe" -m pytest backend -q` desde la raíz del repositorio. Verificación frontend: `npm run test` y `npm run build` desde `frontend/`.
Prerrequisitos: HU-21 (scaffold, cliente HTTP, AppShell y `/`), HU-11 (dashboard de tickets en `/`) y HU-05/HU-14 (cálculo y configuración de SLA ya implementados en `develop`).
No se repiten las tareas antiguas de `resolved_at` ni del dominio de SLA: ya existen en `develop` por HU-05/HU-14 y HU-12 solo las reutiliza.

- [ ] **T1. Contrato de lectura de tickets para SLA.** RF-100
  - Hecho cuando: `tickets/interface/sla_contract.py` expone `SlaTicketView` y `list_sla_tickets()` con id, prioridad, estado, `created_at`, `resolved_at`, `resolved_target_minutes` y técnico; no expone descripción, solicitante ni datos personales; tests del contrato en verde.
- [ ] **T2. Agregación de SLA.** RF-94, RF-98, RF-99, RF-101
  - Hecho cuando: `sla/application/dashboard.py` filtra por rol y periodo, reutiliza `calculate_ticket_sla` para cada ticket, cuenta `sin_sla` y `closed_without_resolved_at`, calcula totales, porcentajes y `by_priority` con ceros; una sola pasada; tests de fórmulas, ceros, periodos 7/30/90, límites y dataset vacío en verde.
- [ ] **T3. Router y validación.** RF-93, RF-94
  - Hecho cuando: `GET /api/dashboard/sla` responde 401 sin sesión, 404 para cliente, 200 para administrador/técnico y 422 para `days` fuera de 7/30/90; esquemas Pydantic con la composición del plan; tests de API en verde.
- [x] **T4. Tipos, servicio y hook del frontend.** RF-98 a RF-101
  - Hecho cuando: `types/dashboard.ts` incluye el contrato de SLA; `dashboard.api.ts` consume el endpoint con `days`; `useSlaDashboard(days)` usa TanStack Query; tests con `FakeApiClient` de éxito, cambio de periodo, 401, 404 y error de red en verde.
- [ ] **T5. Panel de cumplimiento.** RF-102
  - Hecho cuando: `/` muestra el panel con donut SVG, porcentaje al centro, leyenda de en tiempo/en riesgo/cumplido/incumplido, selector 7/30/90 con 30 por defecto y nota de `sin_sla`/`closed_without_resolved_at`; al cambiar el periodo se recarga con esqueleto; tests de valores, leyenda y selector en verde.
- [ ] **T6. Estados, accesibilidad e integración.** RF-100, RF-103, RF-104
  - Hecho cuando: el panel cubre carga, vacío y error con «Reintentar»; un 401 cierra sesión; la leyenda no depende solo del color; es responsive; convive con el dashboard de HU-11 sin romper sus pruebas; no usa `DemoBadge`; tests de estados, accesibilidad y consistencia `total_evaluated + sin_sla` en verde.
- [ ] **T7. Cierre, build y smoke.** RF-93 a RF-104
  - Hecho cuando: `pytest` del backend y `npm run test`/`npm run build` pasan; smoke manual con administrador y técnico en 7/30/90 días; `MEMORY.md` actualizado; no hay RF sin cubrir o se documenta la brecha.
