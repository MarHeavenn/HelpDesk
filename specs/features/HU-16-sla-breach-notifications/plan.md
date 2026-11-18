# Plan HU-16 — Notificaciones de incumplimiento de SLA
Spec: `specs/features/HU-16-sla-breach-notifications/spec.md` (aprobada)
Estado: propuesto

## 1. Enfoque

HU-16 extiende el centro de notificaciones de HU-15 sin crear un módulo nuevo. Las alertas son notificaciones del módulo `tickets` con dos tipos adicionales (`sla_near_due` y `sla_breached`) y una clave interna de deduplicación.

El problema principal es **cuándo** generar la alerta. No hay planificador ni proceso en segundo plano y la historia no debe introducirlo. La solución es un **análisis perezoso** (`generate_sla_alerts`) que se ejecuta antes de responder `GET /api/notifications` y `GET /api/notifications/unread-count`. El frontend ya sondea esas rutas cada 30 segundos y al recuperar el foco, de modo que las alertas aparecen sin cambiar el mecanismo de actualización.

El análisis:

1. selecciona los tickets del ámbito del actor (administrador/supervisor: su empresa; técnico: los asignados a él; cliente: ninguno);
2. descarta resueltos/cerrados y tickets sin prioridad;
3. calcula el SLA con el contrato existente `sla/interface/contract.get_ticket_sla`, usando un único `now`;
4. por cada ticket `near_due` o `breached`, resuelve los destinatarios (administradores activos de la empresa del ticket + técnico asignado);
5. inserta una notificación por destinatario si no existe ya una con la misma clave `(ticket, tipo, destinatario, due_at)`.

La operación es idempotente y solo escribe notificaciones; nunca modifica tickets ni su historial. La deduplicación se apoya en el propio registro de notificaciones, que actúa como «registro del evento notificado».

Se descartan dos alternativas:

1. **Generar la alerta al cambiar la prioridad o el estado.** No cubre el simple paso del tiempo: un ticket puede entrar en riesgo sin que nadie lo modifique. Además obligaría a repetir el análisis en cada caso de uso.
2. **Un cron o hilo en segundo plano.** Añade infraestructura, concurrencia y estados que el MVP no necesita; el sondeo de 30 s ya existe.

La clave de deduplicación incluye `due_at`: si un cambio de prioridad, de la política de SLA o una reapertura mueve el vencimiento, se considera un evento nuevo y puede emitirse otra alerta. Las alertas antiguas se conservan como histórico.

## 2. Backend

### 2.1 Dominio — `backend/app/modules/tickets/domain/entities.py`

Constantes nuevas:

```python
NOTIFICATION_TYPE_SLA_NEAR_DUE = "sla_near_due"
NOTIFICATION_TYPE_SLA_BREACHED = "sla_breached"
SYSTEM_ACTOR_ID = "system"
```

`NOTIFICATION_TYPES` pasa a incluir los siete tipos. La entidad `TicketNotification` añade un campo interno opcional:

```python
dedupe_key: str | None = None
```

`dedupe_key` no se serializa por HTTP. `notify_ticket_event` sigue funcionando sin cambios porque el campo tiene valor por defecto.

### 2.2 Aplicación — `backend/app/modules/tickets/application/generate_sla_alerts.py`

```python
def generate_sla_alerts(
    *,
    actor_id: str,
    actor_role: str,
    actor_company_id: str | None,
    tickets: InMemoryTicketRepository,
    notifications: InMemoryNotificationRepository,
    administrator_ids: Callable[[str | None], list[str]],
    now: datetime | None = None,
) -> list[TicketNotification]:
```

Reglas:

1. `now` se fija una sola vez (UTC) para todo el análisis.
2. Ámbito:
   - `administrador` y `supervisor`: `tickets.list_all()` filtrado por `ticket.company_id == actor_company_id`;
   - `tecnico`: `tickets.list_by_assignee(actor_id)`;
   - cualquier otro rol: no analiza y devuelve `[]`.
3. Descarta tickets en `RESOLVED_STATUSES`.
4. Calcula el SLA con `get_ticket_sla(TicketSlaSnapshot(...), reference)`. Si es `None`, continúa.
5. Determina el tipo: `sla_breached` si `sla.breached`; `sla_near_due` si `sla.near_due`; si no, continúa.
6. Destinatarios: `administrator_ids(ticket.company_id)` en orden, más `ticket.assignee_id` si existe, sin duplicados.
7. Clave de deduplicación: `sla:{ticket_id}:{type}:{recipient_id}:{due_at.isoformat()}`.
8. Si `notifications.find_by_dedupe_key(key)` existe, no crea nada.
9. Crea `TicketNotification` con UUID nuevo, `company_id` del ticket, título, tipo, `actor_id=SYSTEM_ACTOR_ID`, `previous_value=None`, `new_value=due_at.isoformat()`, `created_at=reference`, `read_at=None` y `dedupe_key`.
10. Devuelve las creadas. Un fallo de resolución de administradores se propaga; no se silencia.

La función no importa `sla` por su dominio: usa su contrato. Tampoco importa `identity`: recibe un `Callable` que devuelve identificadores. El router compone ambas dependencias.

### 2.3 Infraestructura — `tickets/infrastructure/notification_repository.py`

Añadir:

```python
def find_by_dedupe_key(self, dedupe_key: str) -> TicketNotification | None
```

