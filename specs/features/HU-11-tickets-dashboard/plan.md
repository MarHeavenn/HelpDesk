# Plan HU-11 — Dashboard de tickets

Spec base: `specs/features/HU-11-tickets-dashboard/spec.md` (aprobada; RF-81 a RF-92).
Alcance: contrato real de agregación en el backend y vista `/` en el frontend. Sin SLA, sin periodo y sin datos mock.

## 1. Módulos y capas afectadas

| Capa | Módulo | Cambio |
|---|---|---|
| `domain` | `tickets` | Sin cambios: usa `Ticket`, `PRIORITIES` y `STATUSES` existentes. |
| `infrastructure` | `tickets` | `InMemoryTicketRepository.list_all()` para obtener una instantánea. |
| `application` | `tickets` | `dashboard.py`: agrega el resumen por rol (RF-82 a RF-90). |
| `interface` | `tickets` | `dashboard_router.py` + esquemas de respuesta; traduce permisos a 404 y sesión a 401. |
| `interface` | `identity` | Contrato `get_technician_directory()` para incluir técnicos con cero tickets (RF-87). |
| `main` | — | Registra el router del dashboard. |
| `frontend` | — | Servicio, hook, componentes y página `/` que consumen el contrato. |

No se crea un módulo nuevo: el agregado es de tickets y se apoya en el contrato de identity. Así se respeta la propiedad del módulo y no se accede a sus tablas internas.

## 2. Contrato HTTP (RF-81 a RF-90)

`GET /api/dashboard/tickets`

- Sesión válida obligatoria (401 con `{"detail": ...}`).
- Rol `administrador`: todos los tickets.
- Rol `tecnico`: solo `assignee_id == current["id"]`.
- Rol `cliente`: 404 uniforme `{"detail": "tickets not found"}`.
- Sin cuerpo, sin parámetros y sin paginación.

Respuesta 200:

```json
{
  "total_tickets": 12,
  "by_status": [
    {"status": "Abierto", "count": 4},
    {"status": "En progreso", "count": 3},
    {"status": "Resuelto", "count": 3},
    {"status": "Cerrado", "count": 2}
  ],
  "by_priority": [
    {"priority": "Crítica", "label": "Crítica", "count": 1},
    {"priority": "Alta", "label": "Alta", "count": 3},
    {"priority": "Media", "label": "Media", "count": 5},
    {"priority": "Baja", "label": "Baja", "count": 1},
    {"priority": null, "label": "Sin prioridad", "count": 2}
  ],
  "by_assignee": [
    {"technician": null, "label": "Sin asignar", "count": 3},
    {"technician": {"id": "u-1", "name": "Ana Torres"}, "label": "Ana Torres", "count": 4},
    {"technician": {"id": "u-2", "name": "Luis Vega"}, "label": "Luis Vega", "count": 5}
  ],
  "recent_tickets": [
    {
      "id": "uuid",
      "title": "No puedo iniciar sesión",
      "priority": "Alta",
      "status": "Abierto",
      "assignee": {"id": "u-2", "name": "Luis Vega"},
      "created_at": "2026-11-02T10:00:00+00:00"
    }
  ],
  "generated_at": "2026-11-02T12:00:00+00:00"
}
```

Reglas de composición:

- Las cuatro entradas de `by_status` y las cuatro prioridades del catálogo aparecen siempre, con cero si no hay tickets (RF-85, RF-86).
- La entrada `sin_prioridad` solo aparece si hay tickets sin prioridad; su `priority` es `null` y su `label` es «Sin prioridad».
- `by_assignee` incluye `sin_asignar` si hay tickets sin técnico y, para el administrador, todos los técnicos registrados, incluidos los de cero tickets (RF-87).
- Para el técnico, `by_assignee` solo contiene su propia entrada y `sin_asignar` vale cero (RF-87).
- `recent_tickets` usa la composición del resumen de HU-02 (sin descripción) y se ordena por `created_at` descendente (RF-88).
- Los conteos se calculan en una sola pasada sobre la instantánea (RF-89).
- Sin tickets: 200 con ceros y `recent_tickets` vacío (RF-90).

## 3. Agregación (RF-84 a RF-90)

`get_ticket_dashboard(actor_id, actor_role, tickets, technicians, now)`:

1. Valida el rol: `administrador` o `tecnico`; cualquier otro lanza `DashboardAccessDeniedError`.
2. Obtiene `snapshot = tickets.list_all()` (copia) y, para técnico, filtra por `assignee_id`.
3. Inicializa contadores de estado y prioridad con todas las claves del catálogo en cero.
4. Recorre la instantánea una vez: suma total, estado, prioridad (`None` → «Sin prioridad») y técnico (`None` → «Sin asignar»).
5. Para administrador, añade los técnicos del directorio con cero si no aparecieron.
6. Ordena `by_status` según `STATUSES`, `by_priority` según `PRIORITIES` y deja `sin_prioridad` al final; `by_assignee` deja `sin_asignar` primero y luego por nombre.
7. Toma los cinco `recent_tickets` ordenados por `created_at` descendente.
8. Devuelve el DTO con `generated_at = now`.

