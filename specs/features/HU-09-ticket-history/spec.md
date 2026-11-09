# Spec HU-09 — Registrar historial y trazabilidad del ticket
Estado: implementada

## Contexto y objetivo

HU-03, HU-04, HU-07 y HU-08 ya dejan constancia interna de los cambios importantes del ticket: prioridad y estado en el registro de modificaciones, asignaciones y reasignaciones en su propio registro, y comentarios de seguimiento en el repositorio de comentarios. Sin embargo, esa información no se puede consultar: cada registro es interno y está repartido en fuentes distintas. El administrador y el técnico no disponen de una vista única que explique qué le ocurrió a un ticket, quién lo hizo y cuándo.

HU-09 convierte esos registros en una **consulta cronológica de historial** por ticket. La historia no crea un registro nuevo ni duplica los existentes: expone una vista de solo lectura que reúne, ordena y presenta los eventos ya registrados por las historias anteriores. Así se conserva la trazabilidad sin introducir una segunda fuente de verdad y sin cambiar las reglas de negocio de prioridad, estado, asignación o comentarios.

## Usuarios / actores

- Administrador (rol `administrador`): consulta el historial completo de cualquier ticket, para auditar y supervisar.
- Técnico (rol `tecnico`): consulta el historial completo de cualquier ticket, para entender el trabajo previo antes de atenderlo.
- Cliente (rol `cliente`): no consulta el historial; recibe el 404 uniforme de HU-02/HU-06 aunque el ticket sea suyo.
- Visitante sin autenticación: 401, como en el resto de operaciones de gestión.

## Historias de usuario

- H1: Como administrador, quiero consultar el historial de cambios de un ticket, para conocer las acciones realizadas y mantener su trazabilidad.
- H2: Como técnico, quiero consultar el historial de un ticket, para entender su evolución antes de continuar la atención.
- H3: Como responsable de soporte, quiero que cada evento identifique la acción, el usuario responsable, la fecha y hora y los valores anteriores y nuevos cuando apliquen, para poder reconstruir lo ocurrido.
- H4: Como usuario, quiero que el historial se conserve aunque el ticket esté cerrado, para no perder la trazabilidad al finalizar la solicitud.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global de requisitos llega a RF-80. HU-08 y HU-14 ocuparon en paralelo el bloque RF-71 a RF-80; para no agravar ese solapamiento previo, HU-09 usa RF-81 a RF-90.

- RF-81: EL SISTEMA expondrá la consulta `GET /api/tickets/{ticket_id}/history`, de solo lectura, que devolverá 200 con un array JSON con todos los eventos del ticket ordenados del más antiguo al más reciente. La consulta no modificará el ticket ni ninguno de los registros consultados.

- RF-82: EL SISTEMA incluirá en el historial exactamente estos eventos, cada uno con su propio tipo de acción:
  - la **creación** del ticket, con el solicitante como usuario responsable y la fecha y hora de creación;
  - cada **asignación** y **reasignación** efectiva de técnico, con el usuario que la realizó, el técnico anterior (vacío en la primera asignación), el técnico nuevo y la fecha y hora del registro;
  - cada **cambio efectivo de prioridad**, con el usuario que lo realizó, la prioridad anterior (vacía si el ticket no tenía prioridad) y la nueva;
  - cada **cambio efectivo de estado**, incluida la **reapertura** de `Cerrado` a `Abierto`, con el usuario que lo realizó, el estado anterior y el nuevo;
  - cada **comentario de seguimiento**, con su autor, su contenido y la fecha y hora de registro.

- RF-83: EL SISTEMA identificará cada evento con: el tipo de acción, el usuario responsable mediante su identificador opaco de sesión y, cuando esté disponible en el contrato de identidad, su nombre visible; la fecha y hora en formato ISO 8601 con zona UTC; y los valores anterior y nuevo cuando el evento los tenga (prioridad, estado, técnico anterior y técnico nuevo). Los comentarios incluirán además su contenido. El usuario responsable y la fecha nunca se tomarán del cuerpo de una petición, sino de los registros generados por las historias de origen.

- RF-84: EL SISTEMA permitirá consultar el historial únicamente a los roles `administrador` y `tecnico`, tomando rol e identidad de la sesión de HU-01. SI la petición llega sin sesión válida, ENTONCES EL SISTEMA responderá 401 antes de cualquier otra comprobación. SI un usuario autenticado con rol `cliente` consulta el historial, o si el ticket no existe o el identificador no tiene formato válido, ENTONCES EL SISTEMA responderá 404 con el cuerpo uniforme `{"detail": "ticket not found"}`, sin revelar si el ticket existe. No se usa 403.

- RF-85: EL SISTEMA mantendrá el historial consultable en cualquier estado del ticket. SI el ticket está `Cerrado`, ENTONCES EL SISTEMA responderá 200 con su historial completo, sin responder 409 y sin reabrir ni modificar nada. La consulta no habilitará operaciones bloqueadas por el cierre: solo devuelve información.

- RF-86: EL SISTEMA ordenará los eventos de forma ascendente por fecha y hora. SI dos o más eventos comparten la misma fecha y hora, ENTONCES EL SISTEMA aplicará un orden estable y determinista: primero la creación, después asignación, prioridad, estado y comentario; dentro de una misma fuente se conservará el orden de registro. La consulta repetida sobre el mismo estado devolverá el mismo orden.

