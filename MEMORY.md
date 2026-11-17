# Memoria del proyecto

## Estado actual

- HU-01..HU-14 y HU-21 mergeadas en `develop`; HU-22/HU-23 sin commit en
  `feature/HU-20-tickets-frontend`. HU-13 y HU-19 (T1–T10) completas.
- HU-19 añade el quinto módulo `companies` (D-1) y `/empresas`: catálogo,
  contacto, estado, invitación/reenvío del administrador, asociación de cuentas,
  cuentas sin empresa (RF-125–RF-143, RO-01/RO-02).
- Suites tras R9: backend 1530 passed con PostgreSQL; frontend 188 passed + build + lint.
- R1–R9 (HU-19): R1 `extra="forbid"` invitación; R2 índice `lower(email)` +
  `UserEmailConflictError`; R3 `companies` solo por contrato; R4 decisión de rama/409
  en application (`resolve_administrator_branch` lanza); R6 test SLA inmutable tras
  PATCH; R7 tolerancia heredados + nombre 101; R8 redirect `/empresas` con replace;
  R9 sin código muerto, rama de RF-141 resuelta una sola vez (el router la pasa al
  caso de uso), runbook junto a `006`, `_probe` borrada y `graphify-out/` ignorado.
- Persistencia: memoria + sincronización PostgreSQL (TSK-025); sin `DATABASE_URL` las pruebas de BD se omiten.

## Decisiones clave

- **D-1**: `companies` es dueño del catálogo de empresas y de contacto/estado; `identity` de cuentas e
  invitaciones; `tickets` de tickets. Se relacionan solo por contratos `interface/*_contract.py` (un contrato
  no importa el de otro módulo).
- **D-2**: unicidad del nombre en la aplicación (`pg_advisory_xact_lock` sobre la forma normalizada) con
  índice NO único; se toleran duplicados y nombres heredados fuera de 2–100.
- HU-13: invitaciones de 168 h de un solo uso con hash, unicidad global de correo, último administrador
  activo protegido, login bloqueado si la cuenta está pendiente/desactivada y `email_status`
  `sent`/`failed`/`not-attempted`.
- HU-13: precedencia 401 → 404 → 422 → 409; el ticket nuevo se bloquea por
  empresa inactiva antes de validar la entrada.
- Solo `status == "inactive"` bloquea altas: un `None` heredado (p. ej.
  `company_id="c1"`) NO bloquea, y desactivar no borra datos ni cierra sesiones.
- HU-09 historial derivado; HU-08 reapertura solo admin; HU-05/HU-14 SLA
  120/240/720/1440 min; HU-23 `TicketListPage` común para ambos listados.

## Entorno local

- BD = contenedor `infra-db-1` (`postgres:16`, único dueño del 55432; nunca 5432); sin `.venv` (Python global):
  `docker compose -f infra/docker-compose.yml up -d` y `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.
- Nunca levantar un PostgreSQL nativo/temporal en 55432: deja datos fuera del contenedor; si Docker falla, parar y reportar.
- Verificación: `cd backend` + `python -m pytest -q` (última: 1530 passed en 240 s contra el contenedor);
  `cd frontend` + `npm test`, `npm run build`, `npm run lint`. Frontend en `localhost:5173` (no `127.0.0.1`).
- Semilla RO-01: `backend/scripts/seed_platform_admin.py` con `PLATFORM_ADMIN_NAME/_EMAIL/_PASSWORD`.

## Errores que se deben evitar

- No afirmar pruebas no ejecutadas; `codegraph` solo vía `cmd /c`; ninguna regla de negocio en HTTP ni tablas ajenas.
- 422 de Pydantic: `detail` lista; de dominio: cadena. Un `TestClient` = un rol.
- Envejecer tickets mutando `created_at` (nunca dormir); SLA es singleton con `reset()`; al añadir una ruta, revisar los barridos de ausencia.
- Vitest sin `globals`: `cleanup()` de RTL en `tests/setup.ts` y API falsa o `fetch` stubeado.
- Las pruebas de migración no asumen que una versión concreta sea la última.

## Próximos pasos

- PR HU-22/HU-23 contra `develop`; revisión visual HU-21; conectar vistas restantes.
