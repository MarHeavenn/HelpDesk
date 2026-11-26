# Tareas HU-17 — Búsqueda y filtrado de tickets

Estado: implementación completada; validación con límites de entorno.
R1 y T2–T10 completadas el 2026-11-22. Revisión de integración: 2026-11-25.
Esta síntesis conserva tareas, trazabilidad y resultados de cierre; sustituye
actas incrementales obsoletas. Los 13 Markdown de evidencia se eliminaron por
petición del usuario.

## Tareas ejecutadas

- [x] **R1. Recuperar seguridad de los cuatro listados y suite completa.** RF-171, RF-174, RF-176–RF-178.
  - Hecho: empresa autoritativa, 401/404, supervisor en general, vacíos y
    heredados. Focal 160 passed; suite 1677 passed / 40 skipped.
  - Aceptó los saldos históricos P1 (colección) y T1 (caracterización).
    P2–P5 fueron absorbidas, no ejecutadas como tareas independientes.
- [x] **T2. Añadir solicitante mínimo al resumen.** RF-170, RF-171, RF-174–RF-178.
  - Hecho: ocho claves exactas, `requester` solo `{name}` o `null` en cuatro
    rutas; sin cambiar detalle/escrituras. Focal 151 passed; suite 1725 passed.
- [x] **T3. Adaptar tipos, API y fixtures frontend.** RF-170, RF-174, RF-175.
  - Hecho: nombre/nulo/ausencia en all/mine/assigned sin peticiones por fila.
    Focal final 17 passed; frontend 249 passed.
- [x] **T4. Extender coincidencia y combinación.** RF-165–RF-171.
  - Hecho: AND con ID O título, nombre parcial y estados SLA separados.
    Focal 63 passed; frontend 297 passed.
- [x] **T5. Extender URL, filtros activos y limpieza.** RF-165, RF-167, RF-168, RF-172, RF-173.
  - Hecho: normalización independiente, orden conservado, página 1 y SLA Todos.
    Focal 76 passed; frontend 310 passed.
- [x] **T6. Añadir controles accesibles.** RF-170–RF-173.
  - Hecho: campo libre, seis opciones SLA, debounce y limpieza común.
    Componente 6 passed; frontend 316 passed.
  - Límite histórico: T6 no registró rojo previo; pruebas e implementación se
    escribieron juntas. No se atribuye retrospectivamente un ciclo TDD.
- [x] **T7. Integrar criterios efectivos y vacíos en listado compartido.** RF-165, RF-169, RF-172–RF-174.
  - Hecho: cliente/supervisor ignoran técnico forzado; base vacía prevalece.
    Componente 7 passed; frontend 323 passed.
- [x] **T8. Completar aceptación por vista y rol.** RF-165–RF-174, RF-177, RF-178.
  - Hecho: matriz, URL, filtros, guards, carga/error/reintento/401 y modal.
    Focal 111 passed; frontend 392 passed.
- [x] **T9. Cerrar regresión de callers, snapshot y privacidad.** RF-170, RF-171, RF-174–RF-178.
  - Hecho: 11 combinaciones rol/ruta, ocho claves, reloj fijo, SLA congelado,
    contratos ajenos intactos y sin polling. Focal backend 21/frontend 2 passed.
- [x] **T10. Validar RF por RF y registrar límites.** RF-165–RF-178.
  - Hecho histórico: backend 1746 passed / 40 skipped / 3 warnings;
    frontend 394 passed / 39 archivos, lint/build verdes.
    Smoke real: 55 comprobaciones, 0 fallos.

## Matriz de validación

Todos los RF de esta tabla pertenecen a **HU-17**, no a HU-26.

