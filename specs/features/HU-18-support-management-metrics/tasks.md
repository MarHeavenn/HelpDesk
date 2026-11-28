# Tareas HU-18 — Métricas de gestión de soporte

Estado: aprobadas explícitamente por el usuario con «si»; ejecución por tarea.

Spec aprobada: RF-179–RF-191. Plan aprobado: `plan.md`. T1–T10 completadas en ejecuciones separadas; cierre T10 con límites manuales/SQL explícitos, pendiente revisión independiente (no spec validada).

## Reglas de ejecución y tamaño

Diez bloques, de 20–30 minutos estimados cada uno, en orden de dependencia. Las estimaciones incluyen tests focalizados y puertas automatizadas; no son permiso para omitir pruebas. Si un bloque excede ese tamaño o requiere una undécima tarea, parar y proponer división antes de ampliar el trabajo.

Todas las tareas incluyen primero pruebas que fallen por la capacidad ausente y luego implementación mínima. En backend se usa pytest; en frontend el runner acordado Vitest/Testing Library, con pytest como no regresión, no como sustituto de pruebas de interfaz.

**Puerta G en cada tarea:** ejecutar pytest completo desde raíz (`$env:PYTHONPATH='backend'; python -m pytest -q -rs`) y exigir ausencia de fallos, sin excluir casos ni introducir skips/xfail para obtener verde. Registrar resultados y omisiones del entorno por separado; sin PostgreSQL no afirmar verificación SQL. Si la suite no puede recopilarse, falla o aparecen bloqueos nuevos, detenerse.

**Puerta F en T7–T10:** desde frontend, `npm test`, `npm run lint` y `npm run build` completos en verde. Pruebas focalizadas adicionales no sustituyen G/F.

Tras cada tarea: evidencia de pruebas y RF cubiertos, CodeGraph sync y Graphify update por cambios de código, memoria actualizada por un agente autorizado, marcar solo esa tarea y detenerse. Conservar rama y cambios locales ajenos. Este documento y el plan ya recibieron aprobación explícita.

## Secuencia

- [x] **T1. Evaluador SLA conservado y contrato interno aditivo.** RF-185, RF-186, RF-191. Estimación: 25 min. Dependencia: aprobación plan/tareas.
  - Primero pytest del nuevo evaluador: objetivo ausente/inválido, fechas/prioridad no evaluables, igualdad y superación del vencimiento, sin lectura de política. Después, aplicación pura de SLA que reutiliza `calculate_sla` y exportación por su contrato, sin alterar operaciones previas.
  - Hecho cuando: devuelve cumplido/incumplido/no evaluable según el contrato del plan, no aplica fallback, no importa contratos ajenos y las pruebas nuevas más las existentes de SLA y la puerta G están en verde.
  - Evidencia 2026-11-25: `python -m pytest backend/tests/test_sla_frozen_resolution.py -q --tb=short` primero **56 failed**, exit 1, por operación ausente; después `-q -rs`: **56 passed**, exit 0. Regresión SLA: `$slaTests = @(Get-ChildItem 'backend/tests/test_sla*.py' | ForEach-Object { $_.FullName }); python -m pytest @slaTests -q -rs`: **291 passed, 1 skipped, 3 warnings**, exit 0. Se corrigió la invocación previa con wildcard literal de PowerShell (exit 4, ningún test ejecutado), sin cambiar tests.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1802 passed, 40 skipped, 3 warnings en 135.44 s**, exit 0. Omisiones existentes por PostgreSQL no configurado/disponible; no se acredita SQL. Warnings existentes de FastAPI/Starlette.
  - RF-185/186/191: contrato devuelve `True`/`False`/`None`, igualdad y +1 microsegundo; catálogo exacto, objetivo entero positivo (sin booleanos), fechas explícitas UTC y exclusión de fechas ambiguas/vencimientos fuera de rango. Espías impiden lectura de política/fallback; cambiar política 240→30 conserva resultados `[True, False, None]`. Se delega en `calculate_sla` intacto y se propagan errores técnicos.
  - Sincronizaciones: `cmd /c codegraph sync` y `graphify update .` completados, exit 0. Graphify avisa de seis SQL sin extracción por `tree_sitter_sql` ausente; no se instalan dependencias. Riesgo residual de aislamiento/agregación/HTTP corresponde a T2–T6, no implementadas aquí. Memoria actualizada; detenerse en T1.

