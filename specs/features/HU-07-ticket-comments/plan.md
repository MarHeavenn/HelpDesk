# Plan HU-07 — Registrar seguimiento y comentarios del ticket
Spec: `specs/features/HU-07-ticket-comments/spec.md` (implementada)
Estado: implementado

## 1. Alcance técnico

Backend únicamente, dentro del módulo `tickets`, en memoria y sin dependencias nuevas. La historia añade un subrecurso de comentarios al ticket y reutiliza la visibilidad de HU-06 para leer el seguimiento. No modifica `TicketResponse` ni los contratos de HU-02 a HU-06.

| RF | Dónde se cubre |
| --- | --- |
| RF-61 | `create_comment` + `POST /api/tickets/{ticket_id}/comments` |
| RF-62 | `validate_comment_body` en `tickets/domain` + `CreateCommentRequest` |
| RF-63 | `InMemoryTicketCommentRepository.list_by_ticket` + `GET .../comments` |
| RF-64 | `get_ticket_detail` reutilizado por `list_comments` |
| RF-65 | `get_commentable_ticket` (rol de gestión) + traducción a 404 |
| RF-66 | `get_commentable_ticket` (estado `Cerrado` -> 409) |
| RF-67 | `_author_response` con el contrato de `identity` |
| RF-68 | `CommentResponse` solo en el subrecurso; `TicketResponse` intacto |
| RF-69 | Sin endpoints de edición/borrado; casos de uso de solo lectura |
| RF-70 | `_json_body` como última dependencia; UUID y `isoformat()` |

## 2. Estructura de archivos

```
backend/app/modules/tickets/
  domain/entities.py                       # + TicketComment, validate_comment_body
  infrastructure/ticket_comment_repository.py
  application/get_commentable_ticket.py    # visibilidad HU-06 + permiso de escritura + 409
  application/create_comment.py            # validación + UUID + created_at + persistencia
  application/list_comments.py             # visibilidad HU-06 + listado ascendente
  interface/schemas.py                     # + CreateCommentRequest, AuthorResponse, CommentResponse
  interface/comments_router.py             # POST y GET /api/tickets/{ticket_id}/comments

backend/app/main.py                        # incluye comments_router
```

`identity`, `assignment` y `sla` no cambian. `tickets/interface/comments_router.py` reutiliza los helpers de cuerpo JSON de `tickets/interface/router.py` (`_json_body`, `_json_body_documentation`) para mantener la precedencia 401 > 404 > 409 > 422.

## 3. Contrato HTTP

### Crear comentario

```http
POST /api/tickets/{ticket_id}/comments
Content-Type: application/json

{"body": "  Se revisó el acceso y se reinició el servicio.  "}
```

```json
201 Created
{
  "id": "8a1f...",
  "ticket_id": "6b2c...",
  "body": "Se revisó el acceso y se reinició el servicio.",
  "author": {"id": "u-1", "name": "Ana Torres"},
  "created_at": "2026-11-02T15:30:00.123456+00:00"
}
```

- El autor procede de la sesión; el cliente no puede enviar `author_id`, `created_at` ni ningún campo adicional.
- `body` se recorta con `strip()` y se valida entre 1 y 2000 code points.
- `author` es `null` si el usuario no se resuelve; nunca incluye correo, rol, credenciales ni hash.

### Listar comentarios

```http
GET /api/tickets/{ticket_id}/comments
```

```json
200 OK
[
  {
    "id": "8a1f...",
    "ticket_id": "6b2c...",
    "body": "Primer avance",
    "author": {"id": "u-1", "name": "Ana Torres"},
    "created_at": "2026-11-02T14:00:00.000000+00:00"
  }
]
```

- Lista completa, sin paginación ni filtros, ordenada por `created_at` ascendente.
- Un empate de `created_at` conserva el orden de registro (el repositorio usa un `dict` y un `sort` estable).
- Ticket sin comentarios: `200 []`.

### Errores

