# CI/CD en GitHub (HelpDesk)

Basado en los ejercicios `Ejercicio_CI.pdf` y `Ejercicio_CD.pdf` de la carpeta
`Proceso`. No añade funcionalidad al MVP: automatiza lo que ya se ejecuta en
local.

## Archivos

| Archivo | Función |
|---|---|
| `.github/workflows/ci.yml` | Quality gates de backend y frontend + publicación en GHCR |
| `.github/workflows/deploy.yml` | Despliegue en el VPS tras CI exitosa en `main` |
| `deploy/compose.production.yml` | Compose de producción (solo `image:`) |
| `backend/.dockerignore`, `frontend/.dockerignore` | Contextos de build limpios |

## 1. CI

Se dispara en **pull requests y pushes a `develop` y `main`** (el proyecto abre
PRs contra `develop`). Jobs:

- **Backend quality gates**: Python 3.12, `pip install -r requirements.txt`,
  `pytest -q` con `HELPDESK_ALLOW_IN_MEMORY=1` y `docker build` del contexto
  `backend/`.
- **Frontend quality gates**: Node 22, `npm ci`, `npm run lint`,
  `npm run test`, `npm run build` y `docker build` del contexto `frontend/`.
- **Publish Docker images**: solo en **push a `main`** y tras los dos jobs
  anteriores. Publica en GHCR con `packages: write`.

Los nombres de los checks que aparecerán en los PRs son los de los jobs:
`Backend quality gates`, `Frontend quality gates` y `Publish Docker images`.

### Imágenes publicadas

```
ghcr.io/<owner>/helpdesk-backend:sha-<commit>
ghcr.io/<owner>/helpdesk-backend:latest
ghcr.io/<owner>/helpdesk-frontend:sha-<commit>
ghcr.io/<owner>/helpdesk-frontend:latest
```

`<owner>` se deriva de `GITHUB_REPOSITORY` en minúsculas (para este repo,
`MarHeavenn`). El tag `sha-<commit>` usa el SHA completo; el CD usa el mismo SHA
del `workflow_run` para desplegar esa versión exacta.

### Variables de repositorio (no secretos)

- `VITE_API_URL`: URL pública de la API que se **incorpora al bundle** del
  frontend en tiempo de build. Ejemplo: `http://<host-del-vps>:8000`. Si no se
  define, CI usa `http://localhost:8000`.
- `HEALTH_URL` (opcional): URL que el job de Deploy consulta con `curl --fail`
  después de levantar los contenedores. Ejemplo: `http://<host>:8000/health`.

Ruta: `Settings → Secrets and variables → Actions → Variables → New repository variable`.

> Un valor que termina en JavaScript del navegador es público aunque se guarde
> como secreto. No pongas credenciales en `VITE_API_URL`.

## 2. Preparar el VPS

Una vez, como administrador del servidor:

```bash
sudo adduser deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/helpdesk
sudo chown -R deploy:deploy /opt/helpdesk
```

Copia `deploy/compose.production.yml` a `/opt/helpdesk/compose.yml` y crea
`/opt/helpdesk/.env` con la configuración de runtime (nunca en Git):

```
POSTGRES_USER=helpdesk
POSTGRES_PASSWORD=<valor-seguro>
POSTGRES_DB=helpdesk
FRONTEND_ORIGINS=http://<host>:8080
BACKEND_PORT=8000
FRONTEND_PORT=8080
GHCR_OWNER=MarHeavenn
IMAGE_TAG=sha-<commit-inicial>
```

Pertenecer al grupo `docker` equivale en la práctica a controlar el host:
gobernar ese usuario cuidadosamente.

### Acceso a GHCR

Si las imágenes son públicas, no hace falta login. Si son privadas, crear un PAT
*classic* con **solo `read:packages`** en la cuenta con acceso al paquete y, como
usuario `deploy`:

```bash
echo "$CR_PAT" | docker login ghcr.io -u <github-user> --password-stdin
unset CR_PAT
```

### Clave SSH dedicada y known_hosts

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ./github_actions_deploy
# publica github_actions_deploy.pub en /home/deploy/.ssh/authorized_keys
ssh-keyscan -H <VPS_HOST>   # guardar la salida verificada como VPS_KNOWN_HOSTS
```

Prueba la clave manualmente antes de configurar GitHub. No uses
`StrictHostKeyChecking=no` como solución habitual.

## 3. Environment `production` y secretos

Ruta: `Settings → Environments → New environment → production → Configure environment`.
Opcionalmente activa *Required reviewers* y restringe los branches a `main`.

Environment secrets:

| Secreto | Contenido |
|---|---|
| `VPS_HOST` | IP o DNS del servidor |
| `VPS_USER` | `deploy` |
| `VPS_PORT` | Puerto SSH real (por defecto 22 en el workflow) |
| `VPS_SSH_KEY` | Contenido de la clave privada `github_actions_deploy` |
| `VPS_KNOWN_HOSTS` | Salida verificada de `ssh-keyscan -H` |

Los secretos funcionales de la aplicación (`POSTGRES_PASSWORD`, etc.) viven en
el `.env` del VPS: GitHub no los necesita.

## 4. Probar antes de automatizar

En el VPS, como `deploy`:

```bash
cd /opt/helpdesk
IMAGE_TAG=sha-<commit> docker compose pull
IMAGE_TAG=sha-<commit> docker compose up -d --remove-orphans
docker compose ps
curl --fail http://localhost:8000/health
```

Después, integra un cambio válido en `main` y observa: CI → paquetes en GHCR →
Deploy → `docker compose ps` → health. `Deploy` espera a que `CI` concluya con
éxito y a que el commit esté en `main`; si hay *Required reviewers*, aprueba la
ejecución en `Review deployments`.

## 5. Health, rollback y evidencia

- `docker compose ps` en `Up` demuestra que el contenedor corre; `curl /health`
  con 200 demuestra que la app se considera saludable. No confundirlos.
- Rollback: elegir el tag anterior en GHCR, exportar `IMAGE_TAG=sha-<anterior>`,
  repetir `pull` + `up -d --remove-orphans` y verificar `ps` y health. No hace
  falta recompilar. Ojo con migraciones irreversibles.
- Evidencia a registrar: commit SHA, nombre de imagen y tag, URL del run de CI,
  URL del run de Deploy, imagen efectiva en el VPS y resultado del health.

## 6. Regla de protección (opcional)

Tras el primer check verde:
`Settings → Rulesets → New branch ruleset → apuntar a main → Require status checks
to pass → Backend quality gates / Frontend quality gates`. Así un CI rojo bloquea
el merge.

## Limitación actual

Los workflows se entregan listos, pero **no se ha observado su ejecución en
GitHub**: eso requiere hacer push a `main` y revisar `Actions`, `Packages` y
`Deployments`. No se afirma que CI/CD ya esté corriendo sin esa evidencia.
