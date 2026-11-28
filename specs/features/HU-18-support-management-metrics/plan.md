# Plan HU-18 — Métricas de gestión de soporte

Estado: aprobado explícitamente por el usuario con «si»; implementación por tarea.

## Base y límites de esta fase

- Spec aprobada por el usuario con «si» tras QA aprobable sin bloqueos: RF-179–RF-191. Posteriormente aprobó también este plan y sus tareas con «si»; no se alteran requisitos.
- Rama de trabajo indicada: `feature/HU-18-support-management-metrics`, desde `develop` `0263108`; no cambiar rama ni tocar agentes/configuración locales.
- Se mantiene el monolito modular, las capas y las dependencias existentes. No se necesitan migraciones, tablas de agregados, otro módulo, jobs ni nuevos paquetes.
- Clasificación HIGH vigente, riesgo alto por autorización/aislamiento; se reutiliza sin reclasificar. Las propuestas por tarea están en `tasks.md`; no asignan modelos ni ejecutores.
- La planificación no ejecutó código ni pruebas. La evidencia de implementación se registra por tarea en `tasks.md`.

## Evidencia reutilizada y comprobaciones dirigidas

- Se reutiliza la exploración de tickets, fechas, reapertura, SLA y autorización de las fases anteriores, y la comprobación Graphify completada por QA; no se repite.
- CodeGraph confirmó el contrato de SLA, la dependencia de sesión con empresa, la composición de routers, el dashboard y el cliente frontend. `frontend/package.json` confirma Vitest/Testing Library y los comandos de lint/build existentes.
- `Ticket` contiene creación, resolución, objetivo conservado, prioridad, estado y empresa. No es necesario añadir fecha de cierre: ninguna fórmula de HU-18 la utiliza.
- `get_ticket_sla` consulta la política vigente antes del cálculo; no sirve directamente para RF-191. `calculate_sla` permite evaluar con un objetivo explícito sin consultar configuración; se conservará intacto.
- El repositorio actual de tickets es compartido y en memoria. `list_all()` ordena por creación; ordenar datos inválidos o no comparables puede fallar antes de aplicar las exclusiones de la spec. HU-18 necesita una lectura adicional sin ordenación y sin cambiar las lecturas anteriores.
- Los dashboards existentes pasan empresa opcional a sus agregadores; HU-18 no heredará una ausencia de empresa como acceso global. La aplicación comprobará rol/empresa antes de leer tickets.

## Arquitectura y responsabilidades

El agregado pertenece a **tickets**: ese módulo posee el conjunto y el ciclo de vida. **sla** aporta únicamente la evaluación pura de una resolución con objetivo conservado. **identity** mantiene la autenticación. El frontend presenta el agregado, no reconstruye métricas a partir de listados ni evalúa SLA.

| Parte | Responsabilidad y límite | RF de HU-18 |
|---|---|---|
| `tickets/domain/support_metrics.py` | Registros inmutables mínimos, validez de instantes/duración, clasificación actual, muestras y fórmulas del agregado; sin HTTP, repositorios ni importaciones de otros módulos | 181–188, 191 |
| `tickets/infrastructure/ticket_repository.py` | Lectura aditiva `snapshot_for_metrics`: copia de los campos mínimos de todos los tickets, sin ordenar, filtrar por fecha ni paginar; no cambia `list_all()` ni los consumidores existentes | 180, 181, 184, 188 |
| `tickets/application/support_metrics.py` | Autorizar administrador con empresa antes de leer; filtrar por empresa almacenada; coordinar una instantánea y el evaluador SLA inyectado; producir un solo resultado | 179–188, 191 |
| `sla/application/frozen_resolution.py` y `sla/interface/contract.py` | Operación aditiva que evalúa objetivo conservado válido, sin consultar política vigente; reutiliza el dominio SLA existente | 185, 186, 191 |
| `tickets/interface/metrics_router.py` y `main.py` | Resolver sesión; adaptar y componer contratos; inyectar lectura/evaluación; serializar resultado y traducir errores. Sin reglas de autorización o fórmulas en HTTP | 179, 180, 188–190 |
| API/tipos/hook específicos frontend | Obtener solo el agregado autorizado, conservar nulos, aislar resultados por montaje/actor y gestionar carga/error/reintento/sesión | 179, 188–191 |
| Panel nuevo dentro de `DashboardPage` | Solo administrador; cinco indicadores, notas y muestras; no sustituye paneles de HU-11/HU-12 ni crea rutas | 179, 189, 190 |

Los nombres nuevos son destinos propuestos del plan, no archivos ya implementados. `companies` y `assignment` no requieren cambios. No se añaden accesos a tablas internas ajenas.

### Flujo y composición de contratos

