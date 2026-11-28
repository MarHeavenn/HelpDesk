# Tareas HU-26 — Validación integral y despliegue del MVP

Orden de dependencia. Cada tarea deja evidencia verificable; no se declara una
prueba como superada sin su salida o captura.

- [x] **T1. Infraestructura local reproducible.** RF-168, RF-169
  - Hecho cuando: existen `backend/Dockerfile`, `frontend/Dockerfile` y un
    `infra/docker-compose.yml` con `db`, `api` y `web`; las migraciones se aplican
    antes de arrancar; `.env.example` documenta las variables sin secretos;
    CORS y `VITE_API_URL` apuntan a `localhost`. Si Docker no está disponible,
    el bloqueo queda registrado con la salida del comando.

- [x] **T2. Matriz de casos y guía de ejecución.** RF-166, RF-170
  - Hecho cuando: `README.md` contiene CP-01 a CP-16 con rol/acción/resultado,
    instrucciones de arranque con Docker, credenciales de desarrollo y
    limitaciones conocidas; no hay cifras ni funcionalidades inventadas.

- [x] **T3. Recorrido del flujo principal.** RF-165, RF-171
  - Hecho cuando: CP-01 a CP-08 se ejecutan contra la API real y PostgreSQL, con
    evidencia por paso; cualquier defecto crítico detectado se registra con RF/CP.

- [x] **T4. Validación de módulos nuevos y paneles.** RF-166, RF-171
  - Hecho cuando: CP-09 a CP-12 cubren empresas, usuarios, notificaciones y
    paneles SLA/alertas, con sus resultados y limitaciones documentadas.

- [x] **T5. Corrección de defectos críticos.** RF-167
  - Hecho cuando: todo defecto que impide CP-01 a CP-12 está corregido y cubierto
    por una prueba automatizada o una comprobación reproducible; se referencia
    el RF/CP detectado. Si no hay defectos críticos, se documenta tal cual.

- [x] **T6. Arranque, smoke final y cierre.** RF-168, RF-171, RF-172
  - Hecho cuando: CP-13 a CP-16 se repiten en el entorno levantado; se ejecutan
    y registran suites backend/frontend, lint, build y smoke manual; la spec
    queda con veredicto RF por RF y `MEMORY.md`/`specs/project.md` actualizados.

## Ampliación persistencia/demo — bloque A propuesto

Estado: **división A–E, plan ampliado y tareas A aprobados** por el usuario.
No confundir T1–T6 históricos con tareas de persistencia. A1–A7 hechas; el
bloque A queda **cerrado en validación de composición**, no como persistencia
integral del sistema (tickets, SLA y seed demo siguen pendientes en B–E).
División de A5 aprobada por el usuario con «si»:
nueve tareas ejecutables en A; A5 es agrupador, no un checkbox adicional.
Referencias: DEMO-1–7 y PERSIST-1–8 aprobados; sección 7 de `plan.md`.

Los bloques posteriores se detallan y aprueban por separado, sin añadir tareas
silenciosamente. Al final se propone subdividir B; C–E siguen sin detalle nuevo.
Cada tarea A estima 20–30 minutos incluyendo pruebas focalizadas; si no cabe,
detener y proponer subdivisión. Una tarea por vez, tests primero, pytest completo
en verde antes de marcar y detenerse. No borrar datos existentes.

- [x] **A1. Aislamiento seguro y caracterización de cuentas persistidas.** PERSIST-5, 6.
  - Primero tests del aislamiento SQL y fixtures de `users`/cuentas operativas:
    fila idéntica, solo operativa, conflicto e ID/asociación incompatible.
  - Hecho cuando: las pruebas usan esquema exclusivo o transacciones compartidas
    verificadas, ninguna conexión alcanza datos demo y se preservan valores originales.
    No ejecutar fixtures destructivas si esa garantía falta.
  - Evidencia: `test_hu26_sql_isolation.py` y `hu26_sql_support.py`, 18 pruebas
    focalizadas aprobadas en PostgreSQL real, sin skips; huellas de tablas public
    sin cambios. Suite completa 1971 passed / 52 skipped / 3 warnings, exit 0;
    los 12 casos SQL opt-in se ejecutaron separadamente. Detalle en el plan.

- [x] **A2. Migración incremental de reconciliación.** PERSIST-5, 6.
  - Primero tests de instalación/actualización/repetición y rollback ante conflicto.
    Luego migración nueva sin editar 001–006 ni borrar la tabla operativa previa.
  - Hecho cuando: `users` contiene las cuentas recuperadas con los mismos ID/hash/
    estados/empresa/fechas; conflictos abortan sin pérdida ni remapeo arbitrario.
    No aplicar al entorno demo activo como parte de esta tarea.
  - Evidencia: nueva 007 y `test_hu26_account_reconciliation.py`; A1+A2 SQL real
    41 passed / 2 warnings, sin skips y public intacto; regresión completa
    1972 passed / 74 skipped / 3 warnings, exit 0. Detalle de omisiones en plan.
    Pendiente A3; no desplegar la transición de adaptadores parcialmente.