- [x] **T2. Instantánea mínima de tickets sin ordenación ni paginación.** RF-180, RF-181, RF-184, RF-188. Estimación: 20 min. Dependencia: T1.
  - Primero pytest de lectura con tickets antiguos, más de una página, fechas ausentes/no comparables y modificación posterior del ticket original. Después, registros inmutables mínimos y método aditivo `snapshot_for_metrics`, conservando `list_all()` y demás lecturas.
  - Hecho cuando: copia todos los registros una vez sin ordenar fechas, sin datos personales ni referencias mutables; el cambio del ticket después de capturar no altera la copia; las lecturas anteriores no cambian y la puerta G está en verde.
  - Evidencia 2026-11-25: con `PYTHONPATH=backend`, `python -m pytest backend/tests/test_ticket_metrics_snapshot.py -q --tb=short`: **17 failed**, exit 1, por método ausente; después `-q -rs`: **17 passed**, exit 0. Incluye 125 tickets de 1980, títulos repetidos con IDs distintos, los cuatro estados, empresas distintas/sin empresa, fechas ausentes/naive/no interpretables, siete campos exactos y congelados, mutación posterior del original, captura materializada y recorrido único; lecturas anteriores mantienen orden e identidad.
  - Implementación aditiva: `TicketMetricsSnapshot` en dominio y `snapshot_for_metrics() -> tuple[TicketMetricsSnapshot, ...]` en repositorio. Copia únicamente los siete campos del plan, no retiene tickets originales ni filtra/normaliza datos. No incluye fórmulas, autorización ni HTTP; la delimitación por empresa corresponde a T4.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1819 passed, 40 skipped, 3 warnings en 135.47 s**, exit 0. Skips existentes por PostgreSQL no configurado/disponible; warnings existentes FastAPI/Starlette. No se acredita SQL ni se añaden omisiones.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0. Graphify mantiene aviso de seis SQL sin extractor `tree_sitter_sql`; no se instalan dependencias. Memoria actualizada; detenerse antes de T3.

- [x] **T3. Agregado de volumen y promedio con muestras explícitas.** RF-181–RF-184, RF-188, RF-189. Estimación: 25 min. Dependencia: T2.
  - Primero pytest de estados, vacío, duración cero/fraccionaria, fechas inválidas y exclusiones; después reglas de dominio y resultado tipado, sin infraestructura ni lógica de SLA general.
  - Hecho cuando: total=resueltos+pendientes, promedio sin truncado individual, muestra/exclusión exactas y `null` solo sin muestra; los tickets inválidos permanecen en volumen, no se usa fecha de cierre y la puerta G está en verde.
  - Evidencia 2026-11-25: con `PYTHONPATH=backend`, `python -m pytest backend/tests/test_support_resolution_metrics.py -q --tb=short`: **49 failed**, exit 1, por agregado ausente. Después `python -m pytest backend/tests/test_support_resolution_metrics.py backend/tests/test_ticket_metrics_snapshot.py -q -rs`: **66 passed**, exit 0 (49 nuevas + 17 T2).
  - RF-181–184/188/189, alcance de dominio: vacío, estados actuales y resto como pendientes, ejemplo 5/3/2/promedio 90/muestra 2/exclusión 1, duración cero y microsegundos, fechas ausentes/naive/no interpretables/anteriores, zonas horarias y cambio de offset, cierre irrelevante, sin requisito de prioridad/objetivo SLA, grandes duraciones, un recorrido, datos/resultados inmutables y propagación de errores técnicos.
  - `ResolutionMetrics` congelado contiene los seis campos de volumen/promedio del contrato, sin atribuir resultados SLA todavía. `aggregate_resolution_metrics` consume el conjunto ya autorizado; `resolution_duration` valida instantes explícitos y compara en UTC. Acumula microsegundos enteros y divide una vez en minutos, sin redondear/truncar cada duración ni desbordar la suma de `timedelta`. No añade autorización, coordinación SLA, HTTP ni frontend.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1868 passed, 40 skipped, 3 warnings en 136.20 s**, exit 0. Skips existentes por PostgreSQL no configurado/disponible y warnings FastAPI/Starlette; sin SQL verificado, sin skips/xfail nuevos.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0. Aviso conocido Graphify: seis SQL sin extractor `tree_sitter_sql`, sin instalar dependencias. Memoria actualizada; detenerse antes de T4.

