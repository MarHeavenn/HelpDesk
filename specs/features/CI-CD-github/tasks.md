# Tareas CI/CD — GitHub Actions + GHCR + Render

- [x] **T1. Workflow de CI y contextos de build.** RF-CD-1, RF-CD-6
  - Hecho cuando: `ci.yml` ejecuta calidad de backend y frontend en PRs/pushes a
    `develop` y `main`, verifica ambos `docker build` y usa variables públicas;
    run `45263461824` terminó en verde.

- [x] **T2. Publicación en GHCR.** RF-CD-2
  - Hecho cuando: el job `publish` corre solo en push a `main`, usa
    `packages: write` y publica `helpdesk-backend` y `helpdesk-frontend` con tags
    `sha-<commit>` y `latest`. En PR aparece skipped, correcto.

- [x] **T3. Blueprint de Render y Deploy Hooks.** RF-CD-3, RF-CD-4
  - Hecho cuando: `render.yaml` declara Web Service, Static Site y Postgres en
    plan `free` con `autoDeployTrigger: 'off'` y valida contra el schema oficial;
    `deploy.yml` llama a los Deploy Hooks tras CI verde en `main`; se retiró el
    compose de VPS.

- [x] **T4. Documentación operativa.** RF-CD-5
  - Hecho cuando: `docs/ci-cd.md` explica el Blueprint, las variables del
    dashboard, los secretos del environment, el health, el límite de 30 días de
    la BD free, el rollback y la evidencia; `README.md` enlaza la guía.

- [x] **T5. Validación local y cierre.** RF-CD-1..RF-CD-6
  - Hecho cuando: YAML validado, `render.yaml` validado con jsonschema, sin
    secretos en el repo, `MEMORY.md` actualizado y el despliegue real marcado
    como pendiente de la cuenta y secretos del usuario.
