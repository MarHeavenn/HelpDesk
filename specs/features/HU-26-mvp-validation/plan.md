# Plan HU-26 — Validación integral y despliegue del MVP

Estado: aprobado

Spec base: `specs/features/HU-26-mvp-validation/spec.md` (RF-165 a RF-172).
Alcance: verificación y despliegue local. **No se implementan funcionalidades
nuevas**; los defectos críticos se corrigen y se cubren con pruebas.

## 1. Arquitectura del entorno

Un único `infra/docker-compose.yml` ampliado con tres servicios:

| Servicio | Imagen / build | Puerto | Comprobación de salud |
|---|---|---|---|
| `db` | `postgres:16` | 55432 | `pg_isready` (ya existe) |
| `api` | `backend/Dockerfile` (FastAPI + uvicorn) | 8000 | `GET /health` |
| `web` | `frontend/Dockerfile` (Vite + nginx) | 8080 | `GET /` |

- La API depende de `db` con `condition: service_healthy`; aplica migraciones
  antes de arrancar y siembra las cuentas demo de forma idempotente.
- El bundle del frontend recibe `VITE_API_URL=http://localhost:8000` en tiempo
  de construcción; nginx sirve la SPA y reenvía las rutas a `index.html`.
- CORS permite `http://localhost:8080`; la cookie `SameSite=Lax` viaja entre
  `localhost:8080` y `localhost:8000` por compartir host.
- `POSTGRES_PASSWORD` y las contraseñas demo se leen de variables de entorno con
  valores por defecto solo de desarrollo; se documentan en `.env.example` sin
  secretos reales.

## 2. Estrategia de validación

Recorridos, no módulos aislados, para comprobar la integración real:

1. **Cliente**: login → crear ticket → «Mis tickets» → detalle propio.
2. **Administrador**: login → dashboard → asignar ticket → comprobar SLA →
   usuarios y empresas.
3. **Técnico**: login → ticket asignado → prioridad → estado → comentario →
   notificaciones.
4. **Cierre**: resolver como técnico, cerrar como administrador, comprobar
   `resolved_at` y SLA congelado.
5. **Paneles**: alertas de SLA y notificaciones visibles en el dashboard.
6. **Regresión**: suites de backend y frontend, lint y build.

Cada paso se registra con rol, acción, resultado esperado, obtenido y evidencia
(salida de comando o captura).

## 3. Casos de prueba mínimos

| ID | Rol | Acción | Resultado esperado | RF |
|---|---|---|---|---|
| CP-01 | Cliente | Login y alta de ticket | 201, `Abierto`, sin técnico | RF-165 |
| CP-02 | Cliente | Ver «Mis tickets» y detalle propio | Solo sus tickets, sin acciones de edición | RF-165 |
| CP-03 | Admin | Dashboard y asignación | Métricas reales; técnico visible en el detalle | RF-165, RF-166 |
| CP-04 | Técnico | Prioridad y paso a `En progreso` | 200, SLA recalculado y señal visible | RF-165, RF-166 |
| CP-05 | Técnico | Comentario | 201, visible en seguimiento | RF-165 |
| CP-06 | Técnico | Resolver | 200, `Resuelto`, `resolved_at` fijado | RF-165 |
| CP-07 | Admin | Cerrar | 200, `Cerrado`, SLA congelado | RF-165 |
| CP-08 | Admin | Modificar ticket cerrado | 409, sin cambios | RF-165 |
| CP-09 | Admin | Empresas: alta, estado y administrador | Catálogo real, sin secretos en la respuesta | RF-166 |
| CP-10 | Admin | Usuarios: consulta, rol y estado | Roles aplicados, último admin protegido | RF-166 |
| CP-11 | Técnico | Campana y `/notificaciones` | Avisos visibles, marcar como leída | RF-166 |
| CP-12 | Admin | Panel de alertas y cumplimiento SLA | Cifras derivadas de la API, sin «Demo» | RF-166 |
| CP-13 | Público | Abrir `http://localhost:8080` | Login accesible y API conectada | RF-168, RF-169 |
| CP-14 | Equipo | `docker compose up --build` desde copia limpia | Los tres servicios sanos y migraciones aplicadas | RF-168 |
| CP-15 | Equipo | Ejecutar suites, lint y build | Todo en verde o bloqueo documentado | RF-171 |
| CP-16 | Equipo | Repetir CP-01..CP-13 en el entorno levantado | Evidencia registrada | RF-171 |

## 4. Corrección de defectos

- Crítico: impide CP-01 a CP-12, el login o el arranque con Docker.
- Cada corrección sigue el flujo SDD de su historia: prueba en rojo, cambio
  mínimo, prueba en verde, referencia al RF/CP que lo detectó.
- Los defectos menores se registran en `MEMORY.md` con impacto y workaround.

## 5. Evidencia y documentación

- `README.md`: sustituye el estado obsoleto; instalar, migrar, arrancar con
  Docker, URLs, credenciales de desarrollo, recorridos y limitaciones.
- `MEMORY.md`: estado del despliegue, comandos ejecutados y resultados.
- Matriz CP-01..CP-16 con resultado y evidencia, y validación RF por RF.

## 6. Riesgos

- **Docker no disponible en el entorno de trabajo**: no se puede afirmar el
  despliegue; se documenta y se entregan los archivos listos (RF-171).
- **Puertos ocupados**: 5432 queda reservado para otro contenedor; usar 55432.
- **CORS/cookie**: si se cambia `localhost` por otra dirección, ajustar
  `VITE_API_URL`, CORS y `SameSite`; se documenta.
- **Datos demo en PostgreSQL**: la semilla debe ser idempotente y no borrar
  cuentas persistidas.

## 7. Ampliación de persistencia y datos demo — propuesta

Estado: **división A–E y plan/tareas A aprobados** por el usuario con «apruebo».
DEMO-1–7 y PERSIST-1–8 aprobados. A1–A7 ejecutadas en esquemas de pruebas y
validadas en composición; el bloque A queda cerrado, sin afirmar persistencia
integral. Migración 007 creada, no aplicada a la base activa. Identidad
(lecturas, listados, escrituras, invitaciones), lecturas de empresas y seam de
composición verificados; tickets, SLA, seed demo y reinicios siguen en B–E.

### Evidencia, complejidad y división

CodeGraph confirma repositorios operativos en memoria de tickets, asignaciones,
modificaciones, comentarios, notificaciones y políticas SLA. Cambiar solo `add()`
no basta: estado/prioridad/asignación mutan objetos sin guardar explícitamente.
Identidad escribe en `identity_invitation_accounts`, pero tickets y comentarios
referencian `users`. Empresas y cuentas tienen también lecturas locales.
`001_init.sql` ya define tickets, comentarios y SLA, pero faltan campos/registros
operativos. No reescribir migraciones aplicadas.

Graphify se usó para navegación. El 2026-11-26 Compose mostró PostgreSQL y API
saludables, frontend unhealthy. Esto no acredita persistencia ni autoriza borrar
datos. Complejidad HIGH por esquema, datos previos, autorización y transacciones.

El alcance supera diez tareas: **se propone dividir antes de implementar**:

| Bloque | Entregable | Dependencia | Requisitos |
|---|---|---|---|
| A | Identidad y empresas persistentes, coherentes con relaciones SQL | Aprobar este plan y tareas A | PERSIST-1, 5, 6, 8 |
| B | Tickets, comentarios e historial; escrituras atómicas | A validado; aprobar plan/tareas B | PERSIST-1–3, 6, 8 |
| C | SLA y notificaciones persistentes, incluida deduplicación | B validado; aprobar plan/tareas C | PERSIST-1, 4–6, 8 |
| D | Seed idempotente y ambos administradores | A–C validados; aprobar plan/tareas D | DEMO-1–7, PERSIST-7 |
| E | Reinicio real y regresión integral documentada | A–D validados; aprobar plan/tareas E | Todos los anteriores |

La autorización inicial de tareas ejecutables correspondió solo a A. La sección 8
añade el diseño de B y propone subdividirlo; no autoriza su implementación.
B–E no se implementan de una vez. Ningún bloque aislado equivale a persistencia completa.
Si una tarea supera 20–30 minutos o un bloque supera diez tareas, proponer división.

### Arquitectura y decisiones del bloque A

- Mantener monolito, capas, psycopg y runner existentes, sin ORM ni dependencias
  nuevas. Cada módulo consulta sus propias tablas; los demás reciben contratos.
  Ningún contrato importa el contrato de otro; composición en router/main.
- Elegir adaptadores SQL para operación con PostgreSQL; memoria solo por
  inyección/seam explícito de pruebas. No fallback silencioso ni caché inicial
  como fuente autoritativa. Lecturas desde repositorios independientes deben
  ver lo confirmado, sin depender de objetos del proceso previo.
- **Propuesta de reconciliación:** `users` como fuente canónica compatible con
  las claves foráneas actuales. Nueva migración incremental incorpora cuentas
  operativas de `identity_invitation_accounts` preservando ID, hash, empresa,
  fechas, estado e invitación. Filas coincidentes se reutilizan. Conflictos de
  ID/correo/valores o identificadores/asociaciones incompatibles bloquean con
  diagnóstico y rollback; no escoger arbitrariamente, remapear ni eliminar.
- La tabla previa no se elimina en A. Si los contratos internos vigentes requieren
  compatibilidad transitoria, mantenerla como proyección de la fuente canónica
  en la misma transacción, no como segunda autoridad con escrituras independientes.
  La aprobación del plan incluye esta estructura interna; HTTP e IDs se conservan.
- Actualizar lecturas de identidad y empresas por ID/correo/listado, autenticación
  e invitación; preservar último administrador y bloqueo por nombre normalizado.
  Persistir explícitamente mutaciones de credenciales, rol, estado y asociaciones.
- Descartado: duplicar cuentas para satisfacer FK, eliminar constraints, guardar
  al apagar, hidratar memoria una vez o restaurar hashes/estados con el seed.

| Ubicación/capa | Responsabilidad | RF |
|---|---|---|
| `backend/migrations/` | Reconciliación incremental; instalación y actualización sin pérdida | PERSIST-5, 6 |
| `identity/infrastructure/` | Adaptador SQL canónico; consultas y operaciones atómicas | PERSIST-1, 5, 6 |
| `identity/application/` | Guardado explícito y reglas existentes de cuenta/invitación | PERSIST-5, 6, 8 |
| `companies/infrastructure/` | Recuperar por ID/listado y preservar escritura/bloqueos | PERSIST-1, 5, 8 |
| `interface/*_contract.py`, dependencias y `main.py` | Componer repositorios sin cambiar contratos públicos | PERSIST-1, 8 |

### Diseño de bloques posteriores, pendiente detalle y aprobación

- **B:** ampliar tablas de tickets para resolución/objetivo/proyección del técnico;
  persistir comentarios, asignaciones y modificaciones con orden estable. Unidad
  transaccional local a tickets: guardar cambio e historial juntos, con rollback.
  La aplicación coordina; los adaptadores implementan commit. No confiar en
  mutaciones de referencias compartidas ni poner reglas en controladores.
- **C:** conservar el alcance SLA vigente: HU-14 usa configuración global aunque
  la tabla inicial sea por empresa; diseñar almacenamiento compatible, no convertir
  silenciosamente a otra política. Objetivo conservado pertenece al ticket.
  Guardar notificaciones, lectura y clave única de deduplicación. Los eventos
  internos que formen parte de una operación se coordinan transaccionalmente;
  sin servicios/jobs externos nuevos.
- **D:** composición demo usando contratos internos de preparación de cada módulo.
  Recuperar IDs de empresa, plataforma sin empresa, administrador empresarial,
  técnico y cliente. Completar solo asociaciones faltantes del demo heredado,
  sin reactivar ni reasignar ajenos. Identificar tickets demo persistentemente,
  no deduplicar tickets ordinarios por título. Configuración externa, seed solo
  desde entrypoint demo, producción sin seed.
- **E:** probar por HTTP con proceso nuevo y recreación controlada de API,
  conservando volumen y requiriendo autorización para interrumpir la aplicación.
  Reinicio no sobrescribe progreso, configuración ni lectura de notificaciones.
  Actualizar guía/correos/variables y revisar todos los RF.

### Pruebas, datos existentes y puertas

- Pytest primero; TestClient para HTTP. Nueva instancia de repositorios y nuevo
  proceso para probar independencia de memoria. Reautenticar tras reinicio:
  no prometer sesiones persistentes.
- SQL real solo en `infra-db-1:55432`. No apuntar fixtures destructivas a la BD
  demo: usar transacciones realmente compartidas o esquema de prueba aislado
  dentro del contenedor. Comprobar el aislamiento entre conexiones de API.
  Si no puede garantizarse, detener SQL y consultar; no crear otra instancia.
- Prohibidos clear/truncate/drop sobre datos de aplicación y cambios manuales
  para hacer pasar pruebas. No reiniciar ni migrar el entorno activo en esta fase.
- Probar migración limpia/actualización/repetición y rollback de conflictos;
  conservar hashes, IDs, asociaciones y cuentas ajenas al demo.
- Probar dos empresas, cuatro roles, cuentas sin empresa, invitaciones pendientes/
  vencidas, desactivación y protección concurrente del último administrador.
- Cada tarea: focalizadas y pytest completo; cada bloque: frontend, lint/build y
  matriz RF. Fallos bloquean avance; no ocultar con skips/xfail. Skips SQL impiden
  afirmar persistencia verificada. Diferenciar pruebas SQL/HTTP/manuales.
- Tras cada tarea: evidencia, memoria, checkbox correspondiente y sincronización
  CodeGraph/Graphify por cambios de código; detenerse.

El usuario aprobó la división A–E, la reconciliación y las tareas de A.
Contratos incompatibles, conflictos de datos y cambios de arquitectura no previstos
requieren nueva consulta antes de continuar.

### Evidencia A1 (2026-11-26)

- `backend/tests/hu26_sql_support.py`: esquema aleatorio propio con search_path
  limitado al esquema y pg_catalog, sin public; valida host/puerto y cada conexión.
  Migra únicamente el esquema de prueba, exige pgcrypto preexistente y limpia
  solo el esquema generado. No constituye aislamiento de SQL arbitrario con
  referencias explícitas a public: los tests posteriores deben usar esta factoría
  y no SQL cualificado contra los datos operativos.
- `backend/tests/test_hu26_sql_isolation.py`: conexiones independientes, ausencia
  de fallback si falta una tabla local, arranque con conexiones inyectadas,
  rollback, limpieza y siete casos de cuentas: idéntica, solo operativa, conflicto
  de hash/correo/empresa, ID inválido y empresa inexistente.
- Rojo real: error de colección por helper ausente. Primera ejecución SQL:
  17 passed / 1 failed por formato de search_path; corregida la aserción.
- PostgreSQL real autorizado, `HU26_TEST_DATABASE_URL` solo para la ejecución
  focalizada: `python -m pytest backend/tests/test_hu26_sql_isolation.py -q -rs`
  → **18 passed, 2 warnings**, exit 0. Ningún skip SQL.
  Huellas agregadas de todas las tablas public iguales antes/después; no se
  imprimieron datos de cuentas ni credenciales. Sin reiniciar contenedores.
- Suite completa sin DSN operativo ni DSN opt-in, para no ejecutar las fixtures
  heredadas sobre datos demo: `PYTHONPATH=backend python -m pytest -q -rs`
  → **1971 passed, 52 skipped, 3 warnings**, exit 0 (165,03 s).
  Skips: 40 existentes y 12 casos SQL A1 ya ejecutados separadamente. No se ha
  validado la integración SQL de las demás funcionalidades.
- CodeGraph/Graphify sincronizados; advertencia conocida de extractor SQL
  ausente en Graphify. Diff-check exit 0. A2 no iniciada.

### Evidencia A2 (2026-11-26)

- `backend/migrations/007_reconcile_identity_accounts.sql`: migración incremental,
  sin cambios en 001–006 ni eliminación de la tabla operativa anterior.
  Comprueba UUID, duplicados normalizados, empresa existente, campos/credenciales
  válidos y coincidencia nula-segura de todos los valores. Copia solo cuentas
  ausentes en `users`, con ID, hash, fechas e invitación originales.
- Bloquea escrituras durante validación/copia con locks transaccionales NOWAIT;
  una actividad incompatible aborta, no espera indefinidamente. Conflictos se
  diagnostican sin imprimir hashes/tokens. Versión y copia se confirman juntas
  mediante el runner existente. La tabla operativa previa permanece intacta.
- `test_hu26_account_reconciliation.py`: 23 pruebas, incluida detección de archivo
  nuevo; instalación desde esquema 006, repetición, filas idénticas/solo operativas/
  solo canónicas, conflictos de identidad/datos, invitación pendiente/aceptada,
  desactivación, conservación de fechas y rollback del lote completo.
- Rojo real: prueba de migración incremental falló porque 007 no existía.
  SQL focalizado A1+A2 con `HU26_TEST_DATABASE_URL` opt-in:
  `python -m pytest backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py -q -rs`
  → **41 passed, 2 warnings**, exit 0 (26,42 s), sin skips.
  Huellas de todas las tablas public iguales antes/después.
