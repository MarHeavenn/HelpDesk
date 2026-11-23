# Spec CI/CD — Integración y despliegue continuos en GitHub

Estado: aprobada

## Contexto y objetivo

El repositorio ya tiene calidad verificable en local (pytest, Vitest, lint,
build) y dos imágenes Docker (`backend/Dockerfile` y `frontend/Dockerfile`), pero
no hay automatización en GitHub. Los ejercicios `Ejercicio_CI.pdf` y
`Ejercicio_CD.pdf` de la carpeta `Proceso` piden: quality gates en GitHub
Actions, publicación de imágenes en GHCR y despliegue en un VPS mediante
`workflow_run` + SSH, con un compose de producción basado en `image:`.

Esta historia configura ese pipeline sin cambiar la funcionalidad del MVP.
Los secretos del VPS y las credenciales de runtime quedan fuera del repositorio.

## Decisiones aprobadas

- CI se ejecuta en PRs y pushes a `develop` y `main` (los PRs del proyecto van a
  `develop`); la publicación a GHCR solo ocurre en push a `main`.
- Se publican **dos paquetes**: `ghcr.io/<owner>/helpdesk-backend` y
  `ghcr.io/<owner>/helpdesk-frontend`, con tags `sha-<commit>` y `latest`.
- Se preparan el workflow de Deploy, el compose de producción y la guía; la
  configuración de secretos/environment y el VPS los hace el usuario.

## Requisitos funcionales

- RF-CD-1: EL WORKFLOW `CI` ejecutará, en PRs y pushes a `develop`/`main`, un job
  de calidad del backend (pytest con el seam en memoria) y otro del frontend
  (`npm ci`, lint, test y build), y verificará que ambas imágenes Docker se
  construyen.
- RF-CD-2: CUANDO se haga un push a `main` y los jobs de calidad terminen
  correctamente, EL WORKFLOW publicará las dos imágenes en GHCR con `packages:
  write`, usando el SHA completo del commit para el tag y `latest`.
- RF-CD-3: EL WORKFLOW `Deploy` se disparará por `workflow_run` de `CI`,
  comprobará `conclusion == success` y `head_branch == main`, y usará el
  environment `production` para actualizar el compose en el VPS con el tag
  `sha-<head_sha>`.
- RF-CD-4: EL COMPOSE de producción consumirá imágenes por `image:` (nunca
  `build:`), recibirá `IMAGE_TAG` por entorno y mantendrá secretos y
  configuración de runtime en el `.env` del VPS.
- RF-CD-5: LA DOCUMENTACIÓN cubrirá preparación del VPS, clave SSH dedicada,
  `known_hosts`, environment y secretos de GitHub, verificación manual previa,
  health check, rollback y evidencia a registrar.
- RF-CD-6: No se guardarán claves, tokens ni contraseñas en el repositorio; el
  valor público `VITE_API_URL` se pasará como variable de repositorio al build
  del frontend.

## Criterios de finalización

- Workflows y compose con sintaxis válida, versiones de acciones existentes y
  sin secretos embebidos.
- Guía de operación y README actualizados.
- Evidencia de ejecución en GitHub (runs, checks, paquetes y deployment) que el
  usuario debe completar al hacer push; no se afirmará que CI/CD ya corrió si no
  se observó.

## Validación local (2026-11-23)

| RF | Comprobación | Resultado |
|---|---|---|
| RF-CD-1 | `ci.yml` con jobs de backend/frontend en PR y push a `develop`/`main`; comandos equivalentes ejecutados en local en HU-26 | PASADO (definición); ejecución en GitHub pendiente |
| RF-CD-2 | Job `publish` condicionado a push `main`, `packages: write`, dos `build-push-action` con tags `sha-`/`latest` | PASADO (definición) |
| RF-CD-3 | `deploy.yml` con `workflow_run`, `if` de éxito en `main`, `environment: production`, SSH y `IMAGE_TAG=sha-<head_sha>` | PASADO (definición) |
| RF-CD-4 | `deploy/compose.production.yml` solo usa `image:` con `${IMAGE_TAG}`; secretos en `.env` del VPS | PASADO |
| RF-CD-5 | `docs/ci-cd.md` + sección en `README.md` | PASADO |
| RF-CD-6 | Sin secretos en el repo; `VITE_API_URL` como variable pública; `HEALTH_URL` opcional | PASADO |

Las versiones de acciones se verificaron contra la API de GitHub: checkout,
setup-node y setup-python `v7`; `docker/setup-buildx-action@v4`,
`docker/login-action@v4` y `docker/build-push-action@v7`.

Los cuatro archivos YAML se validaron con `yaml.safe_load` sin errores.

**Evidencia en GitHub:** PR #29 (`feature/CI-CD-github` → `develop`) disparó el
run de CI `45263461824` (https://github.com/MarHeavenn/HelpDesk/actions/runs/45263461824).
En la consulta inicial ambos jobs estaban `in_progress`; los pasos de checkout y
setup de Python/Node ya habían terminado `success`, lo que confirma que el YAML y
las versiones de acciones son válidos. El resultado final debe verificarse en
Actions antes de dar por cerrada la historia.

**Veredicto: infraestructura lista y CI ejecutándose en GitHub; publicación y
Deploy pendientes de push a `main` y de la configuración del VPS/environment por
parte del usuario.**