- [x] **A3. Lectura canónica de identidad por ID y correo.** PERSIST-1, 5, 8.
  - Primero tests con repositorios independientes y login HTTP de cuenta no demo,
    contraseña existente, estado desactivado e invitación pendiente.
  - Hecho cuando: datos de cuentas proceden del almacén canónico y otra instancia
    ve sus cambios; no depende de poblar caché por el seed ni omite errores SQL.
  - Evidencia: `test_hu26_canonical_identity_reads.py`, 19 casos (15 SQL/HTTP y
    4 del seam explícito). Rojo: 12 failed / 7 passed. A1+A2+A3: 60 passed,
    sin skips, huellas public intactas. Suite completa: 1976 passed / 89 skipped /
    3 warnings, exit 0; 49 SQL opt-in ejecutados aparte y 40 skips anteriores.
    Solo lecturas puntuales: listados/escrituras siguen pendientes A4/A5.

- [x] **A4. Listados y contratos de cuentas persistentes.** PERSIST-1, 5, 8.
  - Primero tests de directorio, técnicos, administradores y cuentas sin empresa,
    con dos empresas y actores distintos. Luego conectar lecturas y contratos.
  - Hecho cuando: recuperan todas las cuentas autorizadas, no exponen hashes ni
    datos ajenos y conservan firmas, orden y 401/404 existentes.
  - Evidencia: A4 tiene 32 casos; A1–A4 focalizadas 92 passed sin skips, public
    intacto. La primera G falló por un doble de lectura incompleto; el usuario
    autorizó corregirlo sin relajar producción. `test_users_invitations.py`:
    13 passed, incluido intento del advisory lock y aborto sin mutación.
    G repetida: 1978 passed / 119 skipped / 3 warnings, exit 0;
    79 SQL opt-in ejecutados aparte y 40 skips anteriores. Detalle en el plan.
    A4 terminada; A5 no iniciada.

### A5. Escrituras de identidad y compatibilidad transaccional (A5a–A5c completas)

- [x] **A5a. Persistencia canónica y proyección atómica.** PERSIST-5, 6, 8.
  - Primero tests SQL de alta/guardado, fallos de ambas escrituras y del commit,
    rollback del llamador y lectura desde conexiones independientes.
  - Hecho cuando: users y la proyección previa se guardan en la misma transacción,
    no se publica caché fallida, los errores se propagan y las relecturas con
    bloqueo/token usan la autoridad canónica; firmas existentes intactas.
  - Evidencia: 26 casos nuevos (25 SQL/HTTP, 1 seam), incluidos fallos reales de
    commit y rollback entre conexiones. Rojo 21 failed / 1 passed; A1–A5a:
    118 passed sin skips, public intacto. G: 1979 passed / 144 skipped /
    3 warnings, exit 0 (104 SQL opt-in ejecutados aparte y 40 skips anteriores).
    A5b no iniciada; estados parciales no desplegables.

- [x] **A5b. Mutaciones de cuenta y último administrador.** PERSIST-5, 6, 8.
  - Primero tests de perfil/correo, rol, estado, asociación y concurrencia entre
    administradores, con conservación de credenciales/invitaciones y rollback.
  - Hecho cuando: las mutaciones se guardan explícitamente y su coordinación
    pertenece a la misma transacción; ningún cambio concurrente elimina al
    último administrador activo ni amplía permisos.
  - Evidencia: 40 casos SQL/HTTP nuevos; cinco carreras reales de dos instancias,
    guard obsoleto, rollback/commit y conservación de agregados. Rojo inicial:
    23 failed / 8 passed. A1–A5b: 158 passed sin skips, public intacto.
    G: 1979 passed / 184 skipped / 3 warnings, exit 0
    (144 SQL ejecutados aparte, 40 skips anteriores). A5c no iniciada.

- [x] **A5c. Invitaciones y cierre integrado de escrituras.** PERSIST-5, 6, 8.
  - Primero tests de alta invitada indivisible, aceptación/reenvío/desactivación
    concurrentes, fallos al confirmar y conservación desde otra instancia.
  - Hecho cuando: ciclo de invitación y transacciones del llamador son coherentes,
    HTTP real y regresión A1–A5/G están en verde, sin autoridades divergentes.
  - Evidencia: auditoría del estado parcial ya escrito (sin rojo conservado) y
    `test_hu26_identity_invitations.py` con 25 casos SQL/HTTP/proceso nuevo:
    alta atómica 168 h sin token claro, duplicado 409, rollback inmediato/diferido
    y externo, aceptación única/vencimiento 404, reenvío con rotación, seis
    carreras y HTTP 201/409/200/422/404 sin secretos. Verde focalizada:
    25 passed; A1–A5c: 183 passed sin skips, public intacto. G: 1979 passed /
    209 skipped / 3 warnings, exit 0 (169 SQL opt-in aparte, 40 skips previos).
    A5 cerrada; A6 hecha; A7 pendiente. Detalle en el plan.

- [x] **A6. Lecturas operativas persistentes de empresas.** PERSIST-1, 5, 8.
  - Primero tests por ID/listado y empresa propia desde instancia nueva, con
    asociación de cuentas persistentes, empresa inactiva y aislamiento.
  - Hecho cuando: catálogo y ficha no dependen de caché; unicidad por bloqueo,
    datos de contacto, estados y contratos existentes siguen funcionando.
  - Evidencia: `test_hu26_company_reads.py`, 17 casos (15 SQL/HTTP y 2 del seam).
    Rojo: 12 failed / 5 passed. Verde: 17 passed, exit 0. A1–A6 focalizadas:
    200 passed sin skips; huella de las 11 tablas `public` idéntica antes/después
    (`e31328c8…`) y sin esquemas `hu26_test_*` residuales. G completa:
    1981 passed / 224 skipped / 3 warnings, exit 0 (184 SQL opt-in ejecutados
    aparte y 40 skips anteriores). Detalle y límites en el plan. A7 pendiente
    en ese momento; el bloque A se cierra en A7.

