# Plan HU-06 — Gestionar información y detalle del ticket
Spec: `specs/features/HU-06-ticket-detail/spec.md` (implementada)
Estado: implementado

## 1. Alcance técnico

Backend únicamente, en memoria y sin dependencias nuevas, coherente con `identity`, `tickets`, `assignment` y `sla`. La historia no crea rutas: amplía `GET /api/tickets/{ticket_id}` con visibilidad por rol y añade `requester` y `resolved_at` a la respuesta completa de ticket. El cliente conserva el aislamiento de HU-02.

| RF | Dónde se cubre |
| --- | --- |
| RF-51 | `tickets/application/get_ticket.py` (`get_ticket_detail` con `MANAGEMENT_ROLES`) |
| RF-52 | `get_ticket_detail` (cliente: solo si es el solicitante) |
| RF-53 | `identity/application/user_summaries.py` + `identity/interface/users_contract.py` + `tickets/interface/router.py` |
| RF-54 | `tickets/interface/schemas.py` (`TicketResponse`) y composición en el router |
| RF-55 | Misma `TicketResponse` en creación, detalle, prioridad, estado y asignación; resúmenes intactos |
| RF-56 | `get_ticket_detail` + traducción de `TicketNotFoundError` a 404 en el router |
| RF-57 | `get_current_user` (sin cambios) precede al handler |
| RF-58 | Sin rutas ni permisos nuevos; los PUT de HU-03/HU-04 no cambian |
| RF-59 | `RequesterResponse` solo con `id`, `name` y `email`; resúmenes sin datos personales |
| RF-60 | `router.py` serializa fechas con `isoformat()`; la consulta no muta nada |

## 2. Estructura de archivos

```
backend/app/modules/identity/
  application/user_summaries.py      # UserSummary {id, name, email} + find_user_summary
  interface/users_contract.py        # get_user_summary(user_id) -> UserSummary | None

backend/app/modules/tickets/
  application/get_ticket.py          # + get_ticket_detail(ticket_id, actor_id, actor_role, tickets)
  interface/schemas.py               # + RequesterResponse; requester y resolved_at en TicketResponse
  interface/router.py                # _requester_response, _ticket_response ampliado, detalle con visibilidad
```

`values`/`assignment`: sin cambios. `identity/infrastructure/user_repository.py` ya expone `find_by_id`; no se toca.

## 3. Contrato HTTP

`GET /api/tickets/{ticket_id}` y el resto de respuestas completas de ticket pasan a devolver:

```json
{
  "id": "…",
  "title": "…",
  "description": "…",
  "priority": "Alta",
  "status": "En progreso",
  "assignee": {"id": "…", "name": "Ana Torres"},
  "requester": {"id": "…", "name": "Ana Pérez", "email": "ana@ejemplo.com"},
  "sla": { "target_minutes": 240, "…": "…" },
  "created_at": "2026-11-02T12:00:00.000000+00:00",
  "resolved_at": null,
  "requester_id": "…"
}
```

- `requester` es `null` si el usuario no se resuelve; `resolved_at` es `null` mientras el ticket no esté resuelto.
- `requester_id` se conserva (lo usan HU-02 y tests existentes) y no se elimina.
- Los resúmenes (`GET /api/tickets`, `GET /api/assignments/mine`) no cambian: `{id, title, priority, status, assignee, sla, created_at}`.
- Sin rutas, parámetros ni códigos nuevos; los errores siguen siendo `{"detail": "ticket not found"}` (404) y 401 de identidad.

## 4. Reglas y casos de uso

### 4.1 Contrato de `identity`

```python
@dataclass(frozen=True)
class UserSummary:
    id: str
    name: str
    email: str


def find_user_summary(user_id: object, users: InMemoryUserRepository) -> UserSummary | None:
    if not isinstance(user_id, str):
        return None
    user = users.find_by_id(user_id)
    if user is None:
        return None
    return UserSummary(id=user.id, name=user.name, email=user.email)
```

`users_contract.get_user_summary(user_id)` une `find_user_summary` con `get_user_repository()`. Nunca expone `User`, el hash ni el rol.

### 4.2 Visibilidad del detalle

```python
def get_ticket_detail(ticket_id, actor_id, actor_role, tickets) -> Ticket:
    if not is_valid_uuid_format(ticket_id):
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    ticket = tickets.find_by_id(ticket_id)
    if ticket is None:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    if actor_role not in MANAGEMENT_ROLES and ticket.requester_id != actor_id:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    return ticket
```