1. `main.py` registra el router nuevo de tickets.
2. El router obtiene identidad, rol y empresa con la dependencia existente de `identity/interface/dependencies.py`; una sesión inválida termina en 401.
3. El caso de uso de tickets recibe ese contexto y comprueba administrador y empresa antes de invocar la lectura. Ausencia de empresa o rol distinto: error de acceso uniforme, sin consultar tickets ni SLA.
4. La lectura devuelve una sola colección de registros inmutables con `id`, `company_id`, `status`, `priority`, `created_at`, `resolved_at` y `resolved_target_minutes`. No incluye títulos, descripción, personas ni fecha de cierre.
5. La aplicación excluye empresas ajenas y registros sin empresa antes de validar fechas o llamar al evaluador. Obtiene conteos y muestras del mismo conjunto, sin lecturas por indicador.
6. Solo para candidatos finalizados con fechas válidas y objetivo conservado válido, invoca el evaluador inyectado. El router adapta esos valores al contrato de SLA; el caso de uso no importa dominios/repositorios de SLA.
7. El dominio de tickets produce el agregado. El router lo serializa sin exponer registros individuales.

**Contrato interno aditivo de SLA:** `evaluate_frozen_resolution`, exportado desde `sla/interface/contract.py`, recibe prioridad, creación, resolución y objetivo conservado, y devuelve `True` (cumplido), `False` (incumplido) o `None` (no evaluable). No recibe estado del ticket, empresa, usuario ni acceso a repositorios. SLA comprueba prioridad admitida, fechas comparables y objetivo entero positivo; ausencia o invalidez devuelve `None`. La selección de estados y de empresa sigue perteneciendo a tickets.

La aplicación de SLA delega en `calculate_sla` con resolución presente y el objetivo explícito conservado como objetivo de cálculo. No llama a `calculate_ticket_sla`, `target_minutes_for` ni `get_ticket_sla`, y no escribe objetivos. La operación existente `get_ticket_sla` no cambia.

Un contrato no importa el contrato de otro módulo. El contrato SLA solo importa su propia aplicación/dominio. La composición de identidad, tickets y SLA queda en el router y `main.py`; los callbacks de lectura/evaluación se inyectan al caso de uso. No se amplía el contrato de tickets que consume HU-12 ni se le introduce una dependencia inversa.

## Contrato observable propuesto

Nueva operación aditiva: **`GET /api/dashboard/support-metrics`**.

- 200: agregado autorizado, incluso vacío.
- 401: sesión inválida, tratamiento existente y precedencia antes de obtener datos.
- 404: rol distinto de administrador o cuenta sin empresa, cuerpo uniforme `{"detail": "not found"}`. No hay variante exitosa vacía para esas denegaciones.
- No declara filtros, periodo, empresa ni paginación. Parámetros desconocidos se ignoran conforme a las lecturas existentes, nunca seleccionan alcance. No se cambian rutas, respuestas o parámetros previos.
- No devuelve detalles de tickets ni identificadores de personas/empresas.

| Campo | Tipo y significado |
|---|---|
| `total_tickets` | Entero no negativo; todo el conjunto autorizado |
| `resolved_tickets` | Entero; actualmente Resuelto/Cerrado |
| `pending_tickets` | Entero; total menos resueltos |
| `average_resolution_minutes` | Número finito no negativo o `null`; duración media exacta antes del formato de presentación |
| `resolution_sample_size` | Entero; finalizados con fechas válidas |
| `resolution_excluded_count` | Entero; resueltos menos muestra del promedio |
| `sla_compliance_percentage` | Número 0–100 redondeado a dos decimales, o `null` |
| `sla_sample_size` | Entero; finalizados evaluables con objetivo conservado |
| `sla_met_count` | Entero entre cero y `sla_sample_size` |
| `sla_excluded_count` | Entero; resueltos menos muestra SLA |

Invariantes: `total = resolved + pending`; cada muestra más su exclusión equivale a resueltos; la muestra SLA es subconjunto de la muestra de resolución. `null` corresponde exactamente a muestra cero; cero numérico con muestra positiva es un dato real.

La respuesta de ejemplo con tres finalizados de la spec tendrá total/resueltos 3, pendientes 0, promedio 120, muestra promedio 3, exclusiones promedio 0, porcentaje 50, muestra SLA 2, cumplidos 1 y exclusiones SLA 1. Cambiar política 240→30 sin modificar los tickets conserva todos los campos.

## Reglas de cálculo y lectura