- [x] **A7. Composición y validación del bloque A.** PERSIST-1, 5, 6, 8.
  - Primero comprobaciones de composición SQL obligatoria/seam explícito y nueva
    instancia/proceso; cerrar cobertura sin implementar tickets ni seed todavía.
  - Hecho cuando: migración y HTTP se verifican en PostgreSQL aislado, pytest
    completo y frontend/lint/build verdes, evidencia RF y limitaciones registradas.
    No presentar A como persistencia integral; someter a revisión y preparar B
    solo después de aprobación de la fase siguiente.
  - Evidencia: auditoría inicial sin restos de la ejecución interrumpida. Nuevo
    `test_hu26_composition.py` con 8 casos: 6 estáticos/seam y 2 SQL/HTTP/proceso
    nuevo. Contratos sin importar contratos ajenos (7 revisados), ningún módulo
    accede a tablas de otro, `main.py` como único punto de `include_router`/
    `apply_migrations`, PostgreSQL obligatorio sin configuración, seam solo con
    `HELPDESK_ALLOW_IN_MEMORY=1` y sin fallback con base inalcanzable. En esquema
    aislado 001–006→007: login HTTP 200 y `/api/companies/me` 200 con
    `users_total=1`; la proyección previa queda intacta. Un proceso hijo relee
    por SQL la empresa y la administradora pendiente creadas por HTTP (201).
    A7 focalizada: 8 passed, exit 0. A1–A7: 208 passed, 0 skips, exit 0; huella
    de las 11 tablas `public` idéntica antes/después (`902d1b7e…`) y 0 esquemas
    residuales. Backend completo: 1987 passed / 226 skipped / 3 warnings,
    exit 0. Frontend: 461 passed/43 archivos con API local inalcanzable, lint y
    build verdes; con la API viva en :8000 seis pruebas heredadas reciben 401 y
    cierran sesión (limitación de entorno documentada, sin cambios de código).
     `git diff --check` y grafos sincronizados. Bloque A cerrado en validación;
     B–E pendientes de aprobación. Detalle en el plan.
  - Revisión independiente `reviewer-deep`: **APROBADO solo A1–A7**, incluidas
    A5a/b/c, sin incumplimientos bloqueantes; no editó archivos. QA independiente:
    G sanitizada 1987 passed / 226 skipped / 3 warnings, exit 0 (146,51 s);
    nueve módulos A1–A7 con SQL real/helper aislado 208 passed / 0 skips /
    3 warnings, exit 0 (111,51 s). 186 SQL opt-in probados aparte; 40 skips
    anteriores no acreditados. Las 11 tablas `public` conservaron huellas y no
    hubo esquemas residuales antes/después; diff-check exit 0.
    QA no repitió frontend/lint/build: evidencia previa 461 pruebas/43 archivos,
    lint y build exit 0 con API inaccesible; seis fallos heredados 401 con API
    viva siguen siendo una limitación, sin acreditar integración desplegada.
    PERSIST-1/5/6/8 solo cumplen alcance A y son parciales globalmente;
    PERSIST-2/3 quedan en B, 4 en C, 7 y DEMO-1–7 en D; los demás RF de HU-26
    no se cierran globalmente. A6 solo lecturas, `count()` local; sesiones y B–E
    pendientes. Sin autorización de despliegue, migración de `public` ni reinicio;
    B requiere plan/tareas y aprobación previos a su implementación.

Para cada A: registrar comando/conteos/exit reales; actualizar memoria y sincronizar
índices si cambia código. Si falla la suite o falta SQL seguro, detener y reportar.
Ningún comando destructivo ni recreación de contenedores está autorizado por
estas tareas. Los cambios de esquema del plan no se aplican a datos activos sin
comprobaciones previas y autorización para esa operación.

## Bloque B — subdivisión y detalle B.I aprobados

Estado (2026-11-27): **detalle B.I aprobado**. Tras B.I.1, el usuario pidió
«completa las demas tareas»: autoriza B.I.2–B.I.9 en orden, una tarea por vez
y con sus puertas, no B.II–IV ni migración activa/despliegue. A y sus resultados
permanecen sin cambios. Referencia: secciones 8 y 8.9 de `plan.md`; spec intacta.

**División por tamaño aprobada:** la estimación inicial de B fue de 22 unidades.
El detalle de B.I separa HTTP y proceso nuevo y pasa de siete a nueve tareas,
sin superar diez ni agrupar megatareas: aproximadamente 24 para B completo.
B.II–IV conservan solo estimación/alcance, sin tareas detalladas ni aprobación
para implementar.

### Subbloques aprobados en alcance (no son tareas ejecutables)

