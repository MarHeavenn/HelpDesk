# Spec HU-24 — Paneles visuales y componentes de alertas

Estado: implementada

## Contexto y objetivo

El frontend ya consume datos reales de tickets (HU-22/HU-23), del dashboard de
tickets (HU-11) y del dashboard de SLA (HU-12). El backend expone además, desde
HU-10, `GET /api/tickets/requiring-attention`: los tickets activos cuyo SLA está
`en_riesgo` o `incumplido`, ordenados por urgencia. Hoy esa señal no llega a la
interfaz: el resumen «requieren atención» del dashboard se calcula agrupando por
estado (`Abierto` + `En progreso`), que no es lo mismo que un riesgo de SLA, y
las tablas muestran el objeto `sla` sin una señal visual homogénea.

La tarjeta Trello pide «construir componentes visuales para tarjetas de
indicadores, gráficos o resúmenes, listas de alertas y señales de proximidad o
incumplimiento del SLA», con datos de los servicios existentes y distinción
clara entre estados normales, próximos a vencer y vencidos. Esta historia
convierte esos contratos en componentes reutilizables y los integra en las
vistas que ya existen, sin inventar cifras ni añadir un segundo cálculo de SLA.

## Usuarios / actores

- Técnico (`tecnico`): ve el panel de alertas y las señales de SLA en el
  dashboard y en los listados; prioriza los tickets próximos a vencer o
  incumplidos.
- Administrador o supervisor (`administrador`): ve el mismo panel y las mismas
  señales para supervisar al equipo.
- Cliente (`cliente`): no consume el listado de atención (la API responde 404).
  Solo ve la señal de SLA de sus propios tickets, según HU-05.
- Visitante sin sesión: 401; el frontend cierra la sesión local y vuelve a
  `/login`, como en el resto de vistas.

## Historias de usuario

- H1: Como supervisor o técnico, quiero un panel con los tickets que requieren
  atención para detectar de un vistazo qué solicitudes necesitan acción.
- H2: Como técnico, quiero que la señal de SLA sea la misma en el dashboard, en
  los listados y en el detalle, para no reinterpretar colores en cada pantalla.
- H3: Como usuario, quiero distinguir sin ambigüedad entre un ticket en tiempo,
  uno próximo a vencer y uno vencido, incluso sin depender solo del color.
- H4: Como supervisor, quiero un resumen compacto del riesgo para entender la
  carga del equipo sin recorrer ticket por ticket.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global llega a RF-123 en
> `specs/features/HU-23-tickets-views/spec.md`; esta historia usa RF-124 a
> RF-132. Fuente: tarjeta Trello «HU-24 – Implementar paneles visuales y
> componentes de alertas» (`2tpTJODL`). Los RF se apoyan solo en contratos HTTP
> que ya existen en `backend/`: `GET /api/dashboard/tickets` (HU-11),
> `GET /api/dashboard/sla` (HU-12) y `GET /api/tickets/requiring-attention`
> (HU-10).

- RF-124: EL SISTEMA expondrá un componente de señal de SLA reutilizable que
  represente los estados `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`,
  además de «sin SLA», con color, texto e indicador gráfico. CLASIFICARÁ los
  estados en tres niveles visuales —normal (`en_tiempo`/`cumplido`), próximo a
  vencer (`en_riesgo`) y vencido (`incumplido`)— más el caso «sin SLA». SI el
  objeto `sla` del ticket tiene `breached` verdadero, ENTONCES la señal será
  «vencido»; SI `near_due` es verdadero sin `breached`, ENTONCES será «próximo a
  vencer»; EN CASO CONTRARIO usará `sla.status`. La señal no recalculará el SLA
  en el frontend: solo Presentará los campos que HU-05 ya entrega.

- RF-125: CUANDO un resumen de ticket se muestre en `/tickets`, `/mis-tickets`,
  en el detalle (HU-22) o en el panel de alertas, EL SISTEMA usará la señal de
  RF-124 en la columna de SLA, con el mismo criterio y las mismas etiquetas en
  todas esas vistas. SI el ticket no tiene prioridad (`sla` nulo), ENTONCES
  mostrará «Sin SLA» sin colorearlo como incidente. La tabla de tickets
  recientes del dashboard no muestra la señal porque `GET /api/dashboard/tickets`
  no incluye `sla` en ese bloque y esta historia no cambia el contrato.

