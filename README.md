# Help Desk SaaS — DeskHelp

Sistema Help Desk para registrar, asignar y dar seguimiento a tickets con control
de identidad, roles, SLA, notificaciones y empresas.

Estado: MVP integral. Backend y frontend consumen contratos HTTP reales; la
persistencia es PostgreSQL. Esta entrega incluye el entorno local reproducible
(HU-26) y la validación del flujo completo.

## Stack

- Frontend: React + TypeScript (Vite), servido por nginx en el entorno local.
- Backend: FastAPI + Python 3.12, uvicorn.
- Base de datos: PostgreSQL 16 en contenedor.
- Infraestructura: `infra/docker-compose.yml` (PostgreSQL + API + frontend).

## Arranque rápido con Docker (recomendado)

Requiere Docker con daemon en ejecución y `docker-compose` v1 o `docker compose` v2.

```powershell
# 1. Configuración (sin secretos en el repositorio)
Copy-Item .env.example infra\.env
# Edita infra/.env y define POSTGRES_PASSWORD y las contraseñas demo.

# 2. Arrancar los tres servicios
docker-compose -f infra\docker-compose.yml up --build -d

# 3. Comprobar estado
docker-compose -f infra\docker-compose.yml ps
```

Con `docker compose` v2, sustituye `docker-compose` por `docker compose`.

URLs de la demostración:

| Servicio | URL |
| --- | --- |
| Frontend | <http://localhost:8080> |
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Health | <http://localhost:8000/health> |

El compose aplica las migraciones antes de sembrar las cuentas demo. PostgreSQL
expone el puerto `55432` para no colisionar con otros servicios; internamente el
backend conecta por `5432` al host `db`. Los datos persisten en el volumen
`pgdata`. Para reiniciar desde cero: `docker-compose -f infra\docker-compose.yml
down -v` (borra la base de datos).

### Cuentas de demostración

| Rol | Correo |
| --- | --- |
| Administrador | `admin@helpdesk.dev` |
| Técnico | `tecnico@helpdesk.dev` |
| Cliente | `cliente@helpdesk.dev` |

Las contraseñas se toman de `DEV_ADMIN_PASSWORD`, `DEV_TECH_PASSWORD` y
`DEV_CLIENT_PASSWORD` en `infra/.env`. Si se dejan vacías, el backend genera una
aleatoria y la imprime en consola. No hay credenciales de producción en el repo.

### Configuración

| Variable | Uso |
| --- | --- |
| `POSTGRES_PASSWORD` | Contraseña de la base de datos (obligatoria). |
| `POSTGRES_USER` / `POSTGRES_DB` | Usuario y base (por defecto `helpdesk`). |
| `POSTGRES_PORT` | Puerto host de PostgreSQL (por defecto `55432`). |
| `BACKEND_PORT` / `FRONTEND_PORT` | Puertos publicados (`8000` / `8080`). |
| `DEV_*_PASSWORD` | Contraseñas de las cuentas demo. |
| `FRONTEND_ORIGINS` | Orígenes CORS; el compose fija `http://localhost:8080`. |
| `VITE_API_URL` | URL de la API inyectada al build del frontend. |

El frontend y la API comparten el host `localhost`, por lo que la cookie
`SameSite=Lax` funciona sin configuración adicional. Si se cambia el dominio,
hay que ajustar `FRONTEND_ORIGINS`, `VITE_API_URL` y la política de cookies.

### Entrega de correo de invitaciones (RO-02)

Sin `SMTP_HOST`, las invitaciones se crean y rotan igual; la respuesta informa
`email_status: "not-attempted"` y el acceso no se habilita hasta aceptar el
token. Variables opcionales: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`,
`SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` e `INVITATION_BASE_URL`. El token y
el enlace nunca aparecen en respuestas HTTP, en la interfaz ni en la salida de
los scripts.

## Arranque local sin Docker

Terminal 1 (backend):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd backend
$env:DATABASE_URL="postgresql://helpdesk:PASSWORD@127.0.0.1:55432/helpdesk"
..\.venv\Scripts\python.exe dev_server.py
```

Terminal 2 (frontend):

```powershell
cd frontend
npm install
$env:VITE_API_URL="http://localhost:8000"
npm run dev
```

Abre <http://localhost:5173/login>. Usa `localhost`, no `127.0.0.1`, para que la
cookie viaje a la API. `start-dev.cmd` levanta ambos procesos en memoria sin
PostgreSQL; es útil solo para desarrollo rápido.

## Casos de prueba funcionales (HU-26)