Devuelve la primera notificación con esa clave o `None`. Las notificaciones de HU-15 tienen `dedupe_key=None` y no colisionan.

### 2.4 Identidad — contrato de administradores

Nuevo `backend/app/modules/identity/application/administrators.py`:

```python
def list_active_administrator_ids(
    company_id: str | None,
    users: InMemoryUserRepository,
) -> list[str]:
```

Filtra `role == "administrador"`, `status == "active"` y `company_id` igual al solicitado (incluido `None`). Devuelve solo identificadores, sin correo, hash ni rol.

Nuevo `backend/app/modules/identity/interface/administrators_contract.py`:

```python
def list_company_administrator_ids(company_id: str | None) -> list[str]
```

Une la función anterior con `get_user_repository()`. Es la única frontera que usa `tickets`.

### 2.5 Interfaz — `tickets/interface/notifications_router.py`

Antes de listar y antes de contar no leídas:

```python
generate_sla_alerts(
    actor_id=current["id"],
    actor_role=current["role"],
    actor_company_id=current.get("company_id"),
    tickets=get_ticket_repository(),
    notifications=get_notification_repository(),
    administrator_ids=list_company_administrator_ids,
)
```

`POST /read` y `POST /read-all` no ejecutan el análisis. `_user_response` traduce `SYSTEM_ACTOR_ID` a `{"id": "system", "name": "Sistema"}` sin consultar el repositorio de usuarios. El resto de la serialización no cambia.

### 2.6 Pruebas backend

- `tests/test_notifications_domain.py`: catálogo de siete tipos, `dedupe_key` por defecto y búsqueda por clave.
- `tests/test_sla_notifications.py` (nuevo): ámbito por rol, tickets resueltos/sin prioridad, `near_due` y `breached`, destinatarios (varios administradores, técnico, solapamiento, sin admin, sin técnico, admin desactivado), deduplicación, cambio de `due_at`, sistema como actor y `new_value` con el vencimiento.
- `tests/test_sla_notifications_api.py` (nuevo): el sondeo de `GET /api/notifications` y `unread-count` genera y deduplica alertas; admin de la empresa las ve; técnico asignado las ve; admin de otra empresa no; supervisor no es destinatario; 401 sin sesión; OpenAPI conserva la forma.
- `tests/test_sla_notifications_flow.py` (nuevo o ampliación de `test_notifications_flow.py`): crear ticket antiguo con prioridad, consultar notificaciones y comprobar la alerta; avanzar el reloj a incumplido y comprobar la segunda alerta sin duplicar la primera.

## 3. Frontend

- `types/notification.ts`: añadir `'sla_near_due' | 'sla_breached'` a `NotificationType`.
- `lib/notifications.ts`:
  - claves de icono `slaNearDue` y `slaBreached`;
  - mensajes con `formatTicketDate(new_value)`:
    - `SLA por vencer: vence <fecha>`;
    - `SLA incumplido: venció <fecha>`;
    - si `new_value` falta, mensaje sin fecha.
- `components/notifications/NotificationGlyph.tsx`: `AlertTriangle` para próximo y `ShieldAlert` para incumplido.
- `lib/strings.ts`: etiquetas «SLA por vencer» y «SLA incumplido» y mensajes.
- `pages/NotificationsPage.tsx` y `components/dashboard/NotificationsCard.tsx`: no requieren cambios estructurales; muestran los nuevos tipos con el mismo patrón. La página ya muestra «por Sistema» porque el backend resuelve el actor del sistema.
- Pruebas: `tests/lib/notifications.test.ts` (mensajes e iconos nuevos) y `tests/pages/NotificationsPage.test.tsx` (render de una alerta de SLA y del actor Sistema).

## 4. Demostración local

Para que la funcionalidad se pueda ver sin esperar horas:

- `backend/dev_server.py` siembra, además del administrador y el técnico, un cliente demo y tickets con `created_at` calculado respecto al objetivo de SLA:
  - un ticket `Crítica` dentro de la ventana de riesgo → `sla_near_due`;
  - un ticket `Alta` vencido → `sla_breached`;
  - un ticket `Media` en tiempo → sin alerta;
  - un ticket resuelto → sin alerta.
- La siembra es idempotente y solo existe en desarrollo.
- Al iniciar sesión como administrador y como técnico, el sondeo de notificaciones genera las alertas y se ven en la campana, en `/notificaciones` y en el dashboard.
- Se documenta el paso a paso en el README y se verifican las respuestas con `curl`/`TestClient` y la interfaz en el navegador.

## 5. Riesgos y mitigaciones

- **Coste del análisis por consulta**: se limita al ámbito del actor y al número de tickets del MVP en memoria. Si crece, se podrá mover a un proceso programado sin cambiar el contrato de las alertas.
- **Efecto secundario de un GET**: el análisis escribe notificaciones. Es idempotente, determinista y no altera tickets; se documenta en la spec.
- **Zona horaria en `due_at`**: el backend serializa con offset UTC; el frontend formatea en la zona local con `formatTicketDate`.
- **Administradores sin empresa**: los datos heredados de desarrollo (`company_id=None`) se tratan como un ámbito propio; en producción todas las cuentas tienen empresa.

## 6. Orden de implementación

1. Dominio y repositorio (T1).
2. Contrato de identidad y caso de uso (T2).
3. Router y esquemas (T3).
4. Pruebas backend (T4).
5. Frontend (T5).
6. Demostración local, documentación y verificación completa (T6).