- La instantánea copia valores mínimos, no conserva referencias mutables a tickets para consumirlos más tarde. Se captura una vez por consulta, sin ordenación temporal y sin lecturas repetidas. No se añade bloqueo/transacción distribuida ni se promete seguimiento en tiempo real.
- Para el cálculo se usan instantes interpretables y comparables; normalizar zonas explícitas a UTC no cambia el instante. No se inventan fechas ni zona horaria para datos ambiguos. Datos no interpretables/comparables y resolución anterior a creación se excluyen de las muestras, no del volumen.
- Promedio: sumar duraciones sin truncar cada ticket y dividir una vez. Usar minutos como unidad del contrato; en UI presentar minutos con hasta dos decimales y unidad explícita. No usar `elapsed_minutes` del SLA, que trunca minutos y podría alterar el promedio.
- El dominio de tickets reconoce Resuelto/Cerrado con su catálogo existente; no cuenta eventos. La nueva lectura posterior a un cambio vuelve a usar estado/fechas/objetivo registrados.
- No capturar cualquier excepción como «sin datos»: validar datos de entrada explícitamente; un fallo técnico debe llegar al estado de error. No tratar fallos de infraestructura como colecciones vacías.
- Sin objetivo conservado, no llamar al evaluador ni reconstruir con política. Un objetivo inválido tampoco constituye una muestra evaluable.

## Frontend y presentación

- Crear `SupportMetricsApi`, sus tipos y hook propios, separados de `DashboardApi`: las pruebas/consumidores anteriores no necesitan añadir un método obligatorio a sus dobles.
- Añadir `SupportMetricsPanel` al dashboard existente solo cuando la sesión esté validada y el actor sea administrador. No modificar los datos, textos o selectores de los paneles previos.
- Un hook local al panel conserva estado de la petición, sin almacenar el agregado en una caché compartida entre actores. Reiniciar/descartar datos al cambiar actor o estado de autenticación; ignorar respuestas de peticiones desmontadas o anteriores. Remontar el panel por identidad autenticada.
- No consultar desde supervisor/técnico/cliente ni durante validación de sesión. La UI no sustituye la autorización del servidor.
- Mostrar cinco valores juntos, alcance histórico, definición de resueltos, duración hasta resolución, SLA solo finalizados con objetivo conservado, y para cada muestra incluidos/excluidos.
- Formatear explícitamente `null` como «Sin datos», nunca mediante un valor por defecto cero. Mostrar minutos y porcentaje con formato español; no depender exclusivamente de color.
- Carga sin cifras provisionales; vacío base con volumen cero y dos «Sin datos»; fallo técnico sin métricas previas presentadas como actuales y acción «Reintentar»; 404 sin datos protegidos ni reintento de elevación; 401 usa el manejador existente de sesión y retira el panel.
- No polling, actualización en tiempo real ni refetch periódico nuevos. Una nueva carga/reintento consulta el agregado real; filtros/periodos de otras vistas no forman parte de esta petición.
- Delta técnico T9 autorizado explícitamente por el usuario con «si» el 2026-11-26: en `httpClient.request`, comprobar `options.signal?.aborted` justo antes de notificar el 401 global, después de leer el cuerpo asíncrono. Una petición cancelada no invalida la nueva sesión; el rechazo HTTP y los 401 vigentes se mantienen. Sin cambios a contratos, AuthProvider, reglas RF-179/RF-190 ni clasificación HIGH. Pruebas de cancelación antes/durante respuesta y conservación de errores; no amplía alcance funcional.

## Decisiones y alternativas descartadas

| Decisión | Motivo y alternativa descartada |
|---|---|
| Agregado en tickets, evaluador puro en SLA | Conserva propiedad de datos y reglas. Descartado nuevo módulo de reporting y lectura directa de tablas de otros módulos |
| Callback compuesto en router | Evita contratos importando contratos y acoplar aplicación a otro dominio. Descartado importar contrato SLA desde un contrato de tickets |
| Evaluación conservada aditiva | RF-191 impide el fallback. Descartado reutilizar el porcentaje HU-12 o modificar `get_ticket_sla`/política general |
| Lectura mínima sin ordenar | Incluye historial completo y tolera fechas inválidas sin alterar el listado existente. Descartado consumir una página o cambiar `list_all()` para todos |
| Un agregado, un conjunto de registros | Asegura invariantes y muestras comparables. Descartado consultas independientes por indicador y cálculo en navegador |
| Nulos y muestras explícitos | Distingue ausencia de cero real y explica exclusiones. Descartado 0/100 % por defecto y estados de error como vacío |
| Endpoint y API frontend separados, panel en dashboard | Ampliación aditiva y compatible. Descartado cambiar respuestas de HU-11/HU-12 o añadir otra pantalla/ruta |
| Estado local del panel | Evita compartir métricas sensibles entre sesiones sin modificar el proveedor de autenticación. Descartada una clave global de caché sin contexto de actor |
| Sin migración/persistencia nueva | Se usa la fuente vigente. Descartado prometer reconstrucción de tickets históricos no registrados o persistir agregados |

## Estrategia de pruebas y trazabilidad

Backend: **pytest** para dominio/aplicación/contratos y **TestClient** para la operación HTTP registrada en la aplicación real. Frontend: runner existente **Vitest + Testing Library**; sin dependencias ni pruebas E2E nuevas.