- Suite completa sin conexión operativa para proteger datos demo:
  `PYTHONPATH=backend python -m pytest -q -rs` → **1972 passed, 74 skipped,
  3 warnings**, exit 0 (164,05 s). Los 34 casos SQL de A1/A2 omitidos en esa
  corrida se verificaron por separado; los otros 40 skips son anteriores.
- CodeGraph/Graphify sincronizados; extractor SQL de Graphify ausente.
  No se ejecutó migración en public ni se reiniciaron contenedores.
  **No desplegar A2–A5 parcialmente**: los adaptadores vigentes todavía escriben
  en el almacén anterior. A3 no iniciada; persistencia completa no acreditada.

### Evidencia A3 (2026-11-26)

- PERSIST-1/5/8, acotados a identidad por ID/correo: `find_by_id`,
  `find_by_email` y su alias `find_by_email_persistent` consultan `users` en cada
  llamada con PostgreSQL configurado. Recuperan todos los campos del agregado,
  con ID/empresa textuales, fechas originales y token claro ausente. No hidratan
  ni consultan la caché como autoridad y propagan fallos SQL.
- Se usa la selección condicionada del repositorio existente, sin dependencia
  ni contrato nuevo. Sin PostgreSQL se exige `HELPDESK_ALLOW_IN_MEMORY=1`;
  ese seam conserva referencias e IDs textuales heredados. IDs inválidos no
  consultan la tabla operativa ni convierten datos de producción en IDs legacy.
- `test_hu26_canonical_identity_reads.py`: dos repositorios independientes,
  cambios confirmados entre lecturas, caché obsoleta, tabla operativa divergente/
  sin fila canónica, ausencia de tabla local y lectura sin configuración.
  TestClient de la app real prueba login no demo con contraseña ya registrada,
  `/me` con otro repositorio y cambios de rol/correo, rechazo uniforme de
  contraseña incorrecta/desactivación/invitación pendiente/correo inexistente,
  sin sesión al rechazar ni exposición de credenciales en HTTP.
- Cada conexión de aplicación/arranque pasa por la factoría A1 y su DSN scoped;
  no se usan las fixtures SQL heredadas. Runner temporal fuera del repositorio:
  obtiene configuración Docker solo en memoria, sanitiza `DATABASE_URL` y
  `POSTGRES_PASSWORD` y entrega únicamente `HU26_TEST_DATABASE_URL` al hijo.
- Rojo real, antes de cambiar código: A3 **12 failed / 7 passed**, exit 1.
  Verde: `PYTHONPATH=backend python -m pytest
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py -q -rs`
  con opt-in aislado → **60 passed, 3 warnings**, exit 0 (26,79 s), sin skips.
  A3 aporta 19 casos, 15 SQL/HTTP y 4 del seam. Huellas agregadas public iguales
  antes/después tanto del rojo como del verde; sin migrar/reiniciar la app activa.
- Puerta G sin DSN operativo ni opt-in: `PYTHONPATH=backend python -m pytest -q -rs`
  → **1976 passed, 89 skipped, 3 warnings**, exit 0 (146,52 s).
  De los skips, 49 son los SQL A1–A3 ejecutados aparte y 40 son anteriores.
  No se acredita SQL histórico ni frontend/lint/build (estos últimos, en A7).
- Límite deliberado: listados/contratos de directorio son A4; escrituras,
  invitaciones con bloqueo (`load_persistent_for_update`/token), coordinador del
  último administrador y proyección transaccional son A5. No se modifican esos
  mecanismos ni la política/almacenamiento de sesiones. La semilla es D.
  **No desplegar A2–A5 parcialmente**: aún hay escritores de la tabla anterior.
  La regresión en memoria no acredita su compatibilidad SQL durante la transición.
- CodeGraph y Graphify sincronizados; Graphify sigue sin extractor SQL.
  `git diff --check` exit 0. A3 terminada; A4 no iniciada.

### Evidencia A4 — detenida por puerta G (2026-11-26)

- Implementación pendiente de cierre, PERSIST-1/5/8: `list_all()` recupera
  agregados de `users` en cada llamada, sin poblar/usar caché y sin consultar
  la tabla operativa anterior. Exige el seam explícito sin PostgreSQL.
  SQL usa orden estable por fecha/ID donde antes no se prometía orden; los
  consumidores conservan sus ordenaciones contratadas (administradores por
  fecha/ID; cuentas sin empresa por nombre normalizado/ID).
- Los contratos/directorios existentes ya consumen ese listado. Sus firmas,
  filtros y DTO no cambian: técnicos activos (sin añadir filtro de invitación),
  administradores activos para alertas, estadísticas de todas las cuentas y
  administradores de cualquier estado, exclusión de plataforma en sin empresa.
  `account_email_exists` deja de convertir excepciones SQL en correo disponible;
  la normalización defensiva sigue a cargo del repositorio.
- `test_hu26_identity_directories.py`: 32 casos, 30 SQL/HTTP y 2 del seam,
  dos empresas, cuatro roles, plataforma y cuentas sin empresa, estados activos/
  desactivados e invitaciones pendientes. Prueba repositorios independientes,
  lecturas repetidas tras commit, caché obsoleta/filas solo operativas,
  orden/desempates, DTO mínimos y propagación de errores SQL.
  TestClient real verifica login y listados desde nueva instancia, detalle
  propio frente a ajeno, 401 previo al listado y 404 por rol/ámbito.
- Primer intento de tests: 1 failed / 4 passed / 27 errors por reutilizar un hash
  sintético de invitación en la fixture, incompatible con su índice único.
  Se corrigió únicamente la fixture para dar hashes sintéticos distintos.
  Rojo funcional antes del código: **21 failed / 11 passed**, exit 1.
- Focalizadas con runner temporal de A3, configuración Docker solo en memoria,
  DSN opt-in y conexiones scoped/verificadas por A1:
  `PYTHONPATH=backend python -m pytest
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py -q -rs --tb=short`
  → **92 passed, 3 warnings**, exit 0 (43,84 s), sin skips.
  Huellas agregadas public iguales antes/después del rojo y del verde.
- **Puerta G fallida:** entorno sanitizado, sin DSN operativo ni opt-in,
  `PYTHONPATH=backend python -m pytest -q -rs` →
  **1 failed, 1977 passed, 119 skipped, 3 warnings**, exit 1 (164,20 s).
  79 skips corresponden a SQL A1–A4 ejecutados aparte; 40 son anteriores.
  No se añadieron skips/xfail para ocultar el fallo.
- Fallo: `test_users_invitations.py::
  test_configured_postgres_lock_failure_aborts_acceptance_without_memory_mutation`.
  El test crea su cuenta en memoria, activa `postgresql://configured` y simula
  únicamente `invitations.connection`. Ahora `accept_invitation` llama antes a
  `users.list_all()`, que intenta la lectura SQL canónica: recibe OperationalError
  por DNS ficticio en vez del RuntimeError de lock esperado.
  No se acredita un fallo de bloqueo SQL real ni una regresión funcional de datos;
  sí un doble de lectura incompleto que bloquea el cierre de A4.
- Se detuvo la implementación según la puerta aprobada, sin modificar ese test
  heredado ni adelantar escritores/invitaciones de A5. Propuesta para retomar:
  adaptar de forma focalizada el doble de lectura de ese test para llegar al lock
  simulado y conservar sus aserciones de aborto/no mutación; repetir focalizadas
  y toda G. No hacer fallback de producción ni omitir la prueba.
- CodeGraph/Graphify sincronizados; advertencia conocida del extractor SQL ausente.
  Diff-check exit 0. Sin reiniciar/migrar la aplicación activa ni cambiar datos
  public. Frontend/lint/build siguen para A7. **A4 no marcada; A5 no iniciada.**
  Se mantiene la prohibición de desplegar A2–A5 parcialmente.

### Reanudación autorizada de A4 (2026-11-26)

- El usuario autorizó explícitamente con «si» completar el doble de lectura de
  la prueba de lock y repetir G. No se modificó código de producción.
- En `backend/tests/test_users_invitations.py`, únicamente
  `test_configured_postgres_lock_failure_aborts_acceptance_without_memory_mutation`
  inyecta su lectura previa como `[user]`, conservando el objeto original.
  Ejecuta el `_invitation_lock` real y mantiene la excepción `lock failed`,
  la igualdad completa del agregado antes/después y el tipo de error recibido
  por el cierre transaccional. Además verifica un único intento del advisory
  lock SQL con la clave `identity:account:<id>`, sin sustituir el propio lock.
- Rojo reproducido antes del ajuste: prueba focalizada **1 failed, 3 warnings**,
  exit 1 (10,65 s), por el DSN ficticio. Tras el ajuste autorizado:
  `PYTHONPATH=backend python -m pytest backend/tests/test_users_invitations.py
  -q -rs` → **13 passed, 3 warnings**, exit 0 (9,03 s).
- Repetición SQL/HTTP/seam A1–A4 con el mismo comando y aislamiento documentados:
  **92 passed, 3 warnings**, exit 0 (46,75 s), sin skips; huellas public iguales
  antes/después. Credenciales Docker solo en memoria, ninguna migración ni
  reinicio de la aplicación activa. Sin cambios de dependencias ni de alcance.
- Puerta G repetida en entorno sanitizado sin DSN operativo ni opt-in:
  `PYTHONPATH=backend python -m pytest -q -rs` →
  **1978 passed, 119 skipped, 3 warnings**, exit 0 (149,06 s).
  79 SQL opt-in se verificaron aparte; los otros 40 skips son anteriores.
  No se añadieron skips/xfail ni se modificaron aserciones para ocultar errores.
- CodeGraph y Graphify sincronizados; advertencia conocida del extractor SQL.
  Diff-check exit 0. A4 marcada como terminada (PERSIST-1/5/8, solo alcance de
  lecturas de identidad); A5 no iniciada. Frontend/lint/build siguen para A7.
  Continúa prohibido desplegar A2–A5 parcialmente: escritores aún pendientes.

### Evaluación A5 — subdivisión aprobada (2026-11-26)

- Se revisaron memoria, tarea A5 y las rutas de escritura con CodeGraph/Graphify.
  A5 supera el tamaño aprobado de 20–30 minutos si incluye implementación,
  rollback, HTTP, concurrencia y regresión completa; se detiene antes de TDD
  o cambios de código para solicitar aprobación de una subdivisión.
- Evidencia estructural (no resultados nuevos de pytest):
  `users.create_user` llama a `add` y después a `issue_invitation`, sin una
  transacción común cuando no recibe conexión; `update_user` no guarda todos
  los cambios; `change_user_role` muta el agregado tras un coordinador que puede
  abrir otra transacción. Asociación, desactivación y aceptación/reenvío de
  invitaciones también requieren coordinar relectura, escritura y salida del
  contexto transaccional. No basta con sustituir la tabla de un upsert.
  Los agregados retenidos deben seguir coherentes también si falla el commit,
  no solo si falla `execute`. La tabla operativa anterior no puede seguir siendo
  autoridad para relecturas con bloqueo/token.
- **Subdivisión aprobada por el usuario con «si»**, en orden, sin ampliar PERSIST-5/6/8:
  1. **A5a — Núcleo de persistencia canónica y proyección atómica.**
     Tests SQL aislados de alta/guardado, fallos de cada escritura y commit,
     lectura independiente y transacción del llamador. Implementar `users` y
     proyección previa en la misma transacción, relecturas canónicas con bloqueo
     y por token, sin publicar caché fallida ni admitir IDs legacy en producción.
  2. **A5b — Mutaciones de cuenta y protección concurrente del último admin.**
     Tests primero de perfil/correo, rol, estado y asociación, conservación de
     credenciales/invitación, carreras de administradores y rollback. Guardado
     explícito y coordinación de empresa/cuenta en la transacción de la mutación;
     contratos y reglas de autorización existentes intactos.
  3. **A5c — Ciclo de invitación y cierre integrado de A5.**
     Tests primero de alta invitada indivisible, aceptación/reenvío/desactivación
     concurrentes, fallo al confirmar y conservación de hash/fechas desde otra
     instancia. Mantener composición con transacciones del llamador, probar HTTP
     real y regresión A1–A5/G. Sin adelantar lecturas de empresas A6 ni semilla D.
- Cada subtarea debe incluir sus focalizadas y G, y detenerse si
  aparecen dependencias no previstas o vuelve a exceder 20–30 minutos. A5
  no es un checkbox adicional: se cierra con sus tres subtareas; los estados
  parciales no se despliegan. Nueve tareas ejecutables en el bloque A.
- Al registrar la evaluación inicial no se habían ejecutado pruebas
  nuevas, migraciones, cambios de datos ni reinicios. Evidencia de partida,
  de A4: focalizadas A1–A4 92 passed sin skips/public intacto y G 1978 passed /
  119 skipped / 3 warnings, exit 0. A6 no iniciada; no se acredita A5.

### Evidencia A5a (2026-11-26)

- PERSIST-5/6/8, solo núcleo del repositorio. `add` y `sync_persistent` guardan
  `users` y su proyección `identity_invitation_accounts` en la misma conexión/
  transacción. Se conservan firmas públicas, ID, hash, estados, asociación,
  teléfono y fechas; no se persiste el token claro ni se admite ID legacy en SQL.
  Sin tablas/migraciones/dependencias nuevas.
- Cada operación usa un savepoint. Si la conexión está idle se inicia la
  transacción externa antes de abrirlo (también con autocommit), de modo que
  liberar el savepoint no confirma el trabajo del llamador. Con conexión propia,
  el contexto existente confirma y propaga también errores de COMMIT.
  Un error Python capturado por el llamador no deja media escritura pendiente.
  Diseño contrastado con Context7 para transacciones/savepoints de psycopg.
- El alta de administrador registra su participación en el coordinador existente
  con esa misma conexión, no mediante una segunda transacción después del commit.
  No cambia las reglas del último administrador (A5b).
- Los escritores SQL no incorporan agregados a la caché. Las lecturas normales
  vuelven a consultar `users`, antes y después del rollback/commit. En el seam
  explícito, `add` publica referencias/índices solo después de guardar con éxito.
  `sync_persistent` no muta el argumento: las mutaciones del objeto realizadas
  por aplicación y su compensación al confirmar son materia de A5b/A5c.
- `load_persistent_for_update` bloquea la fila canónica y la resolución del hash
  de invitación consulta `users`, sin relectura autoritativa de la proyección.
- `test_hu26_identity_atomic_storage.py`: 26 casos (25 SQL/HTTP y 1 seam).
  Alta/guardado desde otra instancia; igualdad completa entre ambas tablas;
  fallos SQL inmediatos y triggers de restricción diferidos que fallan al COMMIT
  real, tanto en alta como actualización y en cada tabla; rollback externo,
  autocommit/no autocommit sin confirmación anticipada; captura de error Python
  con posterior commit del llamador; unicidad en cada tabla; bloqueo NOWAIT
  desde otra conexión; token canónico frente a proyección obsoleta; ID inválido.
  Coordinador previo: fallo inmediato/diferido revierte también el alta.
  TestClient de la app real: registro ordinario 201 solo con datos confirmados,
  y 500 sin filas ni caché si falla el commit. No sustituye las pruebas A5b/A5c.
- Rojo antes de implementación:
  `python -m pytest backend/tests/test_hu26_identity_atomic_storage.py
  -q -rs --tb=short` → **21 failed, 1 passed**, exit 1 (11,41 s).
  Primera focalizada verde: **22 passed**, exit 0 (13,44 s); después se
  añadieron cuatro comprobaciones de registro HTTP/coordinador existente.
- Regresión SQL/HTTP/seam en esquemas A1, con runner opt-in y configuración
  Docker únicamente en memoria:
  `PYTHONPATH=backend python -m pytest
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py -q -rs --tb=short`
  → **118 passed, 3 warnings**, exit 0 (53,72 s), sin skips.
  Huellas de public iguales antes/después de cada corrida SQL.
- Puerta G sanitizada, sin DSN operativo ni opt-in:
  `PYTHONPATH=backend python -m pytest -q -rs` →
  **1979 passed, 144 skipped, 3 warnings**, exit 0 (139,73 s).
  104 SQL opt-in se ejecutaron aparte; 40 skips son anteriores. Ningún skip/xfail
  añadido para ocultar fallos; ninguna fixture SQL heredada apuntó a datos demo.
- CodeGraph/Graphify sincronizados; Graphify sin extractor SQL y visualización
  HTML omitida por superar 5000 nodos (5024); grafo y reporte sí actualizados.
  Diff-check exit 0. Sin reiniciar/migrar el entorno activo. A5a terminada,
  A5b/A5c/A6 no iniciadas; frontend/lint/build siguen para A7.
  **No desplegar parcialmente A2–A5**: aún faltan escritores de aplicación.

### Evidencia A5b (2026-11-26)

- PERSIST-5/6/8: perfil/correo, rol, estado y asociación releen la cuenta bajo
  exclusión antes de mutar y guardan explícitamente por A5a en la misma
  transacción. El PATCH aplica solo campos suministrados sobre el estado
  releído, sin sobrescribir cambios confirmados desde otro repositorio.
