# Plan HU-04 — Asignar tickets a técnicos

Spec base: `specs/features/HU-04-assignment/spec.md` (Estado: aprobada; 10 RF: RF-31 a RF-40; decisiones 1–5 confirmadas y 6–7 derivadas aprobadas).
Sin frontend hasta acordar runner. Verificación solo backend con pytest + TestClient de FastAPI.

## 1. Módulos y capas afectadas

El cambio principal vive en `tickets`: el técnico responsable es estado del ticket (RF-34, RF-35) y su registro de asignaciones es la auditoría del mismo agregado (RF-37), igual que HU-03 hizo con prioridad/estado y su log. `identity` recibe el contrato de consulta de técnicos (aplicación + router nuevo). `main.py` gana dos `include_router` (router de técnicos y router de tickets a cargo). `assignment` y `sla` no se tocan (D1).

| Capa | Contenido | RF que cubre |
|---|---|---|
| `tickets/domain/` | `Ticket` gana `assignee_id: str | None = None` y `assignee_name: str | None = None` (siempre ambos `None` o ambos con valor; D8); catálogo de autorización `ASSIGNMENT_ROLES = frozenset({"administrador"})` junto a `MANAGEMENT_ROLES`; entidad `AssignmentRecord` (ticket, técnico anterior, técnico nuevo, responsable, fecha y hora). Reutiliza `is_valid_uuid_format`, `CLOSED_STATUS` y `Ticket`. | RF-34, RF-35.3, RF-37, RF-38 |
| `tickets/application/` | `get_assignable_ticket` (permiso de administrador → 404 uniforme; formato/existencia → 404; `Cerrado` → `TicketClosedError`), `assign_ticket` (validación uniforme del técnico → `TicketValidationError`; repetición del vigente → sin cambio ni registro; cambio efectivo → muta el ticket y añade registro) y `list_assigned_tickets`. Reutiliza `TicketNotFoundError`/`TICKET_NOT_FOUND_MESSAGE` y `TicketClosedError`/`TICKET_CLOSED_MESSAGE` de HU-02/HU-03. | RF-32 a RF-37, RF-38, RF-39, RF-40 |
| `tickets/infrastructure/` | `InMemoryAssignmentLog` append-only (`add`, `list_by_ticket`, `count`, `clear`, singleton `get_assignment_log()`; patrón de `InMemoryTicketModificationLog`); `InMemoryTicketRepository.list_by_assignee` (mismo contrato que `list_by_requester`: descendente por `created_at`, empates sin orden). | RF-36, RF-37 |
| `tickets/interface/` | Esquema `SetAssigneeRequest` (`extra="forbid"`, `StrictStr`); `AssigneeResponse {id, name}` y campo `assignee: AssigneeResponse | None` en `TicketResponse` y `TicketSummaryResponse`; dependencia `_assignable_ticket` + cuerpo leído al final (`_json_body(SetAssigneeRequest)`); ruta `PUT /api/tickets/{ticket_id}/assignee`; router `GET /api/assignments/mine` (prefijo propio). Solo comunica. | RF-31 a RF-40 (códigos, composición y precedencia) |
| `identity/application/` | `technicians.py`: vista `TechnicianSummary {id, name}`, `list_technicians(actor_role, users)` (solo `administrador`, si no `TechniciansAccessDeniedError`) y `find_technician(technician_id, users)`. Sin correo, hash ni rol en la vista. | RF-31, RF-39.3 |
| `identity/interface/` | `technicians_router.py` con `GET /api/technicians` (respuesta `[{id, name}]`); frontera `get_technician_summary(technician_id)` usada por `tickets` (envuelve `find_technician` con el repositorio de `identity`, sin exponer `User` ni estructuras internas); `TechnicianResponse` en `schemas.py`. | RF-31, RF-39.3 |
| `identity/infrastructure/` | `InMemoryUserRepository.list_all()` (lectura para el directorio de técnicos; sin cambios en los contratos existentes). | RF-31 |
| `main.py` | `app.include_router(technicians_router)` y `app.include_router(assignments_router)`. Nada más cambia. | RF-31, RF-36 |

## 2. Contratos entre módulos y contrato HTTP