- `get_my_ticket` se conserva sin cambios (lo usan pruebas de HU-02 y sigue siendo la regla del cliente).
- `MANAGEMENT_ROLES` ya existe (`tecnico`, `administrador`); no se duplica el catálogo.
- El orden garantiza 404 uniforme y no revela la existencia de tickets ajenos a un cliente.
- La autenticación (401) sigue resolviéndose en la dependencia antes del handler (RF-57).

### 4.3 Composición

- `_requester_response(ticket)` llama a `get_user_summary(ticket.requester_id)` y devuelve `RequesterResponse` o `None`.
- `_ticket_response` añade `requester` y `resolved_at`; se mantiene el parámetro `now` para el SLA y los listados.
- No se resuelve el solicitante en los resúmenes: se evita una lectura adicional por elemento del listado.

## 5. Cambios en pruebas

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_identity_user_summaries.py` | unitario | RF-53: resumen de cualquier rol, `None` para id inexistente o no textual, sin rol ni hash |
| `tests/test_ticket_detail_visibility.py` | API + TestClient | RF-51, RF-52, RF-53, RF-56, RF-57: cliente propio/ajeno, técnico sin asignación, administrador, 404 para staff, 401 > 404, `requester` exacto y `null` si el usuario desaparece |
| `tests/test_tickets_detail_contract.py` | API + TestClient | RF-54, RF-55, RF-60: `resolved_at` nulo/fijado/descartado, `sla` presente o nulo, misma composición en creación/prioridad/estado/asignación, resúmenes sin `requester` ni `resolved_at` |
| Tests existentes | regresión | Añadir `requester` y `resolved_at` a los conjuntos exactos; reescribir las dos pruebas que hoy prohíben nombre/correo en el detalle (`test_tickets_detail.py`, `test_tickets_sweep.py`) para prohibir solo rol, contraseña, hash, token y sesión |

Archivos con conjuntos exactos a actualizar: `test_tickets_create.py`, `test_tickets_detail.py`, `test_tickets_list.py`, `test_tickets_sweep.py`, `test_tickets_set_priority.py`, `test_tickets_priority_responses.py`, `test_tickets_update_status.py`, `test_tickets_assignee_responses.py`, `test_tickets_assignment_sweep.py`, `test_tickets_assigned_to_me.py` (solo si cambia) y `test_tickets_modifications_sweep.py` (igualdades de diccionario completas).

Las pruebas de privacidad deben seguir afirmando que el cuerpo crudo no contiene `$argon2`, `Secreta123` ni el rol del solicitante; ahora sí contendrán el nombre y el correo del propio solicitante dentro de `requester`.

## 6. Contratos y dependencias

- Dirección: `tickets.interface` → `identity.interface.users_contract` → `identity.application.user_summaries` → `identity.infrastructure`. `identity` no conoce `tickets`.
- `tickets.application.get_ticket` importa `MANAGEMENT_ROLES` de su propio dominio; no toca otros módulos.
- Sin dependencia circular ni acceso a tablas de otros módulos. `assignment` y `sla` no cambian.

## 7. Riesgos y mitigaciones

- **Pruebas que prohíben datos personales:** dos pruebas afirman hoy la ausencia de `name`/`email`; se reescriben para el nuevo contrato sin perder las prohibiciones de rol, credenciales y hash.
- **Campo nuevo en muchas aserciones:** se actualizan todos los conjuntos exactos en una tarea dedicada y se ejecuta la suite antes de las pruebas nuevas.
- **Fallo al resolver el solicitante:** se devuelve `requester: null` en lugar de 500; el resto del detalle queda intacto.
- **Coste en listados:** el solicitante solo se resuelve en respuestas completas; los listados de resumen no lo hacen.
- **Confusión con «Todos los tickets»:** el plan no añade listados ni filtros; el detalle amplía únicamente la ruta existente.

## 8. Orden de implementación

1. Contrato de `identity` (`UserSummary`, `find_user_summary`, `get_user_summary`) con sus pruebas.
2. Caso de uso `get_ticket_detail` con pruebas unitarias de visibilidad y 404.
3. Esquemas y composición (`RequesterResponse`, `requester`, `resolved_at`) con pruebas de contrato.
4. Endpoint de detalle con `get_ticket_detail` y pruebas de API de visibilidad (cliente, técnico, administrador, 401 > 404).
5. Actualización de los conjuntos exactos y de las dos pruebas de privacidad (regresión).
6. Pruebas de `resolved_at` y de la misma composición en creación, prioridad, estado y asignación.
7. Suite completa con PostgreSQL, `codegraph sync`, `MEMORY.md` y `tasks.md` (documentado al terminar, como en HU-05).

## 9. Estimación

4 horas, repartidas en las tareas de 20-30 minutos del orden anterior.
