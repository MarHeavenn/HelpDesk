# Plan HU-23 — Vistas de tickets con filtros

Spec base: `specs/features/HU-23-tickets-views/spec.md` (aprobada; RF-119 a RF-123).
Restricción: datos reales. Se añade un único endpoint de lectura; no se cambian contratos existentes ni la persistencia.

## 1. Backend

- `tickets/application/list_all_tickets.py`: caso de uso `list_all_tickets(actor_role, tickets)`. Solo `MANAGEMENT_ROLES`; cualquier otro rol lanza `TicketNotFoundError` con el mensaje uniforme de HU-02 antes de leer el repositorio (RF-122).
- `tickets/interface/router.py`: `GET /api/tickets/all` declarado **antes** de `GET /api/tickets/{ticket_id}` para que la ruta estática no se capture como identificador. Reutiliza `ticket_summary` y un único `now` para todo el listado. Traduce `TicketNotFoundError` a 404 y deja el 401 a `get_current_user`.
- Sin cambios en repositorios: `list_all()` ya existe y ordena por `created_at` descendente.
- Pruebas: `backend/tests/test_tickets_list_all_endpoint.py` con TestClient y sesiones reales por rol (un cliente por rol): 200 admin/técnico con todos los tickets y resumen exacto; 404 cliente; 401 sin sesión; orden descendente; lista vacía; parámetros desconocidos ignorados; la ruta no rompe `/api/tickets/{id}`.

## 2. Frontend — datos

- `types/ticket.ts`: `TicketSummary`, `TicketDetail`, `TicketAssignee`, `TicketRequester`, `TicketSla`, `Technician`, catálogos `STATUSES` y transiciones de estado de HU-08.
- `api/tickets.api.ts`: `listMine`, `listAssigned`, `listAll`, `getTicket`, `setStatus`, `assign`, `listTechnicians`, `listComments`, `addComment`; los cuerpos exactos `{status}`, `{assignee_id}`, `{body}`.
- `hooks/useTickets.ts`: claves `['tickets','list',scope]`, `['tickets','detail',id]`, `['tickets','comments',id]` y `['technicians']`; consultas con `retry: false`.
- `lib/tickets.ts`: funciones puras `filterTickets`, `sortTickets`, `paginateTickets`, `parseTicketQuery` y `ticketQueryToParams`, compartidas por ambas vistas y probadas sin React.

## 3. Frontend — componentes y vistas

- `components/tickets/TicketTable.tsx`: tabla del ADR-002 con scroll horizontal, filas enfocables, «Ver detalle» por fila y SLA.
- `components/tickets/TicketFilters.tsx`: buscador con debounce, prioridad, estado, técnico (oculto al cliente), orden y «Limpiar filtros».
- `components/ui/Pagination.tsx`: anterior/siguiente y páginas con `aria-current`.
- `pages/TicketListPage.tsx`: componente único para `/tickets` y `/mis-tickets`; recibe el alcance (`all`, `mine`, `assigned`), sincroniza la query string, aplica filtros/orden/paginación y cubre carga, vacío, error y 401.
- `pages/TicketsPage.tsx` y `pages/MyTicketsPage.tsx`: envoltorios finos con título/subtítulo por rol; `MyTicketsPage` conserva `CreatedTicketNotice`.
- `routes.tsx`: sustituye los marcadores por las vistas reales.

## 4. Detalle (HU-22, desbloqueado)

- `components/ui/Modal.tsx`: diálogo accesible con foco atrapado, Escape, clic fuera y retorno del foco.
- `components/tickets/TicketDetailModal.tsx`: usa `GET /api/tickets/{id}`, muestra todos los campos de `TicketResponse`, permite prioridad/estado (admin/técnico), asignación (admin) y comentarios (admin/técnico); ticket cerrado deshabilita acciones; 409/422 se muestran sin cerrar el modal.
- `lib/permissions.ts`: `canChangeTicketStatus`, `canAssignTicket`, `canCommentTicket`.

## 5. Pruebas

- pytest: endpoint global (RF-122).
- Vitest: `lib/tickets` (filtros/orden/paginación/URL), `TicketsPage` (datos, filtros, URL, vacío, error, 401), `MyTicketsPage` (fuente por rol), `TicketDetailModal` (render, permisos, acciones, 409/422, Escape y comentarios) y cliente API con `fetch` falso.
- `npm run test`, `npm run lint` y `npm run build` desde `frontend/`.

## 6. Decisiones

- **D1. Endpoint dedicado `/api/tickets/all`.** Evita cambiar el significado de `GET /api/tickets` y mantiene el 404 uniforme del cliente. *Alternativa descartada: parámetro `?scope=all`*, que rompe el contrato actual y obliga a ramificar dentro del mismo caso de uso.
- **D2. Filtrado en cliente.** El endpoint devuelve el listado completo (persistencia en memoria, alcance del MVP) y la URL se resuelve sin llamadas adicionales. *Alternativa descartada: paginación en servidor*, fuera de alcance y sin índice de base de datos todavía.
- **D3. Un solo componente de listado.** Evita duplicar tabla, filtros y paginación entre las dos vistas (RF-123). *Alternativa descartada: dos páginas con copia*, mayor deuda.
- **D4. Detalle en modal.** Decisión aprobada por el usuario y coherente con RF-53; no se añade la ruta `/tickets/:id`. *Alternativa descartada: ruta dedicada*, fuera de la spec de referencia.