- `_account_change` conserva un memento del agregado y restaura también índices
  locales ante errores, incluido COMMIT del contexto propio. En SQL, el cambio
  de correo no publica caché; la unicidad se comprueba y la restricción de la BD
  cubre carreras. Comparación de propietario por ID, no por identidad de objeto.
  Asociación revalida no pertenencia/rol/actor tras adquirir el lock de cuenta.
- La retirada/promoción de administradores comparte la conexión de la mutación
  y el advisory lock de empresa. Cuenta administradores activos en `users`
  dentro del lock; `identity_active_admin_guard` es proyección transaccional,
  no autoridad. Un guard obsoleto no permite retirar al último administrador.
  No hay tablas/migraciones/dependencias ni contratos HTTP nuevos.
- Se conservan hash/fechas/invitación salvo los efectos de negocio ya existentes
  de desactivación pendiente y cambio de correo pendiente. Se reutiliza
  `issue_invitation`, sin implementar aquí aceptación/reenvío ni el alta
  invitada indivisible de A5c. Sesiones y autorización pública conservadas.
- `test_hu26_identity_mutations.py`: 40 casos SQL/HTTP, con fixtures A1/A5a y
  cuentas ordinarias en dos empresas. Relectura independiente y PATCH parcial,
  rollback inmediato/diferido de cada mutación y del coordinador, preservación
  del objeto retenido y de ambas tablas; invitaciones pendientes conservadas/
  invalidadas según reglas vigentes. Asociación con conexión externa no confirma
  ni publica datos: el llamador conserva el commit/rollback.
- **Cinco carreras ejecutadas con dos threads y repositorios independientes:**
  retirada rol/rol, estado/estado, rol/estado (exactamente una aceptada y otra
  rechazada, queda un admin activo); dos cuentas por el mismo correo (una sola
  gana); dos asociaciones a empresas distintas (ambas lecturas iniciales
  sincronizadas antes del lock, una gana y la otra no reasigna).
  Todas se verifican leyendo el estado canónico confirmado y la proyección.
- HTTP real de usuarios: perfil/correo/rol/estado, nueva instancia y petición de
  detalle; 401/404/422/409 existentes, sin hashes/tokens; fallo de commit no
  responde éxito. Asociación se verifica en aplicación SQL/contrato existente;
  la composición HTTP de empresas tras reinicio sigue dependiendo de A6/A7.
- Rojo focalizado antes de código: **23 failed / 8 passed, 3 warnings**, exit 1
  (23,33 s). Primera verde: **31 passed, 3 warnings**, exit 0 (24,54 s);
  después se añadieron nueve casos de coordinador/invitaciones/conexión externa.
- Regresión A1–A5b con el comando de A5a más
  `backend/tests/test_hu26_identity_mutations.py`, `-q -rs --tb=short`, en
  esquemas exclusivos y con configuración Docker solo en memoria:
  **158 passed, 3 warnings**, exit 0 (78,94 s), sin skips.
  Huellas public iguales antes/después del rojo y de las verdes.
- Puerta G sin DSN operativo ni opt-in:
  `PYTHONPATH=backend python -m pytest -q -rs` →
  **1979 passed, 184 skipped, 3 warnings**, exit 0 (139,26 s).
  144 SQL opt-in se comprobaron aparte y 40 skips son anteriores.
  No se modificaron tests heredados ni añadieron omisiones para ocultar fallos.
- CodeGraph/Graphify sincronizados; advertencias de extractor SQL y HTML omitido
  por 5052 nodos, grafo/reporte actualizados. Diff-check exit 0. Sin cambios en
  datos activos, migraciones de public, reinicios ni frontend. A5b terminada;
  A5c/A6 no iniciadas. No desplegar A2–A5 parcialmente; frontend/lint/build en A7.

### Evidencia A5c (2026-11-26)

- **Auditoría de la ejecución interrumpida:** existían ya
  `test_hu26_identity_invitations.py` (25 casos con parametrizaciones) y cambios
  coherentes en `create_user`, `accept_invitation`, `resend_invitation` y la
  compensación bajo lock. No se conservó evidencia de un rojo previo; la primera
  verificación del estado parcial fue verde. Se completó el trabajo existente en
  lugar de rehacerlo y se declara honestamente que **no hubo rojo reproducido**.
- PERSIST-5/6/8: el alta invitada ejecuta `add` + `issue_invitation` dentro de la
  misma transacción/bloqueo, sin publicar caché antes del commit. Aceptación y
  reenvío releen `users` bajo el advisory lock de cuenta, exigen el hash vigente
  y no caen a la proyección ni a un agregado vacío si falta la fila canónica.
  El reenvío rota solo invitaciones pendientes y refresca 168 h; la aceptación
  conserva ID, empresa, nombre, correo, teléfono, rol, estado y fecha de alta.
  La desactivación mantiene la regla vigente de invalidar el token pendiente.
  `_invitation_change` restaura el agregado retenido también si falla el COMMIT
  del contexto propio; los fallos SQL inmediatos/diferidos revierten ambas tablas.
- `test_hu26_identity_invitations.py`: 25 casos SQL/HTTP/instancia nueva. Alta
  durable con hash SHA-256, sin token claro ni contraseña; duplicado 409 sin
  reemitir; rollback de alta ante fallo inmediato/diferido y transacción externa;
  aceptación única y vencimiento/estado/empresa/token usado como 404 uniforme
  antes de validar contraseña; reenvío con rotación y conservación de fechas/rol/
  empresa; restauración del objeto retenido; ausencia de fallback si falta la
  fila bloqueada; seis combinaciones de carrera aceptar/reenviar/desactivar con
  dos repositorios; HTTP real 201/409/200/422/404 y login 200 sin exponer tokens,
  hashes ni contraseñas; proceso nuevo que resuelve la invitación pendiente desde
  PostgreSQL sin semilla ni caché local.
- Verificación verde (sin skips):
  `test_hu26_identity_invitations.py` → **25 passed, 3 warnings**, exit 0
  (19,87 s). Focalizadas A1–A5c con el runner opt-in de A1 →
  **183 passed, 3 warnings**, exit 0 (91,24 s). Huellas agregadas de las 11 tablas
  `public` idénticas antes/después:
  `bd0464df54a85d2af9136b4114238e280c52775f0139c8ef80a27e65b0664735`.
- Puerta G sin DSN operativo ni opt-in: `PYTHONPATH=backend python -m pytest -q -rs`
  → **1979 passed, 209 skipped, 3 warnings**, exit 0 (140,64 s). Los 169 SQL
  opt-in se ejecutaron aparte; 40 skips son anteriores y 25 corresponden a A5c.
  No se añadieron omisiones para ocultar fallos. Sin dependencias, migraciones,
  contratos ni reglas nuevas; seed demo, tickets, SLA, empresas y frontend intactos.
- A5a–A5c completas: A5 cerrada. A6/A7 pendientes y no iniciadas. No desplegar
  A2–A5 parcialmente; la composición final y el frontend/lint/build son A7.

### Evidencia A6 (2026-11-26)

- PERSIST-1/5/8, acotados a lecturas de empresas. `find_by_id` y `list_all`
  consultan `companies` en cada llamada con PostgreSQL y devuelven agregados
  nuevos: no hidratan ni reutilizan la memoria del proceso, la caché ni la
  semilla. `list_all` usa orden estable por `created_at`/`id`; los consumidores
  conservan sus ordenaciones contratadas (`list_companies` por nombre
  normalizado/fecha/ID). Sin caché inicial como autoridad y sin fallback
  silencioso: los errores SQL se propagan.
- Un identificador que no es UUID devuelve `None` sin consultar la tabla, de
  modo que el 404 uniforme (`company not found`) se conserva y no aparece un
  500 por conversión. Sin PostgreSQL se exige `HELPDESK_ALLOW_IN_MEMORY=1`; ese
  seam mantiene referencias, orden de inserción e IDs textuales heredados.
  `count()` sigue siendo un contador local de apoyo y no se presenta como
  autoridad del catálogo.
- Se conservan firmas, DTO, permisos y códigos existentes: catálogo y detalle
  solo para administrador de plataforma; `/me` solo para administrador de
  empresa; técnico/cliente y alcance ajeno dan el mismo 404; precedencia
  401 → 404 → 422 → 409 verificada. La ficha no expone `name_normalized` ni
  datos de otras empresas. `companies` sigue dueño de su catálogo, contacto y
  estado; `identity` de cuentas/invitaciones; `tickets` de tickets. No hay
  contratos, tablas, migraciones ni dependencias nuevas.
- `test_hu26_company_reads.py`: 17 casos (15 SQL/HTTP y 2 del seam). Dos
  repositorios independientes recuperan todos los campos; cambios confirmados
  por otra conexión se releen; filas solo en memoria no aparecen; un objeto
  retenido no se muta; el contrato de estado lee la fila canónica; errores SQL
  se propagan en repositorio, contratos y HTTP. TestClient real con conexiones
  inyectadas prueba catálogo/detalle, `/me` de empresa activa e inactiva,
  aislamiento por rol y empresa, cambios externos sin re-login, 401/404/422/409
  y ausencia de campos internos. Los agregados de tickets de la ficha siguen
  en memoria hasta el bloque B; solo se comprueba su forma.
- Rojo real antes del código: **12 failed / 5 passed**, exit 1.
  `HU26_TEST_DATABASE_URL` opt-in, conexiones scoped/verificadas por A1 y
  configuración Docker solo en memoria. Verde focalizada: **17 passed,
  3 warnings**, exit 0. Regresión A1–A6:
  `PYTHONPATH=backend python -m pytest backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py -q -rs --tb=short`
  → **200 passed, 3 warnings**, exit 0 (102,62 s), sin skips.
  Huella agregada de las 11 tablas `public` idéntica antes/después
  (`e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`),
  sin esquemas `hu26_test_*` residuales.
- Dos corridas combinadas intermedias abortaron en la **apertura de una conexión
  de prueba** con `WSAEADDRINUSE` local de Windows, en puntos distintos y sin
  relación con A6; los módulos afectados pasaron por separado (40 passed) y la
  corrida final completa quedó limpia tras drenar los sockets en `TIME_WAIT`.
  No se añadieron skips/xfail ni se cambió código para ocultarlo.
- Puerta G sin DSN operativo ni opt-in: `PYTHONPATH=backend python -m pytest -q -rs`
  → **1981 passed, 224 skipped, 3 warnings**, exit 0 (154,25 s). Los 184 SQL
  opt-in (169 previos + 15 de A6) se ejecutaron aparte; 40 skips son anteriores
  y los 2 casos de seam de A6 pasan en G. No se modificaron pruebas heredadas.
- CodeGraph/Graphify sincronizados; Graphify sin extractor SQL y HTML omitido
  por 5097 nodos; grafo/reporte actualizados. Diff-check exit 0. Sin reiniciar
  ni migrar el entorno activo, sin datos demo tocados ni frontend. **A6
  terminada; A7 no iniciada y el bloque A no se declara cerrado.** Se mantiene
  la prohibición de desplegar A2–A6 parcialmente: tickets, SLA, seed demo y
  composición final siguen pendientes.

### Evidencia A7 (2026-11-26)

- **Auditoría de la ejecución interrumpida:** `git status --short` y
  `git diff --stat` no mostraban restos de A7 (ningún archivo de composición ni
  cambio ajeno atribuible a ella). No se rehizo trabajo de A1–A6 ni se tocaron
  los cambios de HU-18/config/agentes. A7 es una tarea de validación: no cambia
  código de producción ni añade dependencias, migraciones o contratos.
- PERSIST-1/5/6/8, en el alcance del bloque A. `backend/tests/test_hu26_composition.py`
  aporta 8 casos:
  1. Los 7 contratos `interface/*_contract.py` no importan el contrato de otro
     módulo y sí importan el propio.
  2. Ningún módulo contiene SQL que lea tablas de otro (`identity`: `users`,
     `identity_invitation_accounts`, `identity_active_admin_guard`;
     `companies`: `companies`; `tickets`: `tickets`, `ticket_comments`;
     `sla`: `sla_policies`, `ticket_sla`). El escaneo comprueba además que ve
     SQL real en `identity` y `companies`.
  3. `main.py` es el único punto de `include_router`/`apply_migrations`; los 13
     routers de módulo están registrados (38 rutas OpenAPI, incluida `/health`)
     y `startup_database` sigue en el arranque.
  4. Sin `DATABASE_URL`/`POSTGRES_PASSWORD` el arranque, `database_url()` y las
     lecturas de identidad/empresas lanzan `RuntimeError`; no hay fallback.
  5. El seam en memoria solo se activa con `HELPDESK_ALLOW_IN_MEMORY=1` exacto;
     `"true"` no lo activa y con PostgreSQL configurado no sustituye la ruta SQL.
  6. Con una base configurada pero inalcanzable, arranque y lecturas lanzan
     `psycopg.OperationalError` aunque el seam esté en `1`: no se oculta el fallo.
  7. Migración + HTTP en esquema aislado: se instala 001–006, se deja una cuenta
     solo en `identity_invitation_accounts` con hash real, se aplica 007 y se
     arranca la app con `DATABASE_URL` scoped. Login 200 y `/api/companies/me`
     200 con la empresa y `users_total=1`, `has_administrator=true`; la
     proyección previa no cambia. Repositorios independientes releen ambos
     agregados y no hidratan caché (`count()==0`).
  8. Proceso nuevo: HTTP 201 de `POST /api/companies` con administradora
     invitada; un intérprete hijo, solo con `DATABASE_URL` scoped, relee la
     empresa y la cuenta pendiente desde PostgreSQL y confirma que su memoria
     local está vacía.
- Rojo: **no hubo**. Las comprobaciones validan composición ya existente y no
  se forzó un fallo artificial; se registra honestamente. A7 focalizada con
  `HU26_TEST_DATABASE_URL` opt-in:
  `PYTHONPATH=backend python -m pytest backend/tests/test_hu26_composition.py
  -q -rs --tb=short` → **8 passed, 3 warnings**, exit 0 (9,51 s), sin skips.
  Regresión A1–A7 con el runner opt-in de A1 → **208 passed, 3 warnings**,
  exit 0 (110,04 s), sin skips. Huella agregada de las 11 tablas `public`
  idéntica antes/después
  (`902d1b7e48e17248b4eb341cd8f12e19e65d1247f8105b18e0b180ac21ed2571`) y
  0 esquemas `hu26_test_*` residuales.
- Puerta G sin DSN operativo ni opt-in: `PYTHONPATH=backend python -m pytest
  -q -rs` → **1987 passed, 226 skipped, 3 warnings**, exit 0 (144,35 s).
  Los 186 SQL opt-in (184 previos + 2 de A7) se ejecutaron aparte; 40 skips son
  anteriores. No se añadieron skips/xfail ni se modificaron pruebas heredadas.
- Frontend (sin cambios de código en A7): `npm test` con la API local
  inalcanzable (`VITE_API_URL=http://127.0.0.1:1`) → **461 passed / 43
  archivos**, exit 0; `npm run lint` exit 0; `npm run build` exit 0 (1703
  módulos, 347,14 kB JS). **Limitación de entorno:** con `infra-api-1` viva en
  `localhost:8000`, seis pruebas heredadas (5 de `MobileSidebar`, 1 de
  `DashboardPage`) fallan porque una petición de notificaciones/métricas sin
  sesión recibe 401, dispara el cierre global y deja el árbol sin usuario. No es
  una regresión de A7 ni se corrigió tocando pruebas ajenas; el comando offline
  reproduce la puerta de CI.
- RF: PERSIST-1 (relectura canónica por proceso nuevo), PERSIST-5 (007 y HTTP
  sobre PostgreSQL aislado, proyección conservada), PERSIST-6 (migración
  incremental aplicada solo en esquema propio; rollback cubierto en A2),
  PERSIST-8 (contratos sin dependencias cruzadas, tablas propias y composición
  en `main.py`).
- CodeGraph/Graphify sincronizados (`codegraph sync` exit 0; `graphify update .`
  exit 0: 5119 nodos, 10778 aristas, 407 comunidades; extractor SQL ausente y
  HTML omitido por superar 5000 nodos). `git diff --check` exit 0. Sin
  reiniciar/recrear contenedores, sin migrar `public`, sin datos demo tocados.
- **Limitaciones reales del cierre:** tickets, comentarios, asignaciones,
  historial, notificaciones, SLA y sesiones siguen en memoria (bloques B/C);
  la semilla demo es D; la recreación/reinicio real es E. La migración 007 no se
  aplicó a la base activa y no se desplegó nada. El bloque A **no** equivale a
  persistencia integral del sistema y B no se inicia sin aprobación de la fase
  siguiente.
- Revisión independiente `reviewer-deep`: **APROBADO solo bloque A** (A1–A7,
  incluidas A5a/b/c), sin incumplimientos bloqueantes; el reviewer no editó
  archivos. QA ejecutó independientemente G backend sanitizada: **1987 passed,
  226 skipped, 3 warnings**, exit 0 (146,51 s); nueve módulos focalizados A1–A7,
  SQL real y helper aislado: **208 passed, 0 skips, 3 warnings**, exit 0
  (111,51 s). Los 186 SQL opt-in se probaron aparte; los 40 skips previos no
  quedan acreditados. Las huellas de las 11 tablas `public` fueron idénticas y
  hubo 0 esquemas residuales antes y después; `git diff --check` exit 0.