| Propuesta | Dependencia y alcance | RF de HU-26 | Hecho cuando (del subbloque completo, no de una tarea) |
|---|---|---|---|
| **B.I — Base SQL y compatibilidad** | A validado; detalle aprobado. Caracterización legacy, campos de tickets, consultas SQL/instantánea HU-18 y alta confirmada. Nueve tareas | PERSIST-1/2/5 parcial/6/8 | Instalación/actualización/repetición y rollback se prueban en A1; se preservan filas previas, nuevas instancias leen SQL y el alta HTTP confirma antes del 201. Datos históricos no demostrables no se rellenan y cualquier decisión bloqueante se consulta |
| **B.II — Mutaciones y ciclo de vida** | B.I validado y detalle B.II aprobado. Coordinación local; prioridad, estado y reapertura con registro, resolución y objetivo conservado. Estimación: 5 unidades | PERSIST-1/2/3/5 parcial/6/8 | HTTP real verifica transiciones/no-ops/errores; ticket y modificación se confirman o revierten juntos, incluido fallo de COMMIT, transacción externa y carreras. No se pierden campos por guardar una lectura obsoleta ni se publican notificaciones de una operación revertida |
| **B.III — Asignaciones, comentarios e historial** | B.II validado y detalle B.III aprobado. Adaptadores/operaciones de asignación y comentarios, orden persistente e historial derivado. Estimación: 6 unidades | PERSIST-1/2/3/6/8 | HTTP real y SQL recuperan autores/fechas/contenido, asignaciones y registros efectivos en orden HU-09; no-ops/rechazos no generan eventos. Rollback y carreras cierre/comentario y reasignación/mutación mantienen permisos, historial e integridad |
| **B.IV — Composición y cierre de B** | B.I–III validados y detalle B.IV aprobado. Contratos, consumidores, HU-17/HU-18, proceso nuevo y puertas finales. Estimación: 4 unidades | PERSIST-1/2/3/5 parcial/6/8; RF-165/167/171 parciales | Un proceso nuevo reautentica y relee por HTTP lo registrado sin seed/caché; métricas y DTO permanecen compatibles, A+B SQL aislado pasa sin skips, G y frontend/lint/build tienen evidencia real, QA independiente y límites registrados sin cerrar C–E |

### Condiciones de ejecución tras aprobar el detalle

- Máximo diez tareas por subbloque, ordenadas por dependencia y de 20–30 minutos;
  cada tarea incluirá sus RF, tests primero y «Hecho cuando» verificable.
  Una tarea por vez, focalizadas/G y parada; no marcar B como hecho ahora.
- SQL solo con helper A1, esquema propio y DSN opt-in; conexiones de HTTP,
  nueva instancia/proceso y concurrencia también scoped. Huellas agregadas
  `public` antes/después y cero esquemas residuales. No fixtures destructivas
  contra demo ni migración de la base activa.
- G se ejecutará aparte sin `DATABASE_URL`, `POSTGRES_PASSWORD` ni
  `HU26_TEST_DATABASE_URL`; SQL A+B aparte sin skips. Fallos y skips anteriores
  se informan, no se ocultan. Frontend offline de CI no acredita integración
  con API viva; conservar como limitación los seis fallos heredados 401.
- Mantener permisos, DTO y contratos sin imports cruzados; no leer tablas de
  identity/SLA desde tickets. Reutilizar A y verificar su regresión.
- No inventar resolución, objetivo SLA, nombre histórico ni orden legacy.
  Si `ticket_sla` requiere reconciliación o comentarios SQL empatados carecen
  de orden demostrable, detener compatibilidad y consultar antes de decidir.
  No se promete recuperar cachés/listas del proceso anterior ni importarlas.
- PERSIST-5 solo parcial en B; políticas/notificaciones son C, seed D y
  recreación/reinicio desplegado E. Sesiones fuera de esta ampliación.
  Despliegue, migración de `public` y reinicio requieren autorización distinta.

### B.I — tareas detalladas aprobadas (2026-11-27)

**Autorización:** inicialmente solo B.I.1 («empieza con las tareas B.I.1 de
HU-26»); posteriormente «completa las demas tareas» aprueba B.I.2–B.I.9,
sin ampliar a otros subbloques. Nueve tareas, 245 minutos estimados.
Orden secuencial: cada tarea posterior requiere validación de la anterior.
Si una tarea no cabe en 20–30 minutos, parar y proponer su división.
No ejecutar migración en base activa ni desplegar B.I parcialmente.

**Puerta común de cada tarea:** tests primero (sin fabricar rojo en una mera
caracterización), focalizadas nuevas/acumuladas SQL en esquema A1 y sin skips,
después G completa en proceso sanitizado sin `DATABASE_URL`,
`POSTGRES_PASSWORD` ni `HU26_TEST_DATABASE_URL`, seam explícito de memoria.
Registrar comandos, resultados, exit, skips previos no acreditados y huellas
agregadas `public` antes/después de SQL; cero esquemas residuales y sin secretos
en salida. Cualquier fallo bloquea marcar/continuar. Una tarea por vez y parada;
no afirmar que G en memoria valida mutaciones SQL pendientes.
Los nombres de archivo siguientes son propuestas de implementación, no archivos
creados en esta fase.

- [x] **B.I.1. Caracterizar legado SQL y límites recuperables.** HU-26 PERSIST-2,
  PERSIST-3, PERSIST-5, PERSIST-6, PERSIST-8 (precondiciones, no cumplimiento total).
  - Estimación: 25 min. Dependencia: A validado y aprobación del detalle B.I.
  - Archivos previstos: `backend/tests/test_hu26_ticket_legacy.py`; reutilizar
    `backend/tests/hu26_sql_support.py` y patrón de actualización A2 sin
    debilitar su aislamiento.
  - Primero: fixtures sintéticas desde esquema 007 con tickets de dos empresas
    y cuatro estados; conservar IDs, relaciones, creación y `updated_at`.
    Distinguir campos aún inexistentes de valores nulos. Incluir comentarios
    empatados sin orden y filas `ticket_sla` que no autorizan inferir objetivo.
    Definir casos posteriores con resolución conocida y objetivo conocido/
    ausente, sin fingir que ya existían en la tabla de tickets de 007.
  - Hecho cuando: las pruebas caracterizan exactamente qué evidencia existe y
    qué falta, preservan las filas y no generan backfill/eventos/importación de
    memoria. Ambigüedades se diagnostican sin datos personales; si una decisión
    histórica es necesaria para continuar, se solicita antes de resolverla.
     Aislamiento y puerta común pasan; no se inspecciona el demo activo.
   - Evidencia: 4 focalizadas y 212 acumuladas A1–A7+B.I.1, sin skips;
     G sanitizada 1987 passed/230 skipped, exit 0. Detalle y huella en plan,
     sección «Evidencia B.I.1». En ese momento no se había autorizado B.I.2.

