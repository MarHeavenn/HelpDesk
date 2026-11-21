# Tareas HU-24 — Paneles visuales y componentes de alertas

Orden de dependencia. Una tarea cada vez: prueba en rojo → código en verde →
marcar la casilla → `codegraph sync` (si hay índice) → `MEMORY.md`.

- [x] **T1. Contrato y hook del listado de atención.** RF-126
  - Hecho cuando: `createDashboardApi` expone `getAttention()` contra
    `/api/tickets/requiring-attention`; `dashboardKeys.attention` y
    `useAttentionAlerts(api)` existen con `retry: false`; las pruebas de
    `tests/api/dashboard.api.test.ts` y `tests/hooks/useDashboard.test.tsx`
    comprueban la URL, la composición `TicketSummary[]` y la clave de caché, y
    pasan. Sin cambios en backend.

- [x] **T2. Componente `SlaSignal` y sus textos.** RF-124, RF-130, RF-131
  - Hecho cuando: el componente recibe `sla: TicketSla | null`, deriva los
    niveles normal / próximo a vencer / vencido / sin SLA con precedencia de
    `breached` sobre `near_due` y sobre `status`, y anuncia el nivel por texto e
    icono/forma además del color. Los textos nuevos están en `lib/strings.ts`.
    `tests/lib/slaSignal.test.ts` (o el archivo de componentes equivalente)
    cubre los cinco casos y pasa en rojo antes del código.

- [x] **T3. Señal única en tablas y detalle.** RF-125
  - Hecho cuando: `TicketTable` y el bloque de SLA de `TicketDetailModal` usan
    `SlaSignal`; la fecha de vencimiento se mantiene; un ticket sin prioridad
    muestra «Sin SLA» sin tono de incidente. Las pruebas existentes de
    `/tickets`, `/mis-tickets` y detalle siguen pasando y se añade una
    comprobación explícita del mismo criterio en dos vistas.

- [x] **T4. Panel de alertas con resumen y estados.** RF-126, RF-127, RF-129
  - Hecho cuando: `AlertsPanel` consume `useAttentionAlerts`, respeta el orden
    de la API, muestra el resumen «próximos a vencer» / «vencidos» derivado de
    los elementos recibidos, enlaza cada fila al detalle y cubre carga, vacío,
    error con Reintentar y 401 con logout. No consulta si el usuario es cliente.
    `tests/components/AlertsPanel.test.tsx` pasa con los cuatro estados y el
    caso sin rol de gestión.

- [x] **T5. Línea de apoyo del KPI «Abiertos».** RF-128
  - Hecho cuando: `KpiCard` acepta un `hint` opcional con tono; `DashboardPage`
    muestra «N requieren atención» solo cuando la consulta de atención devolvió
    datos y el número es mayor que cero; con error o en carga no aparece la
    línea y nunca se reutiliza el conteo por estado.
    `tests/pages/DashboardPage.test.tsx` pasa con los tres escenarios.

- [x] **T6. Integración y accesibilidad responsive.** RF-130, RF-131
  - Hecho cuando: el panel queda montado en `/` para administrador y técnico;
    no hay cifras hardcodeadas ni etiqueta «Demo»; el resumen usa barras sin
    dependencias nuevas; los componentes son navegables por teclado, tienen
    etiquetas accesibles y conservan contenido de 360 a 1440 px. Revisión
    manual o por pruebas de roles documentada.

- [x] **T7. Verificación y cierre.** RF-132
  - Hecho cuando: `npm run test`, `npm run lint` y `npm run build` pasan en
    `frontend/`; se recorre la spec RF por RF con el resultado de cada prueba;
    `specs/project.md` y `MEMORY.md` quedan actualizados y la spec pasa a
    «implementada».
