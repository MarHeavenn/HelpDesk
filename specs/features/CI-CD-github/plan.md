# Plan CI/CD — GitHub Actions + GHCR + VPS

Spec base: `specs/features/CI-CD-github/spec.md` (RF-CD-1 a RF-CD-6).

## Estructura

| Archivo | Función | RF |
|---|---|---|
| `.github/workflows/ci.yml` | Quality gates y publicación en GHCR | RF-CD-1, RF-CD-2, RF-CD-6 |
| `.github/workflows/deploy.yml` | Deploy por `workflow_run` sobre `production` | RF-CD-3 |
| `deploy/compose.production.yml` | Compose de producción basado en `image:` | RF-CD-4 |
| `backend/.dockerignore`, `frontend/.dockerignore` | Contextos de build limpios | RF-CD-1 |
| `docs/ci-cd.md` | Guía de VPS, secretos, verificación y rollback | RF-CD-5 |
| `README.md` | Enlace a la guía | RF-CD-5 |

## Diseño del workflow de CI

- `quality-backend`: checkout, `setup-python@v7` (3.12, caché pip),
  `pip install -r backend/requirements.txt`, `pytest -q` con
  `HELPDESK_ALLOW_IN_MEMORY=1` y `docker build` del contexto `backend`.
- `quality-frontend`: checkout, `setup-node@v7` (Node 22, caché npm),
  `npm ci`, `npm run lint --if-present`, `npm run test --if-present`,
  `npm run build` y `docker build` del contexto `frontend` con
  `VITE_API_URL` por variable.
- `publish`: solo en push a `main`, después de ambos jobs, con
  `packages: write`; normaliza el nombre del repositorio a minúsculas,
  usa `docker/setup-buildx-action@v4`, `docker/login-action@v4` y
  `docker/build-push-action@v7` para publicar dos paquetes con tags
  `sha-${{ github.sha }}` y `latest`.

## Diseño del workflow de Deploy

- `on.workflow_run` de `CI`, con `if` que exige éxito y `head_branch == main`.
- `concurrency.group: production`, sin cancelación de despliegues en curso.
- Sin checkout: configura `~/.ssh` desde secretos del environment y ejecuta por
  SSH `docker compose pull`, `up -d --remove-orphans` y `ps` en `/opt/helpdesk`.
- Paso opcional de health con `vars.HEALTH_URL`.

## Estrategia de verificación

- Validar sintaxis YAML localmente antes de subir.
- Comprobar que los comandos de CI ya pasan en local (verificado en HU-26).
- La ejecución real solo puede observarse en GitHub tras el push: runs, checks,
  paquetes GHCR y deployments. No se afirmará que ocurrió sin evidencia.

## Riesgos

- Permisos de Actions o packages restringidos por política de la organización:
  documentar y no intentar evadirlos.
- GHCR privado: el VPS necesita un PAT con `read:packages`; se documenta sin
  guardarlo en el repositorio.
- Imagen frontend con `VITE_API_URL` equivocada: variable de repositorio y
  documentación del valor público.
