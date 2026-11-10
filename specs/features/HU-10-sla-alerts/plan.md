# Plan HU-10 — Alertas SLA

Spec: `specs/features/HU-10-sla-alerts/spec.md` (aprobada)
Estado: implementado

## 1. Alcance técnico

Backend únicamente, en memoria y sin dependencias nuevas, coherente con `identity`, `tickets`, `assignment` y `sla`. La historia añade **una única operación de solo lectura**: un listado derivado de tickets que requieren atención por SLA. No se toca PostgreSQL, el frontend ni la autenticación.

El listado **reutiliza por completo el cálculo de HU-05** (`get_ticket_sla` / `TicketSlaSnapshot`, umbral `RISK_THRESHOLD_RATIO = 0.20`): no se introduce un segundo cálculo, una tarea programada ni persistencia del estado. La regla «qué ticket requiere atención» vive en la capa de aplicación de `tickets`, no en el controlador HTTP (`docs/constitution.md`).

| RF | Dónde se cubre |
| --- | --- |
| RF-61 | `tickets/application/list_attention_tickets.py` (filtro: activo + `near_due` o `breached`) |
| RF-62 | `tickets/infrastructure/ticket_repository.py` (`list_all`) + caso de uso (todo el sistema, independiente de creador/asignación) |
| RF-63 | Caso de uso (guardia de rol con `TicketNotFoundError` → 404) + `get_current_user` (401) |
| RF-64 | `tickets/interface/router.py` (`ticket_summary`, sin cambios) + `TicketSummaryResponse` (sin cambios) |
| RF-65 | Caso de uso (orden por `sla.due_at` ascendente) |
| RF-66 | Sin parámetros declarados (los desconocidos se ignoran); colección vacía = 200 |
| RF-67 | Reutilización de `get_ticket_sla` (sin cálculo nuevo ni umbral nuevo) |
| RF-68 | Derivación en vivo con `now`; sin estado persistido, sin tareas programadas |
| RF-69 | `now` único compartido; fechas ISO 8601 ya garantizadas por `ticket_summary` |

El módulo `sla` **no cambia**: ya expone el contrato `get_ticket_sla(snapshot, now)` y el umbral fijo del 20 %, y no importa nada de `tickets` (sin ciclo de dependencias).

## 2. Estructura de archivos

```
backend/app/modules/tickets/
  infrastructure/ticket_repository.py   # + list_all() (colección completa, sin filtro)
  application/list_attention_tickets.py # NUEVO caso de uso: filtro, guardia de rol y orden
  interface/router.py                   # + endpoint GET /requiring-attention (antes de /{ticket_id})

backend/app/modules/sla/                # SIN CAMBIOS (se reutiliza get_ticket_sla)
```

No se añaden esquemas nuevos: `TicketSummaryResponse` y `SlaResponse` se reutilizan tal cual (RF-64, composición idéntica a HU-04/HU-06).

## 3. Contrato HTTP

Nueva operación (única de la historia):

```
GET /api/tickets/requiring-attention
```

| Éxito | Rechazos |
| --- | --- |
| 200 con `list[ TicketSummaryResponse ]` ordenada por `sla.due_at` ascendente (los incumplidos primero); 200 con `[]` si no hay tickets que requieran atención | 401 sin sesión válida; 404 uniforme (`{"detail": "ticket not found"}`) para `cliente` |

- El elemento es exactamente `{id, title, priority, status, assignee, sla, created_at}` (RF-64); `sla` es el objeto de HU-05 con sus 8 campos y **nunca es `null`** en esta respuesta (todo elemento tiene prioridad, RF-61).
- No se declaran parámetros de consulta: los desconocidos se ignoran en silencio (RF-66, misma regla que RF-15).
- No se introducen códigos de error nuevos: 200 en el camino válido y 401/404 en los rechazos (RF-63).
- **Colocación de la ruta**: se declara en `router.py` **antes** de `GET /{ticket_id}`. Al ser una ruta estática, FastAPI/Starlette la casa primero y no compite con la ruta dinámica `/{ticket_id}` (que capturaría `"requiring-attention"` como un `ticket_id`). Sin esta precedencia, el valor no-UUID caería en `get_ticket_detail` y respondería 404 en lugar de 200.

## 4. Reglas y casos de uso

### 4.1 Repositorio: `list_all()`

`InMemoryTicketRepository` solo expone `list_by_requester` y `list_by_assignee`; RF-62 exige la colección completa, con independencia de creador y asignación. Se añade:

```python
def list_all(self) -> list[Ticket]:
    """Todos los tickets del sistema, ordenados por created_at descendente."""
    tickets = list(self._by_id.values())
    tickets.sort(key=lambda ticket: ticket.created_at, reverse=True)
    return tickets
```

