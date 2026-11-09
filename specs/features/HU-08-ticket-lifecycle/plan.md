# Plan HU-08 — Gestionar ciclo de vida del ticket
Spec: `specs/features/HU-08-ticket-lifecycle/spec.md` (aprobada)
Estado: implementado

## 1. Alcance técnico

Backend únicamente, dentro del módulo `tickets`, en memoria y sin dependencias nuevas. La historia sustituye la libertad de transiciones de HU-03 por un flujo explícito y añade una ruta de reapertura exclusiva del administrador. No cambia `TicketResponse`, los resúmenes ni los contratos de HU-02 a HU-07.

| RF | Dónde se cubre |
| --- | --- |
| RF-71 | `STATUS_TRANSITIONS` e `is_allowed_status_transition` en `tickets/domain` |
| RF-72 | `update_ticket_status` (validación de transición) + `PUT /status` |
| RF-73 | `InvalidStatusTransitionError` -> 409 `invalid status transition` |
| RF-74 | `update_ticket_status` (mismo estado, no cerrado) |
| RF-75 | `get_modifiable_ticket` (409 `ticket is closed`, sin cambios) |
| RF-76 | `get_reopenable_ticket` + `reopen_ticket` + `POST /reopen` |
| RF-77 | `get_reopenable_ticket` (rol admin, 404 uniforme, 409 `ticket is not closed`) |
| RF-78 | Dependencias del router y orden de las comprobaciones |
| RF-79 | Sin cambios en esquemas; única ruta nueva `POST /reopen` |
| RF-80 | Reutilización de `resolved_at`, SLA y bloqueos de HU-03/HU-04/HU-07 |

## 2. Estructura de archivos

```
backend/app/modules/tickets/
  domain/entities.py                        # + IN_PROGRESS_STATUS, STATUS_TRANSITIONS,
                                            #   is_allowed_status_transition, REOPEN_ROLES
  application/update_ticket_status.py       # + InvalidStatusTransitionError y validación
  application/get_reopenable_ticket.py      # nuevo: permiso admin + estado Cerrado
  application/reopen_ticket.py              # nuevo: Cerrado -> Abierto, resolved_at, registro
  interface/router.py                       # + _reopenable_ticket y POST /{id}/reopen
                                            #   + traducción del 409 de transición
```

`identity`, `assignment`, `sla`, los repositorios y los esquemas no cambian. No se crea un router nuevo: la reapertura comparte `_ticket_response`, los helpers de cuerpo y las dependencias de sesión con `PUT /status`.

## 3. Contrato HTTP

### Actualizar estado (se conserva la ruta y el cuerpo)

```http
PUT /api/tickets/{ticket_id}/status
Content-Type: application/json

{"status": "En progreso"}
```

```json
200 OK
{
  "id": "6b2c...",
  "title": "No puedo acceder",
  "description": "Error al entrar",
  "priority": "Alta",
  "status": "En progreso",
  "assignee": {"id": "u-2", "name": "Ana Torres"},
  "requester": {"id": "u-1", "name": "Luis Pérez", "email": "luis@ejemplo.com"},
  "sla": { "...": "sin cambios" },
  "created_at": "2026-11-02T14:00:00.000000+00:00",
  "resolved_at": null,
  "requester_id": "u-1"
}
```

Transiciones válidas (RF-71):

| Actual | Destino permitido |
| --- | --- |
| `Abierto` | `En progreso` |
| `En progreso` | `Resuelto` |
| `Resuelto` | `Cerrado`, `En progreso` |
| `Cerrado` | ninguno por esta ruta |

- Mismo estado en un ticket no cerrado: `200` sin cambio ni registro.
- Transición válida: `200`, muta el ticket y añade `TicketModification`.
- Valor del catálogo no permitido: `409 {"detail": "invalid status transition"}`.
- Ticket cerrado: `409 {"detail": "ticket is closed"}` antes de leer el cuerpo.
- Valor fuera del catálogo, cuerpo no textual, campo extra o JSON inválido: `422`.
- Sin sesión: `401`; cliente: `404 {"detail": "ticket not found"}`; ticket inexistente o identificador inválido: `404`.

### Reabrir un ticket cerrado (ruta nueva)

```http
POST /api/tickets/{ticket_id}/reopen
```

