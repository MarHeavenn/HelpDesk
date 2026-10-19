# Plan HU-03 — Gestionar prioridad y estado del ticket

Spec base: `specs/features/HU-03-priority-status/spec.md` (Estado: aprobada, veredicto QA APROBADO, 10 RF: RF-21 a RF-30).
Sin frontend hasta acordar runner. Verificación solo backend con pytest + TestClient de FastAPI.

## 1. Módulos y capas afectadas

El cambio principal vive en el módulo `tickets` (`backend/app/modules/tickets/`). `identity` recibe **una única adición en `application/`** (la vía interna de alta controlada que la spec exige para verificar la historia y que será base de HU-04/HU-13), sin cambios en su router, sus esquemas ni su comportamiento existente. `backend/app/main.py` no cambia (el router de tickets ya está montado). `assignment` y `sla` no se tocan.

| Capa | Contenido | RF que cubre |
|---|---|---|
| `tickets/domain/` | Catálogos `PRIORITIES = ("Crítica", "Alta", "Media", "Baja")` y `STATUSES = ("Abierto", "En progreso", "Resuelto", "Cerrado")`; validadores `validate_priority`/`validate_status` (tipo cadena estricto y coincidencia exacta con el catálogo); `MANAGEMENT_ROLES = frozenset({"tecnico", "administrador"})`; `Ticket` gana `priority: str | None = None`; entidad de auditoría `TicketModification` (ticket, campo, valor anterior, valor nuevo, responsable, fecha y hora). | RF-21, RF-26, RF-27 |
| `tickets/application/` | `get_modifiable_ticket` (resolución y permiso: rol de gestión → 404; formato/existencia → 404; ticket cerrado → `TicketClosedError`), `set_ticket_priority` y `update_ticket_status` (catálogo → `TicketValidationError`; valor repetido → sin cambio ni registro; cambio efectivo → muta el ticket y añade el registro). Reutiliza `TicketNotFoundError` y `TicketValidationError` existentes. | RF-22 a RF-26, RF-28, RF-29 |
| `tickets/infrastructure/` | `InMemoryTicketModificationLog` append-only (`add`, `list_by_ticket`, `count`, `clear`, singleton `get_ticket_modification_log()`; patrón de `InMemorySessionStore`). `InMemoryTicketRepository` sin cambios de contrato (los tickets guardados ganan `priority`). | RF-26 |
| `tickets/interface/` | Rutas `PUT /api/tickets/{ticket_id}/priority` y `PUT /api/tickets/{ticket_id}/status`; esquemas `SetPriorityRequest`/`SetStatusRequest` (`extra="forbid"`, `StrictStr`) y campo `priority: str | None` en `TicketResponse` y `TicketSummaryResponse`; dependencia que invoca `get_modifiable_ticket` y traduce `TicketNotFoundError` → 404 y `TicketClosedError` → 409. Solo comunica. | RF-21 a RF-30 (códigos y contrato HTTP) |
| `identity/application/` | `provision_user`: alta controlada de usuarios con rol `tecnico`/`administrador`, sin operación pública y reutilizando `validate_name`, `validate_password`, `EmailValidator`, `Argon2PasswordHasher` y la unicidad de email existentes. | Soporte de verificación de RF-24 |

## 2. Contratos entre módulos y contrato HTTP

**Contrato reutilizado de `identity`:** la dependencia `get_current_user` → `{id, email, role}` o 401. `tickets` usa `current["id"]` (responsable de la modificación) y ahora también `current["role"]` (autorización); ninguno proviene del cuerpo. Sin acceso a estructuras internas de `identity`.

**Alta controlada (contrato de aplicación, no HTTP):** `provision_user(name, email, password, role, users, hasher=None, validator=None) -> User` en `identity/application/`, con roles admitidos exactamente `tecnico` y `administrador` (sin acentos ni mayúsculas). No expone endpoint: el router de `identity` no cambia. Las pruebas de HU-03 la usan para preparar usuarios de gestión y después inician sesión con `POST /api/auth/login` (sesión real), sin construir entidades ni tocar repositorios más allá de los getters ya usados por los fixtures de limpieza.

**Contrato HTTP (cierra lo diferido en la spec):**