**Contratos entre módulos (casos de uso/frontera de aplicación; ningún módulo lee repositorios ni entidades internas de otro):**

- Existente: `identity/interface/dependencies.get_current_user` → `{id, email, role}` o 401. `tickets` usa `id` (actor) y `role` (autorización); nada procede del cuerpo.
- Nuevo (identity → tickets): `identity/interface/technicians_contract.get_technician_summary(technician_id) -> TechnicianSummary | None` (une `find_technician` con el repositorio compartido de `identity`). Devuelve solo `{id, name}`; `None` si no existe o no es `tecnico` (el formato UUID lo valida `tickets`, D10).
- Nuevo (HTTP, identity): `GET /api/technicians`, solo administradores.
- `tickets/application.assign_ticket` recibe la resolución del técnico como colaborador inyectado (`resolve_technician`) que la interfaz conecta a la frontera anterior: la regla del 422 uniforme vive en aplicación y `tickets` no importa infraestructura de `identity` (D10).
- Composición del ticket: pura sobre el propio ticket (`assignee_id` + `assignee_name`); no hay consultas a `identity` al leer tickets (D8).

**Contrato HTTP definitivo (cierra las referencias diferidas de la spec):**

- `PUT /api/tickets/{ticket_id}/assignee` — cuerpo `{"assignee_id": <StrictStr>}` (`extra="forbid"`) → **200** con `TicketResponse` (ticket completo actualizado); **401** sin sesión válida; **404** con el mensaje unificado `ticket not found` (cliente o técnico sin permiso de asignación, identificador de ticket inválido o ticket inexistente); **409** `ticket is closed` (ticket `Cerrado`, incluida la repetición del técnico vigente); **422** si el cuerpo falta, es nulo, no textual, trae campos extra o el JSON es sintácticamente inválido, y si el técnico no existe, no es un UUID válido, es cliente o es administrador (mensaje único `assignee is not a valid technician`, sin distinguir casos). No hay operación de desasignación.
- `GET /api/technicians` — solo administradores → **200** con `[{id, name}]` (solo usuarios de rol `tecnico`; sin correo, contraseña, hash ni rol; colección vacía 200); **401** sin sesión; **404** uniforme `technicians not found` para cliente y técnico. No declara parámetros de consulta: los desconocidos se ignoran en silencio, como en HU-02.
- `GET /api/assignments/mine` — cualquier usuario autenticado → **200** con los resúmenes de los tickets cuyo `assignee_id` es el de la sesión, en cualquier estado (incluido `Cerrado`), ordenados por `created_at` descendente, con la composición del resumen (incluye `assignee`); colección vacía para cliente, administrador o técnico sin tickets; **401** sin sesión; parámetros desconocidos ignorados. No cambia el listado ni el detalle de HU-02.
- **Composición uniforme (decisiones derivadas 6 y 7):** creación (201), listado, detalle, `PUT .../priority` y `PUT .../status` de HU-03 y asignación devuelven el mismo campo `assignee: {id, name} | null`, `null` cuando no hay asignación. Ninguna respuesta expone correo, credenciales ni el registro de asignaciones.
- Cuerpo de error consistente `{"detail": <mensaje>}`; códigos de la historia: 200 y 201 en los caminos válidos y 401/404/409/422 en los rechazos (sin 400 ni 403). `ticket_id` y `assignee_id` se declaran `str` (no `uuid.UUID`) para que un formato inválido dé 404 (ticket) o 422 uniforme (técnico), nunca un 422 de ruta o serialización.
- **Precedencia 401 > 404 > 409 > 422 con dependencias y cuerpo al final (patrón R1 de HU-03):** `_assignable_ticket` resuelve `get_current_user` (401) y, en orden, permiso de asignación (404 uniforme), formato/existencia del ticket (404) y ticket cerrado (409) antes de que `_assignee_body` —dependencia declarada en último lugar en la firma— lea y valide el JSON. Con JSON sintácticamente inválido se respeta la misma precedencia (401/404/409 antes del 422 de decodificación). El técnico se valida después, en el caso de uso (422). Sin sesión válida, técnicos y tickets a cargo responden 401; la consulta de técnicos exige además permiso de administrador (404 uniforme) y la de tickets a cargo no exige permiso adicional (RF-40).
- **Sin colisión de rutas:** `GET /api/assignments/mine` vive en un router con prefijo propio (`/api/assignments`) y `GET /api/technicians` en otro; ninguna ruta estática compite con `GET /api/tickets/{ticket_id}` ni depende del orden de declaración (D6).
- **El registro de asignaciones no tiene operación pública** ni aparece en ningún cuerpo de respuesta (RF-37).