| Grupo | Casos exigidos | RF |
|---|---|---|
| Evaluador SLA puro | Objetivo presente/ausente/inválido, prioridad no evaluable, fechas inválidas, igualdad/posterior al vencimiento; asegurar que no lee configuración | 185, 186, 191 |
| Instantánea y agregado | Vacío, todos los estados, más de una página de tickets, antiguos, sin prioridad/técnico, duplicación de títulos con IDs distintos, copia estable, fechas mixtas no ordenables | 180–184, 188 |
| Promedio | Duración cero, fracciones de minuto sin truncado previo, cierre irrelevante, resolución ausente/inválida/anterior, muestras independientes y nulos | 183, 184, 189 |
| Autorización de aplicación y HTTP | Cuatro roles con empresa, sin sesión, cuenta sin empresa en cada rol, dos empresas, relaciones cruzadas y ticket sin empresa; espías prueban denegación antes de lectura/evaluación | 179, 180, 188 |
| Contrato HTTP | Claves/tipos exactos, ceros frente a nulos, invariantes, sin datos personales; parámetros externos no amplían ni filtran el conjunto; fallo técnico no se vuelve 200 vacío | 179–186, 188–191 |
| Ciclo y configuración | Cierre, retroceso, reapertura y nueva resolución con fechas fijadas; ejemplo cinco tickets y ejemplo tres tickets 120/50; caso aislado sin objetivo; cambio real de configuración sin cambiar tickets | 183–188, 191 |
| Solo lectura | Comparar tickets, objetivos, historial y notificaciones antes/después; lectura/evaluación una sola fuente; ningún dato ajeno entra en muestras o exclusiones | 180, 188, 191 |
| Frontend API/hook | Petición sin filtros, nulos intactos, error/reintento, 401, 404, desmontaje/cambio de sesión con respuesta antigua; no petición en otros roles | 179, 188–191 |
| Panel e integración | Cinco valores, muestras/exclusiones, notas y unidades, 0 frente a Sin datos, carga/vacío/fallo, teclado y sesión expirada; cambiar periodo HU-12 no altera HU-18 | 179, 189, 190 |
| Regresión | Dashboards HU-11/HU-12: esquemas, periodos, permisos y semántica anteriores; SLA general conserva comportamiento, incluido su tratamiento heredado | 185, 188, 191 y compatibilidad de la spec |

Pruebas con fechas deterministas y sin sleeps. Una instancia TestClient por rol y estado aislado; restaurar singleton de política SLA. En frontend, cleanup y API inyectable/control de respuestas, sin red real.

### Puertas de verificación futuras

- Para cada tarea de backend: primero prueba pytest que falle por el comportamiento ausente; implementar lo mínimo; ejecutar prueba focalizada y suite backend completa en verde antes de marcarla.
- Para tareas frontend: primero Vitest en rojo, implementar, focalizadas y suite frontend/lint/build en verde; ejecutar también la suite pytest como puerta de no regresión. No inventar pruebas pytest para componentes.
- Comandos existentes: desde raíz, `$env:PYTHONPATH='backend'; python -m pytest -q -rs`; desde `frontend`, `npm test`, `npm run lint`, `npm run build`.
- Los tests de integración PostgreSQL solo se consideran verificados cuando corran sobre el Docker autorizado. Si falta daemon, registrar skipped/limitaciones reales, nunca crear otro PostgreSQL, ocultar fallos ni declarar validación SQL. Una suite con fallos bloquea el cierre; pruebas focalizadas no sustituyen la suite.
- Al cerrar cada tarea de implementación: actualizar evidencia RF, sincronizar CodeGraph y Graphify por cambios de código, actualizar memoria con autorización y detenerse. No ejecutar estos pasos como si hubieran ocurrido en esta planificación.

## Dependencias, riesgos y aprobación

- Dependencias existentes: lectura de tickets, sesión con empresa, dominio de SLA, dashboard y runner frontend. La consulta no depende del directorio de usuarios, de primera respuesta ni de fecha de cierre.
- Riesgo principal: fuga de datos agregados por empresa ausente o caché/resultado de otro actor. Controles en aplicación, filtrado previo al evaluador y pruebas cruzadas son obligatorios.
- Riesgo de precisión: truncar tiempos individuales, mezclar muestras o aceptar objetivo ausente. Se mitiga con casos numéricos y pruebas RF-191.
- La fuente actual en memoria limita el historial a registros disponibles; no se presume persistencia completa ni se amplía HU-18 para resolver el pendiente PostgreSQL de HU-17. Es evidencia ya compatible con «datos registrados», no una dependencia nueva.
- No hay dudas de negocio ni decisiones de alcance pendientes. Si aparece necesidad de migración, contrato incompatible o más de diez tareas, detener y consultar/reclasificar antes de continuar.
- Este plan y `tasks.md` fueron aprobados explícitamente con «si». La implementación se autoriza de una tarea por vez, sin ampliar alcance.
- El implementador registra en `MEMORY.md` las aprobaciones de spec/plan/tareas y el resultado real de cada tarea, preservando pendientes anteriores y sin atribuir pruebas a la planificación.