| RF | Cobertura automatizada principal |
|---|---|
| 165 | `frontend/tests/lib/tickets.test.ts`, `TicketSearchAcceptance.test.tsx`, `TicketsPageFilters.test.tsx`: OR agrupado, AND, contador/paginación |
| 166 | `tickets.test.ts`, `TicketSearchAcceptance.test.tsx`: ID/título, `#`, case/trim y exclusión de otros campos |
| 167–168 | `tickets.test.ts`, `TicketSearchAcceptance.test.tsx`: catálogos, prioridad nula e inválidos independientes |
| 169 | `TicketFilters.test.tsx`, `TicketsPageFilters.test.tsx`, `guards.test.tsx`: técnico permitido/forzado por URL |
| 170 | `TicketFilters.test.tsx`, `tickets.test.ts`, `backend/tests/test_hu17_requester_summary.py`: nombre parcial/nulo, sin correo |
| 171 | `TicketSearchAcceptance.test.tsx`, `TicketListSlaSnapshot.test.tsx`, `test_hu17_caller_regression.py`: estados separados, Sin SLA y snapshot |
| 172 | `tickets.test.ts`, `TicketSearchAcceptance.test.tsx`, `TicketsPageFilters.test.tsx`: URL, recarga y página fuera de rango |
| 173 | `TicketsPageFilters.test.tsx`, `TicketFilters.test.tsx`: vacíos, limpieza, orden y debounce |
| 174 | `guards.test.tsx`, `TicketSearchAcceptance.test.tsx`, `TicketsPage.test.tsx`, suites de seguridad backend |
| 175 | `test_hu17_requester_summary.py`, `test_hu17_caller_regression.py`, pruebas API/fixtures frontend: adición mínima |
| 176 | `test_hu17_summary_security.py`, `test_hu17_r1_recovery.py`, `test_hu17_caller_regression.py`: empresa almacenada y relaciones cruzadas |
| 177 | Las suites anteriores y `TicketSearchAcceptance.test.tsx`: supervisor general, sin Mis tickets/técnico/atención |
| 178 | Las suites anteriores: 401, 404 sin empresa, herencia y 200 vacío autorizado |

Las pruebas de página/componente citadas están en `frontend/tests/pages/`,
`frontend/tests/components/` y `frontend/tests/routes/`, respectivamente.

## Smoke histórico y límites

El 2026-11-22 se usaron backend/frontend reales, semilla temporal en memoria y
Edge headless por CDP: 55 comprobaciones sin fallos. Se verificaron filtros,
URL, limpieza, vacíos, detalle, restricciones por rol, teclado/foco, contador
`role="status"`/`aria-live` y anchos 360/768/1024/1440 px.
Se corrigió con autorización el desbordamiento horizontal preexistente añadiendo
`relative` al contenedor de la tabla y se repitieron ambas suites.

No fue una prueba de producción ni de persistencia SQL. No se usó lector de
pantalla real. Los 40 skips históricos corresponden a PostgreSQL no disponible,
incluidas integración, migraciones y semillas persistentes.

## Integración con develop — 2026-11-25

- `develop` local y esta rama actualizadas hasta `53863f0` (7 commits nuevos).
- Cambios locales preservados; conflictos resueltos en
  `backend/tests/test_dev_server_seed.py` y `specs/project.md`, conservando
  cobertura de semilla y las entradas HU-17/HU-26/CI-CD.
- HU-26 también utiliza RF-165–RF-172: usar HU + RF al citar; no se renumeran
  requisitos aprobados en esta integración.
- Docker sin daemon accesible; no se afirma validación de PostgreSQL.
- Frontend posterior a integrar: `npm test` → **394 passed / 39 archivos**;
  `npm run lint` y `npm run build` → exit 0. Advertencias de migración futura
  de React Router, sin fallos.
- Smoke de HU-26 reproducido en rojo: exigía siete campos del resumen.
  `backend/smoke_manual.py` ahora exige ocho y `requester` exactamente
  `{name}`, conservando la comprobación estricta y la privacidad.
- Smoke repetido con `HELPDESK_ALLOW_IN_MEMORY=1`, `DATABASE_URL` vacío y
  `python backend/smoke_manual.py`: **94 comprobaciones en verde**, exit 0,
  con cliente, técnico y administrador contra servidor HTTP real en memoria.
  No sustituye una prueba visual de navegador ni valida persistencia.
- Backend completo: `$env:PYTHONPATH='backend'; python -m pytest -q -rs`
  con Python 3.10.0 → **1746 passed / 40 skipped / 3 warnings**, exit 0,
  175.81 s. Sin exclusiones. Los 40 skips requieren PostgreSQL; advertencias
  de deprecación en FastAPI/Starlette.
- `git diff --check` sin errores; ningún conflicto sin resolver.
  CodeGraph sincronizado y Graphify actualizado (sin extracción SQL por falta
  de `tree_sitter_sql`; no se instalaron dependencias).

## Veredicto

RF-165–RF-178 implementados y cubiertos por las pruebas automatizadas verdes.
No se detectaron fallos funcionales en la integración tras corregir el smoke.
**Implementación completa; validación no exhaustiva**: siguen pendientes las
pruebas de PostgreSQL. El smoke visual citado es histórico, no una ejecución
de navegador nueva del 2026-11-25, y no se valida lector de pantalla real.
