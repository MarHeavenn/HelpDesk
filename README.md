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

`dev_server.py` crea automáticamente un administrador, un técnico y un cliente de demostración:

| Rol | Correo |
| --- | --- |
| Administrador | `admin@helpdesk.dev` |
| Técnico | `tecnico@helpdesk.dev` |
| Cliente | `cliente@helpdesk.dev` |

Si no se define una contraseña, se genera una aleatoria y se muestra en la consola al arrancar. Se puede fijar con variables de entorno:

Si una cuenta demo ya existe en PostgreSQL, se reutiliza sin cambiar su contraseña. En ese caso, si la contraseña indicada no coincide, la consola avisa de que debe usarse la contraseña anterior.

```powershell
$env:DEV_ADMIN_PASSWORD = "una-clave-local"
$env:DEV_TECH_PASSWORD = "otra-clave-local"
$env:DEV_CLIENT_PASSWORD = "clave-local-cliente"
..\.venv\Scripts\python.exe dev_server.py
```

Variables disponibles: `HOST`, `PORT`, y `DEV_ADMIN_*`, `DEV_TECH_*`, `DEV_CLIENT_*` para `NAME`, `EMAIL` y `PASSWORD`.

No se deben guardar contraseñas reales en el repositorio.

### Ver alertas de SLA

1. Inicia el backend con `dev_server.py` y el frontend con `npm run dev` como se indica arriba. Usa el Python del entorno virtual disponible (por ejemplo, `backend\.venv\Scripts\python.exe` desde la raíz).
2. Abre <http://localhost:5173/login> e inicia sesión como administrador o técnico con la contraseña configurada o impresa al arrancar.
3. Abre la campana o la página **Notificaciones**. La semilla incluye un ticket próximo al vencimiento y otro vencido; verás alertas del sistema para los responsables. El ticket próximo a vencer pasa a incumplido con el tiempo.
4. Repite la consulta: no se generan duplicados para el mismo destinatario, tipo y vencimiento. Puedes marcar tus avisos como leídos.

La generación ocurre al consultar notificaciones y el frontend actualiza mediante sondeo cada 30 segundos. En modo memoria los datos se pierden al detener el backend.

### Smoke manual de tickets

`backend/smoke_manual.py` recorre los flujos de las tres cuentas contra la API real: arranca `uvicorn` en un puerto libre, siembra un administrador y dos técnicos en memoria y verifica el alta, los listados, la prioridad, el estado, la asignación, los comentarios, el cierre, la reapertura y los permisos por rol. No usa mocks ni `TestClient`.

```powershell
cd backend
..\.venv\Scripts\python.exe smoke_manual.py
```

Cada comprobación se imprime como `OK`; el proceso termina con código 0 si todo pasa y 1 si algo falla. Los datos viven en memoria y desaparecen al terminar. Variables opcionales: `SMOKE_HOST` y `SMOKE_PORT`.

> **Persistencia en memoria:** al detener el servidor se pierden los tickets y los usuarios registrados. Los usuarios demo se recrean en cada arranque. PostgreSQL todavía no está conectado.

### Semilla del administrador de plataforma

La cuenta con rol `administrador` y sin empresa —la que gestiona el catálogo completo de empresas clientes— no se crea desde la interfaz ni desde la API: se aprovisiona con una semilla idempotente que se ejecuta fuera de la aplicación (RO-01). Requiere las migraciones aplicadas y no guarda credenciales en el repositorio.

```powershell
cd backend
$env:PLATFORM_ADMIN_EMAIL = "plataforma@example.com"
$env:PLATFORM_ADMIN_NAME = "Administración de plataforma"
$env:PLATFORM_ADMIN_PASSWORD = "una-clave-de-operacion"
..\.venv\Scripts\python.exe scripts\seed_platform_admin.py
```

- Ejecutarla dos veces no crea cuentas adicionales ni cambia datos existentes.
- Con la cuenta ya `active` y aceptada no hace nada; si está `deactivated` la reactiva conservando el hash.
- Con la cuenta pendiente de invitación, con otro rol o con empresa falla sin modificarla e informa del motivo.
- `PLATFORM_ADMIN_NAME` y `PLATFORM_ADMIN_PASSWORD` solo son obligatorias cuando hay que crear la cuenta; el correo lo es siempre. La contraseña se guarda únicamente como hash Argon2id.
- La salida nunca muestra la contraseña, el hash, el token ni el enlace de invitación. Termina con código 0 si tiene éxito y 1 si falla.

### Entrega de correo de invitaciones (requisito de operación)

La entrega de las invitaciones (alta con administrador inicial, invitación o reenvío del administrador de empresa y operaciones de invitación de HU-13) necesita un servicio de correo configurado fuera de la aplicación (RO-02). Variables opcionales:

| Variable | Uso |
| --- | --- |
| `SMTP_HOST` | Servidor SMTP. Sin él no se intenta el envío. |
| `SMTP_PORT` | Puerto (por defecto `587`). |
| `SMTP_USE_TLS` | `true` (por defecto) para STARTTLS. |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Credenciales si el servidor las exige. |
| `SMTP_FROM` | Remitente (por defecto `no-reply@helpdesk.local`). |
| `INVITATION_BASE_URL` | Base del enlace de aceptación (por defecto `http://localhost:5173`). |

Sin `SMTP_HOST` la cuenta y la invitación se crean o rotan igual, el código de éxito no cambia y la respuesta informa `email_status: "not-attempted"`; el acceso no se habilita hasta aceptar la invitación y se reintenta con la misma operación cuando el servicio esté configurado. Si la entrega falla se informa `email_status: "failed"` y la cuenta permanece `active`/`pending`. El token y el enlace solo viajan en el correo entregado: nunca aparecen en una respuesta HTTP, en la interfaz ni en la salida de los scripts.

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