- RF-126: CUANDO un técnico o un administrador abra `/`, EL SISTEMA mostrará un
  panel de alertas con la lista de tickets que requieren atención, obtenida de
  `GET /api/tickets/requiring-attention` (HU-10), en el orden que devuelve la
  API (`sla.due_at` ascendente, sin reordenar en cliente). Cada fila mostrará
  identificador y título, prioridad, estado, técnico asignado, la señal de
  RF-124 y el tiempo restante o el tiempo vencido, y enlazará al detalle del
  ticket ya existente (HU-22).

- RF-127: EL SISTEMA cubrirá los estados del panel de alertas: esqueleto mientras
  carga, mensaje «No hay tickets que requieran atención» cuando la colección
  esté vacía, «Reintentar» ante error de red o del servidor, y cierre de sesión
  con vuelta a `/login` ante 401. SI el actor es cliente, ENTONCES el panel no
  se consultará ni se renderizará, porque la API le responde 404.

- RF-128: EL SISTEMA mostrará en el KPI «Tickets abiertos» del dashboard una
  línea de apoyo con el número de elementos del panel de alertas
  («N requieren atención») y aplicará el tono de advertencia solo cuando sea
  mayor que cero. La cifra se derivará de la misma respuesta del panel de
  alertas; SI esa consulta falla o está en carga, ENTONCES no se mostrará la línea
  de apoyo, sin inventar un valor ni reutilizar el conteo por estado.

- RF-129: EL SISTEMA incluirá en el panel de alertas un resumen compacto con el
  número de tickets «próximos a vencer» y «vencidos», derivado de `near_due` y
  `breached` de los elementos ya recibidos, representado con dos barras
  proporcionales y sus etiquetas y conteos. No añadirá peticiones nuevas ni
  cálculos de SLA propios.

- RF-130: EL SISTEMA reutilizará los componentes y hooks existentes
  (`KpiCard`, `TicketTable`, `RecentTicketsTable`, `useDashboard`,
  `createDashboardApi`) y añadirá una única operación al contrato HTTP del
  frontend para el listado de atención. No introducirá datos mock, cifras
  hardcodeadas ni una segunda fuente de verdad para el SLA. Las cadenas nuevas
  irán en el archivo centralizado de textos, en español.

- RF-131: EL SISTEMA cumplirá WCAG 2.1 AA en los componentes nuevos: etiquetas
  accesibles, contraste suficiente en los tres niveles, información no basada
  solo en color (texto + icono/forma), navegación por teclado y adaptación de
  360 a 1440 px sin perder contenido ni funcionalidad.

- RF-132: EL SISTEMA verificará RF-124 a RF-131 con Vitest + Testing Library
  (mapeo de estados, estados de carga/vacío/error/401, derivación de la cifra
  del KPI y del resumen, y uso en las tres vistas), además de `npm run lint` y
  `npm run build` en verde. No se afirmará una prueba que no se haya ejecutado.

## Requisitos no funcionales

- Los componentes solo Presentan datos: la decisión de qué ticket requiere
  atención y el cálculo de SLA siguen en el backend (HU-05 y HU-10).
- Sin dependencias nuevas: los gráficos se resuelven con SVG/CSS, como el donut
  de HU-12 y las barras de HU-11.
- Sin acceso directo a PostgreSQL ni a tablas de otros módulos; el frontend
  consume solo contratos HTTP.
- La sesión y el rol vienen de `GET /api/auth/me` a través de `AuthContext`; no
  se introduce un selector de rol ni modo demo.

## Casos límite

- Ticket `en_riesgo` (`near_due`) con `breached` falso → señal «próximo a
  vencer».
- Ticket `breached` verdadero aunque `status` diga `en_riesgo` → señal
  «vencido» (precedencia de `breached`).
- Ticket sin prioridad → «Sin SLA», sin tono de incidente; no aparece en el
  listado de atención (RF-61 de HU-10).
- Colección de atención vacía → resumen a 0/0 y mensaje de estado vacío, sin
  dividir por cero.
- Consulta de atención con error → KPI sin línea de apoyo (RF-128) y panel con
  «Reintentar».
- 401 en la consulta de atención → cierre de sesión y redirección, sin dejar
  contenido del panel visible.
- Cliente en `/` → redirigido a `/mis-tickets` por HU-21; el panel nunca se
  monta para ese rol.
- Cambio de rol o de sesión mientras el panel está abierto → se descarta la
  consulta del rol anterior.

## Fuera de alcance

- Notificaciones activas, correo o push (HU-15/HU-16) y métricas de gestión
  (HU-18): **sus APIs no existen en este repositorio**, por lo que no se
  consumen ni se simulan.
- Gráfico semanal de tickets creados/resueltos del ADR: no hay endpoint que lo
  alimente; no se inventan datos.