## Evidencia de implementación por tarea

- 2026-11-26, historial T9: se detuvo inicialmente ante dos regresiones HTTP reales (20 passed/2 failed) que demostraron el cierre de la sesión nueva por un 401 antiguo cancelado con cuerpo pendiente. Se consultó antes de modificar código compartido; no se ocultaron tests ni se marcó la tarea.
- 2026-11-26, T9 completada (HIGH vigente) tras «si» explícito al delta técnico anterior: una guardia por señal cancelada justo antes de notificar el 401 global, preservando rechazos, 401 vigentes y contratos/AuthProvider. Siete nuevas pruebas HTTP más 22 de integración de dashboard; rojo adicional **5 failed/30 passed**, exit 1 → focalizadas **118 passed/7 archivos**, exit 0. Puerta F: **461 passed/43 archivos**, lint/build exit 0; G: **1965 passed/40 skipped/3 warnings**, exit 0 (160.94 s). RF-179/188–191 en integración: rol/sesión validada, retirada de datos y descarte de respuestas antiguas, 401/404 y periodos HU-12 independientes; sin alterar fórmulas, SLA general ni paneles previos. Sin SQL verificado ni skips nuevos. T10 no iniciada; comandos y límites en `tasks.md`.

- 2026-11-25, solo T1 completada: evaluador conservado aditivo RF-185/186/191, sin fallback ni cambios al SLA general. Detalle rojo/verde y comandos en `tasks.md`: nuevos 56 passed; SLA 291 passed/1 skipped/3 warnings; puerta G 1802 passed/40 skipped/3 warnings, exit 0.
- Precisión técnica T1: no se atribuye zona a fechas naive, se normalizan instantes explícitos a UTC y un vencimiento no representable devuelve `None`; los errores técnicos del cálculo se propagan. No cambia ninguna regla de negocio aprobada.
- 2026-11-25, T2 completada: `TicketMetricsSnapshot` congelado y tupla materializada mediante `snapshot_for_metrics`, copia mínima de todo el almacenamiento en un recorrido sin ordenar ni filtrar. RF-180/181/184/188 en su alcance de lectura; autorización y agregado siguen pendientes. Rojo 17 failed → verde 17 passed; puerta G **1819 passed/40 skipped/3 warnings**, exit 0 (135.47 s). Sin verificación PostgreSQL; T3–T10 pendientes. Detalle en `tasks.md`.
- 2026-11-25, T3 completada: `ResolutionMetrics` es el resultado parcial inmutable de seis campos de volumen/promedio; no contiene cifras SLA provisionales. `aggregate_resolution_metrics` y `resolution_duration` son dominio puro, reutilizan estados de tickets, normalizan instantes explícitos a UTC y suman microsegundos exactos antes de dividir. RF-181–184/188/189 en alcance de cálculo; autorización y composición SLA quedan para T4. Rojo **49 failed** → focalizadas **66 passed** (49 nuevas + T2); puerta G **1868 passed/40 skipped/3 warnings**, exit 0 (136.20 s). Sin verificación PostgreSQL; T4–T10 pendientes. Evidencia y sincronizaciones en `tasks.md`.
- 2026-11-25, T4 completada: `get_support_metrics` autoriza administrador con empresa antes de la única lectura, materializa el conjunto filtrado por empresa registrada y coordina el evaluador inyectado solo para candidatos. Dominio compone los diez campos en `SupportMetrics`, con muestras independientes y porcentaje redondeado; no hay importaciones de otros módulos ni infraestructura en aplicación, política vigente ni fallback. RF-179/180/185/186/188/191 en alcance de aplicación. Rojo **58 failed** → focalizadas **180 passed** (T1–T4); puerta G **1926 passed/40 skipped/3 warnings**, exit 0 (138.30 s). Sin verificación PostgreSQL. T5–T10 pendientes; HTTP y ciclo/configuración real siguen por verificar en sus tareas.
- 2026-11-25, T5 completada: router aditivo registrado en `main.py`, `GET /api/dashboard/support-metrics` con sesión real, traducción 401→404, diez campos/nulos, parámetros ignorados y composición T4/T1 sin reglas en controlador. RF-179–186/188–191 en alcance API, no presentación frontend. Rojo **28 failed/3 warnings** → focalizadas **208 passed/3 warnings**; puerta G **1954 passed/40 skipped/3 warnings**, exit 0 (136.17 s). CodeGraph/Graphify sincronizados; sin SQL verificado. T6–T10 pendientes. Evidencia detallada en `tasks.md`.
- 2026-11-25, T6 completada: once pruebas nuevas de ciclo/configuración/solo lectura con HTTP y reloj determinista, ambos ejemplos y caso aislado sin objetivo tras cambio real de política 240→30. Comparan estado registrado, historial y notificaciones, y conservan permisos/periodos/semántica de HU-11/HU-12 y fallback general de SLA sin extenderlo a HU-18. **Verde inicial 11 passed/3 warnings**, sin fabricar rojo ni modificar producción, según autorización expresa para esta regresión. Focalizadas **540 passed/1 skipped/3 warnings**; puerta G **1965 passed/40 skipped/3 warnings**, exit 0 (151.00 s). RF-180/183–188/191. Sin SQL verificado; grafos sincronizados, T7–T10 pendientes. Detalle en `tasks.md`.
- 2026-11-25, T7 completada: tipo `SupportMetrics`, `SupportMetricsApi` inyectable y `useSupportMetrics(actorKey, api?)` con estado local, nulos intactos, reintento explícito y cancelación/descarte de respuestas antiguas. `null` deshabilita el contexto; sin polling, caché compartida ni cambios a DashboardApi/AuthProvider. RF-179/188–191 en alcance API/hook; T8/T9 pendientes. Rojo **2 suites por módulos ausentes/0 tests**, exit 1 → focalizadas **26 passed/2 archivos**, exit 0. Puerta F: **420 passed/41 archivos**, lint/build exit 0. Puerta G: **1965 passed/40 skipped/3 warnings**, exit 0 (161.16 s). Context7 React consultado, grafos sincronizados; sin SQL verificado. Detalle de comandos y límites en `tasks.md`.
- 2026-11-25, T8 completada: `SupportMetricsPanel` independiente usa T7, cinco indicadores con minutos/% en `es-ES`, muestras/exclusiones y notas del alcance; distingue nulos, cero, carga, vacío y error/reintento por teclado, con región/encabezado/descripción accesibles. RF-183/184/186/189/190/191 en presentación aislada, sin fórmulas, filtros, datos demo ni montaje en DashboardPage. Rojo **1 suite por componente ausente/0 tests**, exit 1 → **38 passed/3 archivos** (12 nuevas + T7), exit 0. Puerta F: **432 passed/42 archivos**, lint/build exit 0; puerta G: **1965 passed/40 skipped/3 warnings**, exit 0 (158.65 s). Grafos sincronizados; sin SQL verificado. T9/T10 pendientes; comandos y límites en `tasks.md`.

