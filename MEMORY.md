# Memoria del proyecto

## Estado actual

- HU-01..HU-05 completas en `develop` (HU-05 mergeada, PR #10). Suite completa con
  `DATABASE_URL`: **826 passed, 3 failed** (los 3 fallos son previos: precedencia
  401/404 con cookie invalida por `starlette`/`httpx`).
- HU-06 (detalle del ticket) **implementada** en `feature/Hu-06-tickets-sla`
  (cambios sin commit): spec, plan y `tasks.md` en `specs/features/HU-06-ticket-detail/`
  (tareas redactadas a posteriori, todas cerradas).
- HU-10 (alertas SLA) **implementada** en `specs/features/HU-10-sla-alerts/`
  (T1-T6 cerradas; cambios sin commit, a la espera de PR contra `develop`).
- TSK-025 (PostgreSQL multitenant) mergeada (PR #9). Los modulos siguen con
  persistencia en memoria; integrarlos con PostgreSQL es una tarea aparte.
- `HU-20` (frontend) con spec/plan/tareas, sin codigo. HU-08..HU-19 definidas
  solo en el documento general.

## Decisiones HU-07

- Subrecurso `POST/GET /api/tickets/{ticket_id}/comments`: no cambia
  `TicketResponse` ni los resumenes de HU-02..HU-06.
- Escriben `tecnico` y `administrador`; el cliente que intenta escribir recibe el
  404 uniforme (`ticket not found`), aunque el ticket sea suyo. Sin 403.
- Lee quien puede ver el ticket (misma regla de HU-06): cliente solo los suyos;
  staff cualquiera. Un ticket `Cerrado` responde 409 al comentar y 200 al listar.
- `body` texto estricto, recortado, 1-2000 code points; 422 si es invalido o
  trae campos extra. Autor de la sesion y `created_at` del sistema.
- Respuesta: `{id, ticket_id, body, author: {id, name} | null, created_at}`;
  el autor se resuelve con `get_user_summary`. Sin correo, rol ni credenciales.
- Listado ascendente por `created_at`; empate conserva el orden de registro.
- Persistencia en memoria (`InMemoryTicketCommentRepository`). La tabla
  `ticket_comments` ya existe; conectarla a PostgreSQL sigue pendiente.

## Decisiones HU-06

- Cliente solo sus tickets (HU-02); `tecnico` y `administrador` abren cualquier
  ticket, asignado o no. Sin rutas nuevas: se amplia `GET /api/tickets/{id}`.
- `TicketResponse` (creacion, detalle, prioridad, estado y asignacion) añade
  `requester {id, name, email}` y `resolved_at`; `requester_id` se conserva.
  Los resumenes de listado no cambian (evita una lectura N+1).
- `requester` se resuelve por contrato de `identity` (`user_summaries` +
  `users_contract`); `null` si no se resuelve; nunca rol, hash ni credenciales.
- 404 uniforme para staff con ticket inexistente o identificador invalido;
  401 antes que 404. El detalle es de solo lectura: HU-03/HU-04 no cambian.
- «Todos los tickets» con busqueda, filtros y paginacion (ADR-002) queda fuera;
  corresponde a otra historia.

## Decisiones HU-10

- Listado `GET /api/tickets/requiring-attention`: consulta derivada y de solo
  lectura de tickets activos (`Abierto`/`En progreso`) con SLA `en_riesgo` o
  `incumplido`. Reutiliza `get_ticket_sla` de HU-05 (umbral 20 %), sin calculo,
  umbral ni estado persistido nuevos (se deriva en vivo con un unico `now`).
- `list_all()` en `ticket_repository.py` devuelve todos los tickets (sin filtrar
  por creador/asignacion); la regla vive en `list_attention_tickets.py` (aplicacion).
- Ruta estatica declarada **antes** de `/{ticket_id}` para no colisionar.
- Guardia de rol de gestion (`tecnico`/`administrador`) antes de leer el repo:
  cliente -> 404 uniforme (`TicketNotFoundError`), sin sesion -> 401 (precedencia
  401 > 404). Orden por `sla.due_at` ascendente; composicion de resumen HU-04/HU-06.

## Decisiones HU-05

- Valores iniciales: Critica 120, Alta 240, Media 720, Baja 1440 min, en
  `sla/application/policies.py`. Config global en memoria; API/UI -> HU-14.
- Ticket sin prioridad: `sla: null`. Al fijar prioridad vence desde `created_at`.
- Umbral proximo a vencer: <= 20 % del objetivo restante (y > 0).
- `sla` va dentro de todas las respuestas de ticket (misma composicion).
- Al pasar a `Resuelto`/`Cerrado` se fija `Ticket.resolved_at` y el SLA se
  congela (`cumplido`/`incumplido`); al reabrir se descarta y se reanuda.
- Calculo puro en `sla/domain`; `tickets.interface` lo compone via
  `sla/interface/contract.py`. `sla` nunca importa `tickets` (sin ciclo).

## Decisiones TSK-025

- Una BD y un esquema para todas las empresas; `company_id` en `users`,
  `tickets` y `sla_policies`; `ticket_sla` y `ticket_comments` lo heredan.
- FK compuestas `(company_id, requester_id/assignee_id) -> users(company_id,id)`.
- Email unico global; roles `cliente`, `tecnico`, `administrador`.

## Entorno local

- `.venv` en `backend/`; instalar `backend/requirements.txt`.
- `infra/.env` (ignorado por git) con `POSTGRES_PORT=55432`; el 5432 lo ocupa
  un PostgreSQL nativo. Arrancar Docker Desktop y `docker compose up -d` en
  `infra/` antes de los tests de BD.
- `DATABASE_URL=postgresql://helpdesk:helpdesk_dev@127.0.0.1:55432/helpdesk`
  para migraciones y tests de BD; sin el, esos 14 tests se saltan.

## Errores que se deben evitar

- No usar el puerto 5432 en esta maquina.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`.
- `codegraph` solo corre via `cmd /c` (la politica de scripts bloquea el .ps1).
- No poner logica de negocio en los HTTP ni tocar tablas de otros modulos.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default al final.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string.
- Un `TestClient` tiene una sola cookie: usar un cliente por rol.
- Al cambiar el contrato de ticket hay que ajustar los tests que comparan el
  conjunto exacto de campos (ahora incluye `requester` y `resolved_at`); los
  tests de API envejecen el ticket mutando `created_at` para no dormir.

## Proximos pasos

- Commit/PR de HU-06 contra `develop`.
- Commit/PR de HU-10 contra `develop` (cambios ya en verde, sin commit).
- HU-14: configuracion publica de SLA (API/UI).
- Integrar los modulos con PostgreSQL en una tarea aparte.
- Revisar los 3 tests fallidos por dependencias actuales.
- PRs siempre contra `develop`; `main` solo recibe versiones estables.
