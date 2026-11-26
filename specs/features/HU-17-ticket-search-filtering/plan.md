# Plan HU-17 — Búsqueda y filtrado de tickets

Estado: aprobado y ejecutado. R1 y T2–T10 completadas el 2026-11-22;
revisión de integración con `develop` el 2026-11-25. Resultados y límites
en `tasks.md`. Esta síntesis sustituye las actas incrementales contradictorias;
no modifica el alcance aprobado ni constituye una nueva autorización.

## Alcance y arquitectura

- Conservar monolito modular, capas, rutas, permisos y dependencias existentes.
- Extender el listado compartido de HU-23 en ambas vistas autorizadas.
- Filtrar en cliente sobre datos autorizados: filtrar → ordenar → paginar.
- La URL conserva búsqueda, estado, prioridad, técnico permitido, solicitante,
  SLA, orden y página.
- Sin filtros HTTP nuevos, polling nuevo, directorio de personas ni consultas
  de detalle por fila.

## Módulos y capas afectados

| Superficie | Responsabilidad | RF de HU-17 |
|---|---|---|
| `tickets/application` | Autorizar y limitar visible/general/asignados/atención por empresa almacenada y alcance del actor | 174, 176–178 |
| `tickets/interface/router.py`, `assignments_router.py` | Pasar contexto de sesión, traducir errores y componer resúmenes después de autorizar | 170, 171, 174–178 |
| `tickets/interface/schemas.py` | Resumen aditivo con solicitante mínimo | 175 |
| `identity/interface/users_contract.py` | Resolver solicitante por contrato existente, sin cambios en identidad | 170, 175 |
| Contrato de `sla` | Reutilizar snapshot, estados y reloj común de la consulta | 171 |
| Tipos/API/fixtures frontend | Admitir solicitante mínimo, nulo o ausente sin ampliar otros payloads | 170, 175 |
| `frontend/src/lib/tickets.ts` | Coincidencias, combinación, URL, limpieza, orden y paginación | 165–173 |
| `TicketFilters`, `TicketListPage`, textos | Controles accesibles, permisos efectivos y estados de la vista compartida | 165–174 |

Sin acceso a tablas internas ajenas, reglas de negocio en HTTP, contratos que
importen otros contratos, migraciones o cambios de arquitectura.

## Contratos y decisiones

- Resumen: conservar `{id, title, priority, status, assignee, sla, created_at}`
  y añadir únicamente `requester: {name: string} | null`.
- El frontend tolera ausencia del nuevo campo. El detalle conserva su contrato;
  no reutilizar su DTO con correo para el listado.
- Autorizar por empresa de sesión y `ticket.company_id` antes de componer datos.
  No inferir empresa de solicitante/asignado ni de parámetros del cliente.
- General: administrador/supervisor/técnico de la empresa; cliente denegado.
  Visible: cliente limitado además a sus tickets. Asignados: actor asignado.
  Atención: mantener roles y condiciones existentes.
- Sin sesión: 401. Sin empresa o rol permitido: 404 uniforme.
  Consulta autorizada sin datos: 200 con colección vacía.
- Componer solicitante mediante contrato de identidad; reutilizar SLA con un
  instante común, sin recalcular desde colores o banderas visuales.
- Criterios: `(ID O título) Y estado Y prioridad Y solicitante Y técnico
  permitido Y SLA`. Nombre parcial, case/trim, sin correo ni eliminar acentos.
- SLA: `all`, `none`, `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`.
  No agrupar «En tiempo» y «Cumplido».
- Normalizar criterios inválidos individualmente; página fuera de rango a 1.
  Cliente/supervisor ignoran técnico también cuando llega por URL.
- Limpieza común: textos vacíos, selectores en Todos, página 1 y orden conservado.
  Base vacía prevalece sobre vacío por filtros.

Alternativas descartadas: filtrado de seguridad solo en UI, DTO de detalle con
correo, filtros de servidor, nuevas pantallas, directorio/autocompletado,
permisos globales ampliados y actualizaciones automáticas nuevas.

## Secuencia ejecutada y verificación

1. P1/T1 caracterizaron bloqueo de colección y seguridad.
2. R1 recuperó seguridad y suite completa, aceptando esos saldos antes del dato
   nuevo; P2–P5 quedaron absorbidas, no ejecutadas separadamente.
3. T2–T7 implementaron contrato, tipos, funciones, URL, controles e integración.
4. T8–T10 completaron aceptación por rol/vista, regresión y validación.

Pruebas previstas y ejecutadas: pytest/TestClient con sesiones reales, dos
empresas, relaciones cruzadas, sin empresa/sesión, vacíos y contratos exactos;
Vitest/Testing Library para criterios, URL, vacíos, roles y accesibilidad.
Puertas G: pytest completo; F: suite frontend, lint y build. No excluir fallos,
relajar seguridad ni añadir skips/xfail para recuperar verde.

El cierre histórico incluye smoke real de navegador con pila en memoria.
PostgreSQL y lector de pantalla real no quedaron validados. El detalle RF por RF
y la revalidación posterior a integrar `develop` están en `tasks.md`.
