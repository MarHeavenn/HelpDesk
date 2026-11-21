# Plan HU-15 — Notificaciones de tickets
Spec: `specs/features/HU-15-ticket-notifications/spec.md` (aprobada)
Estado: implementado

## 1. Enfoque

HU-15 añade un **centro de notificaciones interno** dentro del módulo `tickets`. No se crea un módulo nuevo: las notificaciones son un subproducto de los eventos del ticket y comparten su ciclo de vida y su persistencia en memoria.

La generación se hace en la capa `application` mediante una función `notify_ticket_event`, que recibe el ticket ya mutado, el tipo de evento y el actor. Las reglas de destinatarios (solicitante, técnico asignado, sin notificar al actor ni duplicar) viven en esa función. Los casos de uso existentes (`assign_ticket`, `update_ticket_status`, `reopen_ticket`) reciben un colaborador opcional `notify` y lo invocan **solo después** de haber aplicado el cambio y registrado su evento de origen. Los routers componen pasando `notify_ticket_event`; los tests unitarios de esas historias siguen sin generar notificaciones si no inyectan el colaborador.

Se descartan dos alternativas:

1. **Derivar notificaciones del historial de HU-09 al consultar.** No permite distinguir “leída/no leída” por destinatario ni saber qué avisos existían antes de la funcionalidad; además mezclaría auditoría con bandeja de entrada.
2. **Crear un módulo `notifications`.** Añadiría un sexto módulo, contratos cruzados y complejidad de composición para un MVP que solo notifica eventos de ticket. La spec fija que viva en `tickets`.

La interfaz solo traduce errores y serializa. La resolución de nombres se hace con el contrato público `identity/interface/users_contract.py` (`get_user_summary`), nunca con las estructuras internas de identidad.

## 2. Backend

### 2.1 Dominio — `backend/app/modules/tickets/domain/entities.py`

Constantes:

```python
NOTIFICATION_TYPE_ASSIGNED = "ticket_assigned"
NOTIFICATION_TYPE_REASSIGNED = "ticket_reassigned"
NOTIFICATION_TYPE_STATUS_CHANGED = "ticket_status_changed"
NOTIFICATION_TYPE_RESOLVED = "ticket_resolved"
NOTIFICATION_TYPE_REOPENED = "ticket_reopened"
NOTIFICATION_TYPES = frozenset({...})

# Roles que supervisan todas las notificaciones de su empresa.
NOTIFICATION_VIEW_ALL_ROLES = frozenset({"administrador", "supervisor"})
```

Entidad mutable (solo `read_at` cambia):

```python
@dataclass
class TicketNotification:
    id: str
    company_id: str | None
    recipient_id: str
    ticket_id: str
    ticket_title: str
    type: str
    actor_id: str
    previous_value: str | None = None
    new_value: str | None = None
    created_at: datetime = ...
    read_at: datetime | None = None
```

`company_id` no se expone por HTTP; sirve para el aislamiento multitenant de la supervisión.

### 2.2 Aplicación

#### `tickets/application/notify_ticket_event.py`

```python
def notify_ticket_event(
    *,
    event_type: str,
    ticket: Ticket,
    actor_id: str,
    previous_value: str | None = None,
    new_value: str | None = None,
    notifications: InMemoryNotificationRepository | None = None,
    now: datetime | None = None,
) -> list[TicketNotification]:
```

Reglas:

1. Valida que `event_type` pertenezca a `NOTIFICATION_TYPES`; un valor desconocido es un error de programación (`ValueError`) y no registra nada.
2. Destinatarios en orden: `ticket.requester_id` y `ticket.assignee_id`; se omiten `None`, el `actor_id` y los duplicados.
3. Por cada destinatario crea un `TicketNotification` con UUID nuevo, `company_id` del ticket, título del ticket, tipo, actor, valores anterior/nuevo y `created_at` UTC.
4. Añade al repositorio y devuelve las creadas.
5. No crea notificaciones si la lista de destinatarios queda vacía (por ejemplo, el actor es el único implicado).

La función no conoce HTTP ni identidad; solo copia identificadores.

#### `tickets/application/list_notifications.py`