- `PUT /api/tickets/{ticket_id}/priority` — cuerpo `{"priority": <valor>}` (`extra="forbid"`, `StrictStr`) → **200** con el ticket completo actualizado `{id, title, description, priority, status, created_at, requester_id}` (RF-22); **422** si el valor falta, el tipo no es texto, hay campos extra o el valor no pertenece al catálogo (RF-21, RF-29); **401/404/409** según la precedencia de abajo.
- `PUT /api/tickets/{ticket_id}/status` — cuerpo `{"status": <valor>}` con las mismas reglas → **200** con el ticket actualizado (RF-23); mismos rechazos.
- `GET /api/tickets` y `GET /api/tickets/{ticket_id}` — composición ampliada: resumen `{id, title, priority, status, created_at}` y detalle `{id, title, description, priority, status, created_at, requester_id}`; `priority` es `null` mientras no se fije (RF-27). `POST /api/tickets` responde 201 con la composición del detalle (`priority: null`) — decisión D5.
- Cuerpo de error consistente `{"detail": <mensaje>}`; códigos de la historia: 200 y 201 en los caminos válidos y 401/404/409/422 en los rechazos (sin 400 ni 403). El 404 de permiso, formato o inexistencia reutiliza el **mismo mensaje y cuerpo** del 404 unificado de HU-02 (`ticket not found`); el 409 usa `ticket is closed`.
- **Precedencia 401 > 404 > 409 > 422, implementada con dependencias:** `get_current_user` (401) y la dependencia que invoca `get_modifiable_ticket` —permiso de rol (404 uniforme), formato/existencia (404), cerrado (409), en ese orden— se resuelven **antes** del cuerpo de la petición, igual que en HU-02 el 401 se resuelve antes que el 422; después se valida la forma del cuerpo (Pydantic) y el catálogo (caso de uso). Resultado: un cliente recibe 404 aunque el cuerpo sea inválido; inexistente o id inválido → 404; cerrado → 409 incluso con entrada inválida; solo un ticket existente, no cerrado y con cuerpo bien formado llega al 422 del catálogo.
- `ticket_id` se declara como `str` (no `uuid.UUID`) para que un identificador mal formado devuelva 404 y nunca 422 (misma razón que en HU-02).
- **El registro de modificaciones no tiene operación pública** y no aparece en ningún cuerpo de respuesta (RF-26).

## 3. Modelo de datos

**Modelo lógico (contrato de persistencia; en memoria en HU-03, D8):**
- `Ticket`: `id`, `title`, `description`, `priority` (`None` o valor del catálogo), `status` (`Abierto`/`En progreso`/`Resuelto`/`Cerrado`), `requester_id`, `created_at`.
- `TicketModification`: `ticket_id`, `field` (`priority`/`status`), `previous_value` (`None` en la primera prioridad), `new_value`, `actor_id` (identificador opaco de la sesión), `changed_at` (instante UTC generado por el sistema). Empates de `changed_at`: sin orden garantizado entre registros (la spec lo exige; las pruebas no afirmarán orden).

**Esquema destino PostgreSQL (orientativo y diferido, no entregable; coherente con HU-02 y `infra/docker-compose.yml`):**

| Tabla.columna | Tipo | Restricción |
|---|---|---|
| `tickets.priority` | `text` | `NULL` permitido; `CHECK (priority IS NULL OR priority IN ('Crítica','Alta','Media','Baja'))` |
| `tickets.status` | `text` | `NOT NULL`; `CHECK (status IN ('Abierto','En progreso','Resuelto','Cerrado'))` (HU-02 difirió el catálogo a HU-03: queda fijado aquí) |
| `ticket_modifications.id` | `uuid` | `PRIMARY KEY` (clave técnica de la tabla futura; el objeto en memoria no la necesita) |
| `ticket_modifications.ticket_id` | `uuid` | `NOT NULL` (referencia interna del módulo `tickets`) |
| `ticket_modifications.field` | `text` | `NOT NULL`, `CHECK (field IN ('priority','status'))` |
| `ticket_modifications.previous_value` | `text` | `NULL` (primera asignación de prioridad) |
| `ticket_modifications.new_value` | `text` | `NOT NULL` |
| `ticket_modifications.actor_id` | `uuid` | `NOT NULL`, valor del contrato de `identity` sin clave foránea |
| `ticket_modifications.changed_at` | `timestamptz` | `NOT NULL` |

Índice `(ticket_id, changed_at)` para el historial de HU-09. Migración diferida: sin SQLAlchemy/Alémbic/driver, sin dependencias nuevas y sin tocar PostgreSQL en esta historia (D8).

## 4. Decisiones justificadas (con alternativa descartada)