- `401` sin sesión válida, antes que cualquier otra comprobación.
- `404 {"detail": "ticket not found"}` para ticket inexistente, identificador inválido, cliente sin visibilidad o cliente que intenta escribir.
- `409 {"detail": "ticket is closed"}` al crear en un ticket `Cerrado`; el listado del mismo ticket sigue devolviendo 200.
- `422` por cuerpo ausente, no JSON, no textual, vacío tras recorte, fuera de 1-2000 o con campos extra.
- Sin rutas, códigos ni mensajes nuevos fuera de estos.

## 4. Reglas y casos de uso

### 4.1 Dominio

```python
COMMENT_MIN_LENGTH = 1
COMMENT_MAX_LENGTH = 2000

@dataclass
class TicketComment:
    id: str
    ticket_id: str
    author_id: str
    body: str
    created_at: datetime


def validate_comment_body(raw: object) -> str:
    return _validate_text(
        raw, field="body", min_length=1, max_length=2000
    )
```

Reutiliza `_validate_text`, que ya aplica tipo estricto, recorte `strip()`, límite en code points y devuelve el valor que debe almacenarse. No se duplica la semántica de HU-02.

### 4.2 Resolución del ticket para escribir

```python
def get_commentable_ticket(ticket_id, actor_id, actor_role, tickets) -> Ticket:
    ticket = get_ticket_detail(ticket_id, actor_id, actor_role, tickets)  # 404 HU-06
    if not isinstance(actor_role, str) or actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if ticket.status == CLOSED_STATUS:
        raise TicketClosedError(TICKET_CLOSED_MESSAGE)
    return ticket
```

- Un cliente nunca escribe: el rol se comprueba antes de devolver el ticket, aunque el ticket sea suyo; recibe el 404 uniforme (RF-65).
- Se reutiliza `TicketClosedError`/`TICKET_CLOSED_MESSAGE` de `get_modifiable_ticket` para no duplicar el contrato del 409 (RF-66).
- La visibilidad y el 404 vienen de `get_ticket_detail`, sin reimplementar la regla de HU-06 (RF-64).

### 4.3 Crear comentario

```python
def create_comment(ticket, body, author_id, comments, now=None) -> TicketComment:
    clean_body = validate_comment_body(body)      # -> TicketValidationError
    comment = TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=ticket.id,
        author_id=author_id,
        body=clean_body,
        created_at=now or datetime.now(timezone.utc),
    )
    comments.add(comment)
    return comment
```

- El ticket ya llega resuelto y autorizado desde `get_commentable_ticket`.
- Solo se toca el repositorio de comentarios; el ticket no se muta (RF-69).

### 4.4 Listar comentarios

```python
def list_comments(ticket_id, actor_id, actor_role, tickets, comments):
    get_ticket_detail(ticket_id, actor_id, actor_role, tickets)  # 404 HU-06
    return comments.list_by_ticket(ticket_id)
```

- La lectura no exige rol de gestión ni comprueba el estado cerrado (RF-63/RF-66).
- El repositorio filtra por `ticket_id` y ordena de forma estable por `created_at`.

### 4.5 Repositorio en memoria

```python
class InMemoryTicketCommentRepository:
    add(comment)
    list_by_ticket(ticket_id) -> list[TicketComment]  # asc, empate = registro
    count()
    clear()

def get_ticket_comment_repository() -> InMemoryTicketCommentRepository
```

Mismo patrón que `InMemoryTicketRepository` y los registros de asignación/modificación. El `dict` interno conserva el orden de inserción; `sort(key=created_at)` es estable, por lo que los empates mantienen ese orden.

### 4.6 Composición de la respuesta

- `_author_response(comment)` llama a `get_user_summary(comment.author_id)` (contrato existente de `identity`) y proyecta solo `id` y `name` en `AuthorResponse`; si devuelve `None`, el autor es `null`. No se crea un contrato nuevo de identidad para no duplicar `UserSummary`.
- `_comment_response(comment)` serializa `id`, `ticket_id`, `body`, `author` y `created_at.isoformat()`.
- `TicketResponse` y `ticket_summary` no cambian.

### 4.7 Rutas

- `POST /{ticket_id}/comments`: dependencias en orden `get_current_user` (401), `_commentable_ticket` (404/409) y `_comment_body` (422); traduce `TicketClosedError` a 409 y `TicketNotFoundError` a 404. Responde 201.
- `GET /{ticket_id}/comments`: solo sesión; el caso de uso resuelve la visibilidad y traduce el 404. Responde 200.
- `tickets/interface/comments_router.py` usa el mismo prefijo `/api/tickets` y se registra en `main.py`; sus rutas tienen un segmento más que `GET /{ticket_id}`, por lo que no compiten con el detalle.