## 3. Modelo de datos

**Modelo lógico (en memoria; D12):**

- `Ticket`: `id`, `title`, `description`, `priority` (`None` o catálogo), `status` (`Abierto`/`En progreso`/`Resuelto`/`Cerrado`), `requester_id`, `created_at` + `assignee_id: str | None` y `assignee_name: str | None` (ambos `None` al crear; RF-34; la creación sigue naciendo `Abierto`, sin prioridad y sin asignación).
- `AssignmentRecord`: `ticket_id`, `previous_assignee_id` (`None` en la primera asignación), `new_assignee_id`, `actor_id` (identificador opaco de la sesión) y `assigned_at` (instante UTC generado por el sistema). Solo cambios efectivos (RF-37); empates de `assigned_at` sin orden garantizado.
- `TechnicianSummary` (vista de `identity`): `id`, `name`.

**Esquema destino PostgreSQL (orientativo y diferido, no entregable; coherente con HU-02/HU-03 y `infra/docker-compose.yml`):**

| Tabla.columna | Tipo | Restricción |
|---|---|---|
| `tickets.assignee_id` | `uuid` | `NULL` permitido (valor del contrato de `identity`, sin clave foránea) |
| `tickets.assignee_name` | `text` | `NULL` permitido; `CHECK ((assignee_id IS NULL) = (assignee_name IS NULL))` |
| `ticket_assignments.id` | `uuid` | `PRIMARY KEY` (clave técnica de la tabla futura; el objeto en memoria no la necesita) |
| `ticket_assignments.ticket_id` | `uuid` | `NOT NULL` (referencia interna del módulo `tickets`) |
| `ticket_assignments.previous_assignee_id` | `uuid` | `NULL` (primera asignación) |
| `ticket_assignments.new_assignee_id` | `uuid` | `NOT NULL` |
| `ticket_assignments.actor_id` | `uuid` | `NOT NULL`, valor del contrato de `identity` sin clave foránea |
| `ticket_assignments.assigned_at` | `timestamptz` | `NOT NULL` |

Índice `(ticket_id, assigned_at)` para el historial de HU-09. Migración diferida: sin SQLAlchemy/Alémbic/driver, sin dependencias nuevas y sin tocar PostgreSQL en esta historia (D12).

## 4. Decisiones justificadas (con alternativa descartada)

**D1. La asignación se implementa en `tickets`; el módulo `assignment` permanece intacto.** El técnico responsable es estado del agregado ticket (RF-34, RF-35) y el registro de asignaciones es la auditoría de ese agregado (RF-37), exactamente el patrón de HU-03 (prioridad/estado + log en `tickets`). Un único dueño del ticket evita contratos de escritura entre módulos. *Alternativa descartada: implementar en `assignment` con contrato de aplicación hacia `tickets`:* el módulo acabaría siendo una fachada que delega en los casos de uso y el repositorio de `tickets` (el estado y las reglas seguirían allí), añadiendo una capa de indirección sin separar nada; el módulo `assignment` queda reservado para políticas futuras de asignación (capacidad, turnos, colas), explícitamente fuera de alcance.

**D2. La consulta de técnicos vive en `identity`, con router propio montado en `main.py`.** `identity` es la dueña de los usuarios y ya expone el contrato de sesión; la lista de técnicos es una consulta de identidad, no de tickets. *Alternativas descartadas: (a) endpoint en `tickets`:* expondría datos de otro módulo y mezclaría responsabilidades; *(b) anidarlo en `/api/auth/technicians`:* confundiría autenticación con directorio y se aleja de la referencia del contrato de la spec (`/api/technicians`); *(c) no cambiar `main.py`:* obligaría a colgar la ruta de un prefijo ajeno; el cambio (una línea) es mínimo y explícito.