- RF-87: EL SISTEMA incluirá únicamente eventos efectivos. SI una operación no produjo un cambio real (repetir la prioridad o el estado vigente, repetir el técnico asignado), o si fue rechazada (transición inválida, ticket cerrado, asignación inválida, comentario inválido, falta de permiso), ENTONCES EL SISTEMA no añadirá ningún evento al historial. Una misma acción no se duplicará por figurar en más de una fuente interna.

- RF-88: EL SISTEMA resolverá el nombre visible de cada usuario a través del contrato público de identidad, sin acceder a las estructuras internas del módulo `identity` ni exponer correo, rol o credenciales. SI un usuario responsable ya no puede resolverse, ENTONCES EL SISTEMA conservará el evento y su identificador, y devolverá el nombre como vacío, sin eliminar ni alterar la trazabilidad.

- RF-89: EL SISTEMA mantendrá intactos los contratos existentes: `TicketResponse`, los resúmenes, los comentarios y las respuestas de las operaciones de HU-02 a HU-08 no cambian. La única ruta nueva es `GET /api/tickets/{ticket_id}/history`; no se añaden campos a las respuestas existentes ni se exponen directamente los registros internos. Los parámetros de consulta desconocidos se ignoran en silencio, con la misma regla de HU-02 y HU-10.

- RF-90: EL SISTEMA limitará esta historia a la consulta del historial. No habrá paginación, filtros, búsqueda, exportación, borrado ni edición de eventos; no se crearán eventos nuevos distintos de los que ya generan HU-02, HU-03, HU-04, HU-07 y HU-08; y no se incluirán cambios globales de configuración de SLA, inicios de sesión ni otras acciones ajenas al ticket. La persistencia seguirá en memoria y la integración con PostgreSQL quedará fuera de alcance.

## Requisitos no funcionales

- Separación de capas y módulos: la vista de historial es un caso de uso de lectura de `tickets/application`; la interfaz solo traduce errores y serializa. No se crea un módulo nuevo.
- Sin duplicar datos: el historial se deriva de las fuentes ya existentes (creación del ticket, registro de modificaciones, registro de asignaciones y repositorio de comentarios) y no crea una segunda fuente de verdad.
- Sin dependencias nuevas, sin cambios de autenticación ni de roles, sin control de concurrencia y sin complejidad innecesaria.
- Coherencia con HU-06: se reutiliza `get_ticket_detail` para la visibilidad y el 404 uniforme, y con HU-07 para la resolución del nombre visible de los autores.
- Rendimiento suficiente para el MVP en memoria: la consulta recorre los registros del ticket una vez por fuente; no se exige paginación en esta iteración.
- Sin cambios de persistencia: todo sigue en memoria; PostgreSQL continúa pendiente y fuera de alcance.

## Casos límite

- Ticket recién creado y sin más acciones → historial con un único evento de creación.
- Ticket con prioridad fijada por primera vez → evento de prioridad con valor anterior vacío.
- Cambio de prioridad repetido o cambio al mismo estado → sin evento nuevo (RF-87).
- Transición de estado inválida o intento sobre ticket cerrado → sin evento nuevo (RF-87).
- Asignación inicial, reasignación y repetición del técnico vigente → solo las dos primeras generan evento; la repetición no (RF-87).
- Comentario creado → evento con autor, contenido y fecha; comentario inválido → sin evento.
- Reapertura de un ticket cerrado → evento de estado `Cerrado` → `Abierto` con el administrador responsable.
- Ticket cerrado con historial → 200 con todos los eventos, sin 409 (RF-85).
- Cliente consultando el historial de un ticket propio → 404 uniforme (RF-84).
- Ticket inexistente o identificador con formato inválido → 404 uniforme (RF-84).
- Petición sin sesión → 401 antes que 404 (RF-84).
- Varios eventos con la misma fecha y hora → orden estable y repetible (RF-86).
- Usuario responsable que ya no se puede resolver → evento conservado con identificador y nombre vacío (RF-88).
- Parámetros de consulta desconocidos → se ignoran sin alterar la respuesta (RF-89).

## Fuera de alcance

- Persistencia del historial en PostgreSQL y cualquier cambio de esquema.
- Paginación, filtros por tipo, usuario o fecha, búsqueda y exportación.
- Edición, borrado o corrección manual de eventos.
- Notificaciones, webhooks o suscripciones al historial.
- Eventos de acciones ajenas al ticket (configuración de SLA, sesiones, cambios de usuarios).
- Frontend y cualquier cambio en `TicketResponse` o en los resúmenes.

## Criterios de finalización

- Todos los RF-81 a RF-90 tienen al menos una prueba automatizada con pytest y TestClient que verifica su cumplimiento.
- La suite completa sigue pasando, salvo los fallos preexistentes de precedencia 401/404 con cookie inválida, que se documentan como ajenos a esta historia.
- `specs/features/HU-09-ticket-history/` contiene `spec.md`, `plan.md` y `tasks.md`; la spec y el plan quedan en `implementada`/`implementado` al cerrar.
- `MEMORY.md` y `specs/project.md` reflejan el estado final y las decisiones tomadas.
- Se ejecuta `codegraph sync` tras los cambios de código.

## Dudas abiertas

- Ninguna pendiente. Las decisiones de visibilidad (administrador y técnico) y de eventos incluidos (creación, asignación, prioridad, estado/reapertura y comentarios) fueron confirmadas por el usuario antes de redactar esta spec.
