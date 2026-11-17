# Spec HU-15 — Notificaciones de tickets
Estado: implementada

## Contexto y objetivo

El ticket ya registra sus eventos importantes (creación, asignación, prioridad, estado, reapertura y comentarios), y HU-09 permite consultarlos como historial. Sin embargo, el solicitante no se entera de lo que ocurre con su solicitud salvo que vuelva a abrir el ticket: no hay ningún aviso dentro de la plataforma cuando se le asigna un técnico, cuando cambia el estado o cuando el ticket se resuelve.

HU-15 incorpora un **centro de notificaciones interno** que registra avisos dirigidos a los usuarios implicados en cada evento efectivo del ticket. Las notificaciones se generan en el backend, se consultan por API y se muestran en el frontend desde el primer momento: campana con contador de no leídas en la barra superior, página `/notificaciones` para todos los roles y panel de novedades en el dashboard del personal. No se usan servicios externos de correo, SMS ni notificaciones push; todo ocurre dentro de la aplicación.

La historia no cambia las reglas de negocio de HU-02, HU-03, HU-04, HU-07 ni HU-08: solo observa sus resultados efectivos y emite avisos. Tampoco duplica el historial de HU-09, que sigue siendo la vista cronológica completa de auditoría.

## Usuarios / actores

- **Cliente** (rol `cliente`): recibe notificaciones de sus propios tickets (asignación, cambios de estado, resolución y reapertura) y las consulta en `/notificaciones` y en la campana.
- **Técnico** (rol `tecnico`): recibe notificaciones de los tickets que tiene asignados y de los tickets que haya creado; accede a la misma campana y a la página de notificaciones que el administrador.
- **Administrador** (rol `administrador`): accede a la campana, a la página de notificaciones y al panel del dashboard; puede ver todas las notificaciones del sistema para supervisar la operación.
- **Supervisor** (rol `supervisor`): igual que el administrador en visibilidad de notificaciones.
- **Visitante sin sesión**: no accede a ninguna notificación; recibe 401.

## Historias de usuario

- H1: Como cliente, quiero recibir notificaciones sobre los cambios importantes de mis tickets, para mantenerme informado del progreso de mis solicitudes sin tener que abrirlos.
- H2: Como técnico, quiero ver los avisos de los tickets que atiendo para no perder de vista asignaciones y cambios relevantes.
- H3: Como administrador o supervisor, quiero consultar todas las notificaciones para supervisar la actividad del servicio.
- H4: Como usuario, quiero saber cuántas notificaciones no he leído y poder marcarlas como leídas, para distinguir lo nuevo de lo ya revisado.
- H5: Como usuario, quiero ver las novedades también desde el dashboard, para enterarme al entrar a la plataforma.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global de requisitos llega a RF-143 en `specs/features/HU-19-gestion-empresas-clientes/spec.md`. HU-15 usa RF-144 a RF-155.

- RF-144: EL SISTEMA registrará una notificación interna por cada evento **efectivo** del ticket que pertenezca a este catálogo:
  - **asignación** inicial de técnico (`ticket_assigned`);
  - **reasignación** a otro técnico (`ticket_reassigned`);
  - **cambio de estado** distinto de la resolución y de la reapertura (`ticket_status_changed`);
  - **resolución**, cuando el ticket pasa a `Resuelto` (`ticket_resolved`);
  - **reapertura**, cuando un ticket `Cerrado` vuelve a `Abierto` (`ticket_reopened`).

  NO se registrarán notificaciones por la creación del ticket, por cambios de prioridad, por comentarios de seguimiento, por operaciones rechazadas ni por repeticiones sin cambio real (mismo técnico, mismo estado, transición inválida, ticket cerrado). La resolución sustituye al cambio de estado genérico en esa transición, para no generar dos avisos por el mismo hecho.

- RF-145: EL SISTEMA dirigirá cada notificación al **solicitante** del ticket y al **técnico asignado** vigente, con estas reglas:
  - el solicitante recibe todos los eventos de su ticket;
  - el técnico recibe la asignación o reasignación que lo designa y los cambios de estado, resolución y reapertura del ticket que tiene asignado;
  - el usuario que ejecuta la acción no recibe notificación de su propia acción;
  - si solicitante y técnico son la misma persona, se registra una sola notificación;
  - si el ticket no tiene técnico asignado, solo se notifica al solicitante;
  - administradores y supervisores no reciben una notificación adicional por su rol; su acceso es de supervisión (RF-148).

- RF-146: EL SISTEMA identificará cada notificación con: identificador UUID opaco, tipo del catálogo de RF-144, ticket afectado `{id, title}`, destinatario `{id, name|null}`, actor `{id, name|null}`, valor anterior y valor nuevo cuando el evento los tenga (nombre del técnico anterior/nuevo o estado anterior/nuevo), fecha y hora de creación en ISO 8601 con zona UTC y `read_at` (`null` mientras no se haya leído). La notificación nunca incluirá correo, rol, credenciales ni datos internos del usuario. Los nombres visibles se resolverán con el contrato público de identidad; si un usuario ya no puede resolverse, se conservará su identificador y el nombre será `null`.

