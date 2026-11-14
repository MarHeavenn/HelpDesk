# Plan HU-22 — Formularios e interfaz de creación y edición de tickets

Spec base: `specs/features/HU-22-create-edit-tickets/spec.md` (Estado: aprobada; RF-105 a RF-112; decisiones D1–D5).
Restricción principal: **solo frontend**. Se usan los contratos existentes del backend; no se añaden endpoints ni campos editables. La creación (RF-105 a RF-108) ya está implementada; este plan conserva lo hecho y detalla lo pendiente (RF-109 a RF-112).

## 1. Estado actual

- `/tickets/nuevo` ya usa `POST /api/tickets` y `PUT /api/tickets/{id}/priority`.
- El SLA del administrador se lee de `GET /api/sla/policies`.
- La validación del alta vive en `frontend/src/lib/ticketForm.ts` y sigue el contrato de HU-02.
- El aviso de alta y el fallo de prioridad se muestran en `/mis-tickets` con `location.state`.
- Hay 10 pruebas en `frontend/tests/pages/CreateTicketPage.test.tsx`.

Lo pendiente es el detalle y la edición: la vista que muestra un ticket y permite cambiar prioridad, estado, técnico y comentarios según el rol.

## 2. Archivos previstos

```
frontend/src/
  api/
    tickets.api.ts          # POST /tickets, GET /tickets/{id}, PUT priority/status/assignee,
                            # GET/POST /tickets/{id}/comments
  types/
    ticket.ts               # Ticket, Priority, Status, Assignee, Requester, Sla, Comment
  lib/
    ticketForm.ts           # validación del alta y del comentario
    permissions.ts          # canSetTicketPriority, canChangeTicketStatus,
                            # canAssignTicket, canCommentTicket
    strings.ts              # todos los textos de la historia
  pages/
    CreateTicketPage.tsx    # ya implementada
    TicketDetailPage.tsx    # pendiente; o el modal equivalente si se elige el ADR
  components/
    tickets/
      TicketEditPanel.tsx   # formulario de prioridad/estado/técnico
      TicketComments.tsx    # listado y alta de comentarios
  routes.tsx                # ruta del detalle si se elige /tickets/:id
frontend/tests/
  pages/TicketDetailPage.test.tsx
  components/tickets/TicketEditPanel.test.tsx
  components/tickets/TicketComments.test.tsx
```

Estado: `TicketDetailPage.tsx` y los componentes no existen todavía. No se crean hasta resolver la duda de presentación.

## 3. Contratos HTTP

| Operación | Petición | Respuesta | Permiso |
|---|---|---|---|
| Crear ticket | `POST /api/tickets` · `{title, description}` | 201 `TicketResponse` | Cualquier sesión |
| Detalle | `GET /api/tickets/{id}` | 200 `TicketResponse` | Cliente: solo el suyo; admin/técnico: cualquiera |
| Prioridad | `PUT /api/tickets/{id}/priority` · `{priority}` | 200 `TicketResponse` | Administrador y técnico |
| Estado | `PUT /api/tickets/{id}/status` · `{status}` | 200 `TicketResponse` | Administrador y técnico |
| Asignación | `PUT /api/tickets/{id}/assignee` · `{assignee_id}` | 200 `TicketResponse` | Solo administrador |
| Comentarios | `GET /api/tickets/{id}/comments` | 200 `CommentResponse[]` | Cliente: su ticket; admin/técnico: cualquiera |
| Nuevo comentario | `POST /api/tickets/{id}/comments` · `{body}` | 201 `CommentResponse` | Administrador y técnico |

Catálogos y reglas que el frontend debe respetar:

- Prioridades: `Crítica`, `Alta`, `Media`, `Baja`.
- Estados: `Abierto`, `En progreso`, `Resuelto`, `Cerrado`.
- Transiciones válidas: `Abierto → En progreso`; `En progreso → Resuelto`; `Resuelto → Cerrado`; `Resuelto → En progreso`.
- Un ticket `Cerrado` no admite prioridad, estado ni asignación (409).
- Comentario: 1 a 2000 code points después de recortar.
- `TicketResponse`: `{id, title, description, priority, status, assignee, requester, sla, created_at, resolved_at, requester_id}`.
- `CommentResponse`: `{id, ticket_id, body, author, created_at}`.

