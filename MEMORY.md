# Memoria del proyecto

## Estado actual

- HU-01..HU-04 completas en `develop`. Suite completa: **746 passed, 3 failed**.
  Los 3 fallos son previos a TSK-025: precedencia 401/404 con cookie invalida
  (dependencias actuales de `starlette`/`httpx`); no tocan la base de datos.
- `feature/localhost-setup` mergeada (PR #7). Rama actual `feature/DataBase`,
  creada desde `develop`: TSK-025 (PostgreSQL multitenant) implementada.
- TSK-025: 8 tablas, migraciones SQL idempotentes, capa de conexion y 14 tests
  de integracion en verde. PostgreSQL 16 en Docker, volumen `infra_pgdata`,
  puerto host **55432** porque el 5432 lo ocupa un PostgreSQL nativo.
- Modulos: `identity`, `tickets` (HU-02..HU-04) con persistencia en memoria;
  `assignment` y `sla` sin implementar. Frontend vacio. Los casos de uso aun
  no usan PostgreSQL (integracion pendiente, tarea aparte).

## Decisiones TSK-025

- Una BD y un esquema para todas las empresas; `company_id` en `users`,
  `tickets` y `sla_policies`. `ticket_sla` y `ticket_comments` heredan la
  empresa via `ticket_id`.
- FK compuestas `(company_id, requester_id/assignee_id) -> users(company_id,id)`:
  la BD impide mezclar empresas en creador o tecnico.
- Trigger al crear empresa: SLA 2h/4h/12h/24h (120/240/720/1440 min).
- Trigger en comentarios: autor y ticket de la misma empresa.
- Email unico global (el login actual no conoce la empresa). Roles:
  `cliente`, `tecnico`, `administrador`.
- Migraciones SQL propias (`migrations/run.py` + `schema_migrations`), sin ORM.
  Driver `psycopg[binary]==3.3.6`. `company_id` siempre sale de la sesion.

## Entorno local

- `.venv` en `backend/`; instalar `backend/requirements.txt`.
- `infra/.env` (ignorado por git) con `POSTGRES_PORT=55432`.
- Aplicar migraciones: `backend\.venv\Scripts\python.exe backend\migrations\run.py`
  con `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`.
- Tests de BD: mismo `DATABASE_URL`; se saltan si no hay PostgreSQL.

## Errores que se deben evitar

- No usar el puerto 5432 en esta maquina: hay un PostgreSQL nativo y las
  conexiones no llegan al contenedor de Docker.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`.
- No poner logica de negocio en los HTTP ni tocar tablas de otros modulos.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default al final.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string.
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.

## Proximos pasos

- PR de `feature/DataBase` contra `develop` (nunca contra `main`).
- Integrar los modulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos por dependencias actuales.
- Frontend pendiente; HU-05 (SLA) descartada por el usuario.