- RF-147: EL SISTEMA expondrá `GET /api/notifications`, que devolverá 200 con las notificaciones visibles para el actor ordenadas de la más reciente a la más antigua. SI dos notificaciones comparten fecha y hora, ENTONCES EL SISTEMA aplicará un orden determinista por orden de registro descendente. La consulta será de solo lectura, no tendrá paginación en esta historia, ignorará en silencio los parámetros de consulta desconocidos y responderá 401 si no hay sesión válida antes de cualquier otra comprobación.

- RF-148: EL SISTEMA aplicará esta visibilidad sobre `GET /api/notifications`:
  - `administrador` y `supervisor` ven todas las notificaciones de su misma empresa (`company_id`), incluido el ámbito sin empresa, con el mismo criterio de aislamiento multitenant que el detalle de ticket de HU-06;
  - `tecnico` y `cliente` ven únicamente las notificaciones dirigidas a ellos;
  - una lista vacía responde 200 con `[]`, nunca 404 ni 403.

  La visibilidad no altera las reglas de acceso a los tickets: un técnico no obtiene acceso al detalle de un ticket por el hecho de ver una notificación, y el cliente sigue viendo solo sus tickets.

- RF-149: EL SISTEMA expondrá `GET /api/notifications/unread-count`, que devolverá 200 con `{"count": n}`, donde `n` es el número de notificaciones **dirigidas al actor** y aún no leídas. El contador será el mismo para todos los roles, incluidos administrador y supervisor: la supervisión de todas las notificaciones no convierte en propias las de otros usuarios. Sin sesión válida responderá 401; los parámetros desconocidos se ignorarán.

- RF-150: EL SISTEMA expondrá `POST /api/notifications/{notification_id}/read`, que marcará como leída una notificación **dirigida al actor** y devolverá 200 con la notificación actualizada. La operación será idempotente: repetirla sobre una notificación ya leída devolverá 200 sin cambiar `read_at`. SI la notificación no existe, el identificador no tiene formato válido o pertenece a otro usuario (incluido el caso de un administrador intentando marcar la de un tercero), ENTONCES EL SISTEMA responderá 404 con el cuerpo uniforme `{"detail": "notification not found"}`, sin revelar su existencia. Sin sesión válida responderá 401 antes que 404.

- RF-151: EL SISTEMA expondrá `POST /api/notifications/read-all`, que marcará como leídas todas las notificaciones no leídas **dirigidas al actor** y devolverá 200 con `{"updated": n}`. Será idempotente: si no hay pendientes devolverá `{"updated": 0}`. Nunca modificará notificaciones de otros usuarios. Sin sesión válida responderá 401.

- RF-152: EL FRONTEND dispondrá de un centro de notificaciones completo:
  - una **campana** en la barra superior con el contador de no leídas propias (incluido `9+` cuando supere nueve) y enlace a `/notificaciones`;
  - la página `/notificaciones`, accesible a todos los roles autenticados, con listado de las notificaciones visibles, distinción visual de no leídas, filtro local «Todas / No leídas», acción «Marcar como leída» por notificación y «Marcar todas como leídas»;
  - estados de carga, lista vacía, error de red con «Reintentar» y 401 con cierre de sesión y vuelta a `/login`;
  - textos en español centralizados, interfaz accesible (WCAG 2.1 AA) y responsive de 360 a 1440 px, sin datos mock ni etiqueta «Demo».

  El contador y el listado se actualizarán con una consulta periódica cada 30 segundos y al recuperar el foco de la ventana. No se usarán WebSockets ni sondeo más agresivo.

- RF-153: EL FRONTEND mostrará en el **dashboard del personal** (`/`, administrador, supervisor y técnico) un panel con las cinco notificaciones visibles más recientes y un enlace a `/notificaciones`. El técnico tendrá el mismo permiso de acceso al panel y a la página que el administrador, respetando la visibilidad de RF-148. El cliente no tiene dashboard; usa la campana y `/notificaciones`.

- RF-154: EL SISTEMA mantendrá intactos los contratos existentes: `TicketResponse`, los resúmenes, el historial y los comentarios no cambian; no se añaden campos a esas respuestas ni se crean rutas de escritura, edición o borrado de notificaciones. Las notificaciones vivirán dentro del módulo `tickets` (sin crear un módulo nuevo) y resolverán nombres solo mediante el contrato público de `identity`, sin acceder a tablas ni estructuras internas de otros módulos. La única superficie HTTP nueva es `/api/notifications` con sus cuatro operaciones.

- RF-155: La verificación cubrirá backend y frontend: pruebas de dominio, casos de uso, API, contrato OpenAPI y flujo completo con pytest y `TestClient`; pruebas de API, hooks, componentes y páginas con Vitest y Testing Library; `npm test`, `npm run build`, `npm run lint` y la suite del backend en verde, salvo los tres fallos preexistentes de precedencia 401/404 con cookie inválida. La persistencia seguirá en memoria, coherente con los tickets; PostgreSQL queda fuera de alcance.

