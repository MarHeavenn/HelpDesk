# Tareas HU-14 — Gestión de configuración de SLA

Orden de dependencia. 20–40 min por tarea. Verificación con pytest + `TestClient` (sin frontend).
Cada tarea se implementa con el test en rojo primero, luego el código, `pytest` y `codegraph sync`.
La configuración es un singleton: toda prueba que la mute debe resetearla en un fixture `autouse`.

- [x] **T1. Dominio de la configuración: catálogo, semilla y conversión horas→minutos.** RF-71, RF-74
  - Archivos: `backend/app/modules/sla/domain/policy_config.py` (nuevo); `backend/app/modules/sla/application/policies.py` (reexportar la semilla y actualizar el docstring).
  - Tests: `backend/tests/test_sla_policy_domain.py`.
  - Hecho cuando: `SLA_PRIORITIES` es exactamente `("Crítica", "Alta", "Media", "Baja")` (y coincide con `PRIORITIES` de `tickets`); `DEFAULT_SLA_TARGET_MINUTES` es `{Crítica: 120, Alta: 240, Media: 720, Baja: 1440}` y sigue importable desde `application/policies.py`; `hours_to_minutes` convierte `2`→120, `0.5`→30, `0.25`→15 y `0.02`→1 con `Decimal` y `ROUND_HALF_UP`; `0`, negativos y `0.001` (redondea a 0 min) lanzan `SlaPolicyValidationError`; `validate_policy_targets` rechaza `{}`, una prioridad ausente y una clave extra, y devuelve el mapa en orden de catálogo; los valores no finitos se rechazan; la prueba de HU-05 de la semilla sigue en verde.

- [x] **T2. Repositorio en memoria de la configuración (semilla, reemplazo atómico y reset).** RF-71, RF-77
  - Archivos: `backend/app/modules/sla/infrastructure/sla_policy_repository.py` (nuevo).
  - Tests: `backend/tests/test_sla_policy_repository.py`.
  - Hecho cuando: una instancia nueva arranca con la semilla de RF-71; `get_target_minutes(priority)` devuelve el objetivo de cada prioridad, y `None` para `None` o una prioridad desconocida; `get_all()` devuelve una copia en orden `Crítica`→`Alta`→`Media`→`Baja`; `replace` sustituye la configuración completa; dos reemplazos consecutivos dejan solo el último («último escritor gana») sin mezclas; un reemplazo fallido no se produce porque la validación es previa; `reset()` vuelve a la semilla y `reset()` de una instancia no afecta a otra; `get_sla_policy_repository()` devuelve siempre el mismo singleton; las firmas aceptan `company_id=None` sin usarlo.

- [x] **T3. Cálculo con la configuración vigente, sin cambiar el contrato.** RF-76
  - Archivos: `backend/app/modules/sla/application/policies.py`, `backend/app/modules/sla/application/calculate_ticket_sla.py`.
  - Tests: `backend/tests/test_sla_calculation.py` (ampliar, con fixture de `reset()`).
  - Hecho cuando: `target_minutes_for` deja de leer la constante y consulta el repositorio en cada llamada; tras `replace({"Crítica": 60, ...})`, `target_minutes_for("Crítica")` y `calculate_ticket_sla`/`get_ticket_sla` usan 60 y el `due_at` se mueve; sin prioridad y con prioridad desconocida sigue devolviendo `None`; `get_ticket_sla(snapshot, now=None)` conserva exactamente su firma y su resultado coincide con el de aplicación; los tests de cálculo de HU-05 siguen en verde (con la semilla reseteada).

- [x] **T4. Casos de uso de consulta y reemplazo con guardia de rol.** RF-72, RF-73, RF-74, RF-75
  - Archivos: `backend/app/modules/sla/application/manage_sla_policies.py` (nuevo).
  - Tests: `backend/tests/test_sla_policies_use_case.py`.
  - Hecho cuando: `ensure_sla_admin("cliente")` y `("tecnico")` lanzan `SlaPolicyAccessDeniedError("not found")` antes de tocar el repositorio (la configuración queda intacta) y `("administrador")` no lanza; `list_sla_policies` devuelve las cuatro prioridades en orden y no muta el repositorio; `replace_sla_policies` valida con el dominio, persiste el reemplazo completo y devuelve la lista resultante (150 min → `SlaPolicy("Crítica", 150)`); un cuerpo inválido lanza `SlaPolicyValidationError` y no escribe; reemplazar con los mismos valores es idempotente; un reemplazo posterior sustituye por completo al anterior.

- [x] **T5. Esquemas HTTP, `GET /api/sla/policies`, dependencia de rol y registro del router.** RF-72, RF-75, RF-78
  - Archivos: `backend/app/modules/sla/interface/schemas.py` (nuevo), `backend/app/modules/sla/interface/dependencies.py` (nuevo), `backend/app/modules/sla/interface/router.py` (nuevo), `backend/app/main.py`; `backend/tests/test_sla_api.py` (ajuste).
  - Tests: `backend/tests/test_sla_policies_api.py` (sección GET), `backend/tests/test_sla_api.py`.
  - Hecho cuando: el administrador recibe 200 con la semilla exacta `[{Crítica,2},{Alta,4},{Media,12},{Baja,24}]` en ese orden y `hours` numérico; `?company_id=x&page=2` se ignora (200); la consulta no muta configuración ni tickets; sin sesión → 401; `cliente` y `tecnico` → 404 `{"detail": "not found"}` sin datos; `require_sla_admin` resuelve el 404 antes del cuerpo; el router queda registrado en `main.py`; la prueba `test_there_is_no_public_sla_configuration_route` de `test_sla_api.py` se sustituye por el contrato nuevo y la suite de HU-05 sigue en verde.