```python
def list_notifications(
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    notifications: InMemoryNotificationRepository,
) -> list[TicketNotification]:
```

- `administrador` y `supervisor`: `notifications.list_by_company(actor_company_id)`.
- `tecnico` y `cliente`: `notifications.list_by_recipient(actor_id)`.
- Cualquier otro rol: lista dirigida al actor (defensivo; la sesión ya valida el rol).
- Orden: más reciente primero, con desempate por orden de registro descendente.

#### `tickets/application/notification_reads.py`

```python
NOTIFICATION_NOT_FOUND_MESSAGE = "notification not found"

class NotificationNotFoundError(ValueError): ...

def count_unread(actor_id, notifications) -> int
def mark_notification_read(notification_id, actor_id, notifications, now=None) -> TicketNotification
def mark_all_notifications_read(actor_id, notifications, now=None) -> int
```

- `mark_notification_read`: valida formato UUID con `is_valid_uuid_format`; busca; exige `notification.recipient_id == actor_id`; si no, lanza `NotificationNotFoundError`. Es idempotente: si ya tiene `read_at`, no lo cambia.
- `mark_all_notifications_read`: recorre solo las del actor, fija `read_at` en las pendientes y devuelve cuántas actualizó. No toca las de otros.
- `count_unread`: cuenta solo las del actor, incluido administrador/supervisor.

### 2.3 Infraestructura — `tickets/infrastructure/notification_repository.py`

`InMemoryNotificationRepository` con lista en orden de alta:

- `add(notification)`
- `list_by_recipient(recipient_id)`
- `list_by_company(company_id)`
- `find_by_id(notification_id)`
- `count()`
- `clear()`

La ordenación se hace con `(created_at, índice_de_alta)` descendente para que dos notificaciones del mismo instante mantengan un orden reproducible. `list_by_company` compara `company_id` con `==`, de modo que el ámbito sin empresa (`None`) también funciona.

Singleton `get_notification_repository()`.

### 2.4 Casos de uso de ticket

Se añade un parámetro opcional al final, para no romper llamadas ni pruebas existentes:

- `assign_ticket(..., now=None, notify=None)`.
  - Captura `previous_assignee_name = ticket.assignee_name` antes de mutar.
  - Tras `assignments.add(...)`, si `notify` no es `None`, llama con `event_type = ticket_assigned` si `previous_assignee_id is None`, si no `ticket_reassigned`; `previous_value` es el nombre anterior y `new_value` el nuevo.
- `update_ticket_status(..., now=None, notify=None)`.
  - Tras `modifications.add(...)`, elige el tipo:
    - `new_status == RESOLVED_STATUS` → `ticket_resolved`;
    - `previous_status == CLOSED_STATUS and new_status == OPEN_STATUS` → `ticket_reopened` (defensivo; el router ya rechaza cerrados);
    - resto → `ticket_status_changed`.
  - `previous_value`/`new_value` son los estados.
- `reopen_ticket(..., now=None, notify=None)`.
  - Tras `modifications.add(...)`, llama con `ticket_reopened`, `Cerrado` → `Abierto`.

No se toca `set_ticket_priority`, `create_comment`, `create_ticket` ni `reopen` en su validación previa: esas operaciones no notifican.

### 2.5 Interfaz — `tickets/interface/schemas.py`

```python
class NotificationTicketResponse(BaseModel):
    id: str
    title: str

class NotificationUserResponse(BaseModel):
    id: str
    name: str | None

class NotificationResponse(BaseModel):
    id: str
    type: str
    ticket: NotificationTicketResponse
    recipient: NotificationUserResponse
    actor: NotificationUserResponse
    previous_value: str | None
    new_value: str | None
    created_at: str
    read_at: str | None

class UnreadCountResponse(BaseModel):
    count: int

class MarkAllReadResponse(BaseModel):
    updated: int
```

Todos los campos se serializan siempre; los que no aplican van a `null`. `recipient` permite que un administrador sepa a quién pertenece cada notificación. No se expone `company_id`.

### 2.6 Interfaz — `tickets/interface/notifications_router.py`

Prefijo `/api/notifications`, etiqueta `notifications`:

| Método | Ruta | Respuesta | Acceso |
|---|---|---|---|
| `GET` | `/api/notifications` | `list[NotificationResponse]` | sesión válida; visibilidad RF-148 |
| `GET` | `/api/notifications/unread-count` | `{count}` | sesión válida; solo propias |
| `POST` | `/api/notifications/read-all` | `{updated}` | sesión válida; solo propias |
| `POST` | `/api/notifications/{notification_id}/read` | `NotificationResponse` | sesión válida; solo propias |

- `Depends(get_current_user)` en todas: 401 antes de cualquier otra comprobación.
- `NotificationNotFoundError` → 404 `{"detail": "notification not found"}`.
- Fechas con `.isoformat()`.
- Nombres con `get_user_summary`; si no se resuelve, `{id, name: null}`.
- Sin parámetros de consulta declarados (los desconocidos se ignoran).
- Las rutas `/unread-count` y `/read-all` se declaran antes de `/{notification_id}/read` por claridad; no hay colisión de segmentos.

`main.py` incluye el router nuevo.

`tickets/interface/router.py` importa `notify_ticket_event` y lo pasa a los tres casos de uso. La composición queda en la interfaz; el caso de uso no importa el router.

## 3. Frontend

### 3.1 Tipos y API

`frontend/src/types/notification.ts`:

```ts
export type NotificationType =
  | 'ticket_assigned'
  | 'ticket_reassigned'
  | 'ticket_status_changed'
  | 'ticket_resolved'
  | 'ticket_reopened'

export interface NotificationUser { id: string; name: string | null }

export interface AppNotification {
  id: string
  type: NotificationType
  ticket: { id: string; title: string }
  recipient: NotificationUser
  actor: NotificationUser
  previous_value: string | null
  new_value: string | null
  created_at: string
  read_at: string | null
}

export interface UnreadCount { count: number }
```

`frontend/src/api/notifications.api.ts` con `createNotificationsApi(http = request)`:

- `list()` → `GET /api/notifications`
- `unreadCount()` → `GET /api/notifications/unread-count`
- `markRead(id)` → `POST /api/notifications/{id}/read` (id codificado con `encodeURIComponent`)
- `markAllRead()` → `POST /api/notifications/read-all`

### 3.2 Hooks

`frontend/src/hooks/useNotifications.ts`:

- `notificationKeys = { all: ['notifications'], list: ['notifications','list'], unread: ['notifications','unread'] }`.
- `useNotifications(api)` y `useUnreadCount(api)`: `refetchInterval: 30_000`, `refetchOnWindowFocus: true`, `retry: false`.
- `useMarkNotificationRead(api)` y `useMarkAllNotificationsRead(api)`: mutaciones que invalidan `notificationKeys.all` al terminar.
- Las páginas y componentes aceptan la API por prop para poder inyectar una falsa en pruebas, siguiendo el patrón de `DashboardPage` y `TicketsPage`.

### 3.3 Campana y armazón

- `frontend/src/components/notifications/NotificationBell.tsx`: usa `useUnreadCount`; muestra la campana, un badge con el contador (`9+` si supera 9) y enlaza a `/notificaciones`. La etiqueta accesible incluye el número de no leídas; el badge es `aria-hidden`.
- `Topbar` recibe `notificationsApi?` y renderiza `NotificationBell` en lugar del enlace simple actual.
- `AppShell` recibe `notificationsApi?` y lo pasa a `Topbar`; `AppRoutes` sigue usándolo sin props.

### 3.4 Página `/notificaciones`

`frontend/src/pages/NotificationsPage.tsx`:

- `PageHeader` con título y subtítulo; acción «Marcar todas como leídas» (deshabilitada si no hay pendientes).
- Filtro local «Todas / No leídas» con `aria-pressed`.
- Lista `<ul>` accesible; cada fila muestra icono por tipo, mensaje, título del ticket, actor, fecha relativa y punto de no leída. Para administrador y supervisor añade «Para: {recipient.name}».
- Botón «Marcar como leída» por notificación no leída.
- Estados: carga (`role="status"`), vacío sin notificaciones, vacío por filtro, error con reintento y 401 con cierre de sesión (el `httpClient` ya dispara el cierre global; la página no pinta datos).
- Sin datos mock ni etiqueta «Demo».