La función no escribe ni muta tickets. Los empates de fecha no fijan orden.

## 4. Interfaz (RF-91, RF-92)

- `pages/DashboardPage.tsx` sustituye el marcador de `/` para administrador y técnico; el cliente sigue redirigido por `RequireRole` de HU-21.
- `PageHeader` con fecha, saludo por hora, subtítulo y botón «+ Crear ticket» → `/tickets/nuevo`.
- Cuatro `KpiCard`: total, abiertos, en atención (abierto + en progreso) y resueltos. Los valores salen del contrato; no hay cifras fijas.
- `DistributionCard` de estado y de prioridad: barras horizontales con etiqueta, conteo y porcentaje calculado en el cliente con protección contra división por cero.
- `AssigneeCard`: lista de técnicos con conteo y una fila «Sin asignar»; para el técnico muestra solo su carga.
- `RecentTicketsTable`: cinco filas con ID amigable, título, prioridad, estado, técnico y fecha; «Ver todos» → `/tickets`.
- Estados: `Skeleton` durante la carga, `EmptyState` «Aún no hay tickets» con enlace a crear, `ErrorState` con «Reintentar»; 401 → logout y `/login`.
- Responsive: KPIs 4/2/1 columnas, tarjetas apiladas y tabla con scroll horizontal; accesibilidad de RF-75 de HU-21.
- Sin `DemoBadge`: el dashboard es real.

## 5. Estrategia de pruebas

Backend (`pytest` + `TestClient`):

- Agregación unitaria con tickets de ejemplo: totales, estados con cero, prioridad `None`, sin asignar, técnicos con cero, recientes y orden.
- API: 401 sin sesión; 404 para cliente; 200 para administrador; 200 para técnico con alcance propio; dataset vacío; invariantes de suma; `generated_at` ISO.
- El repositorio y el directorio de técnicos se preparan con los helpers existentes de las pruebas de HU-02 a HU-04.

Frontend (Vitest + Testing Library):

- `dashboard.api` y `useTicketsDashboard` con `FakeApiClient`: éxito, 401, 404, error de red.
- `DashboardPage`: KPIs, distribuciones, recientes, enlaces, estados de carga/vacío/error, cliente redirigido y alcance del técnico.
- `npm run test` y `npm run build`.

## 6. Cobertura RF por parte

| Parte | RF |
|---|---|
| Repositorio `list_all` y contrato de técnicos | RF-82, RF-87 |
| Agregación y DTO | RF-84, RF-85, RF-86, RF-88, RF-89, RF-90 |
| Router y autorización | RF-81, RF-82, RF-83 |
| Servicio y hook del frontend | RF-84 a RF-90 |
| Vista `/` | RF-91 |
| Estados, responsive y accesibilidad | RF-92 |

## 7. Decisiones justificadas

- **D1. El agregado vive en `tickets`, no en un módulo `dashboard` nuevo.** Es una vista de tickets y evita una capa vacía. *Alternativa descartada: módulo dashboard*, duplicaría contratos y no aporta en esta iteración.
- **D2. Instantánea con `list_all()`.** Garantiza invariantes y evita una consulta por técnico o por estado. *Alternativa descartada: contar con `count_by_*` separados*, puede mezclar instantáneas y romper las sumas.
- **D3. Técnicos con cero desde el contrato de identity.** El dashboard administrativo debe mostrar la carga real del equipo, incluida la capacidad libre. *Alternativa descartada: mostrar solo técnicos con tickets*, oculta quién no tiene carga.
- **D4. `sin_prioridad` y `sin_asignar` explícitos.** Los totales cuadran y la UI puede explicar las categorías. *Alternativa descartada: excluirlos*, los KPIs no sumarían.
- **D5. Sin periodo en HU-11.** El gráfico de actividad y los rangos 7/30/90 son de HU-24; el contrato actual entrega el estado vigente. *Alternativa descartada: añadir `days` ahora*, duplica alcance y complica la semántica de los KPIs.
- **D6. Datos reales desde la fuente en memoria.** Coherente con el estado actual del backend; la sustitución por PostgreSQL no cambia el contrato. *Alternativa descartada: consultar PostgreSQL directamente*, hoy devolvería una base vacía y rompería la coherencia con HU-02..HU-04.

## 8. Riesgos y supuestos

- **Persistencia en memoria**: el dashboard refleja los tickets de la sesión del backend; al reiniciar se vacía.
- **Técnicos con cero**: solo se incluyen si el contrato de identity devuelve el directorio; si no hay técnicos, `sin_asignar` sigue apareciendo.
- **Muchos tickets**: una sola pasada es suficiente para el volumen del MVP; no se añade caché.
- **Clientes**: no acceden; el 404 es coherente con la política de no revelación del proyecto.
- **Frontend**: depende de que HU-21 haya creado el scaffold, el cliente HTTP y el armazón.

## 9. Dudas abiertas

- Ninguna. El orden visual exacto de las tarjetas se ajusta al implementar, sin cambiar el contrato.
