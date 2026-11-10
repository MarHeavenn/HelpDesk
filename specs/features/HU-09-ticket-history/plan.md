# Plan HU-09 — Registrar historial y trazabilidad del ticket
Spec: `specs/features/HU-09-ticket-history/spec.md` (aprobada)
Estado: implementado

## 1. Enfoque

HU-09 es una **vista de lectura derivada**. No crea una tabla ni un registro
nuevo: reúne en un único listado cronológico los eventos que ya generan
HU-02 (creación), HU-03 (prioridad y estado), HU-04 (asignaciones), HU-07
(comentarios) y HU-08 (reapertura). La fuente de verdad sigue siendo cada
registro existente; el historial solo los proyecta.

Ventajas frente a la alternativa de crear un `TicketHistoryLog` propio:

- no duplica datos ni abre la puerta a que el historial y las operaciones
  reales se desincronicen;
- no hay que reescribir los casos de uso de HU-03, HU-04, HU-07 y HU-08
  para emitir un segundo evento;
- las pruebas de esas historias siguen valiendo sin cambios funcionales.

La alternativa descartada era un registro de auditoría nuevo con escritura
en cada caso de uso. Se descarta por complejidad y por riesgo de doble
fuente de verdad. También se descarta exponer directamente los registros
internos: el contrato HTTP debe ser estable y no revelar estructuras
internas ni campos como `actor_id`, `changed_at` o `assigned_at`.

## 2. Capas y archivos afectados

### `tickets/domain/entities.py`

Nuevo concepto de solo datos:

```python
@dataclass(frozen=True)
class TicketHistoryEvent:
    action: str
    actor_id: str
    occurred_at: datetime
    previous_value: str | None = None
    new_value: str | None = None
    previous_assignee_id: str | None = None
    new_assignee_id: str | None = None
    comment: str | None = None
```

Constantes de acción:

- `HISTORY_ACTION_CREATED = "ticket_created"`
- `HISTORY_ACTION_ASSIGNED = "technician_assigned"`
- `HISTORY_ACTION_REASSIGNED = "technician_reassigned"`
- `HISTORY_ACTION_PRIORITY = "priority_changed"`
- `HISTORY_ACTION_STATUS = "status_changed"`
- `HISTORY_ACTION_COMMENT = "comment_added"`

La entidad no conoce HTTP ni `identity`. Sirve para que el caso de uso
ordene y la interfaz serialice.

### `tickets/application/get_historyable_ticket.py`

Resuelve el ticket sobre el que se puede consultar el historial (RF-84,
RF-85):

1. Comprueba que el rol de sesión sea de gestión (`tecnico` o
   `administrador`). Un cliente recibe `TicketNotFoundError`, incluso si el
   ticket es suyo.
2. Delega en `get_ticket_detail` la validación del formato UUID y la
   existencia, reutilizando el 404 uniforme de HU-02/HU-06.
3. No comprueba el estado `Cerrado`: la lectura siempre está permitida.

Se prefiere esta función pequeña a repetir la lógica en el router. La
alternativa de añadir la comprobación de rol dentro de `get_ticket_detail`
se descarta porque cambiaría el contrato de HU-06 para otras rutas.

### `tickets/application/list_ticket_history.py`

Caso de uso `list_ticket_history(ticket_id, actor_id, actor_role, tickets,
modifications, assignments, comments) -> list[TicketHistoryEvent]`:

1. Llama a `get_historyable_ticket` (404 uniforme).
2. Construye la lista de eventos:
   - **Creación:** `ticket_created`, actor `ticket.requester_id`, fecha
     `ticket.created_at`, sin valores.
   - **Modificaciones:** cada `TicketModification` con `field ==
     PRIORITY_FIELD` → `priority_changed`; con `field == STATUS_FIELD` →
     `status_changed`. Conserva `previous_value`, `new_value`, `actor_id` y
     `changed_at`.
   - **Asignaciones:** cada `AssignmentRecord` con
     `previous_assignee_id is None` → `technician_assigned`; en caso
     contrario → `technician_reassigned`. Conserva ambos identificadores,
     `actor_id` y `assigned_at`.
   - **Comentarios:** cada `TicketComment` → `comment_added`, actor
     `author_id`, fecha `created_at` y `comment=body`.
3. Ordena con una clave determinista:
   `(occurred_at, source_rank, insertion_index)`, donde `source_rank` es
   `creación=0`, `asignación=1`, `prioridad=2`, `estado=3`,
   `comentario=4`. Dentro de cada fuente se conserva el orden de alta.