- [x] **T4. Caso de uso autorizado y composición del agregado SLA.** RF-179, RF-180, RF-185, RF-186, RF-188, RF-191. Estimación: 30 min. Dependencias: T1–T3.
  - Primero pytest con espías: denegación antes de leer para rol/empresa inválidos, dos empresas y relaciones cruzadas, exclusión previa al evaluador, muestras SLA y ejemplo 120 minutos/50 %. Después coordinar snapshot/evaluador inyectados sin importar otros contratos desde aplicación.
  - Hecho cuando: solo administrador con empresa puede producir agregado, ningún ticket ajeno/sin empresa participa ni llega al evaluador, una lectura alimenta todo y objetivo ausente no invoca evaluación ni afecta numerador/denominador; puerta G en verde.
  - Evidencia 2026-11-25: con `PYTHONPATH=backend`, `python -m pytest backend/tests/test_support_metrics_use_case.py -q --tb=line`: **58 failed**, exit 1, por caso de uso ausente (sin error de recopilación). Después `python -m pytest backend/tests/test_support_metrics_use_case.py backend/tests/test_support_resolution_metrics.py backend/tests/test_ticket_metrics_snapshot.py backend/tests/test_sla_frozen_resolution.py -q -rs`: **180 passed**, exit 0 (58 nuevas y T1–T3).
  - RF-179/180/185/186/188/191: espías prueban rechazo uniforme antes de leer/evaluar, cuatro roles sin empresa, dos empresas con relaciones cruzadas, exclusión de ajenos/sin empresa antes de inspeccionar estado/fechas, candidatos inválidos sin llamada SLA, ejemplo promedio 120/SLA 50 con muestras 3/2 y exclusión SLA 1, todos sin objetivo con SLA `None`, distinción True/False/None, porcentaje 33.33/66.67/0/100 y 125 tickets antiguos en una sola lectura. Resultado inmutable de diez campos, sin datos personales, lectura sin mutación y errores técnicos propagados.
  - Aplicación: `get_support_metrics(*, actor_role, actor_company_id, read_snapshot, evaluate_resolution)`; `SupportMetricsAccessDeniedError("not found")` para denegación. No importa infraestructura ni contratos/dominios de otros módulos. Reutiliza catálogo/fechas de tickets; el evaluador inyectado recibe solo prioridad/creación/resolución/objetivo de candidatos autorizados. Dominio añade `SupportMetrics` y `compose_support_metrics`, sin política ni fallback. Composición HTTP y traducción 401/404 siguen siendo T5.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1926 passed, 40 skipped, 3 warnings en 138.30 s**, exit 0. Omisiones existentes por PostgreSQL no configurado/disponible y warnings FastAPI/Starlette; no se acredita SQL ni se añaden skips/xfail.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0. Aviso Graphify conocido: seis SQL sin extractor `tree_sitter_sql`, sin nuevas dependencias. Memoria actualizada; detenerse antes de T5. Riesgo residual: verificar traducción HTTP/composición real en T5 y ciclo/configuración en T6, sin atribuirles estas pruebas de aplicación.

- [x] **T5. Operación HTTP y registro del router.** RF-179–RF-186, RF-188–RF-191. Estimación: 25 min. Dependencia: T4.
  - Primero pytest + TestClient para endpoint nuevo: cuatro roles, cuentas sin empresa, sin sesión, 200 vacío, contrato exacto, nulos, muestras y parámetros desconocidos; después router de traducción/composición y registro en `main.py`.
  - Hecho cuando: `GET /api/dashboard/support-metrics` conserva 401→404 sin datos en rechazos, respuesta aditiva prevista y ningún parámetro altera empresa/periodo/página; fórmulas y permisos no están en controlador; API nueva y puerta G en verde.
  - Evidencia 2026-11-25: con `PYTHONPATH=backend`, `python -m pytest backend/tests/test_support_metrics_api.py -q --tb=line`: **28 failed, 3 warnings**, exit 1, por ruta/router ausentes; sin error de recopilación. Después `python -m pytest backend/tests/test_support_metrics_api.py backend/tests/test_support_metrics_use_case.py backend/tests/test_support_resolution_metrics.py backend/tests/test_ticket_metrics_snapshot.py backend/tests/test_sla_frozen_resolution.py -q -rs`: **208 passed, 3 warnings**, exit 0 (28 nuevas + T1–T4).
  - RF-179–186/188–191 en alcance HTTP: cuatro roles con empresa, cuatro sin empresa, sesión ausente/desconocida/revocada con 401 antes de datos, 404 exacto `{"detail":"not found"}`, 200 vacío con diez claves/tipos y nulos intactos, ejemplo cinco tickets, cero real frente a muestra vacía, objetivo ausente sin política, dos empresas y relaciones cruzadas sin datos personales. Parámetros externos no cambian alcance/filtros/página sobre 35 tickets antiguos; espías verifican lectura única y evaluación solo de candidatos autorizados (promedio 120/SLA 50). Fallos de lectura/evaluación producen 500 sin métricas falsas ni detalle técnico.
  - Implementación: `tickets/interface/metrics_router.py` compone `get_current_user`, caso de uso T4, lectura propia y contrato `evaluate_frozen_resolution`; serializa `SupportMetricsResponse` sin fórmulas ni permisos de negocio. `main.py` registra el router aditivo; no cambian contratos previos. Context7 consultado para APIRouter/response_model/dependencia y conservación de `None`.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1954 passed, 40 skipped, 3 warnings en 136.17 s**, exit 0. Omisiones PostgreSQL y warnings FastAPI/Starlette existentes, sin nuevos skips/xfail. SQL no verificado.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0. Graphify mantiene aviso conocido de seis SQL sin extractor `tree_sitter_sql`; no se añaden dependencias. Memoria actualizada; detenerse antes de T6. Ciclo/configuración/solo lectura integral y presentación siguen pendientes de sus tareas; estas pruebas no acreditan frontend.