## 5. Cambios en pruebas

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_ticket_comments_domain.py` | unitario | RF-62, RF-63: validación y recorte, límites 2000/2001, tipos estrictos, entidad, orden ascendente, empate estable, aislamiento por ticket, `clear` |
| `tests/test_ticket_comments_creation.py` | API + TestClient | RF-61, RF-62, RF-65, RF-66, RF-67, RF-70: técnico y administrador crean; autor de sesión; cuerpo recortado; 404 de cliente; 409 en cerrado; 422 de cuerpo inválido/campos extra; 404 de ticket inválido/inexistente; 401 antes que 404/409/422; ticket y SLA sin cambios |
| `tests/test_ticket_comments_listing.py` | API + TestClient | RF-63, RF-64, RF-67, RF-68, RF-69: lista vacía, orden cronológico, empate, aislamiento entre tickets, cliente propio, staff con cualquier ticket, 404 uniforme, parámetros desconocidos, `author` exacto y `null`, sin correo/rol/hash, ticket cerrado con 200 |
| `tests/test_ticket_comments_flow.py` | API + TestClient | RF-61 a RF-70: flujo completo crear ticket -> asignar -> prioridad -> comentar (técnico y administrador) -> leer como cliente -> comprobar detalle/SLA intactos -> cerrar -> 409 al comentar y lectura todavía disponible |

Los tests existentes no deberían cambiar: el contrato de ticket queda intacto y el subrecurso es nuevo. Se ejecutará la suite completa para confirmarlo.

## 6. Contratos y dependencias

- Dirección: `tickets.interface.comments_router` -> `tickets.application` -> `tickets.domain` / `tickets.infrastructure`; la resolución del autor va de `tickets.interface` a `identity.interface.users_contract` -> `identity.application.user_summaries`.
- `identity` no conoce `tickets`; `tickets` no importa el repositorio de usuarios.
- `comments_router` reutiliza helpers de `tickets/interface/router.py` dentro de la misma capa; no hay ciclo porque `router.py` no importa `comments_router`.
- `assignment` y `sla` no cambian.

## 7. Riesgos y mitigaciones

- **Precedencia de errores:** el cuerpo se lee en una dependencia declarada al final; así 401, 404 y 409 prevalecen sobre 422, como en HU-03/HU-04.
- **Cliente que intenta escribir en su propio ticket:** `get_commentable_ticket` comprueba el rol después de la visibilidad y devuelve el mismo 404, sin 403.
- **Empates de fecha:** el `sort` estable sobre un `dict` de inserción mantiene el orden de registro; se prueba explícitamente.
- **Fuga de datos del autor:** `AuthorResponse` solo tiene `id` y `name`; los tests revisan el cuerpo crudo para descartar correo, rol y credenciales.
- **Contrato de ticket intacto:** no se añade `comments` a `TicketResponse`; las pruebas de conjunto exacto de HU-02 a HU-06 deben seguir pasando sin cambios.
- **Conflicto de rutas:** el subrecurso tiene un segmento más; se verifica con la suite existente y con el flujo completo.
- **Autor eliminado:** `author` es `null` y el comentario se conserva; se prueba insertando un comentario con un `author_id` inexistente.

## 8. Orden de implementación

1. Dominio (`TicketComment`, `validate_comment_body`) y repositorio en memoria, con pruebas unitarias.
2. Casos de uso `get_commentable_ticket`, `create_comment` y `list_comments`, con pruebas de aplicación.
3. Esquemas y router de comentarios; registro en `main.py`; pruebas de API de creación.
4. Pruebas de API de listado y privacidad.
5. Prueba de flujo completo e integración con HU-02/HU-04/HU-05/HU-06.
6. Suite completa con PostgreSQL, `codegraph sync`, `MEMORY.md`, `specs/project.md` y `tasks.md` (documentado al terminar).

## 9. Estimación

5 horas, repartidas en las tareas de 20-30 minutos del orden anterior.