**D1. Dos operaciones separadas `PUT` sobre subrecursos (`/priority` y `/status`), cada una con un cuerpo de un único campo.** Cada criterio de la historia es una capacidad independiente con su propio registro (`field`), y el cuerpo estrictamente mono-campo hace imposible mezclar ambas en una petición. *Alternativas descartadas: (a) un único `PATCH /api/tickets/{ticket_id}`* que acepte uno de los dos campos: exigiría una regla "exactamente uno de los dos" y difuminaría la correspondencia RF↔operación; *(b) `POST` de acción (`/set-priority`):* sin precedente en HU-02 y semántica menos idempotente; *(c) el valor en la ruta (`/priority/{valor}`):* los valores llevan acentos y espacios (`Crítica`, `En progreso`) y ensuciarán la ruta; el `PUT` es idempotente y "repite el mismo valor → 200 sin cambio" encaja con su semántica.

**D2. La precedencia 401 > 404 > 409 > 422 se implementa con dependencias que invocan casos de uso (patrón `get_current_user` → `get_current_identity`).** Las dependencias se resuelven antes que el cuerpo (comportamiento ya verificado en HU-02 para 401 > 422); la dependencia de modificación aplica, en orden, permiso de rol (404 uniforme), formato/existencia (404) y estado cerrado (409); después se valida la forma del cuerpo (Pydantic) y el catálogo (caso de uso). *Alternativas descartadas: (a) cuerpo como `dict` crudo validado dentro del caso de uso:* movería la validación de forma HTTP a la capa de negocio, contra el patrón de HU-01/HU-02; *(b) validar primero con Pydantic y resolver después:* daría 422 > 404/409 y contradiría RF-30 y sus casos límite.

**D3. `priority: str | None = None` y `null` en JSON como representación de "no fijada".** Es inequívocamente distinguible de los cuatro valores del catálogo (cadenas no nulas) y es el valor natural de Pydantic y de SQL (`NULL`). *Alternativas descartadas: omitir el campo* (el consumidor no distingue "sin prioridad" de "respuesta antigua"); *cadena vacía* (`""` sigue siendo texto presente); *centinela `"Sin prioridad"`* (introduce un quinto valor en el espacio del catálogo, con riesgo de confusión en SLA y filtros futuros).

**D4. Registro de modificaciones como almacén aparte append-only (`InMemoryTicketModificationLog`), no como historial incrustado en `Ticket`.** `Ticket` mantiene solo el estado vigente; el historial es una colección ordenada por registro que HU-09 podrá consultar sin acoplarse al repositorio de tickets (mismo patrón que `InMemorySessionStore`). Solo se registran cambios efectivos (RF-26). *Alternativas descartadas: (a) lista de cambios dentro de `Ticket`:* mezcla auditoría con entidad y complica la tabla futura; *(b) registrar también los no-ops:* ruido en el historial que la spec no pide.

**D5. Composición uniforme del ticket: `TicketResponse` gana `priority` en creación, detalle y modificación, y `TicketSummaryResponse` también.** Un solo esquema de "información completa del ticket" evita dos formas divergentes del mismo recurso y permite reutilizar el serializador existente; la creación responde `priority: null` sin cambiar su comportamiento (sigue naciendo `Abierto` y sin prioridad, y sigue rechazando `priority` en el cuerpo con 422). *Alternativa descartada: mantener la creación con los seis campos de HU-02 y añadir la prioridad solo a detalle/listado:* parte la representación del mismo recurso en dos contratos, impide reutilizar `_ticket_response` y confunde al consumidor. Queda anotada como decisión derivada revisable (sección 6).

**D6. Alta controlada como función nueva `provision_user` en `identity/application/`, sin endpoint.** Reutiliza validaciones, validador de email, hash Argon2 y unicidad existentes, y admite exactamente `tecnico`/`administrador`. *Alternativa descartada: generalizar `register_user` con un parámetro de rol:* cambiaría el comportamiento y el contrato 422 del autorregistro de HU-01 (que debe seguir exigiendo `cliente`). Los valores de rol son vocabulario estable; `tickets` mantiene su propia lista `MANAGEMENT_ROLES` (política de autorización del módulo) sin importar código interno de `identity`.

**D7. Catálogo validado en dominio/aplicación (`validate_priority`/`validate_status`), no con `Literal`/`Enum` de Pydantic.** Una sola fuente de verdad (el catálogo lo usan casos de uso, SLA futuro y esquema destino) y mensajes de error homogéneos con HU-02. *Alternativa descartada: `Literal["Crítica", ...]` en el esquema HTTP:* duplica el catálogo en la capa de comunicación, lo pone en la interfaz (contra la constitución 3) y amplía el formato de error mixto ya aceptado en HU-02 sin necesidad.

