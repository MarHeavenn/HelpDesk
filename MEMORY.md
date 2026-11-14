# Memoria del proyecto

## Estado actual

- HU-01..HU-12, HU-14 y HU-21 **mergeadas en `develop`**; la persistencia de
  los módulos sigue en memoria (TSK-025 deja PostgreSQL preparado).
- HU-22 (creación y detalle) y HU-23 (listados) en la rama
  `feature/HU-20-tickets-frontend`, sin commit ni PR todavía.
- Suites al 2026-11-13: backend **1191 passed, 14 skipped**; frontend
  **22 archivos / 155 pruebas**; `lint` y `build` en verde.
- HU-23: `/tickets` y `/mis-tickets` reales sobre un `TicketListPage` común;
  filtros, orden y paginación en cliente con la URL como fuente de verdad.
  El técnico ve sus asignados en «Mis tickets»; admin y cliente, los suyos.
- HU-23: nuevo `GET /api/tickets/all` (administrador y técnico; cliente 404,
  sin sesión 401), declarado antes de `GET /{ticket_id}`.
- HU-22: detalle en modal accesible desde la tabla, con prioridad/estado,
  asignación (solo admin) y comentarios; título y descripción inmutables.
- Smoke manual ejecutado el 2026-11-13 con las tres cuentas: API real (90
  comprobaciones) e interfaz real en Chrome headless (27), en verde.
- HU-11 y HU-12: dashboard real de tickets y de SLA en `/`.

## Decisiones clave

- HU-09: historial derivado, no persistido; admin/técnico, cliente 404.
- HU-08: `Abierto` → `En progreso` → `Resuelto` → `Cerrado`; retroceso
  `Resuelto` → `En progreso`; reapertura solo administrador.
- HU-07: comentarios de 1–2000 code points; admin y técnico escriben.
- HU-06: cliente solo sus tickets; el detalle añade `requester` y `resolved_at`.
- HU-05/HU-14: SLA 120/240/720/1440 min; `Resuelto`/`Cerrado` congelan
  `resolved_at`; `GET/PUT /api/sla/policies` solo admin.
- `sla` no importa `tickets`; `tickets` compone el SLA con `get_ticket_sla`.
- HU-23: el filtro de técnico se deriva de los tickets cargados, porque el
  directorio completo (`/api/technicians`) es solo del administrador.
- HU-22/HU-23: `TicketListPage` sirve ambos listados; «Mis tickets» no consulta
  hasta resolver el rol, para no pedir el alcance equivocado.

## Entorno local