- [x] **T6. Ciclo de vida, configuración y garantías de solo lectura.** RF-180, RF-183–RF-188, RF-191. Estimación: 25 min. Dependencia: T5.
  - Primero pytest + TestClient con fechas deterministas para cerrar, retroceder, reabrir y resolver de nuevo, comparando consultas; añadir ambos ejemplos de la spec, caso aislado sin objetivo y sustitución de política 240→30 sin modificar tickets.
  - Hecho cuando: muestras/porcentajes permanecen invariantes ante el cambio de política, incluido «Sin datos» sin objetivo; ciclo cuenta solo el estado y resolución vigentes; no cambian tickets/historial/notificaciones por consultar; regresiones HU-11/HU-12 y SLA general más G en verde. Restaurar política y no alterar sus reglas para satisfacer HU-18.
  - Evidencia 2026-11-25: con `PYTHONPATH=backend`, `python -m pytest backend/tests/test_support_metrics_lifecycle.py -q -rs`: **11 passed, 3 warnings**, exit 0 desde la primera ejecución. Por autorización expresa para esta tarea de regresión, no se fabrica rojo: T1–T5 ya satisfacen los comportamientos comprobados y no se cambia código productivo.
  - RF-180/183–188/191: transiciones reales por HTTP con reloj inyectado al caso de uso, resolución a 60 minutos y cierre posterior sin alargarla, retroceso/reapertura eliminando muestras, nueva resolución a 180/300 minutos desde creación original y muestra única. Ambos ejemplos y finalizado aislado sin objetivo mantienen todos sus campos al cambiar realmente `/api/sla/policies` 240→30, sin mutar tickets, reconstruir objetivos ni incorporar empresa ajena/sin empresa.
  - Solo lectura: compara tickets, objetivos, modificaciones, asignaciones, comentarios, notificaciones (incluido estado de lectura), conteos y política antes/después de consultas repetidas; compara historial HTTP y bloquea escritores de eventos tras generar historial/notificaciones reales. HU-11/HU-12 mantienen permisos, esquema de tickets, periodos 7/30/90 y tratamiento heredado de cerrados sin resolución; SLA general sin objetivo conserva su fallback vigente 240→30, mientras HU-18 permanece invariante.
  - Focalizadas: `$tests = @(Get-ChildItem 'backend/tests/test_sla*.py','backend/tests/test_support*.py','backend/tests/test_ticket_lifecycle*.py','backend/tests/test_tickets_dashboard.py','backend/tests/test_ticket_metrics_snapshot.py' | ForEach-Object { $_.FullName }); python -m pytest @tests -q -rs`: **540 passed, 1 skipped, 3 warnings**, exit 0 (29.93 s). Skip existente `test_sla_demo_seed` requiere PostgreSQL; política singleton y almacenes se restauran por fixtures.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1965 passed, 40 skipped, 3 warnings en 151.00 s**, exit 0. Omisiones existentes por PostgreSQL no configurado/disponible y warnings FastAPI/Starlette; sin nuevos skips/xfail y sin SQL verificado.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0; aviso Graphify conocido de seis SQL sin extractor `tree_sitter_sql`, sin instalar dependencias. Memoria actualizada; no hay cambios productivos ni decisiones de negocio adicionales. Detenerse antes de T7; frontend y cierre integral continúan pendientes.

- [x] **T7. API/tipos/hook frontend propios y estado aislado.** RF-179, RF-188–RF-191. Estimación: 25 min. Dependencia: T5; ejecutar después de T6.
  - Primero Vitest de petición sin filtros, nulos preservados, errores y respuesta tardía tras desmontaje/cambio de actor; después cliente inyectable y hook local sin caché compartida, sin cambios incompatibles en `DashboardApi`.
  - Hecho cuando: una consulta obtiene el agregado, no calcula métricas en cliente ni convierte nulos en cero, no reaparece una respuesta anterior en otra sesión y no hay polling; puertas G/F en verde.
  - Evidencia 2026-11-25: primero `npm test -- --reporter=dot tests/api/supportMetrics.api.test.ts tests/hooks/useSupportMetrics.test.tsx` en rojo, exit 1: **2 suites fallidas por módulos aún ausentes, 0 tests ejecutados** (Vite resuelve también los imports dinámicos al transformar). Después, mismo comando: **26 passed / 2 archivos**, exit 0 (10 API + 16 hook). No se atribuyen 26 fallos al rojo.
  - RF-179/188–191, alcance API/hook: diez campos tipados y nulos sin transformación; una petición GET sin filtros/periodo/paginación; cliente HTTP existente con cookie y manejador global 401; errores 401/404/técnicos sin cifras ficticias. Hook local sin React Query/caché compartida, estados idle/loading/success/error, reintento explícito (sin reintentar 401/404), descarte de respuestas antiguas y AbortSignal al desmontar/cambiar contexto; oculta el dato anterior desde el primer render, no solo tras el efecto.
  - `useSupportMetrics(actorKey, api?)`: `null` deshabilita y retira datos durante sesión no habilitada/validada; el llamador compondrá esa clave en T9. Expone `status`, `data`, `error`, `canRetry`, `retry`; cambiar API/actor o reintentar descarta el contexto anterior. Pruebas con promesas controladas, montaje independiente, errores antiguos 401/404/red, sesión deshabilitada y ausencia de sondeo/refetch por foco. No se cambia `DashboardApi`, `AuthProvider`, páginas ni paneles. Context7 consultado sobre limpieza de efectos/carreras de respuestas en React.
  - Puerta F: desde `frontend`, `npm test`: **420 passed / 41 archivos**, exit 0 (13.83 s); `npm run lint`: exit 0; `npm run build`: exit 0 (TypeScript + Vite, 1700 módulos). Warnings existentes React Router Future Flags en pruebas anteriores. Sin dependencias ni omisiones nuevas.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1965 passed, 40 skipped, 3 warnings en 161.16 s**, exit 0. Skips PostgreSQL y warnings FastAPI/Starlette existentes; no hay omisiones nuevas ni validación SQL.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0; aviso Graphify conocido de seis SQL sin extractor `tree_sitter_sql`. Memoria actualizada; sin cambios de negocio fuera del plan. Panel, montaje por rol/sesión y comprobación integrada siguen pendientes de T8/T9; detenerse antes de T8.