Sin cuerpo. Respuesta `200` con el mismo `TicketResponse`, `status: "Abierto"` y `resolved_at: null`:

```json
200 OK
{
  "id": "6b2c...",
  "status": "Abierto",
  "resolved_at": null,
  "sla": { "...": "reanudado desde created_at" },
  "...": "resto del contrato sin cambios"
}
```

- Solo `administrador`: técnico y cliente reciben `404 {"detail": "ticket not found"}`.
- Ticket inexistente o identificador inválido: `404` uniforme.
- Ticket no cerrado: `409 {"detail": "ticket is not closed"}`.
- Sin sesión: `401` antes que 404/409.
- Cualquier cuerpo enviado se ignora.

### Errores nuevos

- `409 {"detail": "invalid status transition"}` (transición no permitida).
- `409 {"detail": "ticket is not closed"}` (reapertura de un ticket no cerrado).

No se añaden códigos, rutas, campos ni mensajes fuera de estos y de los ya existentes.

## 4. Reglas y casos de uso

### 4.1 Dominio

```python
IN_PROGRESS_STATUS = "En progreso"

STATUSES = (OPEN_STATUS, IN_PROGRESS_STATUS, RESOLVED_STATUS, CLOSED_STATUS)

STATUS_TRANSITIONS = {
    OPEN_STATUS: frozenset({IN_PROGRESS_STATUS}),
    IN_PROGRESS_STATUS: frozenset({RESOLVED_STATUS}),
    RESOLVED_STATUS: frozenset({CLOSED_STATUS, IN_PROGRESS_STATUS}),
    CLOSED_STATUS: frozenset(),
}

REOPEN_ROLES = frozenset({"administrador"})


def is_allowed_status_transition(current: str, new: str) -> bool:
    return new in STATUS_TRANSITIONS.get(current, frozenset())
```

`STATUSES` conserva el orden del catálogo de HU-03. El estado `Cerrado` no tiene destinos por `PUT`: su salida es la reapertura.

### 4.2 Actualización de estado

`update_ticket_status` mantiene su firma y añade, después de validar el catálogo:

1. Si `ticket.status == new_status`, devolver el ticket sin cambios ni registro (RF-74).
2. Si `not is_allowed_status_transition(ticket.status, new_status)`, lanzar `InvalidStatusTransitionError(INVALID_STATUS_TRANSITION_MESSAGE)` (RF-73), sin mutar ni registrar.
3. Si la transición es válida, mutar el estado y registrar como hoy (RF-72).
4. Mantener la lógica de `resolved_at`: `Resuelto`/`Cerrado` lo fijan si falta; `Resuelto` -> `Cerrado` lo conserva; `Resuelto` -> `En progreso` lo descarta (RF-80).

`INVALID_STATUS_TRANSITION_MESSAGE = "invalid status transition"`. La validación del catálogo sigue produciendo `TicketValidationError` (422) y ocurre antes de juzgar la transición: sin un destino válido no hay transición que evaluar.

### 4.3 Resolución del ticket para reabrir

`get_reopenable_ticket(ticket_id, actor_role, tickets)` sigue el patrón de `get_assignable_ticket`:

1. `actor_role in REOPEN_ROLES` (administrador); si no, `TicketNotFoundError` (404 uniforme) sin resolver el ticket.
2. Formato UUID y existencia; si falla, `TicketNotFoundError` (404).
3. `ticket.status != CLOSED_STATUS` -> `TicketNotClosedError(TICKET_NOT_CLOSED_MESSAGE)` (409).

`TICKET_NOT_CLOSED_MESSAGE = "ticket is not closed"`.

### 4.4 Reapertura

```python
def reopen_ticket(ticket, actor_id, modifications, now=None) -> Ticket:
    changed_at = now or datetime.now(timezone.utc)
    ticket.status = OPEN_STATUS
    ticket.resolved_at = None
    modifications.add(
        TicketModification(
            ticket_id=ticket.id,
            field=STATUS_FIELD,
            previous_value=CLOSED_STATUS,
            new_value=OPEN_STATUS,
            actor_id=actor_id,
            changed_at=changed_at,
        )
    )
    return ticket
```

No toca prioridad, técnico, solicitante, título, descripción ni `created_at`. El registro reutiliza `TicketModification`, de modo que HU-09 lo verá sin un formato nuevo.