`routes.tsx` sustituye el `PlaceholderPage` de `/notificaciones` por `NotificationsPage`.

`frontend/src/lib/notifications.ts`:

- `notificationMessage(notification)` con textos en español:
  - `ticket_assigned` → «Ticket asignado a {new_value}»
  - `ticket_reassigned` → «Ticket reasignado a {new_value}»
  - `ticket_status_changed` → «Estado actualizado: {previous_value} → {new_value}»
  - `ticket_resolved` → «Ticket resuelto»
  - `ticket_reopened` → «Ticket reabierto»
- `notificationIcon(type)` devuelve la clave de icono usada por la lista.

### 3.5 Dashboard

- `frontend/src/components/dashboard/NotificationsCard.tsx`: usa `useNotifications`; muestra las cinco más recientes, punto de no leída, mensaje, fecha relativa y enlace «Ver todas» a `/notificaciones`. Estados de carga, vacío y error con reintento, en formato de tarjeta compacta.
- `DashboardPage` recibe `notificationsApi?` y renderiza la tarjeta dentro del dashboard con datos (después de los KPIs), visible para administrador, supervisor y técnico. El cliente no tiene dashboard.

### 3.6 Textos

`frontend/src/lib/strings.ts` añade `strings.notifications` con título, subtítulo, filtros, acciones, estados vacíos, error, etiquetas accesibles, títulos del dashboard y los textos de los cinco tipos. Nada de literales dispersos en los componentes.

## 4. Contrato HTTP exacto

`GET /api/notifications`:

```json
[
  {
    "id": "uuid",
    "type": "ticket_resolved",
    "ticket": { "id": "uuid", "title": "No puedo entrar" },
    "recipient": { "id": "u-client", "name": "Carla Cliente" },
    "actor": { "id": "u-tech", "name": "Tomás Técnico" },
    "previous_value": "En progreso",
    "new_value": "Resuelto",
    "created_at": "2026-11-17T10:00:00+00:00",
    "read_at": null
  }
]
```

`GET /api/notifications/unread-count` → `{"count": 2}`

`POST /api/notifications/read-all` → `{"updated": 2}`

`POST /api/notifications/{id}/read` → la notificación con `read_at` no nulo.

Errores:

- Sin sesión: `401`.
- Notificación inexistente, identificador inválido, ajena o intento de administrador sobre la de otro: `404 {"detail": "notification not found"}`.

## 5. Decisiones y alternativas descartadas

1. **Notificaciones dentro de `tickets`, no módulo nuevo.** Menos contratos y despliegue; coherente con “notificaciones de tickets”.
2. **Generación desde casos de uso, no desde el router.** La regla de destinatarios no vive en HTTP; el router solo inyecta el colaborador.
3. **Colaborador opcional `notify`.** Conserva intactas las pruebas unitarias de HU-03/04/08 y permite inyectar una implementación falsa.
4. **Una notificación por destinatario.** Permite leído/no leído individual y supervisión sin compartir estado de lectura.
5. **Resolución como tipo propio.** Evita duplicar `ticket_status_changed` + `ticket_resolved` en el paso a `Resuelto`.
6. **Sin notificar al actor.** Evita avisos redundantes de la propia acción.
7. **Administrador/supervisor ven todas las de su empresa, pero solo marcan las suyas.** Satisface supervisión sin que un administrador altere la bandeja de un cliente.
8. **Polling 30 s + foco, sin WebSockets.** Confirmado por el usuario; suficiente para el MVP y sin infraestructura nueva.
9. **Listado sin paginación.** El MVP en memoria no lo necesita; el contrato admite añadirla después.
10. **Fechas y nombres resueltos en la interfaz.** El dominio no depende de `identity`; se reutiliza `get_user_summary`.

## 6. Estrategia de pruebas

### Backend (pytest + TestClient)

- `test_notifications_domain.py`
  - Constantes y catálogo de tipos.
  - Campos y valores por defecto de `TicketNotification`.
  - `read_at` nulo al crear.