- [x] **T8. Panel de presentación accesible.** RF-183, RF-184, RF-186, RF-189, RF-190, RF-191. Estimación: 25 min. Dependencia: T7.
  - Primero Vitest/Testing Library con datos controlados para cinco indicadores, etiquetas, muestras/exclusiones, unidad en minutos, 0 frente a «Sin datos», carga, vacío y fallo/reintento; después panel sin fórmulas de negocio ni datos simulados de producción.
  - Hecho cuando: los ejemplos de la spec se interpretan correctamente, las notas distinguen población/muestras, el error no muestra cifras previas como actuales y el reintento funciona por teclado; G/F en verde.
  - Evidencia 2026-11-25: `npm test -- --reporter=dot tests/components/SupportMetricsPanel.test.tsx` primero en rojo, exit 1: **1 suite fallida por componente ausente, 0 tests ejecutados**. Después `npm test -- --reporter=dot tests/components/SupportMetricsPanel.test.tsx tests/api/supportMetrics.api.test.ts tests/hooks/useSupportMetrics.test.tsx`: **38 passed / 3 archivos**, exit 0 (12 nuevas + 26 T7).
  - RF-183/184/186/189/190/191, alcance de panel: cinco indicadores juntos, ejemplos 5/3/2/90 minutos/50 % y 3/3/0/120 minutos/50 %, muestras/exclusiones independientes y caso sin objetivo con promedio válido/SLA Sin datos; cero real distinto de nulo; carga sin cifras, vacío con tres ceros/dos Sin datos, solo pendientes sin falso vacío, error sin cifras antiguas ni detalle técnico y reintento con Tab/Enter. Región, encabezado y alcance enlazados por IDs únicos, cinco artículos etiquetados y estados textuales, sin depender de color.
  - `SupportMetricsPanel({actorKey, api?})` utiliza T7; solo formato `es-ES` hasta dos decimales con minutos/% y nulos explícitos, sin fórmulas ni datos de demostración. Explica todo el historial, Resueltos incluye Cerrados, creación→resolución no cierre, SLA solo finalizados/objetivo conservado y exclusión sin fallback. Reutiliza ErrorState sin modificarlo; 404 no ofrece elevación/reintento. No se monta en DashboardPage ni se cambia Auth; permisos/sesión integrados siguen en T9. Context7 consultado para `useId` y relaciones ARIA.
  - Puerta F: desde `frontend`, `npm test`: **432 passed / 42 archivos**, exit 0 (13.92 s); `npm run lint`: exit 0; `npm run build`: exit 0 (TypeScript + Vite, 1700 módulos). Solo avisos React Router Future Flags existentes; sin dependencias/skips nuevos.
  - Puerta G: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1965 passed, 40 skipped, 3 warnings en 158.65 s**, exit 0. Omisiones PostgreSQL y warnings FastAPI/Starlette existentes; sin skips/xfail nuevos ni validación SQL.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados, exit 0; aviso Graphify conocido de seis SQL sin extractor `tree_sitter_sql`. Memoria actualizada; sin decisiones de negocio fuera del plan. Integración DashboardPage por sesión/rol y revisión visual integrada pendientes de T9/T10; detenerse antes de T9.

