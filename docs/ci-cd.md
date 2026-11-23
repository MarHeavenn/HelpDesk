# CI/CD en GitHub + despliegue en Render

Basado en los ejercicios `Ejercicio_CI.pdf` y `Ejercicio_CD.pdf` de la carpeta
`Proceso`. La diferencia es el destino del CD: **no hay VPS**; todo se despliega
en el plan gratuito de Render, pensado para una demo de **20 días como máximo**.

## Archivos

| Archivo | Función |
|---|---|
| `.github/workflows/ci.yml` | Quality gates y publicación en GHCR |
| `.github/workflows/deploy.yml` | Despliegue en Render tras CI exitosa en `main` |
| `render.yaml` | Blueprint: Web Service + Static Site + Postgres (plan `free`) |
| `backend/.dockerignore`, `frontend/.dockerignore` | Contextos de build limpios |

## 1. CI (sin cambios)

Se dispara en PRs y pushes a `develop` y `main`:
- **Backend quality gates**: Python 3.12, pytest con `HELPDESK_ALLOW_IN_MEMORY=1` y `docker build`.
- **Frontend quality gates**: Node 22, `npm ci`, lint, test, build y `docker build`.
- **Publish Docker images**: solo en push a `main`; publica `helpdesk-backend` y
  `helpdesk-frontend` con tags `sha-<commit>` y `latest`. En un PR aparece como
  *skipped*: es correcto, el PR solo valida.

Run verificado: `45263461824` → `success` (backend y frontend en verde).

Variable de repositorio pública `VITE_API_URL`: se usa en el build de la imagen
del frontend; para la demo conviene fijarla a `https://helpdesk-api.onrender.com`.

## 2. Qué crea el Blueprint

`render.yaml` define tres recursos, todos en plan `free`:

| Recurso | Nombre | Configuración |
|---|---|---|
| Web Service (Python) | `helpdesk-api` | `rootDir: backend`, aplica migraciones y arranca `dev_server.py`, `/health` |
| Static Site | `helpdesk-web` | compila `frontend/` y publica `frontend/dist` |
| Postgres | `helpdesk-db` | plan `free`, `DATABASE_URL` inyectada al API |

`autoDeployTrigger: 'off'`: Render **no** despliega solo con cada commit; lo hace
el workflow de GitHub mediante *Deploy Hooks*. Así el despliegue sigue ocurriendo
solo después de que CI esté en verde en `main`.

### Variables a configurar en el dashboard de Render

El Blueprint marca varias variables con `sync: false` (no se guardan en Git):

| Variable | Dónde | Valor |
|---|---|---|
| `FRONTEND_ORIGINS` | `helpdesk-api` | `https://helpdesk-web.onrender.com` (o tu dominio) |
| `DEV_ADMIN_PASSWORD` | `helpdesk-api` | Contraseña demo del administrador |
| `DEV_TECH_PASSWORD` | `helpdesk-api` | Contraseña demo del técnico |
| `DEV_CLIENT_PASSWORD` | `helpdesk-api` | Contraseña demo del cliente |

Si no defines las contraseñas demo, `dev_server.py` genera unas aleatorias y las
imprime en los logs; la cuenta se reutiliza en arranques posteriores.

El backend ya soporta `SESSION_COOKIE_SECURE=true` y `SameSite=lax`. Como ambos
servicios están bajo `*.onrender.com` son el **mismo sitio**, así que la cookie
viaja sin pasar a `SameSite=None`. Si usas dominios distintos (ej. un dominio
propio para el frontend), cambia `SESSION_COOKIE_SAMESITE=None` y mantén
`SESSION_COOKIE_SECURE=true`.

## 3. Preparar Render en 5 pasos

1. Crear cuenta en Render (plan Hobby, $0).
2. **New → Blueprint** → conectar el repositorio de GitHub → rama `main` → dar
   nombre al Blueprint. Render crea los tres recursos.
3. En `helpdesk-api`, completar las variables `sync: false` indicadas arriba.
4. En cada servicio, abrir **Settings → Deploy Hook** y copiar su URL.
5. En GitHub, crear el environment `production` y guardar esas URLs como
   *environment secrets*:
   - `RENDER_API_DEPLOY_HOOK`
   - `RENDER_WEB_DEPLOY_HOOK`
   
   Variable de repositorio opcional: `HEALTH_URL` =
   `https://helpdesk-api.onrender.com/health`.

## 4. Flujo de despliegue

Push a `main` → CI en verde → el workflow `Deploy` (por `workflow_run`) llama a
los dos Deploy Hooks con `curl --fail` → Render reconstruye y publica → el paso
opcional `Verify health` consulta `HEALTH_URL` con reintentos.

El Web Service gratuito **duerme tras 15 minutos** y tarda ~1 min en despertar;
por eso el health check usa reintentos. Calienta la API antes de la demo.

## 5. Límites de la capa gratuita (importante para los 20 días)

Verificado en la documentación de Render (2026):

- Static sites: gratis, CDN, sin límite de tiempo.
- Web Service free: 750 horas/mes, 512 MB, duerme a los 15 min de inactividad.
- Postgres free: **1 GB, expira 30 días después de crearse**, con 14 días de
  gracia antes de borrarse; sin backups.

Con 20 días de ventana, crea el Blueprint **al empezar esa ventana** y la BD
seguirá viva. Si la demo se alarga, el paso de pago es ~$6/mes de BD y ~$7/mes
de Web Service.

## 6. Verificación y rollback

Antes de dar por buena la demo:
- `curl https://helpdesk-api.onrender.com/health` → 200.
- Login con las tres cuentas y recorrido CP-01..CP-12 del README.
- En Render → cada servicio → **Events/Logs** para confirmar qué commit se desplegó.

Rollback: en el servicio de Render, abrir un deploy anterior y pulsar
**Redeploy**. No hace falta recompilar ni tocar GHCR.

Evidencia a registrar: commit SHA, run de CI, run de Deploy, URL de los tres
servicios y resultado del health.

## 7. Regla de protección (opcional)

Tras el primer check verde: `Settings → Rulesets → New branch ruleset → main →
Require status checks` con `Backend quality gates` y `Frontend quality gates`.

## Limitación actual

El Blueprint y los workflows están listos y validados localmente (el YAML de
Render pasó el JSON Schema oficial), pero **la cuenta de Render y los secretos
los configura el usuario**. No se afirma que el MVP esté desplegado hasta ver
los tres servicios en el dashboard y el health en 200.