- [x] **B.I.2. Añadir solo los campos persistentes faltantes del ticket.**
  HU-26 PERSIST-2, PERSIST-6.
  - Estimación: 30 min. Dependencia: B.I.1.
  - Archivos previstos: nueva `backend/migrations/<siguiente>_ticket_persistence.sql`
    posterior a 007, número libre a comprobar al implementar;
    `backend/tests/test_hu26_ticket_schema.py`.
  - Primero: tests de instalación limpia, actualización desde 007 con datos,
    repetición por el runner y fallo transaccional de migración.
  - Hecho cuando: `assignee_name`, `resolved_at` y `resolved_target_minutes`
    son anulables, sin fechas/objetivos/nombres inventados; se mantienen todos
    los valores previos, `updated_at`, FK y triggers. Un fallo no confirma ni
    versión ni cambio parcial. No se modifican 001–007, `ticket_sla`,
    comentarios ni se crean aún tablas de historial. Puerta común verde;
     ninguna migración aplicada fuera del esquema A1.
   - Evidencia: rojo 6 failed; nueva 008, focalizada 6 passed/0 skips.
     Primera acumulada detenida: 214 passed/4 failed porque cuatro escenarios
     históricos A2/A7 esperaban solo 007 pendiente. Usuario autorizó con «si»
     acotarlos hasta 007, manteniendo todas sus aserciones; ajuste local a esos
     escenarios, sin cambiar runner global, producción ni pruebas de 008.
     Reanudación: focalizadas A2+A7+B.I.2 **37 passed/0 skips** (28,39 s);
     acumulada A1–A7+B.I.1+B.I.2 **218 passed/0 skips** (154,58 s);
     G sanitizada **1988 passed/235 skipped** (196,44 s), todos exit 0.
     195 SQL opt-in probados aparte; 40 skips previos no acreditados.
     Huellas 11 tablas public intactas y 0 residuos. Comandos y límites en
     «Reanudación autorizada de B.I.2» del plan. B.I.3 no iniciada.

- [x] **B.I.3. Leer tickets por ID desde su tabla, con seam explícito.**
  HU-26 PERSIST-1, PERSIST-2, PERSIST-6, PERSIST-8.
  - Estimación: 25 min. Dependencia: B.I.2.
  - Archivos previstos: `backend/app/modules/tickets/infrastructure/ticket_repository.py`;
    `backend/tests/test_hu26_ticket_reads.py`.
  - Primero: tests con dos repositorios/conexiones independientes, fila completa
    y nulos legacy; cambio SQL confirmado entre lecturas, caché obsoleta,
    ID inválido/inexistente, tabla local ausente y base configurada inaccesible.
  - Hecho cuando: `find_by_id` recupera todos los campos propios conservando
    IDs, instantes y ausencia real; no consulta memoria autoritativa ni tablas
    de identity/SLA. Errores SQL se propagan sin resultado vacío de éxito;
    sin SQL se exige `HELPDESK_ALLOW_IN_MEMORY=1`, que no sustituye una base
    configurada fallida. IDs inválidos conservan `None`/404 de aplicación.
     Nombres ausentes quedan ausentes en el agregado, no se inventan aquí.
     Referencias retenidas no se mutan por releer. Puerta común verde.
   - Evidencia: `test_hu26_ticket_reads.py`, 20 casos (9 SQL y 11 de seam/errores).
     Rojo 13 failed/7 passed; verde 20 passed/0 skips (6,22 s);
     acumulada A1–A7+B.I.1–3 238 passed/0 skips (125,73 s).
     G sanitizada 1999 passed/244 skipped/3 warnings (201,91 s), exit 0;
     204 SQL opt-in ejecutados aparte y 40 skips previos no acreditados.
     Todas las corridas SQL conservaron huellas de 11 tablas public y 0 residuos.
     Solo lectura por ID; sin cambios de contratos, listados ni escritores.
     Comandos, entorno y límites en «Evidencia B.I.3» del plan.