- QA no repitió frontend/lint/build: la evidencia previa de implementación es
  461 pruebas en 43 archivos, lint y build exit 0 con API inaccesible. Con API
  viva permanecen seis fallos heredados por 401; no se acredita integración
  desplegada. PERSIST-1/5/6/8 cumplen el alcance A pero son parciales en la spec
  global; PERSIST-2/3 corresponden a B, 4 a C y 7 a D; DEMO-1–7 a D. Los demás
  RF de HU-26 no quedan cerrados globalmente por este veredicto. A6 cubre solo
  lecturas y `count()` de empresas sigue local; sesiones y bloques B–E pendientes.
  No se autoriza despliegue, migración de `public` ni reinicio. B requiere plan y
  tareas propios y aprobación antes de implementar.

## 8. Bloque B — diseño y subdivisión (2026-11-26; aprobación 2026-11-27)

Estado: **subdivisión B.I–B.IV aprobada con «si»; detalle B.I aprobado**.
Tras B.I.1, «completa las demas tareas» autoriza B.I.2–B.I.9 secuencialmente,
una por vez y con sus puertas. B.II–B.IV mantienen su alcance acordado, sin
detalle de tareas aprobado. No autoriza despliegue ni migración activa.
Se conserva íntegra la evidencia de A.
Clasificación recibida: HIGH, riesgo alto, confianza media; no se reclasifica.

### 8.1 Alcance y correspondencia con la spec

B hace persistentes los tickets completos, comentarios y fuentes del historial:
asignaciones y modificaciones de prioridad/estado, incluida la reapertura.
La asignación continúa dentro de `tickets`; no se traslada a `assignment`
(`specs/project.md`, decisión de HU-04). No se detecta discrepancia entre la
explicación aprobada y PERSIST-2/3.

- **HU-26 PERSIST-1/2/3/6/8:** alcance principal de B; lecturas normales desde
  SQL, guardado explícito, ticket e historial coherentes, permisos y HTTP intactos.
- **HU-26 PERSIST-5:** B conserva el objetivo de resolución del ticket, pero no
  implementa la persistencia de la configuración SLA. Identidad/empresas se
  reutilizan desde A; PERSIST-5 global sigue parcial hasta C.
- **HU-26 RF-165/167/171:** B aporta pruebas del tramo de tickets y evidencia de
  regresión; no cierra el recorrido desplegado ni la validación integral.
- Compatibilidad normativa: HU-03 RF-21–30, HU-04 RF-31–40, HU-07 RF-61–70,
  HU-08 RF-71–80, HU-09 RF-81–90, con las precisiones posteriores de empresa,
  asignación y visibilidad de HU-13/HU-17. HU-18 RF-179–191 conserva sus fórmulas
  y muestras; las referencias RF siempre incluyen HU para evitar colisiones.

**No incluye:** almacenamiento de políticas SLA ni notificaciones/deduplicación
(C), seed/importación automática de memoria o identificación demo (D), reinicio
del despliegue y prueba de sus contenedores (E), ni persistencia de sesiones.
El proceso hijo de pruebas de B no equivale al reinicio del entorno desplegado.
No se tocan HU-18, configuración/agentes, rama ni cambios locales ajenos.

### 8.2 Diagnóstico de las fuentes ya revisadas

| Fuente | Situación comprobada | Consecuencia para B |
|---|---|---|
| `001_init.sql`, `tickets` | Ya guarda ID, empresa, solicitante, técnico ID, título, descripción, prioridad, estado, creación y `updated_at`; FK compuestas de empresa a `users` | Reutilizar tabla/IDs/FK; no duplicar tickets ni deduplicar por título |
| `tickets/domain/entities.py`, `Ticket` | Añade `assignee_name`, `resolved_at`, `resolved_target_minutes` que no están en esa tabla | Nueva migración incremental para esos datos, sin valores históricos inventados |
| `ticket_repository.py` | `add`, lecturas, listados y `snapshot_for_metrics` usan `_by_id` | SQL debe ser autoridad en cada llamada, incluida la instantánea de HU-18 |
| `ticket_comments` y `ticket_comment_repository.py` | Tabla con autor/fecha/cuerpo; adaptador solo en memoria; SQL no tiene orden de registro para empates | Adaptador SQL y orden persistente; tratar explícitamente el legado sin ese orden |
| `assignment_log.py`, `ticket_modification_log.py` | Listas append-only; no hay tablas correspondientes en 001–007 | Tablas propias de `tickets`, con orden de registro persistente y sin duplicar una vista de historial |
| Casos de uso de prioridad/estado/reapertura/asignación | Mutan referencias y añaden registros; no guardan el ticket explícitamente | Sustituir dependencia de referencias por coordinación transaccional de aplicación |
| `list_ticket_history.py` | Deriva creación + asignaciones + modificaciones + comentarios; desempata por fuente e índice | Mantener la vista derivada y el orden HU-09, no crear otra tabla de eventos |
| `company_ticket_contract.py`, `sla_contract.py` | Leen `list_all()` y exponen DTO mínimos | Obtendrán SQL a través del repositorio propio, sin imports cruzados de contratos |
| `metrics_router.py`, `support_metrics.py` | Autorizan administrador con empresa y consumen una instantánea + evaluador puro | Conservar una única lectura de tickets y el evaluador de objetivo congelado |

La revisión dirigida se hizo con CodeGraph, sin reabrir fuentes ya servidas.
Se comprobó la presencia de los nodos pertinentes en `graphify-out/graph.json`;
no se pudo ejecutar `graphify query` porque esta sesión no dispone de herramienta
de shell. No se afirma una consulta CLI ni actualización de grafos ejecutada.
No se consultaron datos operativos ni `.env`, ni se ejecutaron pruebas o SQL.

### 8.3 Módulos y capas

| Módulo/capa | Responsabilidad propuesta | Cobertura |
|---|---|---|
| `tickets/domain` | Conservar entidades, catálogos, transiciones y datos del agregado; el orden interno no será un campo HTTP nuevo | PERSIST-2/3/8 |
| `tickets/application` | Coordinar alta y mutaciones; releer/autorizar sobre el estado bloqueado; decidir cambios efectivos; guardar ticket y registro juntos | PERSIST-1/2/3/6/8 |
| `tickets/infrastructure` | Adaptadores de tickets, comentarios, asignaciones y modificaciones; lectura sin caché autoritativa, conexión compartida, rollback y exclusión por ticket | PERSIST-1/2/3/6 |
| `backend/migrations/` | Cambios aditivos posteriores a 007, instalación/actualización verificadas solo en esquema propio; no reescribir 001–007 | PERSIST-2/3/6 |
| `tickets/interface` | Componer dependencias y DTO, traducir errores existentes; no trasladar validaciones o reglas a controladores | PERSIST-8 |
| `identity` y `companies` | Reutilizar almacenamiento aprobado en A y contratos existentes; no añadir consultas de sus tablas desde `tickets` | PERSIST-1/5/8, parte ya cubierta en A |
| `sla` | Consumir vistas de tickets y aportar cálculo/evaluación por sus fronteras existentes; sin persistencia de políticas en B | PERSIST-2/8; PERSIST-5 solo parcial |

### 8.4 Almacenamiento y compatibilidad de datos existentes

1. **Esquema incremental mínimo.** Añadir en tickets los campos de resolución,
   objetivo conservado y nombre proyectado del técnico. Resolución/objetivo serán
   anulables para representar datos ausentes; no usar `now()` ni política vigente
   como backfill. Crear registros de asignación y modificación con los campos
   ya definidos por las entidades y una secuencia técnica de registro.
   Incorporar orden de registro en comentarios para las nuevas escrituras.
   Índices por ticket/orden y por fecha donde sean necesarios para las consultas
   actuales. No añadir estados, roles, endpoints, ORM ni dependencias.
2. **Preservar lo que existe.** Copiar/releer sin cambiar ID, empresa, referencias,
   fechas, contenido, prioridad ni estado. Mantener FK de empresa/solicitante/
   técnico y el trigger vigente de comentarios. No ampliar a tickets sin empresa
   en SQL ni relajar constraints para acomodar fixtures legacy de memoria.
   `count`/`clear` de apoyo no podrán limpiar SQL operativo; el seam de memoria
   seguirá explícito y las fixtures SQL solo limpiarán su esquema generado.
3. **Resolución u objetivo ausentes.** Un finalizado sin resolución permanece
   finalizado y sin fecha conocida; no reconstruirla desde `updated_at`, cierre,
   historial o arranque. Sin objetivo conservado, HU-18 mantiene volumen y,
   si las fechas son válidas, promedio; excluye el ticket de la muestra SLA
   (HU-18 RF-184/191). Si tiene objetivo conocido, conservarlo exactamente.
   No convertir ausencia en incumplimiento ni tomar una política actual como
   sustituto. El cálculo general de HU-05/HU-14 y HU-12 no cambia por B:
   su comportamiento legacy se distingue de la elegibilidad estricta de HU-18.
4. **Filas de `ticket_sla`.** Existen campos con nombres afines, pero esa tabla
   pertenece a `sla`; no se asume que cualquier `target_minutes` sea el objetivo
   realmente congelado al resolver. Conservar sus filas intactas. La primera
   caracterización aislada debe contemplar filas con/sin resolución y posibles
   conflictos. Si aparece evidencia histórica recuperable que exige
   reconciliación, detener el cierre de compatibilidad y presentar un mecanismo
   por el módulo dueño y composición autorizada antes de copiarla. No leer esa
   tabla desde el adaptador de tickets, descartarla ni afirmar que sus valores
   ya se recuperan. Una decisión semántica no demostrable se consulta al usuario;
   no se resuelve convirtiendo este trabajo en la persistencia de políticas C.
5. **Técnico conocido sin nombre proyectado.** Conservar siempre `assignee_id`.
   Para legado sin nombre, la composición autorizada puede resolver el nombre
   actual mediante el contrato de identidad, sin presentarlo como nombre
   histórico. No consultar `users` desde SQL de tickets ni filtrar una asignación
   histórica por elegibilidad actual. Nuevas asignaciones guardarán el nombre
   recibido al asignar, como el comportamiento vigente. Si no se puede componer
   el DTO existente sin inventar información, registrar el caso y detener la
   compatibilidad; no ocultar la asignación ni fabricar un nombre.
6. **Orden y fuentes del historial.** Una secuencia persistente conserva el
   orden de registro de nuevas filas de cada fuente. Comentarios ordenan por
   fecha y luego orden de registro; el historial mantiene fecha, rango
   creación/asignación/prioridad/estado/comentario y orden dentro de la fuente.
   No agregar un evento de creación duplicado ni generar asignaciones o
   modificaciones por migrar un estado actual. En comentarios SQL heredados
   con igual fecha y sin orden registrado, ordenar por UUID no recupera el
   orden original. Preservar filas; si ese caso existe, pedir decisión antes
   de atribuirle un orden histórico o declarar HU-09 plenamente conservada.
7. **Memoria legacy.** No hay copia SQL de los cambios hechos solo en `_by_id`
   o listas. B no promete conservarlos al detener el proceso ni los importa
   al arrancar. No guardar «al apagar» ni regenerar tickets. Una eventual
   extracción del proceso todavía vivo requiere alcance, revisión de conflictos
   y autorización propios; de un proceso ya detenido no se recupera lo perdido.
   Antes de cualquier futuro despliegue deben comunicarse estos límites.

No se ha inspeccionado la base activa para afirmar que existe o no alguno de
estos casos. Los datos de caracterización serán sintéticos y aislados. Las
condiciones de parada evitan inventar reglas de negocio; no son una aprobación
para corregir el legado ni para migrar `public`.

### 8.5 Contratos y transacciones

- **Lecturas:** conservar operaciones públicas del repositorio (`find_by_id`,
  listados por solicitante/técnico, `list_all`, `snapshot_for_metrics`) y de
  los registros (`add`, `list_by_ticket`). En SQL, cada consulta recupera lo
  confirmado sin hidratar memoria como autoridad. IDs inválidos conservan el
  rechazo uniforme, no se convierten en errores de cast SQL ni IDs ficticios.
- **Escrituras:** la aplicación recibe el coordinador y repositorios de su
  módulo; infraestructura comparte una sola conexión entre agregado y registro.
  Alta confirma una vez; prioridad/estado/reapertura/asignación guardan cambio
  y registro en la misma transacción; comentario confirma su fila sin mutar
  el ticket. No-ops no añaden registros ni fechas. El guardado explícito no
  depende de que `find_by_id` devuelva la misma referencia mutable.
- **Concurrencia:** exclusión por fila de ticket y relectura dentro de la
  transacción para evitar actualizaciones perdidas al guardar el agregado.
  Revalidar empresa, asignación, estado e inmutabilidad antes de cambiarlo,
  también en comentario frente a cierre o reasignación. Sin versión/ETag ni
  API nueva: las operaciones efectivas se serializan; una petición rechazada
  o ya satisfecha no genera historia. No se promete un orden de llegada global.
- **Validación HTTP:** mantener dependencias que preceden al cuerpo, incluida
  su decodificación, y repetir en aplicación las comprobaciones dependientes
  del estado después de bloquear. Mantener 401 → 404 → 409 por cerrado → 422;
  la transición inválida sigue evaluándose después del catálogo (409).
  Reabrir sigue siendo administrador, cerrado → abierto, cuerpo ignorado.
- **Fallo y commit:** no devolver 2xx antes de confirmar ni reemplazar SQL por
  memoria. Fallos de execute, registro o COMMIT revierten la operación; no
  publicar objetos/listas modificados ni dejar agregados retenidos con cambios
  fallidos. Si existe conexión del llamador, no confirmar su transacción;
  probar savepoint/rollback y dejar explícita la propiedad del commit.
- **Notificaciones vigentes:** asignación/estado/reapertura invocan hoy callbacks
  en memoria. No publicarlos antes de una confirmación SQL fallida; preservar
  destinatarios y tipos en el camino confirmado, sin añadir avisos de prioridad
  o comentario. Una transacción externa exige coordinación explícita con su
  confirmación, no ejecutar callbacks al liberar solo un savepoint.
  B no acredita durabilidad ni atomicidad distribuida de notificaciones. Si falla
  su callback después de confirmar, no simular rollback del ticket ni ocultar
  el error; registrar esa limitación y no reejecutar automáticamente la mutación.
  La solución persistente de notificaciones/deduplicación se diseña en C;
  no introducir un outbox, job o almacenamiento de avisos encubierto en B.
- **Fronteras:** `company_ticket_contract` mantiene solo conteos y cuatro claves
  de estado; `sla_contract` mantiene `SlaTicketView` y objetivo anulable. Ninguno
  importa el contrato de otro módulo. Resolver usuarios, empresa y SLA mediante
  fronteras existentes; inyectar lo necesario en router/main, nunca mediante
  joins a tablas ajenas desde repositorios. No cambiar DTO HTTP.
- **HU-18:** `snapshot_for_metrics` obtiene todas sus columnas en una sola
  consulta SQL y crea valores inmutables. La autorización ocurre antes de
  leer y delimita por empresa del ticket, no por solicitante o asignado.
  El evaluador de resolución congelada sigue siendo puro; no consulta políticas.
  Los agregados de empresa, dashboards y listados dejan de depender del seed.

### 8.6 Decisiones y alternativas descartadas

| Decisión propuesta | Alternativa descartada y motivo | RF |
|---|---|---|
| Adaptadores SQL y guardado explícito con la infraestructura existente | Hidratar caché al arrancar o guardar al salir: no ve commits ajenos ni resiste pérdida del proceso | PERSIST-1/2/6 |
| Ticket + su registro, misma conexión/commit y exclusión local | Confirmar por repositorio o guardar agregado leído antes del lock: medias operaciones y sobrescrituras | PERSIST-2/3/6 |
| Campos nuevos anulables para ausencia real y legado caracterizado | Completar resolución/objetivo con reloj o política vigente: inventa evidencia y altera HU-18 | PERSIST-2/5/8 |
| Historial derivado de fuentes persistentes con orden de registro | Tabla adicional de historial o desempate arbitrario por UUID: duplicación u orden histórico ficticio | PERSIST-3/8 |
| Preservar FK y contratos, resolución de nombres por composición | Leer tablas de identidad/SLA desde tickets o relajar tenant: viola propiedad de módulos/aislamiento | PERSIST-5/8 |
| SQL obligatorio; seam explícito para pruebas | Fallback a memoria ante error o respuesta vacía exitosa: oculta pérdida de durabilidad | PERSIST-1/6 |
| Subdividir B y aprobar cada detalle antes de implementar | Comprimirlo en diez megatareas: contradice el máximo de 20–30 minutos y dificulta rollback/revisión | Criterio de división de HU-26 |

### 8.7 Estrategia de pruebas y puertas propuestas

TDD por tarea: pytest rojo real cuando se modifica comportamiento, implementación
mínima, focalizadas verdes, puerta G y parada. Una validación de comportamiento
ya existente no inventará un rojo. Aún **no se han ejecutado pruebas de B**.