- [x] **T9. Integración solo administrador y ciclo de sesión.** RF-179, RF-188–RF-191. Estimación: 30 min. Dependencias: T7–T8.
  - Primero Vitest/Testing Library del dashboard con roles, validación de sesión, 401/404, cambio de actor y petición anterior pendiente; después montar el panel solo con administrador validado, inyectando API propia y tratamiento de sesión existente.
  - Hecho cuando: otros roles no montan/consultan HU-18 y conservan sus paneles anteriores; expirar/cambiar sesión retira datos y descarta respuestas antiguas; cambiar periodo HU-12 no cambia la petición ni muestra de HU-18; G/F en verde.
  - Estado inicial 2026-11-26 (histórico, bloqueo resuelto abajo): **incompleta y bloqueada**, HIGH vigente, sin marcar entonces. Integración en DashboardPage con sesión `authenticated`/rol administrador, API propia opcional y remontaje por ID; panel enlaza 401 inyectado al logout existente. DashboardApi y AuthProvider intactos. Ajustadas fixtures de rutas y selectores de pruebas anteriores, sin alterar paneles previos.
  - Historial de ejecución anterior: rojo **14 failed/5 passed**, exit 1; después **17 passed/2 failed**, exit 1, por matcher incompatible. Matcher corregido y reejecutado en esta recuperación: `npm --prefix frontend test -- --reporter=dot tests/pages/DashboardSupportMetrics.test.tsx tests/pages/DashboardPage.test.tsx tests/routes/guards.test.tsx tests/components/SupportMetricsPanel.test.tsx tests/hooks/useSupportMetrics.test.tsx tests/api/supportMetrics.api.test.ts`: **102 passed/6 archivos**, exit 0 (3.81 s), incluidas las 19 pruebas iniciales T9.
  - Prueba concreta adicional con SupportMetricsApi, request y AuthProvider reales (solo fetch/cuerpo controlados): un 401 vigente retira la sesión correctamente; un 401 antiguo cuyas cabeceras ya llegaron, pero cuyo cuerpo sigue pendiente, borra la nueva sesión después del cambio de actor y cancelación. Reproducido tanto al resolver el cuerpo como al rechazar su lectura con AbortError. `npm --prefix frontend test -- --reporter=dot tests/pages/DashboardSupportMetrics.test.tsx`: **20 passed/2 failed**, exit 1 (3.14 s). Esperado `authenticated:admin-other`, recibido `anonymous:none`; sin skips/xfail.
  - Causa del bloqueo inicial: `httpClient.request` invocaba el manejador global 401 después de esperar `readErrorDetail`, sin comprobar cancelación; este último captura también AbortError. El descarte local del hook ocurre después y no puede impedir ese efecto global. Bloqueaba RF-179/RF-190 y el aislamiento entre sesiones requerido por T9. Se consultó antes de modificar el cliente global; propuesta de guardia de cancelación antes de notificar 401, conservando los vigentes.
  - En esa recuperación se detuvo ante el bloqueo según instrucción del usuario: G/F completas no ejecutadas entonces, sin acreditar SQL. Las dos regresiones se conservaron en rojo hasta obtener autorización; no se marcó T9 y T10 no se inició.
  - Recuperación documentada en plan/memoria; `cmd /c codegraph sync`, `graphify update .` y `git diff --check`: exit 0. Graphify mantiene aviso de seis SQL sin extractor `tree_sitter_sql`, sin instalar dependencias.
  - Reanudación autorizada 2026-11-26: el usuario aprueba expresamente con «si» la corrección mínima de `httpClient.ts` para no notificar 401 cancelados en el momento de notificación, incluido cuerpo pendiente. Mantener rechazo/401 vigente, contratos y AuthProvider; HIGH vigente y RF de negocio intactos.
  - Rojo adicional antes de corregir: `npm --prefix frontend test -- --reporter=dot tests/api/httpClient.test.ts tests/pages/DashboardSupportMetrics.test.tsx`: **5 failed/30 passed**, exit 1 (3.65 s). Tres fallos unitarios por notificación cancelada y dos de integración por borrar la sesión nueva; siete nuevas pruebas HTTP, sin skips/xfail. Se verifica cancelación antes de respuesta y durante lectura del cuerpo, detalle tardío/AbortError, señal activa, errores 404/500 conservados y propagación del AbortError de fetch.
  - Corrección mínima: comprobar `!options.signal?.aborted` después de leer el cuerpo y justo antes de llamar al manejador 401. No se cambia el rechazo ApiError ni se ocultan errores; 401 sin señal o con señal activa sigue notificándose. Context7/MDN confirma que abortar después de recibir cabeceras puede rechazar la lectura del cuerpo. Sin cambios a contratos/AuthProvider, dependencias, backend ni reglas de métricas.
  - Verde focalizado: `npm --prefix frontend test -- --reporter=dot tests/api/httpClient.test.ts tests/pages/DashboardSupportMetrics.test.tsx tests/pages/DashboardPage.test.tsx tests/routes/guards.test.tsx tests/components/SupportMetricsPanel.test.tsx tests/hooks/useSupportMetrics.test.tsx tests/api/supportMetrics.api.test.ts`: **118 passed/7 archivos**, exit 0 (4.17 s), incluidas las cinco regresiones antes rojas.
  - RF-179/188–191 en alcance T9: 22 pruebas de integración comprueban administrador validado, tres roles sin consulta/panel HU-18 y paneles anteriores intactos, identidad almacenada aún no validada o validación fallida, 401 vigente/404 sin reintento de elevación, cambio directo de actor, logout/login del mismo actor, revalidación y cambio de rol, cancelación y descarte de datos/errores antiguos con API inyectada y HTTP real. HU-18 se muestra aunque HU-11 esté vacío; periodos HU-12 7/90/30 no alteran la consulta ni muestra HU-18. Sin fórmulas frontend ni fallback SLA.
  - Puerta F: desde `frontend`, `npm test`: **461 passed/43 archivos**, exit 0 (13.76 s); `npm run lint`: exit 0; `npm run build`: exit 0 (TypeScript + Vite, 1703 módulos). Solo avisos React Router Future Flags existentes. Sin dependencias ni omisiones nuevas.
  - Puerta G: desde raíz, `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1965 passed, 40 skipped, 3 warnings**, exit 0 (160.94 s). Omisiones existentes por PostgreSQL no configurado/disponible y warnings FastAPI/Starlette; sin nuevos skips/xfail ni validación SQL.
  - T9 completada con el delta técnico aprobado; memoria y plan actualizados. Se conserva rama y cambios ajenos, sin commit/push. T10 permanece sin iniciar; revisión visual/cierre RF integral corresponden a T10, no se atribuyen a estas pruebas.
  - Cierre T9: `cmd /c codegraph sync`, `graphify update .` y `git diff --check` completados con exit 0. Graphify mantiene aviso conocido de seis SQL sin extractor `tree_sitter_sql`; no se añaden dependencias.

- [x] **T10. Cierre RF por RF y regresión integral documentada.** RF-179–RF-191. Estimación: 25 min. Dependencias: T1–T9.
  - Revisar la matriz del plan: si falta una comprobación, escribir primero el test que la detecte; cerrar cobertura sin ampliar alcance. Ejecutar regresión completa G/F y comprobación manual de panel con datos reales disponibles, alcance, teclado, sesión y reintento.
  - Hecho cuando: cada RF tiene test/resultado y la comprobación manual tiene evidencia o limitación explícita; G/F están en verde, HU-11/HU-12 conservan contratos/métricas/permisos y SLA general no cambia. Documentar entorno, omisiones SQL, pendientes y resultados realmente ejecutados; no declarar cumplida una parte no verificada. Actualizar índice y memoria por agente autorizado, sincronizar grafos y detenerse para revisión final.
  - Evidencia 2026-11-26: revisada la matriz y los trece RF, con tests concretos/resultados en `plan.md`, sección «Cierre T10». HIGH vigente, confianza media y sin aclaraciones nuevas. No se detectó hueco automatizado que exigiera pruebas adicionales; se repiten las existentes sin fabricar rojo, modificar producción ni añadir skips/xfail.
  - Focalizadas backend, desde raíz con `$env:PYTHONPATH='backend'`: `python -m pytest backend/tests/test_sla_frozen_resolution.py backend/tests/test_ticket_metrics_snapshot.py backend/tests/test_support_resolution_metrics.py backend/tests/test_support_metrics_use_case.py backend/tests/test_support_metrics_api.py backend/tests/test_support_metrics_lifecycle.py -q -rs`: **219 passed, 3 warnings**, exit 0 (4.59 s), sin omisiones. Incluye HTTP real de la aplicación mediante TestClient, no acceso de navegador/red real.
  - Focalizadas frontend, desde `frontend`: `npm test -- --reporter=dot tests/api/httpClient.test.ts tests/pages/DashboardSupportMetrics.test.tsx tests/pages/DashboardPage.test.tsx tests/routes/guards.test.tsx tests/components/SupportMetricsPanel.test.tsx tests/hooks/useSupportMetrics.test.tsx tests/api/supportMetrics.api.test.ts`: **118 passed/7 archivos**, exit 0 (5.17 s). Incluye guardia 401 cancelado antes/durante respuesta/cuerpo pendiente y conservación de 401 vigente/rechazos, cambio de actor y periodo HU-12.
  - Puerta G completa desde raíz: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`: **1965 passed, 40 skipped, 3 warnings**, exit 0 (158.84 s). Skips PostgreSQL existentes: companies, migraciones, BD, semillas y edición de usuarios. Warnings FastAPI/Starlette existentes; sin omisiones añadidas y **sin SQL verificado**.
  - Puerta F completa desde `frontend`: `npm test`: **461 passed/43 archivos**, exit 0 (14.63 s); `npm run lint`: exit 0; `npm run build`: exit 0 (TypeScript + Vite, 1703 módulos). Solo avisos React Router Future Flags existentes.
  - Compatibilidad en verde: LIFE verifica esquema de HU-11, periodos 7/30/90 y semántica heredada HU-12, permisos de los cuatro roles y fallback general SLA 240→30 intacto frente a exclusión/invariancia HU-18. Frontend completo conserva paneles/guards previos. RF-179–191 enlazados individualmente en el plan a estos resultados.
  - Manual **no ejecutada**: sin herramienta de navegador expuesta, sin listeners 8000/5173/55432; `docker ps --filter name=infra-db-1 --format "{{.Names}} {{.Status}} {{.Ports}}"` exit 0 sin filas. No hay contenedor autorizado activo ni aplicación/sesión con datos reales disponibles en esos puertos. Tabla del plan distingue explícitamente apariencia/datos reales, alcance, teclado, sesión y reintento no verificados manualmente de las comprobaciones automatizadas verdes. No se inicia BD alternativa ni se instalan dependencias.
  - T10 marcada conforme a «evidencia o limitación explícita». Actualizados índice `specs/project.md` y memoria; `spec.md` sin cambios (aprobada, no validada por implementador). Pendientes revisión independiente final, recorrido manual real y PostgreSQL autorizado; sin invocar reviewer, commit/push/cambio de rama ni tarea nueva. Cambios ajenos preservados.
  - `cmd /c codegraph sync`, `graphify update .` y `git diff --check`: exit 0. Graphify conserva aviso de seis SQL sin extractor `tree_sitter_sql`; no se instala ninguna dependencia. Se detiene para revisión independiente.