- [x] **B.I.4. Conectar listados y contador a consultas SQL propias.**
  HU-26 PERSIST-1, PERSIST-2, PERSIST-6, PERSIST-8.
  - Estimación: 25 min. Dependencia: B.I.3.
  - Archivos previstos: `backend/app/modules/tickets/infrastructure/ticket_repository.py`;
    ampliar `backend/tests/test_hu26_ticket_reads.py`.
  - Primero: tests de `list_by_requester`, `list_by_assignee`, `list_all` y
    `count`, con repositorios independientes, dos empresas, los cuatro estados,
    técnicos sin/asignados, títulos iguales y empates de creación.
  - Hecho cuando: consultas reflejan altas/cambios confirmados sin poblar caché,
    conservan orden descendente por creación (sin atribuir orden histórico a
    sus empates) y no deduplican por texto. `count` cuenta SQL confirmado;
    `clear` rechaza limpieza SQL y sigue disponible solo para el seam.
    No introducir filtros de permisos nuevos en el repositorio; los casos de
    uso conservan sus reglas. Fallos SQL no devuelven listas/ceros ficticios.
     Las fixtures A no se vuelven destructivas; puerta común verde.
   - Primera ejecución detenida (resuelta abajo): rojo 17 failed/15 passed; focalizada verde
     **32 passed/0 skips** (19,58 s). Acumulada A1–A7+B.I.1–4:
     **1 failed/249 passed/0 skips/3 warnings**, exit 1 (131,68 s).
     A7 histórico 006→007 falla al componer HTTP `/api/companies/me`: list_all SQL
     requiere assignee_name de 008. No se modificó esa prueba ni se ejecutó G.
     B.I.4 sin marcar; propuesta de ajuste acotado al escenario A7 pendiente
     de autorización. Huellas de 11 tablas public intactas/0 residuos.
     Comandos, diagnóstico y límites en «Evidencia B.I.4» del plan.
   - Reanudación autorizada con «si»: solo el escenario A7 conserva sus aserciones
     006→007/reconciliación y después aplica pendientes en el mismo esquema A1
     antes del HTTP, sin fijar última migración ni cambiar producción.
     Focalizadas A7+ticket_reads: **40 passed/0 skips/3 warnings**, exit 0
     (27,56 s); acumulada A1–A7+B.I.1–4: **250 passed/0 skips/3 warnings**,
     exit 0 (136,34 s). G sanitizada: **1999 passed/256 skipped/3 warnings**,
     exit 0 (210,29 s): 216 SQL opt-in verificados aparte y 40 skips previos
     no acreditados. Huellas de las 11 tablas public idénticas/0 residuos.
     B.I.4 marcada tras las puertas verdes; B.I.5 no iniciada. Evidencia detallada
     y comandos en «Reanudación autorizada de B.I.4» del plan.

- [x] **B.I.5. Obtener la instantánea SQL de HU-18 sin reconstruir objetivos.**
  HU-26 PERSIST-2, PERSIST-5 (parcial), PERSIST-8;
  compatibilidad HU-18 RF-179–188 y RF-191.
  - Estimación: 25 min. Dependencia: B.I.4.
  - Archivos previstos: `backend/app/modules/tickets/infrastructure/ticket_repository.py`;
    `backend/tests/test_hu26_ticket_metrics_snapshot.py`.
  - Primero: tests de instantánea inmutable y una sola consulta; ejecutar el
    caso de uso HU-18 existente sobre fixtures SQL con pendientes/finalizados,
    resolución ausente/válida, objetivo conservado conocido/ausente y dos empresas.
    Verificar el ejemplo de muestras distintas y una lectura posterior a commit.
  - Hecho cuando: `snapshot_for_metrics` copia exactamente las columnas propias,
    sin política vigente, caché ni fechas inferidas; autorización previa y
    conjunto por empresa siguen en el caso de uso. Solo Resuelto/Cerrado con
    fechas válidas entran al promedio; sin objetivo conservado se excluyen de
    SLA, no de volumen/promedio válido. Cambiar la política en el seam de
    prueba no cambia esas muestras ni valores congelados. No editar fórmulas/
    archivos de HU-18 ni persistir políticas; puerta común verde.
  - Evidencia: nuevo `test_hu26_ticket_metrics_snapshot.py`, 27 casos (16 SQL
    opt-in y 11 de autorización/seam/errores). Rojo **21 failed/6 passed**,
    exit 1 (6,14 s); focalizada **27 passed/0 skips**, exit 0 (7,95 s).
    Acumulada A1–A7+B.I.1–5: **277 passed/0 skips/3 warnings**, exit 0
    (136,39 s). G sanitizada: **2010 passed/272 skipped/3 warnings**, exit 0
    (208,36 s): 232 SQL ejecutados aparte, 40 skips previos no acreditados.
    Las 11 tablas public conservaron su huella y hubo 0 esquemas residuales
    antes/después de cada corrida SQL. Comandos/huella/cobertura en «Evidencia
    B.I.5» del plan. Cierre documental reanudado tras límite de pasos, sin
    repetir pruebas ni cambiar código. Sin decisiones nuevas ni archivos/fórmulas
    HU-18 modificados, políticas persistentes, INSERT o mutaciones nuevas.
    No desplegar el adaptador parcial; B.I.6 pendiente y no iniciada.