- [x] **T6. `PUT /api/sla/policies`: reemplazo total y respuesta.** RF-73, RF-74
  - Archivos: `backend/app/modules/sla/interface/router.py`, `backend/app/modules/sla/interface/schemas.py`.
  - Tests: `backend/tests/test_sla_policies_api.py` (sección PUT).
  - Hecho cuando: el administrador recibe 200 con el array resultante al enviar `{"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 24}`; la respuesta respeta el orden de catálogo; `0.5`→30, `0.25`→15 y `0.02`→1 minutos quedan guardados y se reflejan en el `GET`; guardar 150 minutos devuelve `"hours": 2.5`; reemplazar con los mismos valores devuelve 200 sin cambios; dos `PUT` consecutivos dejan el último («último escritor gana»); la configuración se mantiene durante la vida del proceso; no se añaden códigos nuevos.

- [x] **T7. Validación 422 de cuerpo y precedencias 401 > 404 > 422.** RF-74, RF-75, RF-78
  - Archivos: `backend/app/modules/sla/interface/schemas.py`, `backend/app/modules/sla/interface/router.py` (ajustes si hacen falta).
  - Tests: `backend/tests/test_sla_policies_api.py` (sección validación/precedencia).
  - Hecho cuando: devuelven 422 sin mutar la configuración `{}`, una prioridad ausente, una clave extra (`Urgente`), valores cadena, booleanos, `null`, listas, `0`, negativos, `0.001`, `NaN` e `Infinity`; los errores de forma traen `detail` lista (Pydantic) y los de regla `detail` cadena (dominio); tras cada 422 el `GET` devuelve la configuración anterior; sin sesión y con cuerpo inválido → 401; `tecnico`/`cliente` con cuerpo inválido → 404 uniforme (no 422); administrador con cuerpo inválido → 422; no se usa 403 ni códigos nuevos.

- [x] **T8. Congelación de `Resuelto`/`Cerrado` y re-congelación al cambiar prioridad.** RF-76
  - Archivos: `backend/app/modules/sla/domain/entities.py` (`TicketSlaSnapshot` + `calculate_sla`), `backend/app/modules/tickets/domain/entities.py` (`Ticket.resolved_target_minutes`), `backend/app/modules/tickets/application/update_ticket_status.py`, `backend/app/modules/tickets/application/set_ticket_priority.py`, `backend/app/modules/tickets/application/list_attention_tickets.py`, `backend/app/modules/tickets/interface/router.py`; tests de HU-03/HU-05 si hace falta.
  - Tests: `backend/tests/test_sla_live_config.py` (sección congelación), `backend/tests/test_sla_domain.py` y `backend/tests/test_tickets_update_status.py` (regresión).
  - Hecho cuando: un ticket resuelto conserva `target_minutes`, `due_at`, `elapsed_minutes` y `status` tras cambiar la configuración; un `Cerrado` también; al reabrir se descartan `resolved_at` y `resolved_target_minutes` y el SLA vuelve a derivarse de la configuración vigente; al cambiar la prioridad de un `Resuelto` se usa la configuración vigente **en ese momento** y el ticket queda re-congelado con el nuevo objetivo; un ticket sin prioridad sigue con `sla: null`; `get_ticket_sla` mantiene su firma; no se añade ningún campo a `TicketResponse`/`TicketSummaryResponse`; los tests de congelación de HU-05 siguen en verde.

- [x] **T9. Efecto en vivo sobre tickets activos, listado de atención y ajuste de regresión.** RF-76, RF-78
  - Archivos: `backend/tests/test_sla_live_config.py`, `backend/tests/test_attention_api.py`, `backend/tests/test_sla_api.py` y `backend/tests/test_sla_calculation.py` (fixtures de `reset()`).
  - Tests: `backend/tests/test_sla_live_config.py` (sección en vivo), `backend/tests/test_attention_api.py`.
  - Hecho cuando: un ticket `Crítica` activo creado hace 45 min pasa a `incumplido` al reducir `Crítica` a 0,5 h (30 min), con `target_minutes` 30 y `remaining_minutes` 0; un `Baja` activo en `en_riesgo` con 23 h pasa a `en_tiempo` al ampliar `Baja` a 48 h; el listado `GET /api/tickets/requiring-attention` refleja las entradas y salidas sin recalcular historial; cambiar la configuración no muta `created_at`, `priority`, `status` ni `resolved_at` del ticket (solo el SLA derivado); `GET`/`PUT` de configuración no mutan tickets; `test_attention_api.py` deja de tratar `/api/sla/policies` como ruta inexistente (para un técnico sigue siendo 404 uniforme) y la suite de atención sigue en verde.

- [x] **T10. Verificación final, documentación, índice y cierre.** RF-71 a RF-78
  - Archivos: `specs/project.md`, `MEMORY.md`, `specs/features/HU-14-sla-config/spec.md` (estado), `specs/features/HU-14-sla-config/tasks.md`.
  - Hecho cuando: con Docker y `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`, la suite completa queda en verde salvo los 3 fallos preexistentes de precedencia 401/404 (`test_tickets_assign_access`, `test_tickets_modify_access`), ajenos a HU-14; se ejecuta `codegraph sync`; `specs/project.md` apunta a `specs/features/HU-14-sla-config/`; `MEMORY.md` recoge el estado y las decisiones (semilla, horas/`ROUND_HALF_UP`, 401/404/422, repositorio en memoria y objetivo congelado); la spec queda como `implementada`, el plan como `implementado` y todas las tareas `[x]`; no hay cambios de frontend ni de PostgreSQL en esta historia y el PR se prepara contra `develop`.