| ID | Rol | Acción | Resultado esperado |
| --- | --- | --- | --- |
| CP-01 | Cliente | Login y alta de ticket | 201, `Abierto`, sin técnico |
| CP-02 | Cliente | Ver «Mis tickets» y detalle propio | Solo sus tickets, sin edición |
| CP-03 | Admin | Dashboard y asignación | Métricas reales; técnico visible |
| CP-04 | Técnico | Prioridad y paso a `En progreso` | 200, SLA recalculado |
| CP-05 | Técnico | Comentario | 201, visible en seguimiento |
| CP-06 | Técnico | Resolver | 200, `Resuelto` con `resolved_at` |
| CP-07 | Admin | Cerrar | 200, `Cerrado`, SLA congelado |
| CP-08 | Admin | Modificar ticket cerrado | 409, sin cambios |
| CP-09 | Admin | Empresas: alta, estado y administrador | Catálogo real, sin secretos |
| CP-10 | Admin | Usuarios: consulta, rol y estado | Roles aplicados, último admin protegido |
| CP-11 | Técnico | Campana y `/notificaciones` | Avisos visibles y lectura |
| CP-12 | Admin | Panel de alertas y cumplimiento SLA | Cifras reales, sin «Demo» |
| CP-13 | Público | Abrir <http://localhost:8080> | Login accesible y API conectada |
| CP-14 | Equipo | `docker-compose up --build` desde copia limpia | Servicios sanos y migraciones aplicadas |
| CP-15 | Equipo | Suites, lint y build | Verde o bloqueo documentado |
| CP-16 | Equipo | Repetir CP-01..CP-13 en el entorno levantado | Evidencia registrada |

El detalle de cada caso, su RF y la evidencia están en
`specs/features/HU-26-mvp-validation/`.

## Pruebas automatizadas

```powershell
# Backend (desde la raíz)
.\.venv\Scripts\python.exe -m pytest backend\tests\ -q

# Frontend
cd frontend
npm run test
npm run lint
npm run build

# Smoke de API real con uvicorn (sin mocks)
cd backend
# Sin PostgreSQL, habilita el seam de memoria:
$env:HELPDESK_ALLOW_IN_MEMORY = "1"
..\.venv\Scripts\python.exe smoke_manual.py
```

Si hay PostgreSQL configurado con `DATABASE_URL`, el smoke usa esa base y no
necesita la variable `HELPDESK_ALLOW_IN_MEMORY`.

No se declara una prueba como superada sin evidencia de su ejecución.

## CI/CD

GitHub Actions ejecuta calidad (backend y frontend) en PRs/pushes a `develop` y
`main`, publica dos imágenes en GHCR al hacer push a `main` y despliega en
**Render** mediante `workflow_run` + Deploy Hooks. `render.yaml` crea el Web
Service, el Static Site y PostgreSQL en plan gratuito (demo de hasta 20 días).
La configuración de variables, secretos, health y rollback está en
[`docs/ci-cd.md`](docs/ci-cd.md).

## Limitaciones conocidas

- El entorno de demostración es **local**: no hay despliegue en nube ni servidor
  académico. La URL `http://localhost:8080` es accesible desde la máquina donde
  se ejecuta Docker.
- Sin SMTP configurado, las invitaciones no llegan por correo (RO-02).
- En el equipo donde se preparó esta entrega había CLI de Docker pero **sin
  daemon y sin compose v2**; la sintaxis del compose se validó con
  `docker-compose config -q`, pero no se pudo ejecutar CP-13/CP-14/CP-16. Ver
  `MEMORY.md` antes de afirmar el arranque.

## Flujo de ramas y entrega

- `develop` es la rama de integración; cada historia sale de `develop` como
  `feature/<HU>-<descripcion>` y se integra con PR **contra `develop`**.
- `main` solo recibe versiones estables; nunca se abre un PR directo contra `main`.

## Estructura

- `backend/app/`: FastAPI con módulos `identity`, `tickets`, `assignment`, `sla` y
  `companies`, cada uno con capas `domain`, `application`, `infrastructure` e
  `interface`.
- `backend/Dockerfile` y `frontend/Dockerfile`: imágenes del MVP.
- `infra/docker-compose.yml`: PostgreSQL + API + frontend.
- `frontend/`: SPA React + TypeScript.
- `specs/`: especificaciones, planes y tareas por historia.
- `MEMORY.md`: memoria viva del proyecto.

## Forma de trabajo

Flujo Spec-Driven Development: especificación → plan → tareas → implementación →
verificación. Ver `AGENTS.md` y `docs/constitution.md`.