- [x] **B.I.6. Insertar el ticket con propiedad explícita del commit.**
  HU-26 PERSIST-1, PERSIST-2, PERSIST-6, PERSIST-8.
  - Estimación: 30 min. Dependencia: B.I.5.
  - Archivos previstos: `backend/app/modules/tickets/infrastructure/ticket_repository.py`;
    `backend/tests/test_hu26_ticket_insert.py`.
  - Primero: tests de INSERT con conexión propia y del llamador; rollback,
    error inmediato y error diferido al COMMIT real, fallo capturado por un
    llamador que luego confirma, y dos conexiones que compiten por el mismo ID.
    Reutilizar patrones transaccionales de A5, sin diseñar aún la unidad de
    mutaciones. Probar títulos iguales con IDs diferentes.
  - Hecho cuando: solo una fila nueva se inserta y relee desde otra instancia;
    un ID ya existente no se sobrescribe ni se restaura al estado inicial.
    Con conexión propia no se retorna antes del commit; con conexión externa
    no se confirma trabajo del llamador y las otras conexiones no ven la fila
    pendiente. Fallos no dejan fila/caché ni progreso parcial; el rollback del
    llamador conserva su control. No hay UPSERT de progreso, fallback ni SQL
     ajeno. Seam anterior intacto; puerta común verde.
  - Evidencia: nuevo `test_hu26_ticket_insert.py`, 28 casos (22 SQL opt-in y
    6 de seam/errores). Rojo **27 failed/1 passed**, exit 1 (9,83 s);
    focalizada **28 passed/0 skips**, exit 0 (11,35 s). Acumulada
    A1–A7+B.I.1–6 **305 passed/0 skips/3 warnings**, exit 0 (153,64 s).
    G sanitizada **2016 passed/294 skipped/3 warnings**, exit 0 (213,58 s):
    254 SQL ejecutados aparte y 40 skips previos no acreditados. Conexión
    propia confirma antes del retorno; externa conserva commit/rollback,
    incluso idle/autocommit. Fallos SQL inmediato/COMMIT real y Python
    capturado no publican fila/caché ni trabajo parcial; carrera de dos
    conexiones por ID deja un ganador sin sobrescritura. 11 huellas public
    intactas/0 residuos. Comandos y límites en «Evidencia B.I.6» del plan.
    Sin cambios HTTP, mutaciones, seed, contratos ni dependencias.

- [x] **B.I.7. Verificar alta confirmada y relectura mediante HTTP real.**
  HU-26 PERSIST-1, PERSIST-2, PERSIST-6, PERSIST-8;
  HU-26 RF-165 y RF-171 (solo tramo de alta/consulta).
  - Estimación: 25 min. Dependencia: B.I.6.
  - Archivos previstos: `backend/app/modules/tickets/application/create_ticket.py`
    y `backend/app/modules/tickets/interface/router.py` solo si necesitan
    composición; `backend/tests/test_hu26_ticket_create_http.py`.
  - Primero: TestClient de la app real con login y un cliente por rol.
    POST válido, entradas inválidas, petición sin sesión y fallo de COMMIT real;
    después GET de detalle/listado desde repositorio nuevo y otra conexión.
  - Hecho cuando: 201 corresponde a fila confirmada con mismo UUID/texto/
    creación/empresa/solicitante, Abierto y prioridad/técnico/resolución nulos;
    contrato exacto y reglas de alta vigentes no cambian. 401/422 existentes
    no insertan nada; ante fallo SQL/COMMIT no hay 2xx ni fila ni caché fallida.
     Se prueban rutas y casos de uso reales, no mocks de persistencia.
     No conectar PUT/reopen/comentarios ni seed; puerta común verde.
  - Evidencia: `test_hu26_ticket_create_http.py`, 29 casos SQL/HTTP reales.
    Validación de composición existente: sin rojo artificial ni cambios de
    producción. Focalizada **29 passed/0 skips**, exit 0 (16,52 s); acumulada
    A1–A7+B.I.1–7 **334 passed/0 skips/3 warnings**, exit 0 (166,17 s).
    G sanitizada **2016 passed/323 skipped/3 warnings**, exit 0 (173,69 s):
    283 SQL opt-in ejecutados aparte y 40 skips previos no acreditados.
    201 confirmado, DTO exacto, GET con repositorio nuevo y 401/404/409/422
    sin inserción; fallo SQL inmediato/COMMIT real devuelve 500 sin fila/caché.
    Huellas de 11 tablas public intactas/0 residuos en ambas corridas SQL.
    Comandos y límites en «Evidencia B.I.7» del plan. B.I.8 no iniciada.

- [x] **B.I.8. Preservar DTO y visibilidad de consultas con legado SQL.**
  HU-26 PERSIST-2, PERSIST-5 (parcial), PERSIST-8.
  - Estimación: 30 min. Dependencia: B.I.7.
  - Archivos previstos: `backend/app/modules/tickets/interface/router.py`,
    composición de lectura ya existente si es indispensable;
    `backend/tests/test_hu26_ticket_read_http.py`.
  - Primero: HTTP real de detalle/listados con solicitante propio/ajeno,
    administrador empresarial/plataforma, técnico y cuentas sin empresa según
    el permiso de cada ruta; dos empresas y cuerpos/IDs inválidos pertinentes.
    Filas asignadas sin nombre proyectado y con nombre ya conservado.
  - Hecho cuando: 401/404 y alcances vigentes se mantienen antes de componer
    datos; el resumen conserva sus ocho claves y solicitante mínimo. El nombre
    actual faltante se obtiene solo por el contrato de identidad tras autorizar,
    sin inventar un nombre histórico, cambiar ID o reemplazar la proyección
    conocida; no se filtra una asignación histórica por elegibilidad actual.
    Si no puede componerse sin inventar, detener esa compatibilidad y consultar.
    Resolución/objetivo ausentes no se rellenan y no aparecen campos nuevos,
     hashes/tokens/correos adicionales. No ampliar a validación de todos los
     dashboards ni mutaciones SQL; puerta común verde.
  - Evidencia: nuevo `test_hu26_ticket_read_http.py`, 60 casos SQL/HTTP reales.
    Rojo funcional **22 failed/38 passed**, exit 1 (40,40 s); ajuste mínimo
    de composición en `tickets/interface/router.py`; focalizada **60 passed/
    0 skips/3 warnings**, exit 0 (43,77 s). Nombre actual solo por contrato
    tras autorizar, sin ocultar ID, reemplazar proyección ni filtrar por rol/
    estado actual; detalle y cuatro listados conservan permisos y DTO.
    Acumulada A1–A7+B.I.1–8 **394 passed/0 skips/3 warnings**, exit 0
    (206,68 s); G sanitizada **2016 passed/383 skipped/3 warnings**, exit 0
    (179,70 s): 343 SQL opt-in ejecutados aparte y 40 skips previos no
    acreditados. Huellas de 11 tablas public intactas/0 residuos en todas las
    corridas SQL. Comandos y límites en «Evidencia B.I.8» del plan.
    Sin mutaciones SQL nuevas ni B.I.9 iniciada.

