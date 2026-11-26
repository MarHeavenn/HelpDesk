# Memoria del proyecto

## Estado actual

- HU-01..HU-14, HU-19, HU-21..HU-24 integradas en `develop`; HU-15
  implementada y HU-16 en cierre de validación.
- HU-26 y CI/CD integradas: Dockerfiles/compose/nginx, GitHub Actions,
  GHCR y Blueprint Render free para demo de 20 días. PostgreSQL free expira
  a los 30 días; crear al inicio de la demo. CI run `45263461824` verde.
- Rama actual `feature/HU-17-ticket-search-filtering`: actualizada junto a
  `develop` hasta `53863f0` el 2026-11-25; cambios locales preservados.
- HU-17 implementada (RF-165–RF-178), con validación limitada por PostgreSQL.
  Solicitante mínimo, filtro SLA y aislamiento de cuatro listados.
  Spec/plan/tareas consolidados; eliminados 13 Markdown de evidencia.
- Conflictos resueltos en `test_dev_server_seed.py` y `specs/project.md`;
  conservadas pruebas de idempotencia y entradas HU-17/HU-26/CI-CD.
- HU-17 y HU-26 comparten RF-165–RF-172: citar HU + RF, sin renumerar.
- Verificación actual: frontend 394 pruebas / 39 archivos; lint/build verdes;
  smoke HTTP 94/94 tras corregir contrato de siete a ocho campos + nombre mínimo.
  Backend 1746 passed / 40 skipped / 3 warnings (PostgreSQL no disponible).
- Respaldo previo a integración conservado en stash
  `backup-before-develop-sync-HU17-20261125`; publicación de HU-17 autorizada.
  Agentes/configuración locales excluidos; el usuario abrirá el PR a `develop`.

## Decisiones y reglas

- `companies` posee catálogo/contacto/estado; `identity` cuentas/invitaciones;
  `tickets` tickets. Solo contratos `interface/*_contract.py` entre módulos.
- Unicidad de empresa en aplicación con advisory lock e índice NO único;
  tolerar datos heredados sin inventar empresa o ampliar acceso.
- HU-13: invitación 168 h con hash/un solo uso, correo global único, último
  administrador activo protegido; precedencia 401 → 404 → 422 → 409.
- HU-17 resumen: ocho claves, `requester` solo `{name}` o `null`, sin correo.
  Autorizar por empresa del ticket antes de componer solicitante/SLA.
- HU-23 listado compartido con URL como fuente; HU-24 señal desde `sla`,
  alertas a `/tickets?q=<id>`; dashboard reciente sin SLA ni contador ficticio.
- HU-15 notifica sin actor, polling 30 s + foco; HU-16 deduplica en memoria
  por ticket/tipo/destinatario/vencimiento, no entre procesos.

## Entorno y errores que evitar

- BD solo Docker `infra-db-1` en 55432, nunca PostgreSQL nativo/temporal.
  Docker sin daemon el 2026-11-25: no afirmar validación SQL ni despliegue.
- Python disponible 3.10.0: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`.
  Frontend: `npm test`, `npm run lint`, `npm run build`; cookie en localhost.
- CodeGraph por `cmd /c`; sync tras cambiar código y `graphify update .`.
- Un TestClient por rol; 422 Pydantic devuelve lista, dominio cadena.
- Envejecer tickets con fechas, no sleeps; resetear singleton SLA.
  RTL requiere cleanup y API falsa/fetch stubeado. Migraciones sin última fija.
- Pendientes: persistencia HU-17; Docker CP-13/14/16 HU-26; cierre HU-16;
  smoke HU-15 y revisión visual HU-21/HU-24; configurar Render/secrets y deploy.
- No borrar BD aislada `helpdesk_hu16_validation_20261117` sin autorización;
  no guardar secretos ni afirmar pruebas/despliegues no ejecutados.
