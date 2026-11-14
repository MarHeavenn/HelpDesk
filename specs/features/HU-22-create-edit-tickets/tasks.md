# Tareas HU-22 — Formularios e interfaz de creación y edición de tickets

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde. Verificación desde `frontend/`: `npm run test`, `npm run lint` y `npm run build`.
Fuente de datos: API real. No se modifica el backend ni se añaden campos que no existan en los contratos.

- [x] **T1. Alta real de ticket.** RF-105 a RF-108
  - Hecho cuando: `/tickets/nuevo` valida título 1–200 y descripción 1–5000 code points tras recortar, muestra el SLA de la prioridad solo al administrador, crea con `POST /api/tickets`, fija la prioridad con `PUT /api/tickets/{id}/priority` para administrador y técnico, avisa en `/mis-tickets` y redirige; cancelar con cambios pide confirmación; **10 pruebas en verde** de validación, SLA, alta, prioridad, error de red y descarte.
  - Estado: implementada. Archivos: `api/tickets.api.ts`, `lib/ticketForm.ts`, `types/ticket.ts`, `pages/CreateTicketPage.tsx`, `pages/CreatedTicketNotice.tsx`, `tests/pages/CreateTicketPage.test.tsx`.

- [x] **T2. Extender el cliente API y los tipos del detalle.** RF-109 a RF-111
  - Hecho cuando: `tickets.api.ts` expone `getTicket`, `setStatus`, `setAssignee`, `listComments` y `addComment` con los cuerpos exactos (`{status}`, `{assignee_id}`, `{body}`); `types/ticket.ts` refleja `TicketResponse` completo (`assignee`, `requester`, `sla`, `resolved_at`), los catálogos de estado y el `CommentResponse`; pruebas del cliente con `fetch` falso en verde.
  - Estado: implementada. `assign` cubre la asignación; métodos añadidos también para listados y técnicos. Pruebas: `tests/api/tickets.api.test.ts`.

- [x] **T3. Permisos y textos de edición.** RF-110, RF-111
  - Hecho cuando: `lib/permissions.ts` expone `canChangeTicketStatus` (administrador y técnico), `canAssignTicket` (solo administrador) y `canCommentTicket` (administrador y técnico), con pruebas por rol; `lib/strings.ts` centraliza etiquetas, confirmaciones y errores en español.
  - Estado: implementada. Pruebas en `tests/lib/permissions.test.ts`; textos en `strings.tickets.detail`.

- [x] **T4. Detalle del ticket y panel de edición.** RF-109, RF-110
  - Hecho cuando: el detalle muestra todos los campos disponibles, el título y la descripción son de solo lectura, el cliente no ve acciones, el técnico cambia prioridad y estado y el administrador además asigna técnico; un ticket cerrado deshabilita las acciones; los errores 409/422 se muestran sin perder la vista; pruebas de render, permisos, éxito y error en verde.
  - Presentación decidida: modal accesible desde la tabla (2026-11-13).
  - Estado: implementada. Archivos: `components/ui/Modal.tsx`, `components/tickets/TicketDetailModal.tsx`, `tests/components/TicketDetailModal.test.tsx`.

- [x] **T5. Seguimiento de comentarios.** RF-111
  - Hecho cuando: el detalle lista `GET /api/tickets/{id}/comments`, muestra estado vacío, permite añadir a administrador y técnico con validación 1–2000 code points, el cliente no ve el formulario y los errores del backend conservan el texto escrito; pruebas de listado, alta, validación y permisos en verde.
  - Estado: implementada dentro del modal de detalle y sus pruebas.

- [ ] **T6. Cierre y verificación de la historia.** RF-105 a RF-112
  - Hecho cuando: `npm run test`, `npm run lint` y `npm run build` están en verde; el smoke manual con cliente, técnico y administrador recorre alta, detalle, prioridad, estado, asignación y comentarios; `MEMORY.md` resume el estado y no queda ningún RF sin cubrir o se documenta la brecha.
