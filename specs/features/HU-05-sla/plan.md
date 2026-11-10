# Plan HU-05 — Configurar y controlar SLA por prioridad
Spec: `specs/features/HU-05-sla/spec.md` (implementada)
Estado: implementado

## 1. Alcance técnico

Implementación backend únicamente, en memoria y con configuración global, coherente con `identity`, `tickets` y `assignment`. No se toca PostgreSQL, el frontend ni la autenticación. El módulo `sla` (hoy vacío) pasa a calcular el SLA; el módulo `tickets` incorpora la fecha de resolución y compone el campo `sla` en todas sus respuestas.

| RF | Dónde se cubre |
| --- | --- |
| RF-41 | `sla/application/policies.py` (valores iniciales) y `sla/domain` (catálogo) |
| RF-42 | `sla/application/calculate_ticket_sla.py` (prioridad ausente → `None`) |
| RF-43 | `sla/domain/entities.py` (inicio, vencimiento, transcurrido, restante) |
| RF-44 | `tickets/interface/schemas.py` + `tickets/interface/router.py` |
| RF-45 | `sla/domain/entities.py` (estados, umbral 20 %, indicadores) |
| RF-46 | `tickets/domain/entities.py` (`resolved_at`) + `update_ticket_status.py` |
| RF-47 | Cálculo derivado de la prioridad vigente (sin almacenar el SLA) |
| RF-48 | Cálculo en cada lectura; sin tareas programadas ni endpoints de ajuste |
| RF-49 | Composición en las respuestas existentes; sin rutas ni permisos nuevos |
| RF-50 | `sla/domain/entities.py` (minutos enteros, truncado, UTC) |

## 2. Estructura de archivos

```
backend/app/modules/sla/
  domain/entities.py                 # SlaPolicy, TicketSlaSnapshot, TicketSla,
                                     # estados y reglas puras de cálculo
  application/policies.py            # DEFAULT_TARGET_MINUTES y target_minutes_for()
  application/calculate_ticket_sla.py# resuelve la política y delega en el dominio
  interface/contract.py              # get_ticket_sla(...) para otros módulos
  infrastructure/__init__.py         # sin persistencia en esta historia

backend/app/modules/tickets/
  domain/entities.py                 # + Ticket.resolved_at
  application/update_ticket_status.py# fija/descarta resolved_at
  interface/schemas.py               # + SlaResponse y campo sla
  interface/router.py                # + composición del SLA en detalle y resumen
```

`assignments_router.py` no cambia: usa `ticket_summary`, que ya incluirá `sla`.

## 3. Contrato HTTP

`TicketResponse` (creación, detalle, prioridad, estado y asignación) y `TicketSummaryResponse` (listado y tickets a cargo) incorporan:

```json
"sla": {
  "target_minutes": 240,
  "started_at": "2026-11-02T12:00:00.000000+00:00",
  "due_at": "2026-11-02T16:00:00.000000+00:00",
  "elapsed_minutes": 37,
  "remaining_minutes": 203,
  "status": "en_tiempo",
  "near_due": false,
  "breached": false
}
```

- `sla` es `null` cuando el ticket no tiene prioridad (RF-42).
- `status` es uno de `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`.
- Las fechas usan `isoformat()` con offset UTC y microsegundos, igual que `created_at`.
- No se añaden rutas, parámetros ni códigos de error.

## 4. Reglas de cálculo

Función pura en `sla/domain/entities.py`:

```
calculate_sla(snapshot, target_minutes, now) -> TicketSla | None:
    si snapshot.priority es None: return None

    started_at = snapshot.created_at
    due_at     = started_at + timedelta(minutes=target_minutes)
    resuelto   = snapshot.status in ("Resuelto", "Cerrado") and snapshot.resolved_at is not None
    referencia = snapshot.resolved_at si resuelto, si no now

    si resuelto:
        estado = "cumplido" si snapshot.resolved_at <= due_at si no "incumplido"
    si now >= due_at:
        estado = "incumplido"
    si (due_at - now) <= 20 % de target_minutes y (due_at - now) > 0:
        estado = "en_riesgo"
    si no:
        estado = "en_tiempo"

    elapsed   = max(0, floor((referencia - started_at) / 60 s))
    remaining = 0 si resuelto o now >= due_at
                si no max(0, floor((due_at - now) / 60 s))
    near_due  = (estado == "en_riesgo")
    breached  = (estado == "incumplido")
```

- El umbral se evalúa con duraciones exactas, no con los minutos redondeados, para que el 20 % y el vencimiento sean estables (RF-50).
- Un ticket `Resuelto`/`Cerrado` sin `resolved_at` (dato inconsistente construido a mano en pruebas) se trata como no resuelto; los casos de uso siempre lo rellenan.
- `elapsed` y `remaining` se truncan a minutos completos; `remaining` nunca es negativo.

`calculate_ticket_sla(snapshot, now=None)` en aplicación:

1. Si `snapshot.priority` es `None` → `None`.
2. `target_minutes_for(priority)`; si la prioridad no está en el catálogo → `None` (defensivo; `tickets` ya la valida).
3. Delega en `calculate_sla` con `now or datetime.now(timezone.utc)`.

`interface/contract.py` expone `get_ticket_sla(snapshot, now=None)` y es el único punto que `tickets` importa de `sla`.

## 5. Cambios en `tickets`

