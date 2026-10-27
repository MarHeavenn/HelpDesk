# Help Desk SaaS

Sistema Help Desk SaaS para registrar, asignar y dar seguimiento a tickets de soporte, con control de identidad y roles.

El backend tiene implementadas las HU-01 a HU-04 (registro e inicio de sesión, tickets, prioridad/estado y asignación). El frontend todavía está pendiente: `frontend/` solo contiene la estructura reservada.

## Stack

- Frontend: React con TypeScript (aún sin aplicación).
- Backend: FastAPI con Python 3.12.
- Base de datos: PostgreSQL prevista; actualmente la persistencia es en memoria.
- Infraestructura: `infra/docker-compose.yml` (esqueleto de PostgreSQL, todavía no conectado).

## Requisitos

- Python 3.12.
- Docker es opcional: la API actual no necesita PostgreSQL para funcionar.

## Ejecución local del backend

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe dev_server.py
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
../.venv/bin/python dev_server.py
```

La API queda disponible en:

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>
- Health check: <http://127.0.0.1:8000/health>

### Usuarios de desarrollo

`dev_server.py` crea automáticamente un administrador y un técnico, porque no existe un endpoint público para esos roles:

| Rol | Correo |
| --- | --- |
| Administrador | `admin@helpdesk.dev` |
| Técnico | `tecnico@helpdesk.dev` |

Si no se define una contraseña, se genera una aleatoria y se muestra en la consola al arrancar. Se puede fijar con variables de entorno:

```powershell
$env:DEV_ADMIN_PASSWORD = "una-clave-local"
$env:DEV_TECH_PASSWORD = "otra-clave-local"
..\.venv\Scripts\python.exe dev_server.py
```

Variables disponibles: `HOST`, `PORT`, `DEV_ADMIN_NAME`, `DEV_ADMIN_EMAIL`, `DEV_ADMIN_PASSWORD`, `DEV_TECH_NAME`, `DEV_TECH_EMAIL`, `DEV_TECH_PASSWORD`.

No se deben guardar contraseñas reales en el repositorio.

> **Persistencia en memoria:** al detener el servidor se pierden los tickets y los usuarios registrados. Los usuarios demo se recrean en cada arranque. PostgreSQL todavía no está conectado.

## Endpoints implementados

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/health` | Público |
| `POST` | `/api/auth/register` | Público (crea clientes) |
| `POST` | `/api/auth/login` | Público |
| `GET` | `/api/auth/me` | Sesión |
| `POST` | `/api/auth/logout` | Sin sesión obligatoria (idempotente) |
| `GET` | `/api/technicians` | Administrador |
| `POST` | `/api/tickets` | Sesión |
| `GET` | `/api/tickets` | Sesión (tickets propios) |
| `GET` | `/api/tickets/{id}` | Sesión (ticket propio) |
| `PUT` | `/api/tickets/{id}/priority` | Administrador y técnico |
| `PUT` | `/api/tickets/{id}/status` | Administrador y técnico |
| `PUT` | `/api/tickets/{id}/assignee` | Administrador |
| `GET` | `/api/assignments/mine` | Sesión |

El detalle de contratos y códigos de respuesta está en Swagger y en las especificaciones de `specs/features/`.

## Pruebas

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/ -q
```

## Estructura

- `backend/app/`: aplicación FastAPI. Módulos `identity`, `tickets`, `assignment` y `sla`, cada uno con capas `domain`, `application`, `infrastructure` e `interface`.
- `backend/dev_server.py`: arranque local con datos de demostración.
- `backend/tests/`: pruebas del backend con pytest.
- `frontend/`: estructura reservada para React + TypeScript.
- `infra/docker-compose.yml`: esqueleto de PostgreSQL.
- `docs/constitution.md`: principios del proyecto.
- `specs/`: especificaciones, planes y tareas por historia de usuario.
- `MEMORY.md`: memoria viva del proyecto.

## Forma de trabajo

Flujo Spec-Driven Development: especificación → plan → tareas → implementación → verificación. Ver `AGENTS.md`.