- **Datos y migraciones:** reutilizar `backend/tests/hu26_sql_support.py` (A1),
  DSN opt-in `HU26_TEST_DATABASE_URL` y conexiones independientes con esquema
  aleatorio propio, `search_path` sin `public`, localhost:55432 y pgcrypto ya
  instalado. Instalación limpia y actualización desde 007 con tickets/comentarios
  previos, repetición por el runner, conflictos y rollback; comprobar igualdad
  de valores originales y ausencia de nuevas filas de historial ficticias.
  No fijar en tests que 007 sea para siempre la última migración.
- **Aislamiento seguro:** todas las conexiones de app/arranque/hijo/carreras
  usan la factoría scoped y se verifican. Huellas agregadas de todas las tablas
  `public` antes/después de cada corrida SQL, sin imprimir filas ni secretos;
  cero esquemas de pruebas residuales. Fixtures no destructivas del demo:
  nunca `clear`/truncate/drop sobre datos operativos. Si no se garantiza,
  detener SQL, no conectar las fixtures heredadas a la base activa.
- **Lecturas y HTTP reales:** TestClient sobre la app y routers reales, sesiones
  reales y cliente por rol, repositorios/conexiones independientes; no sustituir
  casos de uso HTTP por mocks. Alta/listados/detalle, asignación/reasignación,
  prioridad, transiciones, comentario, resolución/cierre/reapertura y seguimiento/
  historial después de reemplazar repositorios. Con reloj fijo comparar valores
  durables, no exigir que el tiempo SLA activo deje de avanzar.
- **Autores y visibilidad:** dos empresas, solicitante propietario/ajeno,
  administrador empresarial/plataforma, técnico asignado/no asignado, supervisor
  y cuentas sin empresa según contratos vigentes. Verificar 401/404/409/422 con
  cuerpos inválidos; estados cerrados, no-ops y técnico desactivado o de otro
  tenant sin ampliar acceso. Comentarios solo autor mínimo o null; historial
  conserva ID con nombre null si no resuelve. Sin hashes/tokens/correos extra;
  resúmenes HU-17 conservan ocho claves y solicitante solo `{name}` o null.
- **Rollback/concurrencia:** fallos al escribir ticket, cada registro/comentario
  y al COMMIT real; rollback externo, caché/objetos retenidos y ausencia de
  notificación fantasma. Dos conexiones con barreras, no sleeps: prioridad frente
  a estado (sin perder campos), dos asignaciones/no-op, cierre frente a comentario,
  cambio de asignado frente a mutación de técnico y reaperturas competidoras.
  Comprobar filas confirmadas e historial que describe las transiciones reales.
- **Nuevo proceso:** un padre registra cambios por HTTP; un intérprete hijo
  sin seed ni caché, conectado solo al esquema de prueba, inicia app nueva,
  reautentica y consulta por HTTP detalle/listados/comentarios/historial/métricas.
  IDs, texto, referencias, fechas, estados y objetivo conservado no se regeneran.
  Sesiones previas no forman parte de la promesa. Nunca reiniciar contenedores.
- **Dependencias y HU-18:** pruebas de contratos y propiedad SQL sin imports
  entre contratos; incluir las nuevas tablas propias en el escaneo de A7 sin
  debilitar la prohibición. Probar los ejemplos y exclusiones HU-18 sobre filas
  SQL, incluidos objetivo ausente, objetivo conocido y reapertura; cambio de
  política en el seam SLA solo para comprobar la regla existente, no persistir
  políticas ni certificar C. Ficha de empresas y vista SLA leen tickets recuperados.
- **Regresión A/G:** focalizadas A1–A7 + B en SQL opt-in aparte, sin skips,
  preservando los 208 casos de referencia y reportando conteos reales, no
  sumándolos por anticipado. G completa en proceso con `DATABASE_URL`,
  `POSTGRES_PASSWORD` y `HU26_TEST_DATABASE_URL` retirados, memoria habilitada
  solo por el seam acordado: `PYTHONPATH=backend python -m pytest -q -rs`.
  Informar skips SQL ya ejecutados aparte y skips previos no acreditados;
  no añadir skips/xfail para ocultar fallos. Cualquier fallo bloquea avance.
- **Frontend y cierre de cada subbloque:** runner ya acordado: `npm test`,
  `npm run lint`, `npm run build`. Mantener separada la puerta offline de CI
  de la integración desplegada: A acreditó 461 pruebas/43 archivos con
  `VITE_API_URL=http://127.0.0.1:1`; con API viva constan seis fallos heredados
  401. Registrar el resultado/entorno reales y los fallos, sin arreglos ajenos
  ni declarar integración desplegada por usar API inaccesible. QA independiente,
  matriz RF, evidencia de comandos/exit y diff-check antes de cerrar B.

Tras cambios de código autorizados se sincronizarán CodeGraph/Graphify y se
registrarán sus limitaciones; esta planificación documental no ejecuta esos
cambios. No leer `.env`, imprimir DSN, instalar dependencias, hacer commit/push,
migrar `public`, reiniciar servicios ni borrar
`helpdesk_hu16_validation_20261117`. Despliegue/base activa requieren autorización
distinta y revisión del legado; ningún subbloque parcial se despliega.

### 8.8 Subdivisión aprobada: B excede diez tareas pequeñas

No es honesto agrupar esquema, cuatro adaptadores, coordinación de mutaciones,
concurrencia, HTTP, proceso nuevo y regresión en diez tareas de 20–30 minutos.
La estimación inicial fue de aproximadamente 22 unidades. Al detallar B.I se
separan dos comprobaciones para no crear megatareas: ahora son nueve tareas en
B.I y aproximadamente 24 en B completo, antes de posibles conflictos legacy.
No se crea una cola ejecutable de todo B.

El usuario aprobó esta subdivisión **sin cambiar la spec ni adelantar C–E**:

| Subbloque | Resultado revisable | Dependencia | RF HU-26 | Tamaño |
|---|---|---|---|---|
| B.I — Base SQL y compatibilidad | Caracterización legacy aislada; esquema aditivo; lectura canónica de tickets/listados/instantánea y alta confirmada | A aprobado; detalle B.I aprobado | PERSIST-1/2/5 parcial/6/8 | 9 tareas en tasks.md |
| B.II — Cambios y ciclo de vida atómicos | Coordinación transaccional; modificación persistente de prioridad/estado/reapertura, resolución/objetivo conservados | B.I validado; aprobar detalle B.II | PERSIST-1/2/3/5 parcial/6/8 | 5 unidades pequeñas |
| B.III — Asignación, seguimiento e historial | Asignaciones y comentarios SQL; operaciones atómicas/autorizadas y lectura derivada estable, con carreras y rollback | B.II validado; aprobar detalle B.III | PERSIST-1/2/3/6/8 | 6 unidades pequeñas |
| B.IV — Composición y cierre de B | Contratos/consumidores, HU-17/HU-18 SQL, HTTP con proceso nuevo, regresiones y revisión independiente | B.I–III validados; aprobar detalle B.IV | PERSIST-1/2/3/5 parcial/6/8; RF-165/167/171 parciales | 4 unidades pequeñas |

Los subbloques no son tareas de 20–30 minutos. Solo B.I tiene ahora tareas
detalladas; B.I.1–9 implementadas y aprobadas por QA independiente, solo B.I.
Las cantidades de B.II–IV siguen siendo estimaciones.
Cada detalle requiere aprobación propia. Si una tarea excede 30 minutos, se
propone división antes de implementarla.

**Detalle B.I aprobado** mediante «completa las demas tareas» tras B.I.1.
El bloqueo de regresión de B.I.2 quedó resuelto con autorización expresa;
las puertas de B.I.1–9 están verdes y QA independiente aprobó solo B.I.
No hay autorización implícita para B.II–IV. Si la caracterización revela una
decisión histórica no demostrable necesaria para continuar, consultar el caso
concreto, de uno en uno, sin alterar la spec unilateralmente.

### 8.9 Detalle B.I — base SQL, consultas y alta (2026-11-27)

**Estado: detalle aprobado**. Inicialmente solo B.I.1 mediante
«empieza con las tareas B.I.1 de HU-26»; después «completa las demas tareas»
autoriza las restantes B.I.2–B.I.9 en orden, sin extender a otros subbloques.
Nueve tareas de
20–30 minutos, en vez de las siete estimadas: se separan HTTP de alta, HTTP de
compatibilidad y proceso nuevo para mantenerlas pequeñas. El total estimado es
245 minutos incluyendo focalizadas y G por tarea, sin garantizar la duración de
una investigación de legado o de un fallo de entorno; si no cabe, detener y
replanificar. Clasificación HIGH recibida, sin cambios.

#### Límite de esta entrega

B.I solo caracteriza datos heredados, añade los tres campos faltantes de
`tickets`, conecta consultas de tickets/listados/instantánea HU-18 e inserta
altas confirmadas. Las tablas de asignaciones/modificaciones y el orden SQL de
comentarios de 8.4 se crearán cuando se detalle B.III, no como cambios de
esquema innecesarios de B.I. Las mutaciones y su unidad transaccional completa
son B.II/B.III; aquí no se conectan PUT/reopen/comentarios a escritores SQL.

**No desplegar este estado intermedio:** al releer SQL ya no existe la referencia
compartida que las mutaciones antiguas daban por supuesta. G en memoria y las
pruebas SQL de alta/consulta no acreditan que las mutaciones SQL estén listas.
B.I no demuestra conservación del historial ni de una operación completa de
atención, aunque sus lecturas ya recuperen registros confirmados.

#### Responsabilidades y contratos concretos

- `tickets/infrastructure/ticket_repository.py`: selección SQL/seam explícito,
  mapeo de todos los campos de Ticket, consultas por ID/solicitante/técnico,
  listado completo, contador y `snapshot_for_metrics`. Conservar los métodos y
  argumentos existentes; una conexión opcional para insertar pertenece al
  contrato técnico interno, no al HTTP. No importar repositorios de otros módulos.
- El alta SQL usa INSERT, no un UPSERT que sobrescriba progreso al repetir ID;
  el guardado de mutaciones se diseñará expresamente en B.II. Títulos y
  descripciones repetidos siguen siendo válidos y no generan deduplicación.
  En el seam en memoria se conserva el comportamiento anterior. No hacer del
  seed actual un importador ni cambiarlo para adaptarlo a B.I.
- Una inserción con conexión propia sale del contexto de confirmación antes de
  devolver éxito; no publica caché. Con conexión del llamador no confirma:
  ante error local revierte solo su unidad mediante el patrón transaccional
  existente, incluso si el llamador captura la excepción y luego confirma.
  El endpoint de alta utiliza una transacción cuya confirmación controla el
  caso de uso/adaptador, nunca una conexión externa aún pendiente.
- `tickets/application/create_ticket.py`: mantener validación, empresa/solicitante
  de la sesión, UUID y fecha del sistema, `Abierto` y valores iniciales nulos.
  No responder con el objeto creado si falló INSERT o COMMIT.
- `tickets/interface/router.py`: conservar DTO y rutas. En detalle/resumen ya
  autorizados, resolver por el contrato existente de identidad solo el nombre
  actual que falte en una proyección legacy; no sobrescribir nombres conservados,
  ocultar `assignee_id`, filtrar por elegibilidad actual ni leer `users` desde
  SQL de tickets. Si no es posible resolverlo sin inventar, diagnosticar el
  bloqueo de compatibilidad en vez de declarar el caso superado.
- Los contratos de estadísticas de empresa y vista SLA siguen consultando
  únicamente el repositorio de tickets; no importan contratos ajenos. En B.I
  se comprueba que esta sustitución conserva composición y propiedad de tablas;
  la validación completa de sus consumidores y de HU-17/HU-18 corresponde a B.IV.
- `snapshot_for_metrics` construye valores inmutables con una sola consulta,
  sin leer política SLA, completar objetivos o filtrar por una identidad
  distinta de la empresa del ticket. El caso de uso existente autoriza antes de
  invocar la lectura y delimita su conjunto; no se cambian fórmulas ni HU-18.
- `count()` SQL cuenta filas confirmadas de tickets, sin usar longitud de caché.
  `clear()` queda reservado al seam en memoria y debe rechazar la limpieza SQL,
  no traducirse a DELETE/TRUNCATE ni devolver éxito ficticio. Las fixtures que
  precisen limpieza SQL son dueñas de su esquema A1, no del almacenamiento demo.

#### Compatibilidad que debe quedar demostrada, no inferida

La migración nueva posterior a 007 añade únicamente `assignee_name`,
`resolved_at` y `resolved_target_minutes`, anulables y sin backfill inventado.
Se determinará el siguiente número libre al implementar; no se escribe ni
ejecuta ahora un archivo SQL. Preservar `updated_at` y todas las columnas/FK/
triggers existentes; no editar 001–007 ni forzar fechas/objetivos en finalizados.
La repetición por el runner no duplica cambios y su versión se confirma con
su esquema. No añadir restricciones que obliguen a «reparar» legado ambiguo.

Las fixtures de B.I.1 distinguirán lo recuperable en SQL de la ausencia de
evidencia: estados finales sin resolución, con resolución conocida y sin
objetivo, con objetivo conocido, nombre proyectado ausente, comentarios
empatados sin orden y filas `ticket_sla` de semántica no acreditada.
Los nuevos campos conocidos de pruebas se preparan explícitamente después de
la migración; no se afirma que 007 ya los almacenaba.
La preparación controlada de fixtures puede poblar tablas de varios dueños;
el código de cada módulo no recibe permiso para consultarlas directamente.

Solo `Resuelto`/`Cerrado` participan en las muestras de finalizados de HU-18:
fechas válidas para promedio; además prioridad y objetivo conservado válidos
para SLA. Un objetivo ausente excluye solo de la muestra SLA, sin rellenarlo
con la política vigente. Una resolución ausente no se obtiene del cierre ni
de `updated_at`; un pendiente con datos históricos no entra en esas muestras.
Se preservan valores conocidos y las exclusiones del caso de uso vigente.

No hay ahora evidencia de un conflicto concreto en la base activa ni una duda
de negocio que permita decidir un backfill. Los casos ambiguos se caracterizan
y preservan; si continuar exige reconciliar `ticket_sla`, atribuir orden
histórico o inventar una proyección, detener esa compatibilidad y consultar.
Los datos exclusivamente en memoria no se importan ni se prometen recuperables.

#### Secuencia, cobertura y verificación

El detalle completo está en `tasks.md`, B.I.1–B.I.9. Cada tarea depende de la
anterior y de aprobar este detalle; archivos nombrados de pruebas/migración
son destinos propuestos, no archivos creados en esta fase.

| Tarea | Resultado acotado | Minutos | RF HU-26 |
|---|---|---|---|
| B.I.1 | Caracterización sintética y diagnóstico de compatibilidad | 25 | PERSIST-2/3/5/6/8, solo precondiciones |
| B.I.2 | Migración aditiva de campos de tickets | 30 | PERSIST-2/6 |
| B.I.3 | Lectura canónica por ID y seam seguro | 25 | PERSIST-1/2/6/8 |
| B.I.4 | Listados y contador sin caché autoritativa | 25 | PERSIST-1/2/6/8 |
| B.I.5 | Instantánea SQL inmutable y muestras HU-18 | 25 | PERSIST-2/5 parcial/8 |
| B.I.6 | Inserción durable y propiedad del commit | 30 | PERSIST-1/2/6/8 |
| B.I.7 | Alta y relectura HTTP real | 25 | PERSIST-1/2/6/8; RF-165/171 parciales |
| B.I.8 | DTO, permisos y proyección legacy por HTTP | 30 | PERSIST-2/5 parcial/8 |
| B.I.9 | Proceso nuevo y cierre acotado de B.I | 30 | PERSIST-1/2/6/8; RF-171 parcial |

La sección 8.7 se aplica a todas. Cada tarea empieza por sus tests y termina
con focalizadas SQL opt-in sin skips, G completa sanitizada y evidencia real;
si falla cualquier puerta, no marcar ni continuar. Reutilizar helper A1 y
fixtures/patrones A2/A7 para actualización desde 007 y arranque/HTTP/hijo,
sin modificar la seguridad del helper ni fijar «última migración = 007».
Todas las conexiones, incluidas las de carreras e intérprete hijo, quedan en
el esquema generado propio; huellas de `public` antes/después, cero residuos,
ningún DSN/credencial en salida. La concurrencia necesaria aquí se limita a
visibilidad de INSERT no confirmado/confirmado y a colisión de ID sin
sobrescritura; los locks de mutación y carreras de cierre/asignación son B.II/III.

Al cerrar B.I, repetir SQL A1–A7+B.I completo sin skips, G y frontend/lint/build
con la distinción offline/API viva de 8.7, y someter a revisión independiente.
El proceso hijo prueba solo alta y consultas, reautenticando sin seed ni caché,
no mutaciones ni reinicio de contenedores. No acreditar persistencia integral,
historial, políticas, notificaciones, seed ni integración desplegada.

**Registro de esta fase documental:** solo se actualizan plan y tareas.
`MEMORY.md` queda fuera del permiso de escritura del planner (solo `specs/`);
el coordinador puede registrar la aprobación de subdivisión y el detalle B.I
pendiente. No hubo implementación ni pruebas de código/SQL. `git diff --check`
no está disponible sin shell en esta sesión; no se declara ejecutado.

