# Tareas CI/CD — GitHub Actions + GHCR + VPS

- [x] **T1. Workflow de CI y contextos de build.** RF-CD-1, RF-CD-6
  - Hecho cuando: `ci.yml` ejecuta calidad de backend y frontend en PRs/pushes a
    `develop` y `main`, verifica ambos `docker build` y usa variables públicas
    sin secretos; existen `.dockerignore` para backend y frontend.

- [x] **T2. Publicación en GHCR.** RF-CD-2
  - Hecho cuando: el job `publish` corre solo en push a `main`, usa
    `packages: write` y publica `helpdesk-backend` y `helpdesk-frontend` con tags
    `sha-<commit>` y `latest`.

- [x] **T3. Workflow de Deploy y compose de producción.** RF-CD-3, RF-CD-4
  - Hecho cuando: `deploy.yml` reacciona a `workflow_run` de CI, exige éxito en
    `main`, usa `environment: production` y SSH; el compose usa `image:` con
    `${IMAGE_TAG}` y no contiene secretos.

- [x] **T4. Documentación operativa.** RF-CD-5
  - Hecho cuando: `docs/ci-cd.md` explica VPS, secretos, environment, verificación
    manual, health, rollback y evidencia, y `README.md` enlaza la guía.

- [x] **T5. Validación local y cierre.** RF-CD-1..RF-CD-6
  - Hecho cuando: el YAML se valida sintácticamente, no hay secretos en el repo,
    `MEMORY.md` queda actualizado y se registra que la ejecución en GitHub está
    pendiente de observación (no se afirma sin evidencia).
