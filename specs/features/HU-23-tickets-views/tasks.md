# Tareas HU-23 — Vistas de tickets con filtros

Orden de dependencia. Tests primero (en rojo), luego implementación hasta verde. Verificación: pytest desde la raíz y `npm run test`, `npm run lint`, `npm run build` desde `frontend/`.

- [x] **T1. Endpoint de listado global.** RF-122
  - Hecho cuando: `GET /api/tickets/all` responde 200 a administrador y técnico con todos los tickets y el resumen exacto, 404 al cliente y 401 sin sesión; declarado antes de `/{ticket_id}`; pruebas en verde.
  - Estado: implementada. Archivos: `tickets/application/list_all_tickets.py`, `tickets/interface/router.py`, `tests/test_tickets_list_all_endpoint.py` (8 pruebas).

- [x] **T2. Tipos, cliente API y permisos.** RF-119, RF-120
  - Hecho cuando: `types/ticket.ts` y `api/tickets.api.ts` cubren listados, detalle, acciones, técnicos y comentarios; `lib/permissions.ts` expone los permisos de estado, asignación y comentario; pruebas del cliente API en verde.
  - Estado: implementada. Archivos: `types/ticket.ts`, `api/tickets.api.ts`, `lib/permissions.ts`, `hooks/useTickets.ts`, `tests/api/tickets.api.test.ts`, `tests/lib/permissions.test.ts`.

- [x] **T3. Utilidades de filtros, orden y paginación.** RF-119, RF-121
  - Hecho cuando: `lib/tickets.ts` filtra por texto/prioridad/estado/técnico, ordena por los cuatro criterios, pagina de 10 en 10 y normaliza la query string; pruebas unitarias en verde.
  - Estado: implementada. Archivo: `lib/tickets.ts`, `tests/lib/tickets.test.ts`.

- [x] **T4. Tabla, filtros y paginación compartidos.** RF-119, RF-121, RF-123
  - Hecho cuando: existen `TicketTable`, `TicketFilters` y `Pagination` accesibles y responsive, con «Ver detalle» por fila.
  - Estado: implementada. Archivos: `components/tickets/TicketTable.tsx`, `components/tickets/TicketFilters.tsx`, `components/ui/Pagination.tsx`.

- [x] **T5. Vista «Todos los tickets» y «Mis tickets».** RF-119 a RF-121
  - Hecho cuando: `TicketListPage` sirve ambos alcances, sincroniza la URL, el cliente no ve filtro de técnico, los estados de carga/vacío/error/401 están cubiertos y las pruebas por rol están en verde.
  - Estado: implementada. Archivos: `pages/TicketListPage.tsx`, `pages/TicketsPage.tsx`, `pages/MyTicketsPage.tsx`, `routes.tsx`, `tests/pages/TicketsPage.test.tsx`, `tests/pages/MyTicketsPage.test.tsx`.

- [x] **T6. Detalle en modal y acciones (HU-22 T4).** RF-109, RF-110
  - Hecho cuando: el modal muestra todos los campos, respeta permisos, cambia prioridad/estado, asigna técnico, deshabilita un ticket cerrado y muestra 409/422 sin cerrarse; pruebas en verde.
  - Estado: implementada. Archivos: `components/ui/Modal.tsx`, `components/tickets/TicketDetailModal.tsx`, `tests/components/TicketDetailModal.test.tsx`.

- [x] **T7. Comentarios del detalle (HU-22 T5).** RF-111
  - Hecho cuando: el detalle lista comentarios con estado vacío, permite añadir a administrador/técnico con validación 1–2000 y conserva el texto si falla; el cliente no ve el formulario; pruebas en verde.
  - Estado: implementada. Incluida en `TicketDetailModal.tsx` y sus pruebas.

- [x] **T8. Cierre y verificación.** RF-119 a RF-123
  - Hecho cuando: pytest, `npm run test`, `npm run lint` y `npm run build` en verde; smoke manual de las tres cuentas; `MEMORY.md` actualizado.
  - Estado: verificado el 2026-11-13 (pytest: 1191 passed, 14 skipped; frontend: suite, lint y build en verde; smoke de API: 90 comprobaciones; smoke de interfaz real: 27).