4. Devuelve la lista. No muta ninguna de las fuentes.

Los valores de prioridad, estado y comentario se toman tal cual de los
registros. Los identificadores de técnico se resuelven a nombre visible en
la interfaz, no en el caso de uso, para no acoplar `tickets/application` al
contrato de `identity`.

### `tickets/interface/schemas.py`

Nuevos modelos de respuesta:

```python
class HistoryUserResponse(BaseModel):
    id: str
    name: str | None

class HistoryEventResponse(BaseModel):
    action: str
    actor: HistoryUserResponse
    occurred_at: str
    previous_value: str | None
    new_value: str | None
    previous_assignee: HistoryUserResponse | None
    new_assignee: HistoryUserResponse | None
    comment: str | None
```

Todos los campos se serializan siempre; los que no aplican van a `null`.
Esto facilita el contrato exacto y evita campos ausentes según el tipo de
evento. `previous_value`/`new_value` son cadenas para prioridad y estado;
`previous_assignee`/`new_assignee` son objetos para asignaciones;
`comment` solo se rellena en comentarios.

La alternativa de usar solo `previous_value`/`new_value` también para
técnicos se descarta porque perdería el identificador opaco y obligaría a
mezclar nombres e identificadores en el mismo campo.

### `tickets/interface/history_router.py`

Router nuevo con prefijo `/api/tickets`, etiqueta `history`:

```python
@router.get("/{ticket_id}/history", response_model=list[HistoryEventResponse])
def list_ticket_history_endpoint(
    ticket_id: str,
    current: dict = Depends(get_current_user),
) -> list[HistoryEventResponse]:
    ...
```

Responsabilidades:

- Obtener el ticket con `get_historyable_ticket` y traducir
  `TicketNotFoundError` a 404 uniforme.
- Invocar `list_ticket_history` con los singletons de los registros.
- Resolver nombres visibles con `get_user_summary` del contrato de
  `identity`, tanto para el actor como para técnico anterior/nuevo.
- Serializar fechas con `datetime.isoformat()` (offset UTC y
  microsegundos), igual que comentarios y tickets.
- Si un usuario no se resuelve, devolver `{"id": <id>, "name": null}`,
  conservando el evento y el identificador (RF-88).

`main.py` incluye el router. No se declaran parámetros de consulta: los
desconocidos se ignoran por defecto (RF-89).

### Contratos entre módulos

- `tickets` → `identity`: solo `get_user_summary(id)`, que devuelve
  `{id, name, email}`. No se accede al repositorio de usuarios ni a `User`.
- `tickets` internamente: el caso de uso recibe las tres fuentes ya
  existentes (`InMemoryTicketModificationLog`, `InMemoryAssignmentLog`,
  `InMemoryTicketCommentRepository`) y el repositorio de tickets.
- No se toca `sla`, `assignment` ni `identity`.

## 3. Decisiones y alternativas descartadas

1. **Historial derivado, no persistido.** Se reutilizan las fuentes
   existentes. Alternativa descartada: tabla `ticket_history` con escritura
   en cada caso de uso (duplica datos y obliga a tocar HU-03/04/07/08).
2. **Roles `administrador` y `tecnico`.** Confirmado por el usuario.
   Alternativa descartada: solo administrador, que impediría al técnico
   entender el trabajo previo.
3. **Eventos completos.** Confirmado por el usuario: creación, asignación,
   reasignación, prioridad, estado/reapertura y comentarios. Alternativa
   descartada: excluir comentarios o creación, que dejaría el historial
   incompleto para la auditoría.
4. **Un evento por acción efectiva.** Se apoyan en los registros que ya
   solo anotan cambios efectivos; no se añaden eventos para no-ops ni
   rechazos (RF-87).
5. **Orden determinista.** `(occurred_at, source_rank, insertion_index)`.
   Alternativa descartada: ordenar solo por fecha, que dejaría empates no
   reproducibles.
6. **Nombres resueltos en la interfaz.** El caso de uso permanece puro y
   sin dependencia de `identity`; el router usa el contrato. Alternativa
   descartada: resolver nombres en el dominio, que acoplaría capas.
7. **Sin paginación ni filtros.** El MVP en memoria no lo necesita y la
   spec lo deja fuera de alcance. Se puede añadir después sin romper el
   contrato del array.
8. **Ruta nueva aislada.** Un `history_router.py` mantiene la cohesión,
   como `comments_router.py`, en lugar de engordar `router.py`.

## 4. Estrategia de pruebas