## Cierre T10 — trazabilidad y límites (2026-11-26)

T10 HIGH, riesgo alto, confianza media; clasificación y aprobaciones vigentes. Revisión de la matriz anterior y repetición de pruebas existentes: no se identificó una comprobación automatizada faltante que exigiera añadir tests ni cambiar producción. No se fabrica rojo en esta tarea de regresión. Esta evidencia cierra la tarea documental, **no declara la spec validada ni sustituye revisión independiente**; `spec.md` conserva su estado de aprobada.

### Matriz RF por RF

Referencias backend bajo `backend/tests/`: **API** = `test_support_metrics_api.py`, **UC** = `test_support_metrics_use_case.py`, **RES** = `test_support_resolution_metrics.py`, **SNAP** = `test_ticket_metrics_snapshot.py`, **FROZEN** = `test_sla_frozen_resolution.py`, **LIFE** = `test_support_metrics_lifecycle.py`. Las seis suites suman **219 passed/3 warnings**, sin omisiones, y también pasan dentro de G.

Referencias frontend bajo `frontend/tests/`: **PANEL** = `components/SupportMetricsPanel.test.tsx`, **DASH** = `pages/DashboardSupportMetrics.test.tsx`, **HOOK** = `hooks/useSupportMetrics.test.tsx`, **CLIENT** = `api/supportMetrics.api.test.ts`, **HTTP** = `api/httpClient.test.ts`. Pasan dentro de las focalizadas de **118 pruebas/7 archivos** y de F completa. «Verde» en la tabla significa comprobación automatizada; no implica navegador ni PostgreSQL.

