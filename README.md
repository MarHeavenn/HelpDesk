# Help Desk SaaS

Sistema Help Desk SaaS para registrar, asignar y dar seguimiento a tickets de soporte, con control de identidad y roles.

El backend tiene implementadas las HU-01 a HU-04 (registro e inicio de sesión, tickets, prioridad/estado y asignación). El frontend (HU-21) ya tiene scaffold, pantalla de acceso real, capa de sesión, armazón compartido con navegación por rol y rutas protegidas con guards y 404; las vistas internas de las secciones aún son marcadores.

## Stack

- Frontend: React con TypeScript (Vite).
- Backend: FastAPI con Python 3.12.
- Base de datos: PostgreSQL prevista; actualmente la persistencia es en memoria.
- Infraestructura: `infra/docker-compose.yml` (esqueleto de PostgreSQL, todavía no conectado).

## Requisitos

- Python 3.12.
- Node.js 20 o superior y npm.
- Docker es opcional: la API actual no necesita PostgreSQL para funcionar.

## Ejecución local

### 1. Backend (terminal 1)

Desde la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe dev_server.py
```

Si el entorno ya está creado, basta con:

```powershell
cd backend
..\.venv\Scripts\python.exe dev_server.py
```

Para fijar las contraseñas demo:

```powershell
$env:DEV_ADMIN_PASSWORD = "Demo12345"
$env:DEV_TECH_PASSWORD = "Demo12345"
..\.venv\Scripts\python.exe dev_server.py
```

La API queda disponible en:

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### 2. Frontend (terminal 2)

Desde la raíz del repositorio:

```powershell
cd frontend
npm install
npm run dev
```

El frontend queda en <http://localhost:5173>. `npm` debe ejecutarse dentro de `frontend/`: si aparece `ENOENT ... package.json`, estás en la raíz del repo.

Abre `http://localhost:5173/login` e inicia sesión con una de las cuentas demo. El frontend consume la API en `http://localhost:8000` (configurable con `VITE_API_URL`). Usa `localhost`, no `127.0.0.1`, para que la cookie de sesión `SameSite=Lax` viaje a la API.

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

## Flujo de ramas y entrega

- `develop` es la rama de integración: cada historia sale de `develop` en una rama `feature/<HU>-<descripcion>` y se integra con un PR **contra `develop`**.
- `main` solo recibe versiones estables. No se abren PRs directos contra `main`.
- Cuando `develop` está validado, se promueve a `main` con un PR de release.

```powershell
git switch develop
git pull
git switch -c feature/HU-XX-descripcion
# ... cambios y pruebas ...
git add .
git commit -m "FEAT: descripcion breve (HU-XX)"
git push -u origin feature/HU-XX-descripcion
gh pr create --base develop --head feature/HU-XX-descripcion
```

## Pruebas

Backend (desde la raíz):

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/ -q
```

Frontend:

```powershell
cd frontend
npm run test
npm run build
npm run lint
```

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

## Estructura

- `backend/app/`: aplicación FastAPI. Módulos `identity`, `tickets`, `assignment` y `sla`, cada uno con capas `domain`, `application`, `infrastructure` e `interface`.
- `backend/dev_server.py`: arranque local con datos de demostración.
- `backend/tests/`: pruebas del backend con pytest.
- `frontend/`: aplicación React + TypeScript (Vite) de HU-21.
- `infra/docker-compose.yml`: esqueleto de PostgreSQL.
- `docs/constitution.md`: principios del proyecto.
- `specs/`: especificaciones, planes y tareas por historia de usuario.
- `MEMORY.md`: memoria viva del proyecto.

## Forma de trabajo

Flujo Spec-Driven Development: especificación → plan → tareas → implementación → verificación. Ver `AGENTS.md`.