- `test_notifications_use_case.py`
  - Asignación inicial: notifica a solicitante y técnico; no al actor.
  - Reasignación: notifica a solicitante y nuevo técnico.
  - Solicitante == técnico → una sola notificación.
  - Ticket sin técnico → solo solicitante.
  - Actor solicitante o actor técnico → no se notifica a sí mismo.
  - Cambio de estado, resolución y reapertura generan el tipo correcto.
  - Prioridad, comentario, no-op y transición rechazada no generan notificaciones.
  - Visibilidad: admin/supervisor ven las de su empresa; técnico y cliente solo las suyas; empresa ajena no se filtra.
  - Contador de no leídas solo propias.
  - Marcar una: propia, idempotente, 404 para ajena/inexistente/id inválido.
  - Marcar todas: solo propias, idempotente y devuelve el número actualizado.

- `test_notifications_api.py`
  - 401 sin sesión antes de 404 en las cuatro rutas.
  - `GET` devuelve el contrato exacto, orden descendente y `[]` cuando no hay.
  - Admin/supervisor ven todas las de su empresa; técnico/cliente solo las suyas.
  - `unread-count` propio para cada rol.
  - `POST /{id}/read`: 200, idempotente, 404 uniforme para ajena/inexistente/inválida.
  - `POST /read-all`: actualiza solo las propias.
  - Parámetros de consulta desconocidos ignorados.
  - OpenAPI: cuatro rutas nuevas; sin campos internos (`company_id`, `actor_id`, `recipient_id`) en las respuestas.

- `test_notifications_flow.py`
  - Flujo HU-02 → HU-04 → HU-03/HU-08: creación sin aviso, asignación, cambio de estado, resolución, cierre y reapertura.
  - Verifica tipos, destinatarios, valores anterior/nuevo y ausencia de duplicados.
  - Prioridad y comentarios no generan avisos.
  - La consulta de notificaciones no muta tickets ni historial.

### Frontend (Vitest + Testing Library)

- `tests/api/notifications.api.test.ts`: URLs, métodos y codificación del id.
- `tests/lib/notifications.test.ts`: mensaje por tipo y fallback.
- `tests/hooks/useNotifications.test.tsx`: consulta y contador con API falsa; invalidación tras marcar.
- `tests/components/NotificationBell.test.tsx`: sin badge en 0; badge con 3; `9+`; enlace y etiqueta accesible.
- `tests/components/NotificationsCard.test.tsx`: cinco más recientes, enlace, vacío y error.
- `tests/pages/NotificationsPage.test.tsx`: listado, no leídas, filtro, marcar una, marcar todas, vacío, error/reintento y 401.
- Ajustes a pruebas existentes:
  - `tests/layout/AppShell.test.tsx`: inyectar una API falsa de notificaciones en `renderShell` y comprobar el badge.
  - `tests/pages/DashboardPage.test.tsx`: inyectar la API falsa y comprobar la tarjeta.
  - `tests/routes/guards.test.tsx`: el `fetch` stub devuelve `[]` para `/api/notifications` y `{count: 0}` para `/api/notifications/unread-count`.

### Verificación final

- `cd backend` + `python -m pytest -q` con `DATABASE_URL` (contenedor `infra-db-1`, puerto 55432).
- `cd frontend` + `npm test`, `npm run build`, `npm run lint`.
- Los tres fallos preexistentes de precedencia 401/404 con cookie inválida se documentan como ajenos a HU-15.
- `codegraph sync` tras los cambios.
- Smoke manual con cliente, técnico, administrador y supervisor.

## 7. Orden de implementación

1. Dominio y repositorio de notificaciones.
2. Caso de uso de generación y reglas de destinatarios.
3. Casos de uso de visibilidad y lectura.
4. Esquemas, router y registro en `main.py`.
5. Enganche en `assign_ticket`, `update_ticket_status`, `reopen_ticket` y routers.
6. Pruebas backend de dominio, aplicación, API y flujo; suite completa.
7. Tipos, API y utilidades del frontend.
8. Hooks, campana y armazón.
9. Página `/notificaciones` y ruta.
10. Tarjeta del dashboard.
11. Pruebas frontend y ajuste de stubs existentes; `npm test`, build y lint.
12. Documentación, memoria e índice.
