# Memoria del proyecto
## Estado actual
- HU-01..HU-14, HU-19, HU-21..HU-24 integradas en `develop`; HU-15 implementada y HU-16 en cierre de validación.
- HU-26/CI/CD integradas: Docker/nginx, Actions/GHCR, Render demo 20 días; PostgreSQL free 30 días (crear al inicio). CI `45263461824` verde.
- Rama `feature/HU-18-support-management-metrics`, desde `develop` `0263108` (2026-11-25); cambios locales preservados.
- Usuario autorizó entregar HU-18 + HU-26 A/B.I juntos y hacer push a esta rama;
  excluir configuración local `.opencode/` y `.agents/`. B.II–E siguen pendientes.
- HU-18: T1–T10 y QA aprobados (RF-179–191); panel admin por ID, actorKey/guardia
  401; manual navegador pendiente. Frontend 461/43, lint/build y grafos verdes.
- HU-17 hecha (RF-165–178): solicitante mínimo, filtro SLA y aislamiento de cuatro listados; docs consolidados, PostgreSQL limitado.
- HU-17 y HU-26 comparten RF-165–RF-172: citar HU + RF, sin renumerar.
- Stash `backup-before-develop-sync-HU17-20261125`; agentes/config locales preservados.

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
- HU-15: sin actor, polling 30 s + foco; HU-16 deduplica por ticket/tipo/destinatario/vencimiento solo en memoria.

## Entorno y errores que evitar
- Arranque local autorizado 2026-11-27: Compose db/API/web healthy, puertos
  55432/8000/8080; HTTP `/health`, `/` y `/login` respondieron 200.
  Override externo `C:\Users\nicom\AppData\Local\Temp\opencode\helpdesk-local-no-seed.yml`:
  omite seed antiguo (tickets sin empresa → NOT NULL) y healthcheck web usa 127.0.0.1.
  Usar ambos `-f` al levantar; YAML original intacto. Arranque ejecutó runner de
  migraciones en BD local; backup previo externo `helpdesk_before_local_restart_20261127_223003.dump`.
  Volumen `infra_pgdata` conservado; no se restablecieron contraseñas ni se validó login.
  No fixtures destructivas sobre demo: SQL en esquema propio, sin public en path.
- Python disponible 3.10.0: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`.
  Frontend: `npm test`, `npm run lint`, `npm run build`; cookie en localhost.
- CodeGraph por `cmd /c`; sync tras cambiar código y `graphify update .`.
- Un TestClient por rol; 422 Pydantic lista/dominio cadena; fechas, no sleeps; resetear SLA.
  RTL requiere cleanup y API falsa/fetch stubeado. Migraciones sin última fija.
- HU-26 A aprobado por reviewer-deep: users/proyección atómica, empresas SQL,
  contratos y proceso nuevo; QA A 208 passed/0 skips. Frontend 461/43, lint/build
  offline verdes; API viva: 6 fallos 401 heredados. PERSIST global parcial.
- B.I.1–2 hechas: legado 007 sin inferencias y 008 nullable; «si» autorizó
  acotar cuatro escenarios A2/A7 a 007 sin cambiar aserciones.
- «completa las demas tareas» aprueba B.I.2–9 secuencial, no B.II–IV ni despliegue.
- B.I.1–9 APROBADO por QA independiente reviewer-deep, sin bloqueantes; QA no editó,
  sin reviewer-expert. Lecturas/snapshot/INSERT SQL; HTTP padre→hijo sin seed/caché/sesión.
  A2/A7 históricos autorizados respetados; nombre faltante por contrato tras autorizar.
  QA SQL A1–A7+B.I 399/0 (208,57 s); G 2019/385 skips (166,91 s), exit 0:
  345 SQL aparte, 40 previos no acreditados; 11 huellas public intactas/0 residuos.
  Primera QA SQL 398/1 por Windows10048 al conectar antesHTTP (read_http.py:194);
  repetición completa verde sin cambios código/servicios; diff-check QA 0.
  QA no repitió frontend/lint/build: implementer offline 461/43, lint/build 0;
  seis 401 con API viva siguen como límite, no integración desplegada.
  PERSIST-1/2/5 parcial/6/8, RF-165 alta/consulta y RF-171 cumplen B.I, no global.
  HU-18 RF-179–188/191 compatible; RF-187 ciclo de vida solo memoria, no SQL.
- Pendientes: B.II–E, sesiones, HU-17 persistente, CP-13/14/16, HU-16, smoke HU-15,
  visual HU-21/24 y Render. Graphify sin SQL/HTML; no mutaciones/seed adelantados.
- No borrar `helpdesk_hu16_validation_20261117` sin autorización; no guardar secretos ni afirmar pruebas/despliegues no ejecutados.
