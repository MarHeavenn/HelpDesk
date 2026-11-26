# Spec CI/CD — GitHub Actions + GHCR + Render

Estado: aprobada

## Contexto y objetivo

Los ejercicios `Ejercicio_CI.pdf` y `Ejercicio_CD.pdf` de la carpeta `Proceso`
piden quality gates en GitHub Actions, publicación en GHCR y despliegue
continuo. El destino inicial previsto era un VPS por SSH, pero se cambió a
**Render** por decisión del usuario: todo el MVP (API, frontend y PostgreSQL)
debe funcionar **hasta 20 días sin coste**. La capa free de Render cubre ese
periodo (su Postgres gratis expira a los 30 días).

Esta historia no añade funcionalidad al MVP. Los secretos de Render y las
variables de runtime se configuran fuera del repositorio.

## Decisiones aprobadas

- CI ejecuta calidad en PRs y pushes a `develop` y `main`; publica en GHCR solo
  en push a `main`.
- Se publican dos paquetes: `helpdesk-backend` y `helpdesk-frontend`, con tags
  `sha-<commit>` y `latest` (evidencia del ejercicio; Render despliega desde Git).
- Despliegue en **Render**: Web Service `helpdesk-api`, Static Site
  `helpdesk-web` y Postgres `helpdesk-db`, todos en plan `free`.
- `render.yaml` usa `autoDeployTrigger: 'off'`; el deploy lo dispara el workflow
  de GitHub mediante los Deploy Hooks de Render, tras CI verde en `main`.

## Requisitos funcionales

- RF-CD-1: EL WORKFLOW `CI` ejecutará, en PRs y pushes a `develop`/`main`, un job
  de calidad del backend (pytest con el seam en memoria) y otro del frontend
  (`npm ci`, lint, test, build), y verificará que ambas imágenes Docker se
  construyen.
- RF-CD-2: CUANDO se haga un push a `main` y los jobs de calidad terminen
  correctamente, EL WORKFLOW publicará las dos imágenes en GHCR con
  `packages: write`, usando el SHA completo del commit y `latest`.
- RF-CD-3: EL WORKFLOW `Deploy` se disparará por `workflow_run` de `CI`, exigirá
  `conclusion == success` y `head_branch == main`, y llamará a los Deploy Hooks
  de Render primero del API y después del frontend, con verificación de health.
- RF-CD-4: EL BLUEPRINT `render.yaml` declarará los tres servicios en plan
  `free`, con `autoDeployTrigger: 'off'`, `DATABASE_URL` desde la base de datos y
  variables sensibles marcadas `sync: false`; no contendrá secretos.
- RF-CD-5: LA DOCUMENTACIÓN cubrirá creación del Blueprint, variables del
  dashboard, Deploy Hooks como secrets, verificación con `/health`, límites de
  30 días de la BD free, rollback y evidencia.
- RF-CD-6: No se guardarán claves, tokens ni contraseñas en el repositorio;
  `VITE_API_URL` y `HEALTH_URL` serán variables públicas.

## Criterios de finalización

- Workflows y Blueprint con sintaxis válida (schema oficial de Render), sin
  secretos en el repositorio.
- Guía de operación y README actualizados.
- Evidencia real en GitHub (runs, checks, paquetes) y en Render (servicios y
  health) que el usuario debe completar; no se afirmará despliegue sin verlo.

## Validación (2026-11-23)

| RF | Comprobación | Resultado |
|---|---|---|
| RF-CD-1 | Run de CI `45263461824` en GitHub: backend y frontend en verde (tests + docker build) | PASADO |
| RF-CD-2 | Job `publish` condicionado a push `main`, con `packages: write` y dos imágenes | PASADO (definición; sin ejecutar hasta push a `main`) |
| RF-CD-3 | `deploy.yml` con `workflow_run`, Deploy Hooks y health | PASADO (definición) |
| RF-CD-4 | `render.yaml` validado contra `https://render.com/schema/render.yaml.json` con `jsonschema` | PASADO |
| RF-CD-5 | `docs/ci-cd.md` reescrito para Render + README | PASADO |
| RF-CD-6 | Sin secretos en el repo; `sync: false` en variables sensibles | PASADO |

**Veredicto: CI y artefactos listos; despliegue en Render pendiente de crear la
cuenta/configurar secretos y de un push a `main`.** Se retiró
`deploy/compose.production.yml` porque ya no aplica sin VPS.