- `.venv` en la raíz; `infra/.env` usa `POSTGRES_PORT=55432` (5432 ocupado).
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`;
  sin él, los tests de BD se saltan.
- Frontend: `cd frontend`, `npm install`, `npm run dev` en `localhost:5173`.
- Smoke de API reproducible: `cd backend` y `..\.venv\Scripts\python.exe
  smoke_manual.py` (levanta uvicorn real y siembra las tres cuentas).

## Errores que se deben evitar

- No usar el puerto 5432. No afirmar pruebas no ejecutadas. En PowerShell no
  existe `tail`. `codegraph` solo vía `cmd /c`.
- No poner lógica de negocio en los HTTP ni tocar tablas de otros módulos.
- Logout 204 devuelve cuerpo vacío. 422 de Pydantic: `detail` lista; del
  dominio: `detail` cadena. Un `TestClient` tiene una sola cookie: uno por rol.
- Tests de contrato comparan campos exactos; envejecer tickets mutando
  `created_at` (nunca dormir). La config de SLA es un singleton con `reset()`.
- Al añadir una ruta, revisar los barridos que afirman su ausencia.
- Vitest sin `globals`: registrar `cleanup()` de RTL en `tests/setup.ts`.
- Abrir el frontend en `localhost:5173`, no `127.0.0.1`, por la cookie.
- Las vistas de tickets usan la API real: en pruebas hay que inyectar el fake o
  stubear `fetch`; si no, el 401 global desmonta la vista.

## Próximos pasos

- PR de HU-22/HU-23 contra `develop` (los cambios siguen sin commit).
- Revisión visual manual de HU-21 en 360/768/1024/1440 px, aún pendiente.
- Conectar las vistas restantes: técnicos, SLA, usuarios y empresas.
- Integrar los módulos con PostgreSQL en una tarea aparte.

## HU-13

- A-T1 completada: migración `002_identity_accounts.sql` validada contra PostgreSQL
  y compatible con `001`; mantiene cuentas existentes como `accepted` y aplica
  invariantes de roles, estados e invitación/hash.
- Las pruebas de violaciones de CHECK usan savepoints explícitos para poder
  continuar en la misma transacción tras un error esperado; la migración no fue
  modificada por el fallo de pytest.
- HU-13 A-T2 completada: consulta y alta de usuarios por tenant en `/api/users`,
  representación sin secretos, autorización admin/404 uniforme, validación,
  unicidad global y `email_status=not-attempted` sin SMTP. Focal: 5 passed;
  suite backend: 1206 passed, 1 warning.
- HU-13 A-T3 completada: PATCH parcial de usuarios, cambios de rol/estado,
  revocación de sesiones al desactivar y protección del último administrador
  activo. La invariancia concurrente usa `pg_advisory_xact_lock` y una tabla
  coordinadora compartida creada idempotentemente en PostgreSQL; no depende de
  locks de proceso. Se añadió el estado `email_status=not-attempted` al cambio
  de correo de cuentas pendientes. Focal: 10 passed; suite backend: 1215
  passed, 1 warning.
- HU-13 A-T4 completada: invitaciones de un solo uso con hash y expiración de
   168 horas, aceptación atómica y bloqueo de login para cuentas pending o
   deactivated. Alta, cambio de correo pendiente y reenvío informan únicamente
   `email_status` (`sent`/`failed`/`not-attempted`) mediante SMTP opcional, sin
   header de entrega. Focal: 6 passed; suite backend: 1221 passed, 1 warning.
- HU-13 A-T5 completada: roles, guards, avisos y rutas frontend validados; se
  fijó explícitamente la dependencia de autenticación antes de resolver
  ticket/cuerpo en prioridad, estado y asignación, preservando 401 > 404 >
  409 > 422. Focal backend: 177 passed; suite backend: 1221 passed, 1
  warning; frontend: 123 passed y build correcto.
- HU-13 B-T1 completada: autorización de lectura/listado y modificación de
  tickets por `ticket.company_id`; admin/supervisor/técnico/cliente tienen el
  alcance aprobado, el técnico solo modifica asignados en tickets tenant y se
  conserva compatibilidad de tickets legacy sin tenant. Focal: 5 passed;
  suite backend: 1226 passed, 1 warning.
- HU-13 B-T2 completada: creación de tickets limitada a admin/cliente con
  empresa, requester/tenant fijados por sesión, y comentarios/historial
  aislados por rol y tenant. Se adaptaron fixtures y expectativas heredadas
  de tickets/SLA al contrato vigente, sin relajar las restricciones de
  técnico asignado, cuenta sin empresa, precedencias ni rechazos sin mutación.
  Focal: 5 passed; suite backend: 1231 passed, 1 warning; frontend: 123
  passed y build correcto.
- HU-13 B-T3 completada: dashboards de tickets/SLA, controles existentes y regresión B
   verificados conservando esquemas, métricas, periodos, SLA y aislamiento por tenant.
   Se corrigieron fixtures heredados para invalidar realmente la cookie de sesión antes
   de comprobar la precedencia 401. Focal: 45 passed, 1 warning; backend: 1235
   passed, 1 warning; frontend: 123 passed y build correcto.
- HU-13 C-T1 completada: `GET /api/technicians` limita el directorio a
  administradores/supervisores con empresa, devuelve solo técnicos activos del
  tenant como `{id,name}` y conserva `[]` para el resultado vacío; cuentas sin
  empresa y roles no autorizados reciben el 404 uniforme. La ruta `/tecnicos`
  existente consume el contrato y muestra el estado vacío sin crear rutas nuevas.
  Focal: 30 passed, 1 warning; suite backend: 1240 passed, 18 skipped, 1
   warning; frontend: 125 passed y build correcto.
- HU-13 C-T2 completada: la operación existente `PUT /api/tickets/{id}/assignee`
  admite administrador/supervisor y valida actor, ticket y técnico por tenant;
  UUID inválido conserva 422 estructural, técnico inexistente/cruzado devuelve
  404 uniforme y técnico propio inactivo/no técnico devuelve 422 de dominio.
  Los rechazos no mutan ticket/log y desactivar conserva asignaciones vigentes.
  Focal: 7 passed; suite backend: 1248 passed, 18 skipped, 1 warning;
   frontend: 125 passed y build correcto. HU-13 queda lista para validación RF.
- HU-13 ronda de correcciones 1: aceptación, desactivación y rotación/reenvío
  comparten `pg_advisory_xact_lock` transaccional con clave estable por cuenta,
  sin lock de proceso; se revalida el token tras adquirirlo. Se añadieron
  contratos exactos de `email_status` para alta/PATCH pendiente/reenvío y su
  ausencia en respuestas no aplicables. El arranque configurado de la app aplica
  migraciones y propaga fallos para impedir iniciar con esquema parcial.
  Backend: 1253 passed con PostgreSQL; frontend: 125 passed y build correcto.
- HU-13 ronda de correcciones 2: aceptación, desactivación y rotación/reenvío
  ahora comparten el estado persistente `identity_invitation_accounts` de
  PostgreSQL. Cada operación adquiere el advisory lock por cuenta, relee y
  confirma dentro de la misma transacción; pruebas con repositorios
  independientes cubren aceptación↔desactivación y aceptación↔rotación.
- HU-13 R-T1 completada: se reprodujo inicialmente el fallo aislado de
  aceptación↔reenvío (`state is None`) y quedó verde al repetir la focalizada
  (4 passed), incluyendo ambos órdenes y lectura desde tercera conexión. La
  suite backend con PostgreSQL quedó en 1267 passed, 3 warnings; no se avanzó
  a R-T2.
- HU-13 R-T2 completada: `_invitation_lock` distingue PostgreSQL no configurado
  del entorno configurado; los fallos de conexión, lock o persistencia se
  propagan con rollback y no permiten mutación en memoria. Se añadieron pruebas
  de no mutación. Focalizada: 12 passed; backend con PostgreSQL: 1269 passed,
   3 warnings; frontend: 165 tests passed y build correcto.
- HU-13 corrección R-T2-C: invitaciones y cambio de estado restauran el
  agregado en memoria ante fallos de persistencia. PostgreSQL es obligatorio
  salvo `HELPDESK_ALLOW_IN_MEMORY=1`, seam activado explícitamente por el
  fixture unitario. Backend: 1248 passed/24 skipped sin DB y 1272 passed con
  PostgreSQL; frontend: 165 tests y build correctos.