**D3. El contrato de `identity` hacia `tickets` es un caso de uso + frontera que devuelve `{id, name}`.** `list_technicians` y `find_technician` son servicios de aplicación; la frontera `get_technician_summary` los conecta con el repositorio compartido de identidad. La vista no expone `User`, correo, hash ni rol. *Alternativas descartadas: (a) que `tickets` importe `get_user_repository` o `User`:* acceso a estructuras internas de otro módulo, prohibido por la constitución; *(b) devolver la entidad `User` completa:* filtraría correo y hash a la capa de comunicación.*

**D4. Ruta `PUT /api/tickets/{ticket_id}/assignee` con cuerpo mono-campo `{"assignee_id": ...}`.** Es coherente con los subrecursos de HU-03 (`/priority`, `/status`), idempotente y hace imposible mezclar campos. *Alternativas descartadas: (a) `POST /api/tickets/{ticket_id}/assign`:* sin precedente y menos idempotente; *(b) `PATCH /api/tickets/{ticket_id}`:* reabriría la mezcla con prioridad/estado; *(c) el técnico en la ruta:* los identificadores opacos no aportan nada en la URL y complicarían el 404/422.*

**D5. La precedencia 401 > 404 > 409 > 422 se implementa con la dependencia `_assignable_ticket` y el cuerpo leído y validado al final (patrón R1 de HU-03).** FastAPI resuelve las dependencias antes del cuerpo; la resolución aplica permiso de administrador (404 uniforme), formato/existencia (404) y cerrado (409), y solo después se decodifica el JSON (422), también con JSON sintácticamente inválido. *Alternativas descartadas: (a) cuerpo como parámetro normal:* daría 422 antes de 404/409 con JSON inválido, contra RF-40; *(b) validar todo en el caso de uso:* movería la decodificación HTTP a la capa de negocio.

**D6. `GET /api/assignments/mine` en un router propio del módulo `tickets` (prefijo `/api/assignments`).** Evita por construcción la colisión con `GET /api/tickets/{ticket_id}` y no depende del orden de declaración de rutas. *Alternativa descartada: `GET /api/tickets/assigned` declarada antes de la ruta dinámica:* funciona en FastAPI, pero es frágil (un reordenamiento futuro la rompería) y menos explícita para el consumidor.

**D7. El técnico se compone como `assignee: {"id": ..., "name": ...} | null`, uniforme en todas las respuestas de ticket.** Un único valor `null` representa «sin asignar» (RF-35.3) y un único campo evita repartir la ausencia entre dos claves; se aplica a creación (decisión derivada 7), listado, detalle, asignación y modificaciones de HU-03 (decisión derivada 6). *Alternativa descartada: campos planos `assignee_id`/`assignee_name`:* dos claves en vez de una y el `null` duplicado en cada una.

**D8. `Ticket` guarda `assignee_id` y `assignee_name` (proyección del nombre en el momento de asignar); la composición no consulta `identity`.** El caso de uso ya resuelve el técnico para validarlo (RF-39.3), así que guardar el nombre es gratis y hace que leer un ticket (listado, detalle, modificaciones, a cargo) sea una operación puramente local, sin acoplamiento de lectura entre módulos ni respuestas indefinidas si un usuario desapareciera. *Alternativa descartada: resolver el nombre en cada respuesta vía el contrato de `identity`:* acopla toda lectura de tickets a `identity`, multiplica las consultas en el listado y deja un caso sin definir (usuario inexistente tras asignar). Supuesto: no existe borrado ni renombrado de usuarios en HU-01–HU-04; si HU-13 añade renombrado, se decidirá entonces si se muestra el nombre del momento o el vigente.

**D9. `get_assignable_ticket` es un caso de uso nuevo (solo administrador) y no se modifica `get_modifiable_ticket`.** La autorización de asignación es distinta (solo `administrador`, `ASSIGNMENT_ROLES`) y el código de resolución validado por HU-03 no se toca. *Alternativa descartada: parametrizar `get_modifiable_ticket` con roles admitidos:* cambia la firma y el contrato de una pieza ya validada y sus pruebas, sin ganancia funcional; la duplicación son cuatro comprobaciones explícitas.