**D8. Persistencia en memoria, sin dependencias nuevas ni control de concurrencia.** Se replica el patrón de HU-01/HU-02 (`InMemoryTicketModificationLog` con singleton y `clear()`); el esquema PostgreSQL de la sección 3 queda como referencia orientativa para el futuro adaptador. Las operaciones se aplican en el orden en que se atienden (modelo de referencia, sin transacciones, bloqueos ni versionado; NFR de la spec): la última escritura aplicada prevalece y cada cambio efectivo se registra. *Alternativas descartadas: (a) introducir ahora SQLAlchemy + Alembic + driver:* dependencias no autorizadas y alcance fuera de la historia (ya descartado igualmente en HU-02); *(b) versionado optimista o bloqueos:* complejidad no exigida por los criterios de aceptación.

## 5. Estrategia de pruebas (pytest + TestClient, sin frontend)

- Nuevos archivos en `backend/tests/`:
  - `test_auth_provisioning.py` — alta controlada en `identity`: roles admitidos, reutilización de validaciones y unicidad, login real del usuario creado y ausencia de endpoint público (soporte de RF-24).
  - `test_tickets_modifications_domain.py` — catálogos y validadores, `Ticket.priority` nace `None`, `TicketModification` y el log en memoria (RF-21, RF-26, RF-27).
  - `test_tickets_set_priority.py` — caso de uso y `PUT .../priority` (RF-22, RF-26, RF-29).
  - `test_tickets_update_status.py` — caso de uso y `PUT .../status`, con transiciones libres incluidas saltos y retrocesos (RF-23, RF-26, RF-29).
  - `test_tickets_modify_access.py` — permisos y resolución: cliente 404 uniforme con cualquier cuerpo, cualquier ticket del sistema para técnicos/administradores, 404 de inexistente/id inválido y 409 de cerrado (RF-24, RF-25, RF-28, RF-30).
  - `test_tickets_priority_responses.py` — composiciones: `priority` `null` y con valor en listado, detalle y creación; creación sin cambios de comportamiento (RF-27).
  - `test_tickets_modifications_sweep.py` — barrido RF-21 a RF-30 con el mapa RF→test en la cabecera, composición cruda (`response.text`), tabla de precedencia y "ningún 400 ni 403".
- Preparación de usuarios: cliente por `POST /api/auth/register` + login (HU-01); técnico y administrador por `provision_user(...)` + login real. Dos clientes con cookies propias para las pruebas de coexistencia (cliente + técnico).
- Limpieza: fixture `autouse` por archivo que limpia `get_user_repository()`, `get_session_store()`, `get_ticket_repository()`, `get_ticket_modification_log()` y cookies, antes y después de cada test (patrón de HU-02, sin `conftest.py` compartido).
- Cobertura RF por RF: catálogos exactos y 422 de valores fuera, no textuales, ausentes o con campos extra (RF-21, RF-29); fijar prioridad 200 con el ticket actualizado y registro (RF-22); transiciones libres con registro y no-op sin registro (RF-23); autorización por rol sobre cualquier ticket y 404 uniforme del cliente (RF-24); 404 de inexistente/id inválido (RF-25); contenido, orden y valor anterior vacío del registro, e invisibilidad en las respuestas (RF-26); `priority` en listado/detalle con `null` y con valor, y creación intacta (RF-27); cerrado 409 incluso con el valor vigente o entrada inválida (RF-28); precedencia 401 > 404 > 409 > 422 y no revelación (RF-30).
- Revisión obligada de pruebas de HU-02 (tarea T9): las afirmaciones de inmutabilidad de `status` en `test_tickets_sweep.py` y `test_tickets_isolation.py` se ajustan al alcance de HU-02 (el estado deja de ser globalmente inmutable), y las composiciones exactas de `test_tickets_create.py`, `test_tickets_detail.py`, `test_tickets_list.py` y `test_tickets_sweep.py` pasan a esperar `priority`, porque RF-23 y RF-27 cambian ese contrato.
- TDD por tarea (test en rojo primero, luego el código mínimo hasta verde); `pytest backend/tests/` en PowerShell sin tuberías (no existe `tail`). Sin dependencias nuevas: `pytest`, `httpx` (TestClient), Pydantic y `argon2-cffi` ya están.

## 6. Dudas abiertas

Sin dudas abiertas pendientes. La decisión derivada D5 (la respuesta de creación también incluye `priority: null`, por composición uniforme) queda anotada para revisión del reviewer; si se prefiere la lectura literal de RF-27.2, se separaría únicamente el esquema de creación sin alterar nada más.
