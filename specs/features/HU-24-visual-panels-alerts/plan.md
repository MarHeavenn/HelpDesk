# Plan HU-24 — Paneles visuales y componentes de alertas

Estado: aprobado

## Alcance técnico

Historia **solo de frontend**. No se toca `backend/`, no se crean rutas HTTP
nuevas ni se modifica la base de datos. Se reutilizan tres contratos que ya
existen:

| Contrato | Uso en HU-24 | RF |
|---|---|---|
| `GET /api/tickets/requiring-attention` (HU-10) | Listado del panel de alertas; cifra del KPI y del resumen | RF-126 a RF-129 |
| `GET /api/dashboard/tickets` (HU-11) | KPIs y distribuciones ya integradas; se añade la línea de apoyo | RF-128 |
| `GET /api/dashboard/sla` (HU-12) | Panel de cumplimiento ya integrado (sin cambios) | RF-124 ( coherencia de estados ) |

El resumen de tickets recientes del dashboard **no se modifica**: su contrato no
incluye `sla` (decisión 5 de la spec).

## Capas y archivos afectados

- `frontend/src/types/ticket.ts`: sin cambios de contrato; se reutiliza
  `TicketSla` y `TicketSummary`.
- `frontend/src/api/dashboard.api.ts`: una única operación nueva,
  `getAttention(): Promise<TicketSummary[]>`, que llama a
  `/api/tickets/requiring-attention`. Se agrupa aquí porque el único consumidor
  es el dashboard y así `DashboardPage` sigue recibiendo un solo `api` inyectable.
- `frontend/src/hooks/useDashboard.ts`: `dashboardKeys.attention` y
  `useAttentionAlerts(api)` con `retry: false`, igual que los hooks actuales.
  React Query deduplica la consulta entre el panel y el KPI.
- `frontend/src/components/ui/SlaSignal.tsx` **(nuevo)**: señal reutilizable.
  Recibe `sla: TicketSla | null`, deriva el nivel (`normal` / `riesgo` /
  `vencido` / `sin_sla`) con precedencia de `breached` sobre `near_due` y sobre
  `status`, y pinta color + texto + icono/forma. No recalcula fechas ni SLA.
- `frontend/src/components/dashboard/AlertsPanel.tsx` **(nuevo)**: panel con
  el resumen compacto (RF-129) y la lista (RF-126), estados de carga, vacío,
  error y 401 (RF-127). Usa `useAttentionAlerts`.
- `frontend/src/components/dashboard/KpiCard.tsx`: parámetro opcional `hint`
  (texto + tono) para la línea de apoyo del RF-128, sin cambiar su uso actual.
- `frontend/src/components/tickets/TicketTable.tsx`: sustituye el badge local de
  SLA por `SlaSignal`, conservando la fecha de vencimiento al lado.
- `frontend/src/components/tickets/TicketDetailModal.tsx`: usa `SlaSignal` en
  el bloque de SLA del detalle.
- `frontend/src/pages/DashboardPage.tsx`: monta `AlertsPanel` y pasa la cifra de
  atención como `hint` del KPI «Abiertos».
- `frontend/src/lib/strings.ts`: textos nuevos en español, centralizados.
- `frontend/tests/`: fixtures y pruebas nuevas/ajustadas (ver «Estrategia de
  pruebas»).

## Contratos entre piezas

- `SlaSignal` es puro: no consulta nada, solo presenta. Las vistas le pasan el
  `sla` que ya recibieron de la API.
- `AlertsPanel` no ordena ni filtra la colección: respeta el orden de la API
  (HU-10 RF-65). Solo deriva los dos contadores del resumen de `near_due` y
  `breached` de los elementos ya recibidos.
- El 401 lo gestiona `AlertsPanel` (logout + redirección vía `AuthContext`), al
  igual que `SlaCompliancePanel`. `DashboardPage` solo lee `data?.length` para el
  KPI: si no hay datos, no muestra la línea de apoyo.
- El cliente nunca monta `AlertsPanel`: `DashboardPage` ya redirige a
  `/mis-tickets` para ese rol según HU-21. El panel tampoco consulta si se
  renderiza con un usuario sin rol de gestión.

## Decisiones justificadas

1. **Un solo componente de señal** en lugar de estilos por vista.
   *Descartada:* duplicar `SLA_STYLES` en cada tabla; es la causa de que hoy el
   mismo estado se pinte de forma distinta.
2. **Añadir `getAttention` al facade del dashboard** en vez de inyectar un
   segundo API en `DashboardPage`. *Descartada:* dos props de API; complicaría
   todas las pruebas existentes sin aportar valor.
3. **Derivar la cifra del KPI de la misma query del panel**, no del conteo por
   estado de HU-11. *Descartada:* reutilizar `by_status`, que mide otra cosa
   (estado del ticket, no riesgo de SLA) y daría un número engañoso.
4. **Sin librería de gráficos**: barras con `div`/SVG, como HU-11 y HU-12.
   *Descartada:* añadir una dependencia para dos barras, en contra de la
   constitución.
5. **Sin contador en la campana** y sin mocks de HU-16/HU-18 (decisiones 1 y 2
   de la spec).

## Estrategia de pruebas

Runner acordado: Vitest + Testing Library (jsdom), ya configurado en
`frontend/`. Se usa el fake de API inyectable y `renderApp` de
`tests/helpers/renderApp.tsx`; nunca `fetch` real.

- `tests/lib/slaSignal.test.ts` (nuevo): tabla de casos de RF-124 — `en_tiempo`,
  `cumplido`, `en_riesgo`, `breached` con `status` engañoso, `sla` nulo — y
  comprobación de que el nivel se anuncia por texto y no solo por clase.
- `tests/components/AlertsPanel.test.tsx` (nuevo): datos y orden de la API
  (RF-126), resumen derivado (RF-129), vacío, error + Reintentar y 401 con
  logout (RF-127). Se añade un builder de atención en
  `tests/helpers/dashboardFixtures.ts`.
- `tests/api/dashboard.api.test.ts` y `tests/hooks/useDashboard.test.tsx`:
  nueva operación y query key.
- `tests/components/TicketTable.test.tsx` / `tests/pages/TicketsPage.test.tsx` /
  `tests/pages/MyTicketsPage.test.tsx`: la señal aparece con el mismo criterio
  (RF-125).
- `tests/pages/DashboardPage.test.tsx`: panel integrado y línea de apoyo del
  KPI, incluido el caso sin datos de atención (RF-128).
- `npm run test`, `npm run lint` y `npm run build` en verde.

## Cobertura RF → pieza

| RF | Pieza / prueba |
|---|---|
| RF-124 | `SlaSignal` + `tests/lib/slaSignal.test.ts` |
| RF-125 | `TicketTable`, `TicketDetailModal`, `SlaSignal` + pruebas de listados y detalle |
| RF-126, RF-127 | `AlertsPanel`, `useAttentionAlerts` + `AlertsPanel.test.tsx` |
| RF-128 | `KpiCard` + `DashboardPage` + `DashboardPage.test.tsx` |
| RF-129 | `AlertsPanel` + `AlertsPanel.test.tsx` |
| RF-130 | `dashboard.api.ts`, `strings.ts`, hooks y componentes existentes |
| RF-131 | Pruebas de accesibilidad/roles en los componentes nuevos + revisión responsive |
| RF-132 | `npm run test`, `npm run lint`, `npm run build` |