**D10. La validación del técnico vive en `assign_ticket`, con la resolución inyectada como colaborador (`resolve_technician`).** La interfaz conecta ese colaborador a `get_technician_summary`; así el mensaje 422 uniforme (`assignee is not a valid technician`) para inexistente / no UUID / cliente / administrador es una regla de aplicación y `tickets` no importa infraestructura de `identity`. *Alternativas descartadas: (a) validar en el router:* regla de negocio en la interfaz, prohibida por la constitución; *(b) importar el repositorio de `identity` desde `tickets.application`:* acceso a estructuras internas.*

**D11. Registro de asignaciones como almacén aparte append-only (`InMemoryAssignmentLog`), con solo identificadores.** `Ticket` mantiene el estado vigente; el historial queda listo para HU-09, no se incrusta en la entidad y no se expone. *Alternativas descartadas: (a) lista dentro de `Ticket`:* mezcla auditoría con entidad; *(b) registrar también los no-ops:* ruido no pedido por RF-37 (ya descartado en HU-03 con el mismo criterio).*

**D12. Persistencia en memoria, sin dependencias nuevas ni control de concurrencia.** Se replica el patrón de HU-01–HU-03 (`InMemoryAssignmentLog` con singleton y `clear()`); el esquema PostgreSQL de la sección 3 queda como referencia orientativa para el futuro adaptador. *Alternativas descartadas: (a) introducir ahora SQLAlchemy + Alémbic + driver:* dependencias y alcance no autorizados; *(b) versionado optimista o bloqueos:* complejidad no exigida (NFR de la spec).*

## 5. Estrategia de pruebas (pytest + TestClient, sin frontend)

- Nuevos archivos en `backend/tests/`:
  - `test_assignment_domain.py` — `Ticket.assignee_id`/`assignee_name` nacen `None`, `ASSIGNMENT_ROLES` y `AssignmentRecord` (RF-34, RF-35.3, RF-37).
  - `test_assignment_log.py` — `InMemoryAssignmentLog` append-only: orden, `list_by_ticket`, `count`/`clear` y singleton (RF-37).
  - `test_identity_technicians.py` — contrato de aplicación y frontera: `list_technicians` (solo `tecnico`, `{id, name}`, sin correo; vacía válida; denegación para cliente/técnico) y `find_technician`/`get_technician_summary` (inexistente, cliente, administrador y no textual → `None`), con usuarios de `provision_user` (RF-31, RF-39.3).
  - `test_identity_technicians_api.py` — `GET /api/technicians`: 200 de administrador con solo `id` y `name`, 200 vacío, 401 sin sesión, 404 uniforme para cliente y técnico y parámetros de consulta desconocidos ignorados (RF-31).
  - `test_tickets_assign_access.py` — resolución y autorización: `get_assignable_ticket` (solo administrador; 404 uniforme del cliente y del técnico; id inválido/inexistente → 404; `Cerrado` → 409) y su traslado HTTP, incluida la precedencia con JSON sintácticamente inválido (RF-38, RF-39.4, RF-40).
  - `test_tickets_assign.py` — casos de uso y API de asignación: inicial, reasignación, repetición del mismo técnico (200 sin cambio ni registro), técnico inválido uniforme, cuerpo estricto, composición de la respuesta y registro (RF-32, RF-33, RF-37, RF-39).
  - `test_tickets_assigned_to_me.py` — `GET /api/assignments/mine`: 401, solo tickets asignados, cualquier estado incluido `Cerrado`, orden descendente, composición del resumen, colección vacía (cliente, administrador y técnico sin tickets), parámetros ignorados, reasignación entre listas y no regresión de HU-02 (RF-36).
  - `test_tickets_assignee_responses.py` — composición uniforme de `assignee` (`{id, name}` y `null`) en creación, listado, detalle, asignación y `PUT .../priority|status` de HU-03; cuerpo crudo (`response.text`) con el token `null`; sin correo ni credenciales (RF-35, RF-35.5; decisiones derivadas 6 y 7).
  - `test_tickets_assignment_sweep.py` — barrido RF-31 a RF-40 con mapa RF→test en cabecera, composición cruda, tabla de precedencia (incluido JSON inválido), invisibilidad del log, empates de fecha sin afirmar orden y «ningún 400 ni 403» (RF-31 a RF-40).