### 4.5 Interfaz

- `set_status_endpoint` añade `except InvalidStatusTransitionError` -> `HTTPException(409, detail=...)` después de `TicketValidationError` (no son jerárquicos, se capturan por separado).
- `_reopenable_ticket` es una dependencia con `get_current_user` (401), traduce `TicketNotFoundError` a 404 y `TicketNotClosedError` a 409.
- `POST /{ticket_id}/reopen` usa `ticket: Ticket = Depends(_reopenable_ticket)`, `current: dict = Depends(get_current_user)` y llama a `reopen_ticket`.
- No se declara `requestBody` para la reapertura; el cuerpo se ignora.

### 4.6 Precedencia resultante

`PUT /status`: 401 > 404 (rol/visibilidad/existencia) > 409 `ticket is closed` > 422 (cuerpo o catálogo) > 409 `invalid status transition`.
Reapertura: 401 > 404 (rol/existencia) > 409 `ticket is not closed`.

## 5. Cambios en pruebas

### 5.1 Archivos nuevos

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_ticket_lifecycle_domain.py` | unitario | RF-71, RF-74: las 16 combinaciones de la tabla, transiciones válidas e inválidas, mismo estado, constantes y `REOPEN_ROLES` |
| `tests/test_ticket_lifecycle_status.py` | API + TestClient | RF-71 a RF-75, RF-78: transición válida, no-op, 409 de transición, 409 de cerrado, registro, `resolved_at`/SLA, 422, 401, 404 y composición intacta |
| `tests/test_ticket_lifecycle_reopen.py` | API + TestClient | RF-76, RF-77, RF-80: reapertura por admin, 404 de técnico/cliente, 404 de inexistente/inválido, 409 de no cerrado, cuerpo ignorado, registro, `resolved_at: null`, SLA reanudado y operaciones habilitadas de nuevo |
| `tests/test_ticket_lifecycle_flow.py` | API + TestClient | RF-71 a RF-80: flujo completo `Abierto` -> `En progreso` -> `Resuelto` -> `Cerrado` -> reapertura, con prioridad, asignación, comentarios y SLA; intentos inválidos intercalados |

### 5.2 Archivos existentes que hay que ajustar

Las pruebas de HU-03 a HU-07 que hoy hacen saltos directos deben recorrer el flujo permitido, sin debilitar sus afirmaciones. Afectados detectados:

- `test_tickets_update_status.py`: reescribir `test_any_transition_between_open_states_is_allowed`, `test_jump_from_open_to_closed_is_allowed`, `test_each_catalog_status_is_accepted`, `test_put_status_accepts_each_catalog_value` y `test_put_status_allows_regression_without_sequence_rules`; añadir los 409 de transición inválida y conservar catálogo, 422, 404, 409 de cerrado y 401.
- `test_tickets_modifications_sweep.py`: sustituir `test_sweep_free_transitions_accumulate` por el flujo válido; ajustar `VALID_BODIES["status"]` y la tabla de precedencia (un destino válido desde `Abierto` ya no es `Resuelto`); crear los tickets cerrados recorriendo el flujo; conservar el mapa RF.
- `test_tickets_modify_access.py`, `test_tickets_assign_access.py`, `test_tickets_set_priority.py`, `test_tickets_invalid_utf8.py`, `test_tickets_isolation.py`: los tickets cerrados se crean con `Abierto` -> `En progreso` -> `Resuelto` -> `Cerrado` mediante un helper local.
- `test_tickets_detail_contract.py`: la resolución se hace desde `En progreso`; el caso de «reabrir» un `Resuelto` pasa a `Resuelto` -> `En progreso` (retroceso permitido), y la reapertura de un `Cerrado` se prueba por `POST /reopen`.
- `test_tickets_assignee_responses.py`, `test_tickets_assign.py`: ajustar los estados de origen de los cambios.
- `test_ticket_comments_creation.py`, `test_ticket_comments_listing.py`, `test_ticket_comments_flow.py`: cerrar recorriendo el flujo; en el flujo de HU-07, `En progreso` -> `Resuelto` -> `Cerrado`.
- `test_sla_api.py` y las pruebas de SLA que cierren o resuelvan directamente: recorrer el flujo manteniendo las afirmaciones sobre `resolved_at`, congelación y reanudación.
- `test_tickets_sweep.py`, `test_tickets_validation.py`: solo contienen estados en cuerpos de creación inválidos; se revisan para confirmar que no cambian.
- La suite completa identificará cualquier otro archivo con saltos; se corrige igual, sin relajar aserciones.

Se añadirá en cada archivo afectado un helper local mínimo, por ejemplo:

```python
def _advance_status(api, ticket_id, target):
    path = {"En progreso": [], "Resuelto": ["En progreso"],
            "Cerrado": ["En progreso", "Resuelto"]}[target]
    for status in path + [target]:
        response = api.put(
            f"/api/tickets/{ticket_id}/status", json={"status": status}
        )
        assert response.status_code == 200, response.text
