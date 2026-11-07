# Memoria del proyecto

## Estado actual

- HU-01..HU-04 completas en `develop`. Suite: **746 passed, 3 failed** (fallos
  previos por precedencia 401/404 con cookie invalida; no tocan la BD).
- TSK-025 (PostgreSQL multitenant) en `develop`: 8 tablas, migraciones SQL
  idempotentes y 14 tests de integracion en verde. PostgreSQL 16 en Docker,
  puerto host **55432** (el 5432 lo ocupa un PostgreSQL nativo).
- Modulos `identity` y `tickets` (HU-02..HU-04) con persistencia en memoria;
  `assignment` y `sla` sin implementar. Casos de uso aun sin PostgreSQL.
- Asignaciones Trello de Tina: HU-11, HU-12 y HU-21 (en desarrollo). Specs,
  planes y tareas **aprobados**: `HU-21-frontend-shell/`,
  `HU-11-tickets-dashboard/` y `HU-12-sla-dashboard/` (RF-69..RF-104).
  Decisiones: dashboards con endpoints reales; HU-21 con shell + rutas + auth
  real; HU-11 admin global / tecnico asignados / cliente 404; HU-12 con 4
  estados SLA, umbral 20%, politica 2/4/12/24 h y panel dentro de `/`.
- Frontend HU-20 con spec/plan/tareas aprobadas. HU-21 T1 (scaffold Vite +
  React 18 + TS + Tailwind + Router + Query + Vitest) implementado en
  `frontend/`; `npm run test`, `build` y `lint` en verde. HU-21 T2 listo
  (tipos, textos, fechas es-CO y matriz de permisos con tests). T3 listo:
  `httpClient` con cookie/JSON/errores tipados, `auth.api` y `AuthContext`
  (loading/authenticated/anonymous/error, 401 global, nombre persistido).
  Suite frontend: **31 tests en verde**. Siguiente: T4 (pantalla de acceso).

## Decisiones TSK-025

- Una BD y un esquema; `company_id` en `users`, `tickets` y `sla_policies`.
  `ticket_sla` y `ticket_comments` heredan la empresa via `ticket_id`.
- FK compuestas `(company_id, requester_id/assignee_id) -> users(company_id,id)`.
- Trigger al crear empresa: SLA 2h/4h/12h/24h. Email unico global; roles
  `cliente`, `tecnico`, `administrador`. Migraciones propias, sin ORM.

## Entorno local

- `.venv` en `backend/`; instalar `backend/requirements.txt`.
- `infra/.env` (ignorado) con `POSTGRES_PORT=55432`.
- Migraciones: `backend\.venv\Scripts\python.exe backend\migrations\run.py`
  con `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.
- Tests de BD: mismo `DATABASE_URL`; se saltan si no hay PostgreSQL.

## Errores que se deben evitar

- No usar el puerto 5432: hay un PostgreSQL nativo y las conexiones no llegan
  al contenedor de Docker.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`.
- No poner logica de negocio en los HTTP ni tocar tablas de otros modulos.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default al final.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string.
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.

## Proximos pasos

- Aprobar las specs HU-11, HU-12 y HU-21; luego plan y tareas de cada una.
- Orden previsto: HU-21 (shell) → HU-11 (tickets) → HU-12 (SLA).
- HU-21 T4: pantalla de acceso `/login`.
- HU-21 T5..T10: shell, routing/guards, drawer, marcadores, logout y cierre.
- Integrar los modulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos por dependencias actuales.
- HU-20: siguiente T1 (scaffold) si se retoma antes que HU-21.
- HU-05 (SLA) descartada por el usuario.
- PRs siempre contra `develop`; `main` solo recibe versiones estables.