## Propuesta de clasificación por tarea

Evidencia para el coordinador, sin delegación ni elección de ejecutores. Se reutiliza HIGH de la feature. Puntuación en orden alcance/complejidad/riesgo/ambigüedad/validación; los overrides prevalecen sobre la suma. Entradas: RF y contratos del plan; evidencia de código y runner en `plan.md`. No hay aclaraciones de negocio pendientes.

```yaml
clasificaciones:
  - tarea: T1
    clasificacion: HIGH
    riesgo: alto
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 2, complejidad: 1, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Contrato entre módulos y cálculo SLA crítico; preservar semántica general."]
  - tarea: T2
    clasificacion: MEDIUM
    riesgo: medio
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 1, complejidad: 1, riesgo: 1, ambiguedad: 0, validacion: 1, total: 4}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=1 ⇒ mínimo MEDIUM"
    justificacion: ["Lectura aditiva dentro de tickets; comprobar copia estable y compatibilidad."]
  - tarea: T3
    clasificacion: HIGH
    riesgo: alto
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 0, complejidad: 1, riesgo: 2, ambiguedad: 0, validacion: 1, total: 4}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Cálculo crítico con muestras, nulos y precisión de duraciones."]
  - tarea: T4
    clasificacion: HIGH
    riesgo: alto
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 1, complejidad: 2, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Autorización por empresa antes de lectura y coordinación SLA inyectada."]
  - tarea: T5
    clasificacion: HIGH
    riesgo: alto
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 2, complejidad: 2, riesgo: 2, ambiguedad: 0, validacion: 1, total: 7}
    nivel_por_puntuacion: HIGH
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Contrato HTTP público y composición entre módulos con autorización."]
  - tarea: T6
    clasificacion: HIGH
    riesgo: alto
    confianza: media
    requiere_aclaracion: false
    puntuacion: {alcance: 2, complejidad: 1, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Verifica cálculo crítico y no regresión entre tickets/SLA; fixtures existentes por integrar."]
  - tarea: T7
    clasificacion: HIGH
    riesgo: alto
    confianza: media
    requiere_aclaracion: false
    puntuacion: {alcance: 1, complejidad: 2, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Consumo de contrato público y evitar resultados protegidos de otra sesión."]
  - tarea: T8
    clasificacion: MEDIUM
    riesgo: medio
    confianza: alta
    requiere_aclaracion: false
    puntuacion: {alcance: 1, complejidad: 1, riesgo: 1, ambiguedad: 0, validacion: 1, total: 4}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=1 ⇒ mínimo MEDIUM"
    justificacion: ["Presentación acotada con runner existente; riesgo de confundir cero, vacío y error."]
  - tarea: T9
    clasificacion: HIGH
    riesgo: alto
    confianza: media
    requiere_aclaracion: false
    puntuacion: {alcance: 1, complejidad: 2, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Permisos de presentación y expiración/cambio de sesión sin datos residuales."]
  - tarea: T10
    clasificacion: HIGH
    riesgo: alto
    confianza: media
    requiere_aclaracion: false
    puntuacion: {alcance: 2, complejidad: 1, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
    nivel_por_puntuacion: MEDIUM
    override: "riesgo=2 ⇒ HIGH"
    justificacion: ["Aceptación incluye aislamiento y contratos; disponibilidad SQL no asegurada."]
reclasificacion: {requiere: false, motivo: null}
supuestos:
  - "Sin nuevos consumidores externos, migraciones ni dependencias."
  - "El tamaño de cada bloque se revisará al comenzar, sin ampliar silenciosamente."
```

Resumen: ocho tareas HIGH por cálculo/contratos/autorización y dos MEDIUM de lectura/presentación acotadas; sin nueva clasificación de la feature ni asignación de ejecutores.

## Estado documental y memoria

La planificación no ejecutó tareas ni pruebas. El usuario aprobó spec y después plan/tareas con «si»; la evidencia posterior corresponde a implementación, no a planificación.

El implementador actualiza `MEMORY.md`: rama HU-18 desde `0263108`, aprobaciones de spec/plan/tareas, RF-191 sin fallback, HIGH vigente y resultados reales por tarea. Conservar pendientes anteriores: persistencia HU-17, Docker CP-13/14/16 HU-26, cierre HU-16, smoke HU-15, revisión visual HU-21/HU-24, Render/secrets y despliegue. No atribuir a planificación las pruebas históricas de la memoria.