### Evidencia B.I.1 (2026-11-27; autorización de ese momento)

- Autorización literal limitada a B.I.1; el detalle B.I global sigue en borrador
  y B.I.2–B.I.9 no se autorizan ni ejecutan. La caracterización cubre solo
  precondiciones de PERSIST-2/3/5/6/8, no cumplimiento de persistencia.
- `test_hu26_ticket_legacy.py` instala 001–007 en esquemas aleatorios A1,
  prepara ocho tickets sintéticos de dos empresas/cuatro estados, conserva ID,
  referencias y fechas, distingue columnas inexistentes de nulos y relee filas
  sin cambios. Comentarios con igual fecha no demuestran orden; `ticket_sla`
  no acredita que su objetivo sea el congelado del ticket. Los casos futuros
  de resolución conocida y objetivo conocido/ausente son valores hipotéticos,
  no columnas ni registros de 007. No se atribuye resolución desde `updated_at`,
  no se producen backfills, eventos ni importaciones de memoria. Si una
  compatibilidad posterior exige decidir un orden o reconciliación, consultar;
  no se ha inspeccionado el demo para afirmar que ocurra.
- Sin rojo artificial: es caracterización de esquema existente. Python 3.10,
  `PYTHONPATH=backend`, DSN opt-in obtenido de configuración Docker solo en
  memoria y conexiones de fixtures scoped por A1. Comandos:
  `python -m pytest backend/tests/test_hu26_ticket_legacy.py -q -rs --tb=short`
  → **4 passed, 0 skipped**, exit 0 (2,51 s).
  `python -m pytest` con los nueve módulos A1–A7 listados en evidencia A7,
  más `backend/tests/test_hu26_ticket_legacy.py -q -rs --tb=short`
  → **212 passed, 0 skipped, 3 warnings**, exit 0 (143,76 s).
- Antes, después de focalizadas y después de acumuladas: huella agregada de 11
  tablas public idéntica `91d33c404b4670ed68598d3c4acaaabc27afa151c2f36b5358f0162fb117ca71`;
  **0 esquemas residuales** en los tres momentos. No se mostraron filas ni
  credenciales. Solo lecturas agregadas de public; ninguna migración en public.
- G en proceso sanitizado sin `DATABASE_URL`, `POSTGRES_PASSWORD` ni
  `HU26_TEST_DATABASE_URL`, con `HELPDESK_ALLOW_IN_MEMORY=1`:
  `PYTHONPATH=backend python -m pytest -q -rs` → **1987 passed, 230 skipped,
  3 warnings**, exit 0 (146,26 s). De los skips, 190 SQL opt-in se ejecutaron
  aparte y los 40 previos siguen sin acreditar. G en memoria no valida
  mutaciones SQL pendientes.
- La base estaba detenida/ausente; el usuario autorizó levantar solo PostgreSQL.
  `docker compose -f infra/docker-compose.yml up -d --no-deps --no-recreate
  --pull never db` creó solo db usando `infra_pgdata` preexistente, etiquetado
  como volumen Compose `infra/pgdata` y con 299,5 MB; healthy en 55432.
  No se recrearon ni reiniciaron servicios existentes, ni se arrancó API/web.
- `cmd /c codegraph sync`, `graphify update .` y `git diff --check`: exit 0.
  Graphify actualizó grafo/reporte; sin extractor SQL y sin HTML por 5147 nodos.

### Evidencia B.I.2 — primera ejecución detenida (2026-11-27; resuelta abajo)

- Autorización B.I.2–B.I.9 registrada arriba; solo se ejecutó B.I.2. Riesgo HIGH
  por migración sobre datos previos. Sin decisión de negocio, dependencia,
  contrato ni arquitectura nueva. No se cierra PERSIST-2/6 globalmente.
- Tests primero: `backend/tests/test_hu26_ticket_schema.py`, seis casos de
  archivo incremental, instalación limpia, actualización 007 con dos empresas/
  cuatro estados y comentarios/SLA previos, repetición con valores conocidos,
  fallo SQL después del DDL real y conservación funcional de FK/triggers.
  Compara catálogo de columnas/constraints/triggers/índices y datos/fechas/
  registro de versiones. Capturar la excepción y confirmar después no conserva
  DDL ni versión parciales. Las pruebas nuevas acotan su versión a 008, sin
  imponer que sea la última migración futura.
- Se comprobó libre 008. Nueva `008_ticket_persistence.sql`: solo ALTER TABLE
  tickets con `assignee_name text`, `resolved_at timestamptz` y
  `resolved_target_minutes integer`, anulables, sin defaults/backfill. No se
  editaron 001–007, helper A1, runner, adaptadores ni pruebas anteriores.
  No se cambian ticket_sla/comentarios ni se crean tablas de historial.
- Python 3.10.0; runner temporal externo `hu26_bi2_runner.py` obtiene Docker
  solo en memoria, retira DATABASE_URL/POSTGRES_PASSWORD/HU26_TEST_DATABASE_URL,
  habilita `HELPDESK_ALLOW_IN_MEMORY=1` y PYTHONPATH=backend; para SQL entrega
  solo HU26_TEST_DATABASE_URL. Conexiones y migraciones solo en esquemas A1,
  sin public en search_path; no fixtures destructivas heredadas contra demo.
- Comando focalizado: `python <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_schema.py -q -rs --tb=short`.
  Rojo previo a 008: **6 failed**, exit 1 (2,85 s).
  Después de 008: **6 passed/0 skips**, exit 0 (3,34 s).
- Comando acumulado: mismo runner `--sql`, nueve módulos A1–A7 de evidencia A7
  más `backend/tests/test_hu26_ticket_legacy.py` y
  `backend/tests/test_hu26_ticket_schema.py -q -rs --tb=short`.
  **214 passed/4 failed/0 skips/3 warnings**, exit 1 (225,58 s).
  Fallan A2 `test_clean_install_and_repetition_are_idempotent`,
  `test_existing_accounts_are_copied_or_reused_without_overwriting` (2 casos),
  y A7 `test_migration_and_http_compose_on_isolated_postgres`.
  Las cuatro esperan `[007_reconcile_identity_accounts.sql]` pero reciben
  también `008_ticket_persistence.sql`. Los seis casos nuevos pasan también
  en la acumulada. No se alteraron las expectativas ni se ocultaron fallos.
- **Parada obligatoria:** B.I.2 queda sin marcar, B.I.3 no iniciada. G completa
  no se ejecutó tras fallar la puerta SQL. No se acredita G nueva; la anterior
  B.I.1 fue 1987 passed/230 skipped (190 SQL aparte y 40 previos no acreditados).
  Propuesta al coordinador: autorizar ajuste focalizado de pruebas A2/A7 para
  acotar el runner hasta 007 durante sus escenarios históricos, manteniendo
  todas sus aserciones de reconciliación/HTTP; luego repetir focalizadas,
  acumuladas sin skips y G sanitizada. No cambiar producción ni relajar tests.
- Antes/después de las tres corridas: **11 tablas public**, misma huella
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Solo huellas agregadas, sin filas ni
  secretos. Sin migrar public, desplegar, reiniciar/recrear contenedores ni
  arrancar API/web. Frontend/lint/build no repetidos en esta tarea.
- `cmd /c codegraph sync` y `graphify update .`: exit 0. Graphify:
  5162 nodos/10844 aristas/395 comunidades; sin extractor SQL ni HTML por tamaño.
  `git diff --check`: exit 0; se repite después de esta última edición documental.

### Reanudación autorizada de B.I.2 — completada (2026-11-27)

- El usuario respondió **«si»** a «¿Autorizas acotar esos cuatro escenarios
  históricos hasta 007, conservando sus aserciones, y repetir todas las
  verificaciones?». Misma tarea/riesgo HIGH, sin nuevo alcance. El rojo previo
  y el fallo de puerta se conservan arriba; no se rehízo la migración.
- Ajuste mínimo exclusivamente local a los tres casos A2 y el caso A7 indicados:
  cada escenario limita `run.migration_files` con monkeypatch a archivos
  `<= 007_reconcile_identity_accounts.sql`. Concluido el escenario se restaura
  automáticamente. Todas las aserciones originales permanecen intactas:
  aplicación/repetición, preservación, login y composición HTTP. Los otros
  escenarios A2/A7 y el runner global no se acotan; no se modifica el helper A1,
  producción, contratos ni reglas de negocio. Sin nuevos skips/xfail/fallback.
  La instalación limpia y actualización 007→008 de B.I.2 siguen probando 008,
  y otras instalaciones completas del helper siguen aplicando todas las versiones.
- Python 3.10.0, mismo runner temporal externo y garantías de aislamiento
  descritos arriba. Focalizadas relevantes:
  `python <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_schema.py -q -rs --tb=short`
  → **37 passed/0 skipped/3 warnings**, exit 0 (28,39 s).
- Acumulada:
  `python <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py -q -rs --tb=short`
  → **218 passed/0 skipped/3 warnings**, exit 0 (154,58 s).
- Antes/después de ambas corridas SQL: **11 tablas public**, huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales** en los cuatro momentos. Configuración
  Docker solo en memoria, sin credenciales ni filas en salida; conexiones y
  migraciones solo en esquemas A1, sin public en search_path.
- G completa: `python <temporal>/hu26_bi2_runner.py -q -rs`, equivalente a
  `PYTHONPATH=backend python -m pytest -q -rs` en proceso sanitizado, sin
  DATABASE_URL/POSTGRES_PASSWORD/HU26_TEST_DATABASE_URL y con
  HELPDESK_ALLOW_IN_MEMORY=1 → **1988 passed/235 skipped/3 warnings**, exit 0
  (196,44 s). Los **195 SQL opt-in** se probaron aparte; los **40 skips previos
  siguen sin acreditar**. G en memoria no certifica mutaciones SQL pendientes.
- B.I.2 marcada solo tras todas las puertas verdes. PERSIST-2/6 cubiertos en
  el alcance de esquema aditivo/rollback; no se acredita persistencia operativa
  integral. B.I.3 no iniciada; B.II–IV sin aprobación de detalle. No se migró
  public, arrancó API/web, desplegó ni reinició/recreó contenedores. Frontend/
  lint/build no repetidos en esta tarea; límites de integración previos vigentes.
- `cmd /c codegraph sync` y `graphify update .`: exit 0 (5163 nodos,
  10848 aristas/394 comunidades; extractor SQL ausente y HTML omitido por tamaño).
  `git diff --check`: exit 0, repetido después de la última edición documental.

### Evidencia B.I.3 — completada (2026-11-27)

- HU-26 PERSIST-1/2/6/8, acotados a lectura por ID. `find_by_id` consulta
  únicamente `tickets` en cada llamada con PostgreSQL configurado, recupera
  todos los campos del agregado con IDs textuales, instantes originales y nulos,
  y devuelve objetos nuevos sin poblar caché ni mutar referencias retenidas.
  No completa nombres, resolución ni objetivos desde identidad/SLA/updated_at.
  IDs inválidos devuelven None y conservan el error uniforme de aplicación.
  Los errores SQL se propagan; sin SQL se exige HELPDESK_ALLOW_IN_MEMORY=1
  exacto, sin sustituir una base configurada fallida.
- `backend/tests/test_hu26_ticket_reads.py`: 20 casos, 9 SQL y 11 de seam/errores.
  Dos repositorios y conexiones independientes, fila completa, cuatro estados
  y nulos legacy, resolución conocida con/sin objetivo, cambio confirmado entre
  lecturas, caché obsoleta, objetos retenidos, fila solo en memoria, ID inválido/
  inexistente, tabla local ausente y base inaccesible. La lectura sigue funcionando
  con users/ticket_sla locales renombradas: no son fuentes de este adaptador.
  No se sustituyen pruebas HTTP posteriores por estos tests de aplicación.
- Python 3.10.0; runner temporal externo existente `hu26_bi2_runner.py`:
  configuración Docker solo en memoria y DSN opt-in entregado al hijo; conexiones
  y migraciones reales mediante A1, sin public en search_path. Comando focalizado:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_reads.py -q -rs --tb=short`.
  Rojo previo al cambio: **13 failed/7 passed**, exit 1 (4,00 s).
  Verde tras cambio mínimo: **20 passed/0 skipped**, exit 0 (6,22 s).
- Acumulada: `py -3.10 <temporal>/hu26_bi2_runner.py --sql` con
  `backend/tests/test_hu26_sql_isolation.py`,
  `backend/tests/test_hu26_account_reconciliation.py`,
  `backend/tests/test_hu26_canonical_identity_reads.py`,
  `backend/tests/test_hu26_identity_directories.py`,
  `backend/tests/test_hu26_identity_atomic_storage.py`,
  `backend/tests/test_hu26_identity_mutations.py`,
  `backend/tests/test_hu26_identity_invitations.py`,
  `backend/tests/test_hu26_company_reads.py`,
  `backend/tests/test_hu26_composition.py`,
  `backend/tests/test_hu26_ticket_legacy.py`,
  `backend/tests/test_hu26_ticket_schema.py` y
  `backend/tests/test_hu26_ticket_reads.py -q -rs --tb=short`
  → **238 passed/0 skipped/3 warnings**, exit 0 (125,73 s).
- Antes/después del rojo, verde y acumulada SQL: **11 tablas public**, huella
  idéntica `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Solo huellas agregadas, sin filas ni
  secretos en salida; no se inspeccionaron datos demo.
- La ejecución se interrumpió por límite de pasos después de la acumulada verde,
  antes de G/documentación. Se reanudó la misma tarea sin cambiar código ni
  repetir SQL. G: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  proceso sin DATABASE_URL, POSTGRES_PASSWORD ni HU26_TEST_DATABASE_URL,
  HELPDESK_ALLOW_IN_MEMORY=1 y PYTHONPATH=backend →
  **1999 passed/244 skipped/3 warnings**, exit 0 (201,91 s; runner 203,05 s).
  **204 SQL opt-in ejecutados aparte; 40 skips previos no acreditados**.
  No se añadieron omisiones/xfail para ocultar fallos ni se ajustaron tests ajenos.
- Sin decisiones nuevas de negocio, contratos, DTO, dependencias ni arquitectura.
  Listados/count/snapshot, INSERT, mutaciones, políticas, notificaciones y seed
  siguen fuera de esta tarea. No desplegar el adaptador transitorio: G en memoria
  no acredita las mutaciones SQL pendientes ni persistencia integral.
  B.I.3 marcada solo después de las puertas verdes; B.I.4 no iniciada.
  Sin migrar public, arrancar API/web, desplegar ni reiniciar/recrear servicios.
  Frontend/lint/build no repetidos; límites anteriores de integración vigentes.
  `cmd /c codegraph sync`, `graphify update .` y `git diff --check`: exit 0.
  Graphify actualizó grafo/reporte (5177 nodos, 10887 aristas, 399 comunidades);
  extractor SQL ausente y HTML omitido por tamaño. Se repite diff-check después
  de esta última edición documental.

### Evidencia B.I.4 — detenida por puerta SQL (2026-11-27)

- Solo B.I.4, HU-26 PERSIST-1/2/6/8 acotados a listados/contador. Se ampliaron
  primero las pruebas de `test_hu26_ticket_reads.py`: ahora 32 casos (21 SQL
  opt-in y 11 de seam/errores). Dos empresas, cuatro estados, técnicos con/sin
  tickets, asignaciones nulas, títulos/descripciones repetidos y fechas empatadas.
  Comparan todos los campos y orden descendente sin atribuir historia a empates;
  repositorios/conexiones independientes, commits externos, objetos retenidos,
  caché obsoleta, conteo antes/después de commit y rechazo de clear sin conectar.
  Errores de tabla ausente/base inaccesible se propagan; memoria solo con seam exacto.
- Cambio mínimo en `ticket_repository.py`: consultas propias de listados y count,
  sin hidratar caché, joins ajenos ni filtros de permisos nuevos. clear rechaza SQL.
  Sin cambios en snapshot, INSERT, mutaciones, HTTP, fixtures A ni helper A1.
  Context7 consultado para parámetros y filas diccionario de psycopg 3.