## Requisitos no funcionales

- **Arquitectura**: nueva funcionalidad dentro de `tickets` (`domain`, `application`, `infrastructure`, `interface`). No se crea un sexto módulo ni se accede a tablas ajenas. Las reglas de destinatarios y de visibilidad viven en `application`; la interfaz solo compone y serializa.
- **Integridad**: una notificación se registra solo después de que la operación del ticket haya tenido éxito y haya dejado su registro efectivo. Las operaciones rechazadas no dejan notificaciones.
- **Privacidad**: cada usuario ve sus notificaciones; administrador y supervisor ven todas por supervisión, pero su contador y sus acciones de lectura se limitan a las suyas.
- **Sin dependencias nuevas**: no se añaden librerías, servicios de correo, colas, WebSockets ni trabajos programados.
- **Rendimiento**: consultas en memoria y sondeo ligero cada 30 s; el MVP no exige paginación.
- **Accesibilidad**: campaña con etiqueta accesible que incluya el número de no leídas, foco visible, navegación por teclado, contador anunciado y página responsive.
- **Mantenibilidad**: textos centralizados en `frontend/src/lib/strings.ts` y cliente HTTP tipado, siguiendo los patrones de tickets y empresas.

## Casos límite

- Ticket recién creado → sin notificación (la creación no está en el catálogo).
- Asignación inicial → notificación al solicitante y al nuevo técnico, salvo que alguno sea el actor.
- Reasignación al mismo técnico → sin evento y sin notificación.
- Cambio de prioridad → sin notificación.
- Comentario de seguimiento → sin notificación.
- Transición de estado inválida o intento sobre ticket cerrado → sin notificación.
- Ticket que pasa a `Resuelto` → una notificación `ticket_resolved`, no una de estado genérico.
- Ticket que pasa de `Resuelto` a `Cerrado` → una notificación `ticket_status_changed`.
- Reapertura de `Cerrado` a `Abierto` → una notificación `ticket_reopened`.
- Solicitante y técnico son la misma persona → una sola notificación.
- Ticket sin técnico asignado → solo se notifica al solicitante.
- Actor que coincide con el destinatario → no se le notifica su propia acción.
- Usuario destinatario o actor ya no resoluble → notificación conservada con `name: null`.
- Cliente que consulta notificaciones → solo las suyas; lista vacía si no tiene.
- Técnico que consulta notificaciones → solo las dirigidas a él.
- Administrador o supervisor que consulta → todas; su contador de no leídas solo cuenta las suyas.
- Administrador que intenta marcar como leída la notificación de otro → 404 uniforme.
- Marcar dos veces la misma notificación → 200 idempotente.
- «Marcar todas» sin pendientes → `{"updated": 0}`.
- Petición sin sesión → 401 antes de 404.
- Parámetros de consulta desconocidos → se ignoran sin alterar la respuesta.
- Fallo de red al cargar o marcar → la interfaz conserva el estado anterior y permite reintentar; un 401 cierra la sesión.

## Fuera de alcance

- Correo electrónico, SMS, notificaciones push y cualquier servicio externo.
- WebSockets, SSE, colas o trabajos programados.
- Preferencias de notificación, suscripciones, silenciar tipos o canales por usuario.
- Notificaciones de creación de ticket, prioridad, comentarios o alertas de SLA (estas últimas pertenecen a HU-10).
- Edición, borrado, reenvío o creación manual de notificaciones; no habrá endpoint de escritura distinto de marcar como leída.
- Paginación, filtros de servidor, búsqueda y exportación.
- Persistencia en PostgreSQL y cambios de esquema.
- Cambios en `TicketResponse`, resúmenes, historial, comentarios o reglas de ticket.
- Pruebas E2E y despliegue.

## Criterios de finalización

- Todos los RF-144 a RF-155 tienen al menos una prueba automatizada: pytest + `TestClient` en el backend y Vitest + Testing Library en el frontend.
- La suite del backend queda en verde salvo los tres fallos preexistentes de precedencia 401/404 con cookie inválida, documentados como ajenos a HU-15.
- `npm test`, `npm run build` y `npm run lint` en verde.
- `specs/features/HU-15-ticket-notifications/` contiene `spec.md`, `plan.md` y `tasks.md`; la spec y el plan quedan en `implementada`/`implementado` al cerrar.
- `specs/project.md` y `MEMORY.md` reflejan el estado final.
- Se ejecuta `codegraph sync` tras los cambios de código.
- Smoke manual con cliente, técnico, administrador y supervisor: campana, contador, página, panel del dashboard, marcar una y marcar todas.

## Dudas abiertas

Sin dudas pendientes. Las decisiones de destinatarios, eventos, estado leído/no leído, actualización cada 30 s y visibilidad por rol fueron confirmadas por el usuario antes de redactar esta spec.