- [x] **B.I.9. Probar proceso nuevo y cerrar solo la base SQL de B.I.**
  HU-26 PERSIST-1, PERSIST-2, PERSIST-6, PERSIST-8;
  HU-26 RF-171 (evidencia parcial, no despliegue).
  - Estimación: 30 min. Dependencia: B.I.8.
  - Archivos previstos: `backend/tests/test_hu26_ticket_base_composition.py`,
    reutilizando patrones de `test_hu26_composition.py` de A7;
    evidencia en este `tasks.md` y `plan.md`.
  - Primero: HTTP de alta en padre, luego app en intérprete hijo con solo
    configuración scoped de pruebas y reautenticación, sin seed ni caché;
    GET de detalle/listados conserva ID, texto, fechas, referencias y nulos.
    Comprobar fronteras propias y contratos sin imports cruzados. El hijo no
    recupera supuestas mutaciones hechas solo en memoria ni sesiones anteriores.
  - Hecho cuando: prueba SQL/HTTP/proceso nuevo pasa sin skips y sin reiniciar
    servicios; A1–A7+B.I SQL completo pasa aparte de G sanitizada, public queda
    intacto y no hay esquemas residuales. Frontend/lint/build tienen evidencia
    con API/entorno declarados y límites 401 heredados sin ocultarlos; revisión
    independiente y matriz RF dejan explícito el alcance parcial. No se cierra
     PERSIST-3, políticas/notificaciones, seed, recorrido desplegado ni B completo.
     Sin cambios de contratos ni tablas ajenas; si falla cualquier puerta, parar.
  - Evidencia de implementación B.I.9: nuevo
    `test_hu26_ticket_base_composition.py`, tres comprobaciones de fronteras/
    composición y dos casos SQL/HTTP/proceso nuevo (alta cliente/administrador).
    Sin rojo artificial ni cambios de producción: se valida composición existente.
    Hijo con solo SQL scoped, sin seed/caché, rechaza cookie anterior (401),
    reautentica y conserva detalle/listados, referencias/fechas/nulos. Cambios
    exclusivamente locales y caché fantasma no se recuperan; sesiones no persistidas.
    Focalizada **5 passed/0 skips/3 warnings**, exit 0 (5,36 s);
    acumulada A1–A7+B.I.1–9 **399 passed/0 skips/3 warnings**, exit 0 (226,10 s).
    Huellas de las 11 tablas public intactas/0 residuos en ambas corridas SQL.
    Comandos, matriz RF parcial y límites en «Evidencia B.I.9» del plan.
    G sanitizada **2019 passed/385 skips/3 warnings**, exit 0 (179,52 s):
    345 SQL opt-in probados aparte y 40 skips previos no acreditados.
    Frontend offline `VITE_API_URL=http://127.0.0.1:1`: **461 passed/43 archivos**,
    exit 0 (16,56 s); lint/build exit 0. No integración desplegada: API/web
    apagadas, seis fallos 401 heredados con API viva siguen documentados.
    **Implementada y aprobada en QA independiente reviewer-deep**, solo B.I.1–9,
    sin incumplimientos bloqueantes; QA no editó archivos ni invocó reviewer-expert.
  - QA independiente: acumulada SQL A1–A7+B.I **399 passed/0 skips**, exit 0
    (208,57 s); G sanitizada **2019 passed/385 skips**, exit 0 (166,91 s),
    345 SQL opt-in pasados aparte y 40 skips previos no acreditados. Primera QA
    SQL **398 passed/1 failed** por Windows 10048 al conectar antes del HTTP
    (`test_hu26_ticket_read_http.py:194`); repetición completa verde sin cambios
    de código/servicios. 11 huellas public idénticas/0 residuos; diff-check QA 0.
    QA no repitió frontend/lint/build: evidencia offline anterior y límite
    de seis 401 con API viva vigentes. Matriz/compatibilidad HU-18 en el plan:
    RF-187 ciclo de vida solo en memoria, no mutaciones SQL.
    PERSIST-1/2/5 parcial/6/8, RF-165 solo alta/consulta y RF-171 cumplen
    alcance B.I, parciales globalmente; no cierra PERSIST-3, B ni HU-26.

**Dudas y límites de aprobación:** no hay ahora una decisión concreta de negocio
demostrada por datos activos; los posibles conflictos de resolución/objetivo/
orden/nombre se diagnostican en fixtures y se consultan si bloquean continuar.
No se garantiza rescate de cachés ni importación de memoria.
B.II conserva mutaciones/ciclo de vida; B.III asignaciones/comentarios/historial;
B.IV validación completa de consumidores y cierre B. Ninguno se adelanta aquí.

**Cierre B.I:** B.I.1–9 implementadas y aprobadas por QA independiente reviewer-deep.
B.II–IV y C–E permanecen pendientes de sus detalles/aprobaciones separados.
El permiso de B.I no autoriza B.II–IV, despliegue, migrar public ni reinicios.