- `Ticket.resolved_at: datetime | None = None` (campo con default al final, coherente con la nota de `MEMORY.md`).
- `update_ticket_status` calcula un único instante `changed_at` (el `now` recibido o `datetime.now(timezone.utc)`) y:
  - al pasar a `Resuelto` o `Cerrado`: `resolved_at = changed_at`;
  - al pasar de `Resuelto` a `Abierto` o `En progreso`: `resolved_at = None`;
  - al pasar de `Resuelto` a `Cerrado`: conserva `resolved_at`;
  - `Cerrado` no llega aquí (HU-03 lo rechaza con 409);
  - si el estado no cambia, no toca `resolved_at`.
- `tickets/interface/router.py` construye `TicketSlaSnapshot` desde el ticket y llama a `get_ticket_sla`. Los compositores aceptan un `now` opcional para que un listado use un único instante de referencia.
- `tickets/interface/schemas.py` define `SlaResponse` (tipos estrictos de respuesta) y añade `sla: SlaResponse | None` a `TicketResponse` y `TicketSummaryResponse`.

## 6. Contratos y dependencias

- Dirección: `tickets.interface` → `sla.interface` → `sla.application` → `sla.domain`. `sla` no importa nada de `tickets`.
- El contrato de entrada es `TicketSlaSnapshot` (prioridad, creación, estado y resolución), definido en `sla.domain`. Así `sla` no conoce `Ticket` ni accede a sus estructuras internas.
- No hay dependencia circular ni acceso a repositorios de otros módulos.
- `identity` no cambia: la visibilidad sigue rigiéndose por las rutas existentes.

## 7. Estrategia de pruebas

Sin pruebas de frontend (no hay runner acordado). Todo con pytest; las rutas con `TestClient` de FastAPI y sesiones reales creadas con `provision_user` + login, como en HU-02..HU-04.

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_sla_domain.py` | unitario, `now` inyectado | RF-41, RF-43, RF-45, RF-50: valores por prioridad, umbral exacto del 20 %, límites del vencimiento, truncado, restante no negativo, indicadores |
| `tests/test_sla_calculation.py` | aplicación/contrato | RF-42, RF-43, RF-45.3, RF-46, RF-47: `None` sin prioridad, vencimiento desde creación, cambio de prioridad, resolución antes/en/después del vencimiento, reapertura |
| `tests/test_sla_api.py` | API + TestClient | RF-44, RF-47, RF-48, RF-49: `sla` en creación, listado, detalle, prioridad, estado y asignación; `null` sin prioridad; congelación al resolver; reapertura; visibilidad del cliente; inexistencia de `GET/PUT /api/sla/policies` |
| Tests existentes de HU-02..HU-04 | regresión | Añadir `"sla"` a los conjuntos exactos de campos y comprobar `null` donde no hay prioridad: `test_tickets_detail.py`, `test_tickets_sweep.py`, `test_tickets_set_priority.py`, `test_tickets_priority_responses.py`, `test_tickets_update_status.py`, `test_tickets_assignee_responses.py`, `test_tickets_assignment_sweep.py`, `test_tickets_assigned_to_me.py`, `test_tickets_modifications_sweep.py` |

Para probar estados sin depender del reloj real:

- Los tests de dominio y aplicación inyectan `now`.
- Los tests de API crean tickets con `create_ticket(..., now=pasado)` o insertan el ticket directamente en el repositorio con `created_at` controlado, y solo usan la API para fijar prioridad/estado. Así `en_riesgo` e `incumplido` son deterministas sin dormir ni parchear el reloj global.
- La fecha de resolución se controla con el `now` de `update_ticket_status` cuando el test opera por casos de uso; por API se usa un ticket con `created_at` suficientemente antiguo para que la resolución real quede antes o después del vencimiento.

Cada tarea se implementa con el test en rojo primero, luego el código, `pytest` y `codegraph sync`.

## 8. Riesgos y mitigaciones

- **Regresión por el nuevo campo `sla`:** una decena de tests comparan el conjunto exacto de claves. Mitigación: tarea T5 dedicada solo a actualizar esos conjuntos; se ejecuta antes de los tests nuevos de API.
- **Reloj real en pruebas de API:** evitar umbrales exactos en API; usar márgenes amplios (p. ej. creado hace 3 h con Crítica de 2 h) y dejar los límites exactos a los tests con `now` inyectado.
- **Inconsistencia de minutos en un listado:** calcular un único `now` por respuesta de listado y pasarlo a los compositores.
- **Doble fuente de verdad del SLA:** no se persiste el estado; se deriva del ticket y la política. Esto evita divergencias y cumple RF-48.
- **Compatibilidad con HU-14:** la política se resuelve por prioridad en el momento de la consulta; HU-14 decidirá si congela el objetivo por ticket. No se adelanta esa decisión.

## 9. Orden de implementación

1. Dominio SLA y sus pruebas unitarias (RF-41, RF-43, RF-45, RF-50).
2. Aplicación SLA: políticas y cálculo, con pruebas (RF-41..RF-43, RF-47).
3. `resolved_at` en `tickets` y `update_ticket_status`, con pruebas (RF-46).
4. Contrato de `sla` y composición en esquemas/rutas de `tickets` (RF-44, RF-49).
5. Actualización de los tests existentes por el nuevo campo (regresión).
6. Tests de API de creación, prioridad, listado, detalle y asignación (RF-42, RF-44, RF-47).
7. Tests de API de resolución, reapertura, visibilidad y ausencia de configuración pública (RF-45.3, RF-46, RF-48, RF-49).
8. Suite completa, `codegraph sync` y `MEMORY.md`.

El detalle verificable de cada paso está en `tasks.md`.