- Cambios en backend, en los contratos de HU-10 a HU-12 ni en la base de datos.
- Nuevas rutas de navegación; los componentes se integran en `/`, `/tickets` y
  `/mis-tickets`.
- Contador de la campana del encabezado: no se añade. No existe API de
  notificaciones y `/notificaciones` es un marcador; la campana conserva su
  enlace actual sin cifras (decisión confirmada por el usuario).

## Criterios de finalización

- RF-124 a RF-132 verificados uno por uno con pruebas ejecutadas y su resultado
  documentado en la validación.
- `npm run test`, `npm run lint` y `npm run build` en verde en `frontend/`.
- Sin cifras ni estados inventados: todo lo que se muestra procede de las tres
  respuestas de API citadas.
- `specs/project.md` y `MEMORY.md` actualizados al terminar.

## Decisiones aprobadas (2026-11-21)

1. **Solo contratos reales (confirmado).** El listado de atención (HU-10) y los
   dashboards (HU-11/HU-12) son la única fuente. *Alternativa descartada:*
   mocks de notificaciones/métricas, que vulnerarían la constitución y HU-21
   (RF-78). Las dependencias HU-16 y HU-18 de la tarjeta quedan fuera de
   alcance hasta que existan sus APIs.
2. **Sin contador en la campana (confirmado).** La campana sigue sin cifra y
   enlaza a `/notificaciones`. *Alternativa descartada:* derivar el conteo del
   listado de atención, que mezclaría alertas de SLA con notificaciones y
   apuntaría a un marcador vacío.
3. **Dashboard y tablas (confirmado).** Panel de alertas en `/` y señal de SLA
   en `/`, `/tickets`, `/mis-tickets` y detalle. *Alternativa descartada:*
   página de alertas nueva o bloque en `/tickets`, que duplicarían el panel y
   añadirían una ruta no prevista en HU-21.
4. **Señal única y derivada.** Un solo componente para los tres niveles, sin
   recalcular SLA en cliente. *Alternativa descartada:* colores distintos por
   vista, que es el problema actual.
5. **Sin cambios de contrato en el backend.** `GET /api/dashboard/tickets` no
   expone `sla` en `recent_tickets`, así que la señal no se muestra allí.
   *Alternativa descartada:* añadir el campo al backend, que rompería el
   contrato de HU-11 y ampliaría el alcance de esta historia.

## Dudas abiertas

Ninguna pendiente. Las tres dudas iniciales fueron resueltas por el usuario y
sus decisiones quedan reflejadas en «Decisiones aprobadas», en «Fuera de
alcance» y en los RF correspondientes.

## Validación (2026-11-21)

| RF | Prueba / comprobación | Resultado |
|---|---|---|
| RF-124 | `tests/components/SlaSignal.test.tsx` (7 pruebas: cinco estados, precedencia de `breached`, icono + texto) | PASADO |
| RF-125 | `tests/components/TicketTable.test.tsx` (1), `tests/components/TicketDetailModal.test.tsx` (9), `tests/pages/TicketsPage.test.tsx` (8), `tests/pages/MyTicketsPage.test.tsx` (3) | PASADO |
| RF-126, RF-127, RF-129 | `tests/components/AlertsPanel.test.tsx` (6: orden de la API, resumen derivado, vacío, error + reintento, 401 con logout, sin consulta para cliente) | PASADO |
| RF-128 | `tests/pages/DashboardPage.test.tsx` (11: panel integrado para administrador y técnico, cifra real, sin cifra si vacío) | PASADO |
| RF-130, RF-131 | Textos en `lib/strings.ts`; sin «Demo» (comprobado en `AlertsPanel`); regiones y enlaces etiquetados; `sm:`/`lg:` para 360–1440 px; sin dependencias nuevas | PASADO |
| RF-132 | `npm run test` (25 archivos / 174 pruebas), `npm run lint` (0 errores, 0 advertencias), `npm run build` (TypeScript + Vite) | PASADO |

Nota de integración: el detalle de HU-22 es un modal, no una ruta; cada fila del
panel enlaza a `/tickets?q=<id>`, que filtra la lista y permite abrir el detalle,
según lo previsto en ADR-009 para los enlaces de notificaciones.

**Veredicto: la spec está cumplida.** No se ejecutaron pruebas de backend porque
esta historia no modifica el backend. No se sincronizó CodeGraph porque el
repositorio no tiene índice `.codegraph/`; la indexación queda a decisión del
equipo. Queda pendiente la revisión visual manual en 360/768/1024/1440 px,
heredada de HU-21.