| RF | Test concreto / comprobación | Resultado T10 |
|---|---|---|
| 179 | API: `test_only_administrator_with_company_can_consult`, `test_account_without_company_gets_uniform_404_without_reading`, `test_invalid_session_has_401_precedence_before_data_access`. UC deniega antes de leer/evaluar. DASH: administrador validado, tres roles sin panel/consulta, validación pendiente/fallida y 401/404. | Verde: 200 autorizado, 401 previo y 404 uniforme sin datos; no confiar en identidad almacenada. |
| 180 | API: `test_response_uses_session_company_not_crossed_links_or_query`, `test_unknown_parameters_never_filter_or_expand_the_history`. UC: `test_foreign_or_unscoped_data_is_excluded_before_dates_status_or_evaluator`. SNAP: `test_snapshot_includes_all_history_without_pagination_or_deduplication`. DASH cambio de periodo HU-12. | Verde: dos empresas, relaciones cruzadas/sin empresa excluidas antes de evaluar; 125 registros antiguos completos; consulta histórica independiente. |
| 181 | SNAP: `test_snapshot_includes_all_history_without_pagination_or_deduplication`; UC: `test_one_read_of_one_shot_snapshot_feeds_every_indicator_without_pagination`; API: `test_reference_five_tickets_serializes_independent_samples`. | Verde: conteo por ID, sin deduplicar títulos ni excluir sin prioridad/SLA/técnico; no limitado a una página. |
| 182 | RES: `test_current_status_alone_classifies_volume_and_finalized_sample`, `test_reference_example_uses_only_valid_finalized_resolution_dates`; API ejemplo cinco tickets. | Verde: Resuelto/Cerrado una vez, resto pendientes; total = resueltos + pendientes, ejemplo 5/3/2. |
| 183 | RES: `test_zero_duration_is_a_real_sample_not_missing_data`, `test_average_never_truncates_or_rounds_individual_durations`, `test_valid_duration_does_not_require_priority_or_sla_target`, `test_timezone_transition_uses_elapsed_time_not_wall_clock_duration`, `test_closure_date_never_changes_or_replaces_resolution`. | Verde: media continua sin truncado individual, instantes explícitos, cero válido, cierre irrelevante; ejemplo 90 minutos. |
| 184 | RES: `test_invalid_dates_exclude_only_samples_never_volume`, `test_closure_date_never_changes_or_replaces_resolution`; API: `test_no_sample_is_distinct_from_zero_and_missing_target_has_no_fallback`; PANEL cero frente a Sin datos. | Verde: fechas ausentes/ambiguas/inválidas/anteriores excluyen muestra, no volumen; null no se transforma en cero ni se infiere resolución. |
| 185 | UC: `test_ineligible_rows_never_reach_injected_evaluator`; FROZEN: `test_missing_or_invalid_frozen_target_is_not_evaluable`, `test_evaluator_never_reads_current_policy_or_uses_general_fallback`; API: `test_real_composition_reads_once_and_only_evaluates_frozen_candidates`. | Verde: solo finalizados evaluables, no pendientes, no primera respuesta ni objetivos reconstruidos. |
| 186 | FROZEN: `test_evaluates_exact_resolution_deadline`; UC: `test_true_false_and_none_are_distinct_evaluator_results`, `test_percentage_uses_only_evaluable_sample_and_rounds_to_two_decimals`; PANEL formato español y cero con muestra positiva. | Verde: igualdad cumple, +1 microsegundo incumple, 0/100 y 33,33/66,67 %, muestra vacía null/Sin datos. |
| 187 | LIFE: `test_lifecycle_uses_current_resolution_once_and_keeps_original_creation`, parametrizado retroceso/reapertura, reloj controlado y transiciones mediante TestClient de la aplicación. | Verde: cierre conserva duración, retroceso/reapertura retiran muestras, nueva resolución única a 180/300 minutos desde creación original. |
| 188 | API: `test_real_composition_reads_once_and_only_evaluates_frozen_candidates`; SNAP: `test_original_mutation_and_repository_changes_do_not_change_captured_snapshot`, `test_next_snapshot_reflects_updates_without_reusing_records`; LIFE: `test_metrics_never_use_event_writers_or_mutate_registered_history`. | Verde: una snapshot, muestras consistentes, consultas sin mutar tickets/historial/notificaciones/objetivos/política; actualización al consultar de nuevo. |
| 189 | PANEL: `presenta juntos los cinco indicadores y las muestras del ejemplo de cinco tickets`, `distingue población y muestras independientes del ejemplo 120 minutos/50 %`, `formatea en español hasta dos decimales sin alterar ni recalcular el agregado`, relaciones ARIA únicas. | Verde DOM: cinco valores, unidades/notas/muestras/exclusiones y ambos ejemplos; sin fórmulas frontend. Apariencia/lector de pantalla reales no verificados. |
| 190 | API: `test_empty_authorized_response_preserves_nulls_and_exact_types`, `test_technical_failure_is_500_not_success_with_zero_or_null`. PANEL carga/vacío/fallo y `fallo técnico no se presenta como vacío y se reintenta con teclado`. DASH cambio/salida/revalidación de sesión y respuestas antiguas; HTTP cancelación antes de respuesta/durante cuerpo y 401 vigente. | Verde: carga sin cifras, vacío 0/0/0 + dos Sin datos, error distinto/reintento Tab+Enter, retirada de datos y 401 cancelado sin cerrar nueva sesión; errores HTTP siguen rechazándose. |
| 191 | LIFE: `test_policy_change_240_to_30_preserves_examples_and_missing_target_exclusion` (cinco/tres/aislado sin objetivo), `test_previous_dashboards_and_general_sla_keep_their_legacy_meaning`; FROZEN prueba de prohibición de lectura de política; PANEL sin objetivo conserva promedio/SLA Sin datos. | Verde: cambio real por HTTP 240→30 mantiene HU-18 y objetivos ausentes; 120 minutos/50 % con muestras 3/2 y aislado 180 minutos/Sin datos. SLA general conserva su fallback, no se altera para HU-18. |

