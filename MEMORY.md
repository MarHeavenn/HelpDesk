# Memoria del proyecto

## Estado actual

- HU-01..HU-04 y TSK-025 en `develop`: backend en memoria + migraciones
  PostgreSQL idempotentes (8 tablas, 14 tests de integracion). Suite backend:
  **746 passed, 3 failed** (precedencia 401/404 con cookie invalida).
- Modulos `identity` y `tickets` con persistencia en memoria; `assignment` y
  `sla` sin implementar. Casos de uso aun sin PostgreSQL.
- Specs, planes y tareas aprobados: `HU-21-frontend-shell/`,
  `HU-11-tickets-dashboard/` y `HU-12-sla-dashboard/` (RF-69..RF-104).
  Dashboards con endpoints reales; HU-11 admin global / tecnico asignados /
  cliente 404; HU-12 con 4 estados SLA, umbral 20%, politica 2/4/12/24 h y
  panel dentro de `/`.
- HU-21 T1..T4 completas en `feature/HU-21-frontend-shell`: scaffold Vite +
  React 18 + TS + Tailwind + Router + Query + Vitest; tipos, textos, fechas
  es-CO y permisos; `httpClient`/`auth.api`/`AuthContext`; `/login` real con
  validacion, estados y redireccion por rol. Suite frontend: **39 tests en
  verde**. Contrato de auth verificado contra el backend real (login 200 +
  cookie HttpOnly SameSite=Lax, `/me` 200, logout 204, CORS con credenciales).
  Siguiente: T5 (AppShell, Sidebar, Topbar y PageHeader).

## Decisiones TSK-025

- Una BD y un esquema; `company_id` en `users`, `tickets` y `sla_policies`.
  `ticket_sla` y `ticket_comments` heredan la empresa via `ticket_id`.
- FK compuestas `(company_id, requester_id/assignee_id) -> users(company_id,id)`.
- Trigger al crear empresa: SLA 2h/4h/12h/24h. Email unico global; roles
  `cliente`, `tecnico`, `administrador`. Migraciones propias, sin ORM.

## Entorno local

- `.venv` en la raiz con `backend/requirements.txt`. Arranque del backend:
  `backend\dev_server.py` (crea admin/tecnico demo; contrasenas por entorno).
- `infra/.env` (ignorado) con `POSTGRES_PORT=55432`.
- Migraciones: `.venv\Scripts\python.exe backend\migrations\run.py` con
  `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.
- Tests de BD: mismo `DATABASE_URL`; se saltan si no hay PostgreSQL.
- Frontend: `cd frontend`, `npm install`, `npm run dev` en
  <http://localhost:5173>, API en `http://localhost:8000`.

## Errores que se deben evitar

- No usar el puerto 5432: hay un PostgreSQL nativo y las conexiones no llegan
  al contenedor de Docker.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`.
- No poner logica de negocio en los HTTP ni tocar tablas de otros modulos.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default al final.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string.
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.
- Vitest sin `globals`: registrar `cleanup()` de RTL en `tests/setup.ts`.
- Abrir el frontend en `localhost:5173`, no `127.0.0.1`, por la cookie.

## Proximos pasos

- HU-21 T5..T10: shell, routing/guards, drawer, marcadores, logout y cierre.
- HU-11 y HU-12: endpoints reales `GET /api/dashboard/tickets` y `/sla`.
- Integrar los modulos con PostgreSQL en una tarea aparte.
- PR de `feature/HU-21-frontend-shell` contra `develop`.