```

No se añade un módulo de utilidades compartido para no introducir una dependencia nueva entre archivos de prueba; la duplicación local sigue el estilo actual del repositorio.

## 6. Contratos y dependencias

- Dirección: `tickets.interface.router` -> `tickets.application` -> `tickets.domain` / `tickets.infrastructure`.
- `get_reopenable_ticket` reutiliza `TicketNotFoundError` y `is_valid_uuid_format`; no importa estructuras de `identity` (el rol llega de la sesión).
- `reopen_ticket` reutiliza `TicketModification`, `STATUS_FIELD` y el registro de modificaciones de HU-03.
- `get_modifiable_ticket`, `get_commentable_ticket` y `get_assignable_ticket` no cambian: el ticket cerrado sigue bloqueando prioridad, comentarios y asignación con 409.
- `sla` no se toca: el SLA se reanuda porque `resolved_at` queda en `None`, igual que ya ocurre al volver a un estado no resuelto.

## 7. Riesgos y mitigaciones

- **Cambio de contrato de HU-03:** muchas pruebas asumen transiciones libres. Se actualizan recorriendo el flujo y se conservan sus aserciones de estado, registro y SLA; la suite completa actúa de red de seguridad.
- **Precedencia 409/422:** el 409 de transición solo se evalúa con un destino válido del catálogo; el 422 de cuerpo o catálogo va antes. Se prueba explícitamente con cuerpos inválidos y con destinos válidos no permitidos.
- **Cierre y reapertura:** `PUT /status` sobre `Cerrado` sigue devolviendo `ticket is closed`; la única salida es `POST /reopen`. Se prueba que no se puede reabrir por la ruta de estado.
- **Roles:** el técnico puede cambiar estados pero no reabrir; se prueba el 404 uniforme y que no se filtra el ticket.
- **Coherencia con HU-07:** tras reabrir, el ticket deja de estar cerrado y los comentarios vuelven a aceptarse; antes del cierre siguen dando 409. Se prueba en el flujo.
- **SLA:** `Resuelto` -> `En progreso` y la reapertura descartan `resolved_at`; `Resuelto` -> `Cerrado` lo conserva. Se prueba con los campos del SLA, no solo con el estado.
- **Ruta nueva:** se verifica en OpenAPI que solo aparece `POST /api/tickets/{ticket_id}/reopen` y que no se añaden campos a `TicketResponse`.

## 8. Orden de implementación

1. Dominio: constantes, tabla de transiciones y `is_allowed_status_transition`, con pruebas unitarias.
2. `update_ticket_status` con `InvalidStatusTransitionError`; ajustar sus pruebas unitarias y de API.
3. `get_reopenable_ticket` y `reopen_ticket`, con pruebas de aplicación.
4. Router: traducción del 409 de transición, dependencia `_reopenable_ticket` y `POST /reopen`; pruebas de API.
5. Actualizar las pruebas existentes que hacían saltos, archivo por archivo, hasta dejar la suite en verde.
6. Prueba de flujo completo y coherencia con HU-02/HU-04/HU-05/HU-06/HU-07.
7. Suite completa con PostgreSQL, `codegraph sync`, `specs/project.md`, `MEMORY.md` y `tasks.md` (documentado al terminar).

## 9. Estimación

5 horas, repartidas en las tareas de 20-30 minutos del orden anterior. El mayor esfuerzo está en actualizar las pruebas de HU-03 a HU-07 que asumían transiciones libres.