### Compatibilidad, ejecución y entorno

- LIFE: `test_previous_dashboard_permissions_are_not_replaced_by_hu18` verifica los cuatro roles: HU-11/HU-12 siguen 200 para administrador/supervisor/técnico y 404 para cliente; HU-18 solo administrador. `test_previous_dashboards_and_general_sla_keep_their_legacy_meaning` comprueba esquema de tickets, periodos 7/30/90, cerrado sin resolución y fallback general 240→30. La suite frontend completa incluye dashboard/API/SLA/guards previos y los periodos HU-12 independientes.
- Regresión autorizada T9 incluida sin cambios: un 401 cancelado, incluso con cuerpo pendiente que resuelve o rechaza con AbortError, no notifica al manejador de la sesión nueva; 401 vigente con/sin señal mantiene notificación y los errores 404/500/abort siguen rechazándose. AuthProvider y contratos no se modifican en T10.
- Windows/PowerShell, Python 3.10.0, Node v24.14.0, npm 11.4.2. Rama conservada `feature/HU-18-support-management-metrics`; sin dependencias, cambios de producción/tests, commit ni push en T10.
- Resultados de esta ejecución, no heredados de T9: G **1965 passed/40 skipped/3 warnings**, exit 0 (158.84 s); F **461 passed/43 archivos**, exit 0 (14.63 s), lint/build exit 0. Focalizadas backend **219 passed/3 warnings** (4.59 s) y frontend **118 passed/7 archivos** (5.17 s), exit 0. Comandos reproducibles en T10 de `tasks.md`.
- Los 40 skips existentes corresponden a PostgreSQL no configurado/disponible (companies, migraciones, integración BD, semillas y edición de usuarios); no se añaden skips/xfail ni se excluyen pruebas. Tres warnings existentes FastAPI/Starlette; frontend conserva avisos React Router Future Flags. No se acredita SQL.

### Comprobación manual y pendientes para revisión independiente

Comprobación de disponibilidad: `docker ps --filter name=infra-db-1 --format "{{.Names}} {{.Status}} {{.Ports}}"` terminó exit 0 sin filas; no hay contenedor autorizado activo. `Get-NetTCPConnection` no encontró listeners en 8000/5173/55432. No hay herramienta de navegador expuesta en la sesión. No se inicia infraestructura alternativa, instala navegador/dependencias ni se inventan datos reales.

| Aspecto manual solicitado | Evidencia o limitación explícita |
|---|---|
| Panel con datos registrados reales, cinco cifras y muestras | No ejecutado en navegador: sin aplicación/sesión con datos reales disponible en puertos comprobados. TestClient/fixtures y DOM controlado no equivalen a revisión visual real. |
| Alcance histórico y separación HU-12 | No comprobación visual manual; pruebas API de parámetros/empresas y DASH de periodos verdes. Pendiente inspección con datos registrados. |
| Teclado/accesibilidad | Tab+Enter, foco y relaciones ARIA verificados automáticamente en PANEL; no se afirma recorrido manual en navegador ni prueba con lector de pantalla/responsive. |
| Sesión expirada/cambio de actor | DASH/HTTP/HOOK verdes con promesas controladas y cliente/proveedor reales, fetch controlado; no sesión/cookie real verificada manualmente en navegador. |
| Error y reintento | PANEL verifica recuperación por teclado automáticamente; no se provoca fallo de infraestructura real ni se afirma revisión manual del reintento. |

T10 se cierra conforme al criterio aprobado «evidencia **o limitación explícita**» de la comprobación manual. Quedan pendientes para revisión independiente la aceptación final, recorrido visual/teclado/sesión/reintento en navegador con datos reales y verificación PostgreSQL sobre `infra-db-1:55432`. No se declara despliegue ni cumplimiento de esas partes no ejecutadas. Índice y memoria actualizados; sin invocar reviewer ni empezar otra tarea.

Sincronizaciones finales: `cmd /c codegraph sync`, `graphify update .` y `git diff --check`, exit 0. Aviso conocido Graphify de seis SQL sin extractor `tree_sitter_sql`, sin instalar dependencias.