Todas con pytest y `TestClient` de FastAPI, sin frontend. Se añaden tres
archivos nuevos y se ajustan tres pruebas existentes que afirmaban la
ausencia de una ruta de historial.

### Nuevos

- `backend/tests/test_ticket_history_domain.py`
  - Constantes de acción y forma de `TicketHistoryEvent`.
  - Orden determinista con empates de fecha: creación → asignación →
    prioridad → estado → comentario.
  - Estabilidad del orden al repetir la consulta.
  - Cobertura: RF-82, RF-83, RF-86.

- `backend/tests/test_ticket_history_api.py`
  - Ticket recién creado → un único evento `ticket_created`, actor
    solicitante, fecha de creación.
  - Asignación inicial y reasignación → acciones y técnicos anterior/nuevo
    correctos; repetir técnico no genera evento.
  - Prioridad inicial (`previous_value: null`), cambio y repetición sin
    evento.
  - Estado `Abierto → En progreso → Resuelto → Cerrado` y reapertura;
    transición inválida y ticket cerrado sin evento nuevo.
  - Comentario → acción, autor, contenido y fecha; comentario inválido sin
    evento.
  - Contrato exacto de campos (`action`, `actor`, `occurred_at`,
    `previous_value`, `new_value`, `previous_assignee`,
    `new_assignee`, `comment`).
  - 404 uniforme para cliente (aunque sea su ticket), ticket inexistente e
    identificador inválido; 401 sin sesión antes de 404.
  - Ticket cerrado → 200 con historial completo, sin 409 ni mutación.
  - Usuario no resoluble → evento conservado con `name: null`.
  - Parámetros de consulta desconocidos ignorados.
  - OpenAPI: solo se añade `GET /api/tickets/{ticket_id}/history`; no
    cambian `TicketResponse` ni los resúmenes.
  - Cobertura: RF-81, RF-83, RF-84, RF-85, RF-87, RF-88, RF-89.

- `backend/tests/test_ticket_history_flow.py`
  - Flujo completo HU-02 → HU-04 → HU-03/HU-05 → HU-07 → HU-08:
    creación, asignación, prioridad, comentario, avance de estado,
    resolución, cierre, reapertura y nuevo avance.
  - Verifica la secuencia exacta de acciones, actores y valores, la
    ausencia de duplicados y que el historial no altera el ticket.
  - Cobertura: RF-82, RF-86, RF-87.

### Ajustes a pruebas existentes

Estas pruebas afirmaban que no existía ninguna ruta de historial, como
parte del alcance de historias anteriores. HU-09 las sustituye por
aserciones equivalentes sobre la nueva ruta documentada, sin debilitar la
protección de los registros internos:

- `backend/tests/test_assignment_log.py::test_no_public_route_exposes_the_assignment_log`:
  permitir exactamente `GET /api/tickets/{ticket_id}/history` y seguir
  prohibiendo cualquier otra ruta con `history`, `historial` o `record`;
  mantener la prohibición de `previous_assignee_id`, `new_assignee_id`,
  `assigned_at` y `actor_id` en los esquemas.
- `backend/tests/test_tickets_modifications_domain.py::test_no_public_route_exposes_the_modification_log`:
  permitir la ruta de historial; mantener `changed_at` y `actor_id` fuera
  de los esquemas. `previous_value`/`new_value` pasan a ser parte
  documentada del contrato de historial, así que la aserción global sobre
  esos nombres se sustituye por una comprobación de que no aparecen en
  `TicketResponse` ni en los resúmenes.
- `backend/tests/test_tickets_assignment_sweep.py` (barrido de rutas):
  permitir la ruta de historial y seguir rechazando `log`/`record` y
  cualquier otra ruta de historial no documentada.

### Verificación final

- Ejecutar los archivos nuevos por separado y luego la suite completa con
  `DATABASE_URL` (Docker en el puerto 55432).
- Documentar los tres fallos preexistentes de precedencia 401/404 con
  cookie inválida como ajenos a HU-09.
- `codegraph sync` tras los cambios.
- Actualizar `MEMORY.md`, `specs/project.md` y el estado de la spec/plan.

## 5. Orden de implementación

1. Dominio y constantes de acción.
2. Resolución autorizada del ticket (`get_historyable_ticket`).
3. Caso de uso de historial y orden determinista.
4. Esquemas HTTP y router.
5. Pruebas de API y de dominio.
6. Flujo completo.
7. Ajuste de pruebas existentes y suite completa.
8. Documentación, memoria e índice.