## 4. Capas y responsabilidades

La historia es de presentación: no toca `domain`, `application`, `infrastructure` ni `interface` del backend.

- **API**: `tickets.api.ts` encapsula las rutas y tipos. Ningún componente llama a `fetch`.
- **Tipos**: `types/ticket.ts` refleja exactamente `TicketResponse` y `CommentResponse`; no se inventan campos.
- **Permisos**: `lib/permissions.ts` concentra la matriz de acciones para que la vista no repita condicionales de rol.
- **Validación**: `lib/ticketForm.ts` mantiene la validación del alta y añade la del comentario.
- **Presentación**: la página o el modal solo orquesta estado de carga, error, formulario y confirmaciones.
- **Textos**: todo en `lib/strings.ts`, en español.

## 5. Decisiones y alternativas

- **D1 — El cliente no elige prioridad.** Ya implementado. *Alternativa descartada: guardar la prioridad local*, que mostraría un dato que el backend no tiene.
- **D2 — Título y descripción de solo lectura.** No hay endpoint de edición y HU-06 es de solo lectura. *Alternativa descartada: habilitar la edición y descartar los cambios*, que engaña al usuario.
- **D3 — Edición limitada a prioridad, estado, técnico y comentarios.** Son los datos que el backend acepta. *Alternativa descartada: edición genérica*, que exige cambios de backend.
- **D4 — Sin mock.** La historia usa la API real. *Alternativa descartada: seed de ejemplo*, que mezclaría datos.
- **D5 — Pruebas con un cliente API falso.** Igual que el resto del frontend. *Alternativa descartada: E2E*, fuera del runner acordado.
- **D6 — Presentación pendiente.** El ADR proponía un modal; una ruta `/tickets/:id` es más adecuada para un formulario de edición con comentarios. Se decide antes de T4. La alternativa del modal se conserva como respaldo si se prioriza no añadir rutas.

## 6. Estrategia de pruebas

- **Alta (ya hecha)**: 10 pruebas de validación, SLA, alta, prioridad, error de red y descarte.
- **Detalle**: render de los campos, ticket sin prioridad/SLA, ticket cerrado y estados de carga/error.
- **Edición**: prioridad y estado para técnico; asignación solo para administrador; cliente sin acciones; 409/422 visibles; actualización de la vista tras el éxito.
- **Comentarios**: listado, estado vacío, alta para admin/técnico, cliente sin formulario, validación 1–2000 y error del backend.
- **Permisos**: pruebas de `canChangeTicketStatus`, `canAssignTicket` y `canCommentTicket` por rol.
- **Cierre**: `npm run test`, `npm run lint` y `npm run build` en verde.

No se declara una prueba ejecutada si no se ha ejecutado.

## 7. Orden de implementación

1. Resolver la duda de presentación (modal o `/tickets/:id`).
2. Extender `tickets.api.ts` y `types/ticket.ts` con detalle, estado, asignación y comentarios.
3. Añadir permisos y textos.
4. Implementar el detalle y el panel de edición.
5. Implementar el seguimiento de comentarios.
6. Probar, lint, build y smoke manual con las tres cuentas.

## 8. Riesgos

- **El backend no edita título ni descripción.** Si el usuario espera un formulario completo, hay que acordar primero un cambio de backend; no se simula.
- **El cliente no puede editar nada.** La tarjeta dice «cliente o técnico»; el backend solo permite crear al cliente. Se documenta y se valida con el usuario.
- **La presentación en modal puede quedarse corta.** Prioridad, estado, técnico y comentarios en un modal exigen mucho espacio; la ruta dedicada es la opción recomendada.
- **Los errores de precedencia del backend** (401 > 404 > 409 > 422) deben reflejarse sin romper la vista; el cliente HTTP ya normaliza `detail`.