- No filtra por rol, creador ni asignación: devuelve la materia prima que el caso de uso depura.
- El orden por `created_at` descendente solo da determinismo de base; el orden de negocio (por `due_at`) lo aplica el caso de uso, no el repositorio (las reglas de negocio no viven en infraestructura).
- Respeta la arquitectura: `tickets` posee su repositorio y no accede a tablas de otros módulos.

### 4.2 Caso de uso: `list_attention_tickets`

```python
def list_attention_tickets(
    actor_role: str,
    tickets: InMemoryTicketRepository,
    now: datetime | None = None,
) -> list[Ticket]:
    if actor_role not in MANAGEMENT_ROLES:
        raise TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)
    reference = now if now is not None else datetime.now(timezone.utc)
    attention: list[tuple[datetime, Ticket]] = []
    for ticket in tickets.list_all():
        if ticket.status in RESOLVED_STATUSES:      # RF-61: solo Abierto / En progreso
            continue
        sla = get_ticket_sla(
            TicketSlaSnapshot(ticket.priority, ticket.created_at, ticket.resolved_at),
            reference,
        )
        if sla is None:                             # RF-61: sin prioridad -> fuera
            continue
        if sla.near_due or sla.breached:            # RF-61: en_riesgo o incumplido
            attention.append((sla.due_at, ticket))
    attention.sort(key=lambda item: item[0])        # RF-65: due_at ascendente
    return [ticket for _, ticket in attention]
```

- **Guardia de rol primero** (RF-63): un `cliente` lanza `TicketNotFoundError(TICKET_NOT_FOUND_MESSAGE)` antes de leer el repositorio, sin revelar datos. Se reutiliza la excepción y el mensaje de HU-02/HU-03/HU-04, de modo que no hay tipo de error ni código nuevos.
- **Reutilización total de HU-05** (RF-67): se llama a `get_ticket_sla` con el `TicketSlaSnapshot`; no hay umbral nuevo ni lógica de SLA duplicada. La dirección de dependencia es `tickets.application → sla.interface → sla.application → sla.domain`; `sla` no importa `tickets`.
- **Filtro** (RF-61): `status not in RESOLVED_STATUSES` (es decir, `Abierto`/`En progreso`) **y** `sla` no nulo **y** (`near_due` o `breached`).
- **Orden** (RF-65): por `sla.due_at` ascendente. El `sort` es estable, así que un empate de `due_at` conserva el orden de `list_all` y no fija orden entre iguales (la spec no exige desempatar).
- El caso de uso devuelve `list[Ticket]`; la composición del resumen y el recálculo del `sla` quedan en la interfaz (como en `list_my_tickets`/`list_assigned_tickets`), con el **mismo `now`** para garantizar coherencia entre filtro y serialización.

### 4.3 Endpoint

```python
@router.get("/requiring-attention", response_model=list[TicketSummaryResponse])
def list_attention_tickets_endpoint(
    current: dict = Depends(get_current_user),
) -> list[TicketSummaryResponse]:
    now = datetime.now(timezone.utc)          # único instante de referencia (RF-69)
    try:
        tickets = list_attention_tickets(
            actor_role=current["role"],
            tickets=get_ticket_repository(),
            now=now,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ticket_summary(ticket, now) for ticket in tickets]
```

- `get_current_user` resuelve el 401 **antes** del handler (precedencia 401 > 404, RF-63), igual que HU-06 (RF-57).
- El `now` se calcula **una vez** y se pasa al caso de uso (para el filtro) y a cada `ticket_summary` (para la serialización), cumpliendo RF-69 (un único instante de referencia).
- No muta tickets ni registros (RF-62, RF-68): es una consulta de solo lectura.

## 5. Estrategia de pruebas