- Python 3.10.0, runner temporal existente: configuración Docker solo en memoria,
  entorno hijo sanitizado y únicamente HU26_TEST_DATABASE_URL opt-in para SQL.
  Conexiones/migraciones scoped por A1, sin public en search_path.
  Comando focalizado:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_reads.py -q -rs --tb=short`.
  Rojo real antes del código: **17 failed/15 passed**, exit 1 (9,89 s).
  Verde focalizada: **32 passed/0 skipped**, exit 0 (19,58 s).
- Acumulada: mismo comando SQL y los doce módulos del comando acumulado B.I.3
  (A1–A7, ticket_legacy, ticket_schema y ticket_reads), `-q -rs --tb=short`:
  **1 failed/249 passed/0 skipped/3 warnings**, exit 1 (131,68 s).
  Falló `test_hu26_composition.py::test_migration_and_http_compose_on_isolated_postgres`:
  el escenario histórico conserva solo 006→007 también durante el arranque HTTP.
  GET `/api/companies/me` compone estadísticas mediante `tickets.list_all()`,
  ahora SQL, y obtiene UndefinedColumn: assignee_name (añadida en 008).
  No se trata de un fallo de aislamiento ni se oculta mediante fallback.
- **Parada obligatoria:** B.I.4 sin marcar; G no ejecutada tras fallar la puerta.
  Última G válida, de B.I.3: 1999 passed/244 skipped, 204 SQL aparte y 40 skips
  previos no acreditados; no constituye evidencia nueva de G para B.I.4.
  Propuesta pendiente de autorización: mantener intactas las aserciones 006→007
  y la proyección canónica del escenario A7, pero restaurar el runner completo
  y aplicar pendientes solo en su esquema A1 antes del tramo HTTP. Así el código
  actual consume su esquema requerido sin simular columnas/fallback ni saltar tests.
  No se modificó A7 ni se anticipó B.I.5; repetir focalizadas/acumulada/G al autorizar.
- Antes/después del rojo, verde y acumulada: **11 tablas public**, huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Sin secretos/filas en salida, migrar public,
  arrancar API/web, desplegar ni reiniciar/recrear servicios. Frontend/lint/build
  no repetidos. Adaptador transitorio no desplegable; B.I.5 y B.II–IV no iniciados.
- `cmd /c codegraph sync`, `graphify update .` y `git diff --check`: exit 0.
  Graphify: 5191 nodos/10942 aristas/415 comunidades, extractor SQL ausente y
  HTML omitido por tamaño; grafo/reporte actualizados. Diff-check se repite tras
  esta última edición documental. No se autoriza ni implementa un ajuste ajeno
  para convertir la puerta fallida en verde.

### Reanudación autorizada de B.I.4 — completada (2026-11-27)

- El usuario respondió **«si»** a mantener las comprobaciones históricas 006→007
  y aplicar después las migraciones pendientes **solo en su esquema de prueba**
  antes del tramo HTTP. Misma tarea MEDIUM, sin cambio de alcance; se conservan
  arriba el rojo real 17 failed/15 passed y el bloqueo acumulado anterior.
- Ajuste exclusivamente en
  `test_hu26_composition.py::test_migration_and_http_compose_on_isolated_postgres`:
  conserva el runner completo en una variable local, limita la fase histórica a
  007 y mantiene todas sus aserciones originales de migración/reconciliación/
  proyección y HTTP. Después de comprobar la proyección, restaura la función
  original y aplica pendientes por el runner existente en la misma conexión
  scoped/esquema A1 antes de HTTP. Comprueba la lista de pendientes descubierta
  dinámicamente; no fija que 008 sea la última migración global.
  No se tocan otros escenarios, helper A1, aislamiento, reglas ni producción.
- Python 3.10.0; runner temporal existente
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`, configuración
  Docker solo en memoria. SQL opt-in únicamente mediante HU26_TEST_DATABASE_URL,
  conexiones y migraciones aisladas por A1 sin public en search_path.
  Focalizadas relevantes:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_composition.py backend/tests/test_hu26_ticket_reads.py
  -q -rs --tb=short`
  → **40 passed/0 skipped/3 warnings**, exit 0 (27,56 s; runner 28,36 s).
- Acumulada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py
  backend/tests/test_hu26_ticket_reads.py -q -rs --tb=short`
  → **250 passed/0 skipped/3 warnings**, exit 0 (136,34 s; runner 137,16 s).
- Antes/después de ambas corridas SQL: **11 tablas public**, huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales** en los cuatro momentos. Sin filas,
  secretos ni DSN en salida; sin fixtures heredadas contra datos demo.
- G completa: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a `PYTHONPATH=backend python -m pytest -q -rs` con DATABASE_URL,
  POSTGRES_PASSWORD y HU26_TEST_DATABASE_URL retirados y HELPDESK_ALLOW_IN_MEMORY=1:
  **1999 passed/256 skipped/3 warnings**, exit 0 (210,29 s; runner 211,44 s).
  **216 SQL opt-in ejecutados aparte; 40 skips previos no acreditados**.
  No se añadieron skips/xfail ni se relajaron aserciones para ocultar errores.
- B.I.4 completa para HU-26 PERSIST-1/2/6/8 en su alcance de consultas propias,
  contador confirmado y clear solo seam. Sin decisiones de negocio nuevas.
  El ajuste de escenario histórico fue consultado y autorizado expresamente.
  B.I.5 no iniciada; snapshot/INSERT/mutaciones/HTTP posteriores no se adelantan.
  G en memoria no certifica mutaciones SQL pendientes ni persistencia integral.
  No se migró public, arrancó API/web, desplegó ni reinició/recreó ningún servicio.
  Frontend/lint/build no repetidos; límites de integración anteriores vigentes.
- `cmd /c codegraph sync` y `graphify update .`: exit 0; grafo/reporte actualizados
  (5191 nodos/10942 aristas/415 comunidades), extractor SQL ausente y HTML
  omitido por tamaño. Se ejecuta diff-check tras la última edición documental.

### Evidencia B.I.5 — completada (2026-11-27)

- Solo B.I.5, clasificación HIGH por compatibilidad de métricas/SLA. HU-26
  PERSIST-2/5 parcial/8, compatibilidad HU-18 RF-179–188/191. Sin decisiones
  nuevas de negocio, arquitectura, dependencias ni contratos; no se modifican
  archivos/fórmulas de HU-18 ni se persisten políticas SLA.
- Cambio mínimo en `tickets/infrastructure/ticket_repository.py`:
  `snapshot_for_metrics` obtiene siete columnas propias de `tickets` en una
  sola consulta y devuelve una tupla de valores inmutables. Copia ID/empresa
  textuales, estado, prioridad, creación, resolución y objetivo conservado,
  incluidos sus nulos. Sin caché, joins, ordenación, filtros de permisos,
  inferencias desde updated_at ni consulta de política vigente. El caso de uso
  existente autoriza antes de leer y delimita por empresa del ticket.
  Los errores SQL se propagan; memoria solo con el seam explícito exacto.
- Nuevo `backend/tests/test_hu26_ticket_metrics_snapshot.py`: 27 casos,
  16 SQL opt-in y 11 de autorización/seam/errores. Consulta única real, siete
  campos mínimos inmutables, tablas ajenas indisponibles, caché obsoleta/no
  consultable y conjunto vacío SQL; cambio pendiente frente a commit desde
  conexión independiente, nueva instancia y valores retenidos sin mutación.
  Ejecuta el caso de uso/evaluador existentes sobre dos empresas, cuatro
  estados, resolución ausente/anterior/válida/cero y objetivo conocido/
  ausente/no positivo, sin completar datos ni alterar filas.
- Compatibilidad comprobada: HU-18 RF-179 (autorización de aplicación previa;
  no se añade prueba HTTP 401 aquí), RF-180–182 (conjunto por empresa y volumen),
  RF-183–186/191 (muestras independientes, exclusiones y objetivo conservado),
  RF-187–188 (estado confirmado posterior, instantánea única y solo lectura).
  Ejemplo de cinco tickets: 5/3/2, promedio 90 sobre 2 y SLA 50 % sobre 2,
  un finalizado excluido de cada muestra. Ejemplo de tres finalizados:
  promedio 120 sobre 3, SLA 50 % sobre 2 y una exclusión SLA; solo el finalizado
  sin objetivo: promedio 180 sobre 1, SLA sin datos/muestra 0. Cambiar la
  política del seam de 240 a 30 minutos conserva exactamente estos resultados,
  muestras, valores congelados y filas SQL; no acredita persistencia de políticas.
- Python 3.10.0; runner temporal existente
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`.
  Configuración Docker solo en memoria; entorno hijo sin DATABASE_URL ni
  POSTGRES_PASSWORD, solo HU26_TEST_DATABASE_URL opt-in para SQL, con
  HELPDESK_ALLOW_IN_MEMORY=1 y PYTHONPATH=backend. Conexiones/migraciones
  únicamente scoped por el helper A1, sin public en search_path ni fixtures
  destructivas heredadas sobre el demo. Context7 consultado para filas
  diccionario/lecturas de psycopg 3.
- Comando focalizado:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_metrics_snapshot.py -q -rs --tb=short`.
  Rojo real antes del código: **21 failed/6 passed**, exit 1
  (6,14 s; runner 6,83 s). Verde tras implementación mínima:
  **27 passed/0 skipped**, exit 0 (7,95 s; runner 8,59 s).
- Acumulada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py
  backend/tests/test_hu26_ticket_reads.py
  backend/tests/test_hu26_ticket_metrics_snapshot.py -q -rs --tb=short`
  → **277 passed/0 skipped/3 warnings**, exit 0
  (136,39 s; runner 137,28 s).
- Antes/después del rojo, focalizada verde y acumulada SQL: **11 tablas public**,
  huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Solo huellas agregadas; ningún secreto,
  DSN ni fila operativa en salida.
- G completa: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a `PYTHONPATH=backend python -m pytest -q -rs` con DATABASE_URL,
  POSTGRES_PASSWORD y HU26_TEST_DATABASE_URL retirados y HELPDESK_ALLOW_IN_MEMORY=1:
  **2010 passed/272 skipped/3 warnings**, exit 0
  (208,36 s; runner 209,30 s). **232 SQL opt-in ejecutados aparte; 40 skips
  previos no acreditados**. No se añaden skips/xfail para ocultar fallos.
- Interrupción por límite de pasos después de las puertas verdes; se reanuda
  exclusivamente el cierre documental, sin repetir pruebas ni modificar código.
  B.I.5 se marca tras esas puertas; B.I.6 no iniciada. INSERT, mutaciones,
  políticas persistentes, notificaciones, seed y validación HTTP posterior
  siguen fuera de esta tarea. G en memoria no certifica mutaciones SQL ni
  persistencia integral. No desplegar el adaptador parcial; sin migrar public,
  arrancar API/web, reiniciar/recrear servicios ni hacer commit/reset.
  Frontend/lint/build no repetidos; límites de integración anteriores vigentes.
- Cierre: `cmd /c codegraph sync`, `graphify update .` y `git diff --check`,
  exit 0. Grafo/reporte actualizados: 5212 nodos, 10980 aristas y 388 comunidades.
  Graphify sigue sin extractor SQL y omite HTML por superar 5000 nodos.
  Se repiten las comprobaciones después de esta última edición documental.

### Evidencia B.I.6 — completada (2026-11-27)

- Solo B.I.6; clasificación HIGH recibida por integridad transaccional/concurrencia,
  riesgo alto y confianza alta. HU-26 PERSIST-1/2/6/8 en el alcance de inserción,
  no cumplimiento global. Sin decisiones nuevas de negocio, arquitectura,
  contratos ni dependencias. Se reutiliza localmente el patrón A5, sin importar
  infraestructura de identity ni diseñar la unidad de mutaciones.
- `tickets/infrastructure/ticket_repository.py`: `add(ticket, conn=None)`
  ejecuta un INSERT de los doce campos del agregado, incluidos nulos, texto y
  fechas exactos. No hay UPSERT/deduplicación por texto ni consultas SQL ajenas.
  Un ID existente propaga UniqueViolation y conserva toda la fila previa,
  incluido updated_at; no restaura el estado inicial. No publica caché SQL.
  Con conexión propia retorna solo tras salir del contexto que confirma;
  con conexión externa inicia BEGIN si está idle (también autocommit) y usa
  transaction() como savepoint, dejando el commit/rollback al llamador.
  Errores locales revierten su unidad aunque se capturen para confirmar otro
  trabajo. SQL configurado fallido nunca se sustituye por memoria.
  El seam explícito conserva referencias y reemplazo anteriores.
- Nuevo `backend/tests/test_hu26_ticket_insert.py`: **28 casos**, 22 SQL opt-in
  y 6 de seam/errores. Alta completa y con nulos, relectura por otra instancia,
  títulos iguales/IDs diferentes, duplicado propio/externo sin alterar progreso,
  FK vigente y tablas de otros módulos renombradas sin consultas desde tickets.
  Rollback/visibilidad externos con transacción idle/abierta y autocommit on/off;
  confirmación externa publica solo después del commit. Trigger inmediato y
  constraint trigger inicialmente diferido verifican COMMIT real (no simulado).
  Inyección Python después del INSERT real comprueba rollback al savepoint
  aunque el llamador capture el error y confirme trabajo independiente previo.
  Dos conexiones scoped, sincronizadas por barrera y sin sleeps, compiten por
  el mismo ID: un commit, un UniqueViolation y una sola fila igual al ganador.
- Python 3.10.0; runner temporal existente
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`.
  Configuración Docker solo en memoria, sin DSN/secretos ni filas operativas
  en salida. Hijo sanitizado: DATABASE_URL/POSTGRES_PASSWORD retirados;
  SQL solo con HU26_TEST_DATABASE_URL opt-in, PYTHONPATH=backend y
  HELPDESK_ALLOW_IN_MEMORY=1. Todas las conexiones/migraciones/carreras pasan
  por helper A1 en esquema propio, sin public en search_path; no se usan
  fixtures destructivas heredadas contra el demo. Context7 consultado para
  transaction()/savepoints, BEGIN/autocommit y commit del contexto psycopg 3.
- Comando focalizado:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_insert.py -q -rs --tb=short`.
  Rojo antes de producción: **27 failed/1 passed**, exit 1
  (9,83 s; runner 10,52 s). Verde tras cambio mínimo:
  **28 passed/0 skipped**, exit 0 (11,35 s; runner 12,05 s).
- Acumulada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py
  backend/tests/test_hu26_ticket_reads.py
  backend/tests/test_hu26_ticket_metrics_snapshot.py
  backend/tests/test_hu26_ticket_insert.py -q -rs --tb=short`
  → **305 passed/0 skipped/3 warnings**, exit 0
  (153,64 s; runner 154,44 s).
- Antes/después del rojo, focalizada verde y acumulada SQL: **11 tablas public**,
  huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**.
- G completa: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a PYTHONPATH=backend python -m pytest -q -rs con DATABASE_URL,
  POSTGRES_PASSWORD y HU26_TEST_DATABASE_URL retirados y HELPDESK_ALLOW_IN_MEMORY=1:
  **2016 passed/294 skipped/3 warnings**, exit 0
  (213,58 s; runner 214,62 s). **254 SQL opt-in ejecutados aparte; 40 skips
  previos no acreditados**. Ningún skip/xfail para ocultar fallos.
- B.I.6 se marca tras puertas verdes; B.I.7 no iniciada. No se modificaron
  create_ticket/router/HTTP, mutaciones, políticas, notificaciones, seed,
  tablas ajenas ni migraciones. G en memoria no acredita mutaciones SQL ni
  persistencia integral. Sin migrar public, reiniciar/recrear servicios,
  arrancar API/web, desplegar ni hacer commit/reset; cambios ajenos preservados.
  Frontend/lint/build no repetidos y límites previos de integración vigentes.
   Tras el cierre documental se ejecutan `cmd /c codegraph sync`,
   `graphify update .` y `git diff --check`; su resultado se informa en la entrega.

### Evidencia B.I.7 — completada (2026-11-27)

- Solo B.I.7, clasificación HIGH recibida, riesgo alto/confianza alta.
  HU-26 PERSIST-1/2/6/8 y RF-165/171 únicamente en alta/consulta HTTP.
  Test primero: **no hubo rojo** porque verifica la composición existente de
  B.I.6; no se fabrica un fallo ni se cambia producción innecesariamente.
  `create_ticket.py` y `tickets/interface/router.py` permanecen intactos.
  Sin decisiones nuevas, dependencias, contratos ni reglas de negocio.
- Nuevo `backend/tests/test_hu26_ticket_create_http.py`: **29 casos SQL/HTTP**.
  TestClient de app real con startup/login, un cliente/cookie por actor, sin
  overrides de rutas/casos de uso/persistencia. Alta de cliente/administrador,
  texto Unicode recortado, límites 1/200 y 1/5000, títulos idénticos con UUID
  distintos. Antes de cualquier GET, otra conexión confirma UUID, texto,
  creación UTC, empresa/solicitante de sesión, Abierto y prioridad/asignación/
  resolución/objetivo nulos. Instancia independiente recupera el agregado;
  GET detalle/listado y `/all` usan un singleton nuevo y conservan DTO exactos
  de once/ocho claves, solicitante completo/mínimo y caché vacía.
  Entradas inválidas y campos de sesión/progreso inyectados dan 422 sin fila;
  401 sin sesión, 404 por rol/sin empresa y 409 empresa inactiva preceden incluso
  al JSON malformado. Triggers reales de B.I.6 (inmediato y constraint trigger
  inicialmente diferido al COMMIT) causan HTTP 500, sin fila/caché ni ticket
  fantasma en listados posteriores desde repositorio nuevo.
- Python 3.10.0; runner temporal existente
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`.
  Configuración Docker solo en memoria; SQL solo con DSN opt-in, esquema propio
  del helper A1 y sin public en search_path. También startup y cada conexión
  de HTTP pasan por `isolated.connect` y verifican ese aislamiento. No fixtures
  destructivas heredadas sobre demo. Context7 consultado para TestClient como
  contexto/startup y `raise_server_exceptions=False` al comprobar HTTP 500.
- Focalizada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_create_http.py -q -rs --tb=short`
  → **29 passed/0 skipped/3 warnings**, exit 0 (16,52 s; runner 17,06 s).
