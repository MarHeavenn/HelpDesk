# Memoria del proyecto

## Estado actual

- HU-01..HU-14, HU-19 y HU-21 **mergeadas en `develop`**; HU-15/HU-16
  implementadas (HU-16 en cierre de validación). Persistencia en memoria y
  PostgreSQL Docker (TSK-025).
- `companies` es el quinto módulo (HU-19, RF-125–RF-143): catálogo de empresas,
  contacto, estado e invitación/reenvío del administrador; `/empresas` real.
- HU-22/HU-23/HU-24 ya mergeadas en `develop` (PR #27). En
  `feature/HU-26-mvp-validation`: spec renombrada de HU-20-mvp-validation y
  renumerada a RF-165..RF-172; infra local creada (Dockerfiles + compose + nginx).
- HU-26 validada salvo el despliegue: suites verde y smoke 93/93; dos defectos
  de pruebas/smoke corregidos (test_dev_server_seed.py y smoke_manual.py) por
  cambios de HU-13/HU-19. Sin daemon de Docker no se ejecutaron CP-13/14/16:
  no afirmar que el MVP está arrancado.
- HU-23: `/tickets` y `/mis-tickets` sobre `TicketListPage`; filtros, orden y
  paginación en cliente con la URL como fuente de verdad; `GET /api/tickets/all`.
- HU-22: detalle en modal accesible con prioridad, estado, asignación y
  comentarios; título y descripción inmutables.
- HU-24 **implementada y validada**: `SlaSignal`, panel de alertas en `/` y
  cifra real en el KPI «Abiertos», sobre HU-10/11/12. Sin cambios en backend:
  `recent_tickets` no trae `sla`; campana sin contador (decisión del usuario).
  Spec, plan, tareas y validación RF por RF en
  `specs/features/HU-24-visual-panels-alerts/`.
- Suites: backend **1574 passed / 40 skipped** en memoria; frontend **34
  archivos / 236 pruebas**; `lint` y `build` correctos; smoke 93 comprobaciones.
- CI/CD (ejercicios de la carpeta `Proceso`): `ci.yml` (calidad en develop/main,
  GHCR solo en push a main con `helpdesk-backend`/`helpdesk-frontend`) y
  `deploy.yml` (`workflow_run` + Deploy Hooks de Render). Run `45263461824` en
  verde; `Publish Docker images` skipped en PR, correcto.
- CD decidido: **todo en Render free** (Web Service `helpdesk-api`, Static Site
  `helpdesk-web`, Postgres `helpdesk-db`) para una demo de 20 días a $0.
  `render.yaml` con `autoDeployTrigger: 'off'` y validado con el schema oficial;
  se retiró el compose de VPS. BD free expira a los 30 días: crearla al inicio
  de la ventana de demo. Spec/plan/tareas en `specs/features/CI-CD-github/`.
- R1–R9 (HU-19): `extra="forbid"`, unicidad de correo, `companies` solo por
  contrato, decisión de rama/409 en application, SLA inmutable en PATCH,
  tolerancia de heredados, redirect `/empresas` y sin código muerto.

## Decisiones clave

- **D-1**: `companies` es dueño del catálogo de empresas y de contacto/estado;
  `identity` de cuentas e invitaciones; `tickets` de tickets. Se relacionan solo
  por contratos `interface/*_contract.py` (un contrato no importa el de otro).
- **D-2**: unicidad del nombre en la aplicación (`pg_advisory_xact_lock` sobre
  la forma normalizada) con índice NO único; se toleran duplicados y heredados.
- HU-13: invitaciones de 168 h de un solo uso con hash, unicidad global de
  correo, último administrador activo protegido y login bloqueado si la cuenta
  está pendiente/desactivada (`email_status` `sent`/`failed`/`not-attempted`).
- HU-13: precedencia 401 → 404 → 422 → 409; alta bloqueada por empresa
  inactiva antes de validar la entrada; `None` heredado no bloquea.
- HU-09 historial derivado; HU-08 reapertura solo admin; HU-05/HU-14 SLA
  120/240/720/1440 min; HU-23 `TicketListPage` común para ambos listados.
- HU-15: notificaciones dentro de `tickets` (no módulo nuevo), una por
  destinatario y sin avisar al actor; polling 30 s + foco, sin WebSockets.
- HU-16: alerta para administradores activos del ámbito y técnico asignado;
  deduplicación en memoria por ticket, tipo, destinatario y vencimiento.
- HU-24: solo contratos reales, sin mocks; señal única derivada de `sla`;
  enlace de cada alerta a `/tickets?q=<id>` porque el detalle es modal.

## Entorno local

- BD = contenedor `infra-db-1` (`postgres:16`, único dueño del 55432; nunca
  5432): `docker compose -f infra/docker-compose.yml up -d` y
  `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.
- Nunca levantar un PostgreSQL nativo/temporal en 55432: deja datos fuera del
  contenedor; si Docker falla, parar y reportar.
- Verificación: `backend/.venv/Scripts/python.exe -m pytest -q`; en `frontend/`,
  `npm test`, `npm run build`, `npm run lint`. Frontend en `localhost:5173`
  (no `127.0.0.1`, por la cookie).
- Semilla RO-01: `backend/scripts/seed_platform_admin.py` con
  `PLATFORM_ADMIN_NAME/_EMAIL/_PASSWORD`.

## Errores que se deben evitar

- No afirmar pruebas no ejecutadas; `codegraph` solo vía `cmd /c`; ninguna
  regla de negocio en HTTP ni tablas ajenas.
- 422 de Pydantic: `detail` lista; de dominio: cadena. Un `TestClient` = un rol.
- Envejecer tickets mutando `created_at` (nunca dormir); SLA es singleton con
  `reset()`; al añadir una ruta, revisar los barridos de ausencia.
- Vitest sin `globals`: `cleanup()` de RTL en `tests/setup.ts` y API falsa o
  `fetch` stubeado (incluidas las vistas que consultan la API real).
- Las pruebas de migración no asumen que una versión concreta sea la última.
- Sin daemon de Docker no hay CP-13/14/16: validar compose con `docker-compose
  config -q` pero no afirmar arranque. `docker compose` v2 no está instalado.
- No afirmar que CI/CD corre en GitHub sin ver runs/checks/paquetes; los Deploy
  Hooks de Render y el environment `production` los configura el usuario, nunca
  en el repo.
- `smoke_manual.py` sin PostgreSQL necesita `HELPDESK_ALLOW_IN_MEMORY=1`; sus
  cuentas se siembran con `company_id` porque el registro público no lo asigna.

## Próximos pasos

- CI/CD: crear el Blueprint en Render, configurar variables del dashboard y los
  Deploy Hooks como secrets; hacer push a `main` y verificar CI, GHCR, Deploy y
  health. Crear la BD free al iniciar la ventana de 20 días.
- HU-26: ejecutar CP-13/14/16 en un equipo con daemon de Docker y completar la
  spec a «implementada»; revisión visual pendiente de HU-21/HU-24.
- Completar validación HU-16 RF por RF y revisión visual como técnico; no
  afirmar cierre hasta verificar criterios y actualizar sus documentos.
- Base aislada de pruebas Docker `helpdesk_hu16_validation_20261117`: no
  borrarla sin autorización. La deduplicación no coordina múltiples procesos.
- Smoke manual HU-15 con cliente, técnico, administrador y supervisor.