Sin pruebas de frontend (no hay runner acordado). Todo con pytest; las rutas con `TestClient` y sesiones reales (`provision_user` + login), como en HU-02..HU-06. Cada tarea es TDD: test en rojo, implementación, `pytest` y `codegraph sync`.

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_tickets_list_all.py` | unitario (repositorio) | RF-62: `list_all` devuelve todos los tickets sin filtrar por creador/asignación, orden base determinista y colección vacía; `list_by_requester`/`list_by_assignee` intactos |
| `tests/test_attention_use_case.py` | unitario, `now` inyectado | RF-61, RF-62, RF-63, RF-65, RF-66, RF-67: activos con `near_due`/`breached`; exclusión de `Resuelto`/`Cerrado` y de sin prioridad; orden por `due_at`; cliente → `TicketNotFoundError`; vacío; reutiliza `get_ticket_sla` |
| `tests/test_attention_api.py` | API + TestClient | RF-62..RF-69: 200 técnico/admin, 404 cliente uniforme, 401 sin sesión, composición exacta sin `requester`/descripción, `sla` nunca `null`, orden ascendente, parámetros desconocidos ignorados, sin mutación, derivación en vivo, ISO 8601 |

Para estados deterministas sin depender del reloj real:

- Los tests de caso de uso inyectan `now` y construyen tickets con `created_at`/`priority`/`status`/`resolved_at` controlados (p. ej. `Crítica` creada hace 3 h → `incumplido`; `Baja` creada hace 23 h → `en_riesgo`).
- Los tests de API insertan tickets directamente en el repositorio con `created_at` controlado y usan márgenes amplios (horas), dejando los límites exactos del 20 % a `test_sla_domain.py` de HU-05 (que ya existen).

## 6. Contratos y dependencias

- Dirección: `tickets.interface → tickets.application → tickets.infrastructure`, y `tickets.application → sla.interface → sla.application → sla.domain`. `sla` no importa nada de `tickets` (sin ciclo).
- `identity` no cambia: la identidad y el rol proceden de la sesión vía `get_current_user`, nunca de la petición (RF-63).
- No hay acceso a repositorios o tablas de otros módulos, ni dependencias nuevas.

## 7. Decisiones técnicas

- **Obtención de la colección completa (RF-62):** se añade `list_all()` al repositorio de `tickets`, que es quien posee los datos. *Alternativa descartada: que `sla` o un módulo nuevo consulte los tickets, lo que acoplaría `sla` a `tickets` o crearía un repositorio transversal prohibido por la constitución; y filtrar en el repositorio (p. ej. `list_requiring_attention`), que trasladaría la regla de negocio a infraestructura.*
- **Ubicación de la regla:** el filtro y la guardia de rol viven en `tickets/application` (no en el controlador HTTP). *Alternativa descartada: filtrar y ordenar en el endpoint, violando la constitución («las reglas de negocio no se implementan en los controladores HTTP»).*
- **Ruta:** `GET /api/tickets/requiring-attention`, declarada **antes** de `GET /{ticket_id}`. *Alternativa descartada: prefijo propio separado (`/api/alerts`), que fragmentaría el recurso `tickets` sin necesidad; la referencia de la spec ya lo sitúa bajo `/api/tickets`.*
- **404 del cliente sin código nuevo:** se reutiliza `TicketNotFoundError` + `TICKET_NOT_FOUND_MESSAGE` («ticket not found»), el mismo criterio de no revelación de HU-03 (RF-24) y HU-04 (RF-38). *Alternativa descartada: un mensaje específico de listado, que introduciría una variante de error no contemplada por la spec (RF-63 exige 404 uniforme).*
- **Sin recalcular `sla` en la respuesta:** el caso de uso devuelve `list[Ticket]` y la interfaz serializa con `ticket_summary(ticket, now)` usando el **mismo `now`** del filtro. *Alternativa descartada: devolver pares `(ticket, sla)` del caso de uso, que duplicaría la composición o acoplaría la aplicación a la vista HTTP.*
- **Umbral:** se conserva el `RISK_THRESHOLD_RATIO = 0.20` de HU-05 (sin operación pública de lectura/escritura); la configuración pública queda en HU-14.

## 8. Riesgos y mitigaciones

- **Colisión de ruta con `/{ticket_id}`:** se declara `requiring-attention` antes de la ruta dinámica y se cubre con un test que pide el listado y verifica 200 (no 404). 
- **Inconsistencia de reloj entre filtro y serialización:** un único `now` compartido por el endpoint (RF-69); los tests inyectan `now` o usan márgenes amplios.
- **Segundo cálculo o umbral duplicado:** el plan reutiliza `get_ticket_sla`; un test afirma que no existe lógica de SLA nueva (solo importaciones del contrato).
- **Regresión de listados existentes:** `list_by_requester`/`list_by_assignee` no se tocan; `ticket_summary` no cambia; la suite completa debe quedar en verde salvo los 3 fallos preexistentes documentados en `MEMORY.md`.
- **`sla` nulo en un elemento (defensivo):** por RF-61 es imposible (todo elemento tiene prioridad), pero el caso de uso descarta `sla is None` para no romper la respuesta.

## 9. Orden de implementación

1. `list_all()` en el repositorio con su test (RF-62).
2. Caso de uso `list_attention_tickets` (filtro, guardia de rol, orden) con tests unitarios (RF-61, RF-62, RF-63, RF-65, RF-66, RF-67).
3. Endpoint con guardia de rol y tests de visibilidad (RF-62, RF-63).
4. Tests de composición, orden, solo lectura e ISO (RF-64, RF-65, RF-69).
5. Tests de reutilización del cálculo y derivación en vivo (RF-67, RF-68).
6. Suite completa con PostgreSQL, `codegraph sync`, `MEMORY.md`, `specs/project.md` y cierre de spec/plan.

El detalle verificable de cada paso está en `tasks.md`.

## 10. Estimación

3 horas, repartidas en las 6 tareas de 20-30 minutos del orden anterior.

## Notas para el coordinador

- Ninguna: la spec cubre todas las decisiones de negocio (umbral, alcance, visibilidad, composición y orden). No surgen dudas nuevas.