- Revisión obligada de pruebas existentes (T10): localizar con grep las aserciones de composición exacta (`set(body) ==`, conjuntos de campos por igualdad y comprobaciones de claves) en `test_tickets_create.py`, `test_tickets_detail.py`, `test_tickets_list.py`, `test_tickets_sweep.py`, `test_tickets_priority_responses.py`, `test_tickets_set_priority.py`, `test_tickets_update_status.py` y `test_tickets_modifications_sweep.py`, y actualizarlas para esperar `assignee` (objeto o `null`). Las pruebas que afirmen «el cuerpo no contiene X» solo se ajustan si X es `assignee`.
- Preparación de usuarios: cliente por `POST /api/auth/register` + login (HU-01); técnico y administrador por `provision_user(...)` + login real. Un `TestClient` por rol cuando coexistan sesiones (MEMORY: una sola cookie por cliente).
- Limpieza: fixture `autouse` por archivo que limpia `get_user_repository()`, `get_session_store()`, `get_ticket_repository()`, `get_ticket_modification_log()`, `get_assignment_log()` y cookies, antes y después de cada test (patrón de HU-02/HU-03, sin `conftest.py`).
- Cobertura RF por RF:
  - RF-31: directorio solo con `tecnico` (id + nombre, sin correo ni credenciales), colección vacía, 401 sin sesión, 404 uniforme para cliente y técnico, parámetros desconocidos ignorados.
  - RF-32: primera asignación 200 con el ticket actualizado (prioridad, estado, fecha y solicitante intactos) y registro con anterior vacío.
  - RF-33: reasignación 200 con registro del anterior; repetición del mismo técnico → 200 sin cambio ni registro; ticket `Cerrado` → 409 también al repetir el vigente.
  - RF-34: creación sin asignación (`assignee: null`, ambos campos `None`), técnico en el cuerpo de creación sigue 422 y ningún ticket se asigna solo.
  - RF-35 / RF-35.5: `assignee` en creación, listado, detalle, asignación y modificaciones de HU-03; cambia tras asignar y reasignar; sin datos personales distintos del nombre.
  - RF-36: a cargo solo los asignados, cualquier estado, orden descendente, resumen, colección vacía para los demás, parámetros ignorados y visibilidad de HU-02 intacta.
  - RF-37: contenido y acumulación del registro, ausencia en no-ops y en todas las respuestas y operaciones públicas, empates sin orden.
  - RF-38: cliente y técnico → 404 uniforme en todos los supuestos; el administrador asigna cualquier ticket (propio o ajeno, cualquier solicitante) y no existe autoasignación (administrador como destinatario → 422 uniforme).
  - RF-39: cuerpo ausente/nulo/no textual/extra/JSON inválido → 422; técnico inexistente/no UUID/cliente/administrador → 422 con el mismo mensaje; ticket inválido o inexistente → 404; cerrado → 409.
  - RF-40: 401 por delante de todo; orden 401 > 404 > 409 > 422 también con JSON sintácticamente inválido; técnicos exige sesión + administrador y a cargo solo sesión; sin 400 ni 403.
- TDD por tarea (test en rojo primero, luego el código mínimo hasta verde); `.venv\Scripts\python.exe -m pytest backend/tests/` desde la raíz en PowerShell, sin tuberías (no existe `tail`). Sin dependencias nuevas: `pytest`, `httpx` (TestClient), Pydantic y `argon2-cffi` ya están.

## 6. Dudas abiertas

Sin dudas abiertas pendientes: las decisiones 1–5 están confirmadas y las derivadas 6–7 (composición uniforme, incluida la creación con `assignee: null`) quedaron aprobadas con la spec. Supuestos de implementación (no son dudas): no hay borrado ni renombrado de usuarios en HU-01–HU-04, por lo que todo `assignee_id` asignado conserva su nombre de proyección; el orden de la lista de técnicos no se exige y las pruebas no lo afirman; los empates de fecha del registro no fijan orden.