- Acumulada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py
  backend/tests/test_hu26_ticket_reads.py
  backend/tests/test_hu26_ticket_metrics_snapshot.py
  backend/tests/test_hu26_ticket_insert.py
  backend/tests/test_hu26_ticket_create_http.py -q -rs --tb=short`
  → **334 passed/0 skipped/3 warnings**, exit 0 (166,17 s; runner 166,74 s).
- Antes/después de ambas corridas SQL: **11 tablas public**, huella idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Sin DSN/secretos/filas en salida.
- G completa: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a PYTHONPATH=backend python -m pytest -q -rs con DATABASE_URL,
  POSTGRES_PASSWORD y HU26_TEST_DATABASE_URL retirados y HELPDESK_ALLOW_IN_MEMORY=1:
  **2016 passed/323 skipped/3 warnings**, exit 0 (173,69 s; runner 174,47 s).
  **283 SQL opt-in ejecutados aparte; 40 skips previos no acreditados**.
  Los 29 nuevos son opt-in, no omisiones para ocultar fallos.
- B.I.7 marcada tras puertas verdes; B.I.8 no iniciada. Sin conectar mutaciones,
  reopen/comentarios, seed ni políticas; G no acredita mutaciones SQL pendientes
  ni persistencia integral. Sin migrar public, arrancar API/web, desplegar,
  reiniciar/recrear servicios ni hacer commit/reset. Cambios locales preservados.
  Frontend/lint/build no repetidos; límites previos de integración vigentes.
  Tras esta última edición se ejecutan `cmd /c codegraph sync`,
   `graphify update .` y `git diff --check`; resultados en la entrega.

### Evidencia B.I.9 — validación acotada (2026-11-27)

- Solo B.I.9, clasificación HIGH recibida, riesgo alto/confianza alta. Tests
  primero, sin rojo artificial: se verifica composición existente, sin cambios
  de producción, contratos, migraciones, dependencias ni pruebas ajenas.
- Nuevo `backend/tests/test_hu26_ticket_base_composition.py`: tres comprobaciones
  estáticas reutilizan A7 y exigen SQL propio real de tickets, ausencia de
  imports de repositorios ajenos, contratos sin imports cruzados (incluido
  `sla/interface/contract.py`) y composición/migraciones solo en main.
  Dos casos SQL/HTTP/proceso nuevo parametrizan alta como cliente/administrador:
  dos POST 201 de texto idéntico conservan UUID distintos. Un intérprete hijo
  inicia la app real, rechaza petición anónima y cookie anterior con 401,
  reautentica por HTTP y compara detalle/listados propios y `/all` con los DTO
  originales. Conserva ID/texto/creación/empresa/solicitante y nulos reales,
  sin regenerar ni deduplicar tickets. Contratos existentes de estadísticas
  de empresa y vista SLA releen SQL, sin validar todos sus consumidores.
  Cambios sintéticos exclusivamente locales de una referencia/caché fantasma
  no aparecen en el hijo; no se invocan mutaciones HTTP pendientes ni se
  promete rescatar memoria/sesiones. Las filas completas, incluido updated_at,
  permanecen idénticas después de todas las consultas.
- Helper A1 crea/limpia solo su esquema propio. El padre usa su factoría en
  arranque/HTTP; el hijo recibe DATABASE_URL scoped, retira opt-in/seam,
  configuración demo/SMTP y no ejecuta seed. Cada conexión real del hijo
  valida current_schema/current_schemas antes de startup/HTTP/contratos:
  únicamente el esquema generado y pg_catalog, nunca public.
- Python 3.10.0; runner temporal existente
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`; configuración
  Docker solo en memoria, sin DSN/secretos en salida.
  Focalizada: `python <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_base_composition.py -q -rs --tb=short`
  → **5 passed/0 skipped/3 warnings**, exit 0 (5,36 s; runner 5,91 s).
- Acumulada A1–A7+B.I.1–9: PowerShell
  `$tests = @(Get-ChildItem backend/tests/test_hu26_*.py | Sort-Object Name |
  ForEach-Object { 'backend/tests/' + $_.Name })`;
  `python <temporal>/hu26_bi2_runner.py --sql @tests -q -rs --tb=short`.
  Se incluyeron los 17 módulos HU-26 existentes:
  **399 passed/0 skipped/3 warnings**, exit 0 (226,10 s; runner 226,78 s).
- Antes/después de focalizada y acumulada SQL: **11 tablas public**, huella
  agregada idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Sin migrar public, fixtures heredadas
  contra demo, reiniciar/recrear servicios ni arrancar API/web.
- G completa: `python <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a PYTHONPATH=backend python -m pytest -q -rs, sin DATABASE_URL,
  POSTGRES_PASSWORD ni HU26_TEST_DATABASE_URL y con HELPDESK_ALLOW_IN_MEMORY=1:
  **2019 passed/385 skipped/3 warnings**, exit 0 (179,52 s; runner 180,27 s).
  **345 SQL opt-in ejecutados aparte; 40 skips previos no acreditados**.
  Los dos SQL nuevos reutilizan la fixture B.I.7 y su mensaje opt-in; no son
  omisiones para ocultar fallos. G en memoria no acredita mutaciones SQL.
- Frontend, sin modificar código: desde `frontend/`,
  `$env:VITE_API_URL='http://127.0.0.1:1'; npm test` →
  **461 passed/43 archivos/0 skips**, exit 0 (Vitest 16,56 s; comando 20,25 s).
  En ese mismo entorno `npm run lint` → exit 0 (5,76 s);
  `npm run build` → exit 0 (7,40 s; Vite 3,44 s), 1703 módulos y 347,13 kB JS.
  Es la puerta offline de CI con API deliberadamente inaccesible, no integración
  desplegada. API/web permanecieron apagadas: no se repitió con API viva, ni
  se arrancó para esta tarea. Siguen documentados los seis fallos 401 heredados
  de A7 (cinco MobileSidebar, uno DashboardPage); no se ocultaron con cambios
  de código, mocks nuevos ni relajación de producción.
- B.I.9 **implementada y aprobada en QA independiente por reviewer-deep**,
  exclusivamente junto con B.I.1–9. Solo se cierra la base SQL/alta/consultas
  de B.I; no B completo ni HU-26. Evidencia independiente al final de la matriz.
  Sin nuevas decisiones de negocio o alcance. Cambios locales ajenos preservados,
  sin commit/reset ni operaciones activas. Tras la última edición documental se
  ejecutan `cmd /c codegraph sync`, `graphify update .` y `git diff --check`;
  resultados en la entrega. Graphify conserva la limitación sin extractor SQL
  y sin HTML para grafos mayores de 5000 nodos.

#### Matriz RF del cierre B.I (no cierre de HU-26)

| RF de HU-26 | Evidencia acotada | Veredicto y límite global |
|---|---|---|
| PERSIST-1 | B.I.9: alta HTTP confirmada en padre y consulta HTTP en hijo sin seed/caché | CUMPLE alcance B.I; PARCIAL global: no reinicio desplegado ni mutaciones completas |
| PERSIST-2 | B.I.2–8: columnas nullable, lecturas/snapshot/INSERT y DTO; B.I.9 preserva altas/nulos entre procesos | CUMPLE alcance B.I; PARCIAL global: ciclo de vida/asignaciones pendientes B.II/III; no reconstrucción histórica |
| PERSIST-5 (parcial) | A reutilizado; objetivo conservado en snapshot SQL y nombre actual faltante mediante contrato tras autorizar | CUMPLE alcance B.I; PARCIAL global: configuración SLA pendiente C |
| PERSIST-6 | Fallos SQL/COMMIT/rollback y concurrencia en B.I.2/3/4/5/6/7; regresión acumulada como puerta | CUMPLE alcance B.I; PARCIAL global: no atomicidad de mutaciones e historial |
| PERSIST-8 | B.I.8 permisos/DTO/dos empresas; B.I.9 fronteras y detalle/listados tras reautenticar | CUMPLE alcance B.I; PARCIAL global: consumidores completos e historial/notificaciones pendientes |
| RF-165 (solo alta/consulta) | TestClient real sobre PostgreSQL aislado, alta confirmada y relectura | CUMPLE alcance B.I; PARCIAL global: no atención completa ni recorrido desplegado |
| RF-171 | Salidas reales de pytest/frontend/lint/build; QA independiente SQL/G | CUMPLE alcance B.I; PARCIAL global: sin smoke/recorrido desplegado ni integración acreditada por frontend offline |

PERSIST-3 no cerrado; configuración SLA/notificaciones (C), seed DEMO/PERSIST-7
(D), sesiones y reinicio/recorrido desplegado (E) no quedan acreditados.
B.II–IV no iniciados ni autorizados en detalle; C–E requieren sus detalles y
aprobaciones separados. B completo y HU-26 siguen parciales. La aprobación de
QA siguiente no amplía la autorización más allá de B.I.

#### Cierre fase 7 — QA independiente de B.I aprobado (2026-11-27)

- Veredicto comunicado por el coordinador: **APROBADO solo B.I.1–9**, por
  `reviewer-deep`, sin incumplimientos bloqueantes. QA no editó archivos;
  no se invocó `reviewer-expert`. Clasificación HIGH vigente.
- QA repitió las puertas pytest documentadas arriba: acumulada SQL A1–A7+B.I
  (17 módulos HU-26, runner aislado `hu26_bi2_runner.py --sql @tests
  -q -rs --tb=short`) → **399 passed/0 skips**, exit 0 (**208,57 s**).
  G sanitizada (runner sin `--sql`, `-q -rs`; sin DATABASE_URL,
  POSTGRES_PASSWORD ni HU26_TEST_DATABASE_URL, HELPDESK_ALLOW_IN_MEMORY=1)
  → **2019 passed/385 skips**, exit 0 (**166,91 s**):
  **345 SQL opt-in pasados aparte y 40 skips previos no acreditados**.
- Incidente de la primera acumulada QA SQL: **398 passed/1 failed**, por
  Windows **10048 al conectar antes del HTTP** en
  `test_hu26_ticket_read_http.py:194`. La repetición **completa** posterior
  fue verde, sin cambios de código ni servicios; no se ocultó el fallo.
  Huellas de las **11 tablas public idénticas y 0 esquemas residuales**;
  `git diff --check` de QA exit 0.
- QA confirmó HTTP con TestClient real, arquitectura/contratos/fronteras y
  ajustes históricos autorizados A2/A7. Compatibilidad HU-18 RF-179–188/191
  aprobada mediante snapshot SQL y G; RF-187 de ciclo de vida solo tiene
  regresión **en memoria**, sin acreditar mutaciones SQL.
- QA **no repitió frontend/lint/build**: conserva evidencia del implementador
  **461 passed/43 archivos**, lint/build exit 0, **offline**. Los seis fallos
  401 heredados con API viva siguen siendo limitación; no integración desplegada.
- Este cierre solo registra evidencia recibida en plan/tareas/memoria: no
  ejecuta nuevas pruebas/SQL, cambios de código, migración de public, reinicios,
  API/web ni despliegue. Se verifica diff-check después de la última edición.

### Evidencia B.I.8 — completada (2026-11-27)

- Solo B.I.8, clasificación HIGH recibida sin reclasificación, riesgo alto y
  confianza alta. HU-26 PERSIST-2/5 parcial/8 en consultas autorizadas y DTO,
  sin cumplimiento global. Sin decisiones nuevas de negocio, arquitectura,
  contratos públicos ni dependencias; no se implementan mutaciones SQL.
- Nuevo `backend/tests/test_hu26_ticket_read_http.py`: **60 casos SQL/HTTP**.
  Reutiliza fixtures de aislamiento, hash sintético y clientes de B.I.7, con
  mundo propio de dos empresas, solicitantes propio/ajeno, administradores de
  ambas empresas/plataforma, supervisor, técnicos asignado/no asignado y
  cuentas sin empresa. TestClient de app real, startup/login y conexiones
  scoped de A1; sin sustituir rutas, casos de uso ni persistencia.
  Detalle y cuatro listados verifican 401/404, alcance antes de composición,
  once/ocho claves exactas y solicitante completo/mínimo. Espías delegan en
  contratos reales y comprueban que solo se componen datos autorizados.
  IDs inválidos/inexistentes con cuerpo GET malformado conservan 401/404.
  Filas sin nombre proyectado y con nombre conservado mantienen el ID;
  cambios SQL de nombre/rol/estado actuales no ocultan asignaciones históricas.
  Resolución/objetivo ausentes permanecen nulos, valores conocidos permanecen
  intactos y todas las filas, incluido updated_at, se conservan tras consultar.
- Cambio mínimo en `tickets/interface/router.py`, `_assignee_response`:
  solo si falta el nombre proyectado resuelve el nombre actual mediante
  `get_user_summary`, sin filtrar elegibilidad ni sobrescribir el agregado.
  Un nombre ya conservado no provoca esa resolución ni se reemplaza.
  No consulta tablas ajenas ni añade campos/correos a las respuestas.
  La autorización existente sigue precediendo al serializador; contratos
  siguen sin imports cruzados. Context7 consultado para TestClient como
  contexto/startup y request con contenido.
- Python 3.10.0; mismo runner temporal externo
  `C:\Users\nicom\AppData\Local\Temp\opencode\hu26_bi2_runner.py`.
  Configuración Docker solo en memoria; SQL opt-in por HU26_TEST_DATABASE_URL,
  todas las conexiones/startup/migraciones solo en esquema generado A1, sin
  public en search_path ni fixtures destructivas heredadas contra demo.
- Tests primero, comando focalizado:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_ticket_read_http.py -q -rs --tb=short`.
  Primera ejecución **22 failed/38 passed**, exit 1 (41,14 s), incluyó dos
  errores de fixture al usar estado de empresa `inactive` en usuarios.
  Corregida únicamente la fixture nueva a `deactivated`, antes de producción:
  mismo comando con `--tb=no` → rojo funcional **22 failed/38 passed/
  3 warnings**, exit 1 (40,40 s; runner 40,95 s).
  Tras cambio mínimo, focalizada **60 passed/0 skipped/3 warnings**, exit 0
  (43,77 s; runner 44,45 s). Sin rojo artificial ni cambios de tests ajenos.
- Se reanudó esta misma tarea tras límite de pasos: no se repitió focalizada
  ni se modificó código; se ejecutaron las puertas restantes. Acumulada:
  `py -3.10 <temporal>/hu26_bi2_runner.py --sql
  backend/tests/test_hu26_sql_isolation.py
  backend/tests/test_hu26_account_reconciliation.py
  backend/tests/test_hu26_canonical_identity_reads.py
  backend/tests/test_hu26_identity_directories.py
  backend/tests/test_hu26_identity_atomic_storage.py
  backend/tests/test_hu26_identity_mutations.py
  backend/tests/test_hu26_identity_invitations.py
  backend/tests/test_hu26_company_reads.py
  backend/tests/test_hu26_composition.py
  backend/tests/test_hu26_ticket_legacy.py
  backend/tests/test_hu26_ticket_schema.py
  backend/tests/test_hu26_ticket_reads.py
  backend/tests/test_hu26_ticket_metrics_snapshot.py
  backend/tests/test_hu26_ticket_insert.py
  backend/tests/test_hu26_ticket_create_http.py
  backend/tests/test_hu26_ticket_read_http.py -q -rs --tb=short`
  → **394 passed/0 skipped/3 warnings**, exit 0
  (206,68 s; runner 207,28 s).
- Antes/después de cada corrida SQL, incluida la acumulada de reanudación:
  **11 tablas public**, huella agregada idéntica
  `e31328c88cf2d3144b687cdc34af1fb699523fa9b6496b21124af1daf6be6699`,
  **0 esquemas hu26_test_* residuales**. Sin DSN, secretos ni filas operativas
  en salida; no se modifican datos activos.
- G completa: `py -3.10 <temporal>/hu26_bi2_runner.py -q -rs` (sin --sql),
  equivalente a PYTHONPATH=backend python -m pytest -q -rs con DATABASE_URL,
  POSTGRES_PASSWORD y HU26_TEST_DATABASE_URL retirados y HELPDESK_ALLOW_IN_MEMORY=1:
  **2016 passed/383 skipped/3 warnings**, exit 0 (179,70 s; runner 180,52 s).
  **343 SQL opt-in ejecutados aparte; 40 skips previos no acreditados**.
  Los 60 nuevos usan el opt-in/fixture existente de B.I.7 (su mensaje de skip
  conserva esa etiqueta); no se añaden omisiones/xfail para ocultar fallos.
- B.I.8 marcada solo tras puertas verdes; B.I.9 no iniciada. No ampliar a
  dashboards, mutaciones, historial, políticas persistentes, notificaciones,
  seed ni despliegue. G en memoria no acredita mutaciones SQL pendientes ni
  persistencia integral. Sin migrar public, arrancar API/web, reiniciar/recrear
  servicios ni hacer commit/reset; cambios locales ajenos preservados.
  Frontend/lint/build no repetidos; límites previos de integración vigentes.
  Tras esta última edición se ejecutan `cmd /c codegraph sync`,
  `graphify update .` y `git diff --check`; resultados en la entrega.
