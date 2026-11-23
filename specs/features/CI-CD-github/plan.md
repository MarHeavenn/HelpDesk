# Plan CI/CD — GitHub Actions + GHCR + Render

Spec base: `specs/features/CI-CD-github/spec.md` (RF-CD-1 a RF-CD-6).

## Arquitectura de despliegue

| Recurso | Tipo Render | Plan | Función |
|---|---|---|---|
| `helpdesk-api` | Web Service (Python) | free | Migraciones + semilla + uvicorn en `/health` |
| `helpdesk-web` | Static Site | free | SPA compilada desde `frontend/` |
| `helpdesk-db` | Postgres | free | Persistencia (1 GB, 30 días) |

`render.yaml` usa `autoDeployTrigger: 'off'` en ambos servicios: el despliegue lo
dispara GitHub Actions mediante Deploy Hooks. Se retiró el compose de VPS.

## Flujo

1. Push a `main` → CI (calidad + publicación GHCR).
2. Al terminar CI con éxito, `workflow_run` → `Deploy` → `curl -X POST` a los
   Deploy Hooks de `helpdesk-api` y `helpdesk-web`.
3. Health opcional con reintentos (el Web Service free duerme tras 15 min).

## Variables

- En Render (dashboard, `sync: false`): `FRONTEND_ORIGINS` y `DEV_*_PASSWORD`.
- En GitHub (environment `production`): `RENDER_API_DEPLOY_HOOK`,
  `RENDER_WEB_DEPLOY_HOOK`.
- Variables públicas de repo: `VITE_API_URL`, `HEALTH_URL`.

## Verificación

- CI verificada en GitHub (run `45263461824`, success).
- `render.yaml` validado con el JSON Schema oficial de Render.
- YAML de workflows validado con `yaml.safe_load`.
- Sin secretos en el repositorio.

## Riesgos mitigados

- BD free expira a los 30 días → ventana de demo de 20 días y aviso en la guía.
- Cold start del Web Service free → health con reintentos y calentamiento previo.
- Cookies entre servicios → mismo sitio `*.onrender.com`, `SameSite=lax` y
  `Secure=true`; si se usan dominios distintos, documentado `SameSite=None`.
