# Spec HU-06 — Gestionar información y detalle del ticket
Estado: implementada

## Contexto y objetivo
HU-02 creó el ticket y su consulta de detalle, pero esa consulta nació cerrada al propio solicitante: un técnico o un administrador no puede abrir un ticket que no creó, y la respuesta solo expone el identificador opaco del solicitante, sin sus datos de contacto. HU-06 convierte el detalle en la vista completa que el equipo de soporte necesita para atender una solicitud: reúne en una sola respuesta el ticket (título, descripción, prioridad, estado), el técnico asignado (HU-04), el solicitante con su nombre y correo, las fechas de creación y resolución y la situación del SLA (HU-05), siempre calculada en el momento de la consulta.

La historia no añade rutas: amplía `GET /api/tickets/{ticket_id}` con visibilidad según el rol y con los datos consolidados. El cliente conserva el aislamiento de HU-02 (solo sus tickets); el técnico y el administrador pueden abrir el detalle de cualquier ticket existente. El listado completo con búsqueda, filtros y paginación («Todos los tickets» del ADR-002 del frontend) queda fuera de esta historia.

## Usuarios / actores
- Técnico (rol `tecnico`): actor principal. Consulta el detalle completo de cualquier ticket para atenderlo o para revisar la cola, esté o no asignado a él.
- Administrador (rol `administrador`): consulta el detalle completo de cualquier ticket para supervisar y asignar.
- Cliente (rol `cliente`): mantiene el comportamiento de HU-02: solo el detalle de los tickets que creó. No ve tickets ajenos.
- Visitante sin autenticación: 401, como en HU-01 y HU-02.

## Historias de usuario
- H1: Como técnico, quiero consultar el detalle completo de un ticket (incluido el contacto del solicitante, el técnico asignado, la prioridad, el estado, las fechas y el SLA), para conocer toda la información necesaria para atender la solicitud.
- H2: Como administrador, quiero abrir el detalle de cualquier ticket, para supervisar y asignar con información actualizada.
- H3: Como cliente, quiero seguir viendo solo mis tickets, para que mi información no quede expuesta a otros clientes.

## Requisitos funcionales (criterios de aceptación en EARS)
> Numeración: se continúa la secuencia global de requisitos del proyecto, que llega a RF-50 en `specs/features/HU-05-sla/spec.md`, por lo que esta historia usa RF-51 a RF-60. Fuente: tarjeta Trello «HU-06 — Gestionar información y detalle del ticket» y documento general del repositorio, secciones 2 y 4. Las decisiones de alcance están en «Decisiones tomadas».

- RF-51: CUANDO un usuario autenticado con rol de gestión (`tecnico` o `administrador`) solicite `GET /api/tickets/{ticket_id}` de un ticket existente, EL SISTEMA responderá 200 con la información completa del ticket, con independencia de quién lo creó y de si el ticket está asignado o no. La visibilidad de gestión no exige que el técnico sea el responsable del ticket.
- RF-52: CUANDO un usuario autenticado con rol `cliente` solicite el detalle de un ticket, EL SISTEMA mantendrá exactamente el comportamiento de HU-02: 200 solo si el ticket lo creó él y 404 uniforme si el ticket no existe, pertenece a otro usuario o el identificador no tiene formato válido (RF-16, RF-17 y RF-18 de HU-02). Ningún cliente accede al detalle de un ticket ajeno.
- RF-53: EL SISTEMA incluirá en toda respuesta completa de ticket un objeto `requester` con el identificador opaco, el nombre y el correo del solicitante (`{id, name, email}`), resuelto a través del contrato de `identity` por el `requester_id` del ticket. El objeto no incluye rol, credenciales, hash ni ningún otro dato del usuario. SI el solicitante no se puede resolver (por ejemplo, un dato inconsistente en la persistencia), ENTONCES `requester` será `null` y el resto del detalle se devolverá con normalidad, sin error.
- RF-54: EL DETALLE de un ticket devolverá la información consolidada y actualizada: `id`, `title`, `description`, `priority` (`null` mientras no se haya fijado), `status`, `assignee` (`{id, name}` o `null`), `requester` (objeto de RF-53 o `null`), `created_at`, `resolved_at` (`null` mientras el ticket no esté resuelto; fecha y hora en que se congeló el SLA, HU-05) y `sla` (objeto de HU-05 o `null` sin prioridad). Todos los valores se derivan en el momento de la consulta: prioridad, estado, técnico, resolución y SLA reflejan el valor vigente, sin caché ni copia almacenada.
- RF-55: EL SISTEMA mantendrá la misma composición de RF-54 en todas las respuestas completas de ticket —creación, detalle, fijación de prioridad, actualización de estado y asignación o reasignación—, de modo que el mismo recurso devuelva la misma forma con independencia de la operación que lo produzca. Las respuestas de resumen (listado de tickets propios y tickets a cargo) no cambian: siguen siendo `{id, title, priority, status, assignee, sla, created_at}`, sin `requester` ni `resolved_at`.
- RF-56: SI un usuario con rol de gestión solicita el detalle de un ticket inexistente o con un identificador sin formato válido, ENTONCES EL SISTEMA responderá 404 con el mismo cuerpo uniforme de HU-02 (`{"detail": "ticket not found"}`), sin distinguir entre ambos casos y sin revelar la existencia de tickets. No se usa 403 ni se introducen códigos de error nuevos.
- RF-57: SI una petición de detalle llega sin sesión válida, ENTONCES EL SISTEMA responderá 401 antes de resolver el recurso, con independencia del rol pretendido y de que el identificador sea inexistente o inválido (precedencia 401 > 404 de HU-02, RF-18).
- RF-58: EL SISTEMA no añadirá operaciones, rutas, parámetros ni permisos nuevos: HU-06 solo amplía el detalle existente. La visibilidad de lectura de RF-51 no altera las reglas de modificación de HU-03 y HU-04 (prioridad, estado y asignación siguen rigiéndose por sus propios permisos) ni crea derechos de escritura.
- RF-59: EL SISTEMA protegerá los datos personales: nunca devolverá contraseña, hash, token, sesión ni rol del solicitante; el correo y el nombre solo aparecen dentro del objeto `requester` de las respuestas completas de ticket, nunca en los resúmenes de los listados ni en los cuerpos de error. Los parámetros de consulta desconocidos se siguen ignorando en silencio (regla de RF-15 de HU-02).
- RF-60: EL SISTEMA expresará `created_at` y `resolved_at` en ISO 8601/RFC 3339 con offset UTC y microsegundos, igual que el resto de fechas de HU-02 y HU-05, y `requester` con cadenas de texto. La consulta de detalle es de solo lectura: no muta el ticket, no registra modificaciones ni altera el SLA.

## Requisitos no funcionales
- Separación de módulos y capas: la resolución del solicitante vive en `identity` y se expone mediante un contrato de su capa `interface`; `tickets` solo compone el resultado en su capa `interface`. `tickets` no accede a las tablas internas ni al repositorio de `identity`, y `identity` no conoce `tickets`.
- Sin dependencias nuevas ni complejidad innecesaria: no se añaden librerías, cachés, endpoints ni migraciones. La persistencia sigue en memoria, como el resto de módulos.
- Consistencia de contratos: se conservan las rutas, los códigos HTTP, los mensajes de error y las reglas de HU-02 a HU-05; el único cambio es la ampliación del detalle y de las respuestas completas de ticket con `requester` y `resolved_at`.
- Privacidad y mínimo privilegio: el cliente no gana ninguna visibilidad nueva; el técnico y el administrador no reciben credenciales ni roles de terceros.
- Rendimiento suficiente: la resolución del solicitante es una lectura por ticket completo; los listados de resumen no la realizan.

## Casos límite
- Cliente consultando su propio ticket → RF-52 (200, con `requester` resuelto a sí mismo).
- Cliente consultando un ticket ajeno, inexistente o con identificador inválido → RF-52 (404 uniforme, sin datos del ticket).
- Técnico consultando un ticket no asignado → RF-51 (200; es el caso que HU-02 no cubría).
- Administrador consultando cualquier ticket → RF-51 (200).
- Técnico consultando un ticket inexistente o con identificador inválido → RF-56 (404 uniforme).
- Petición de detalle sin sesión con identificador inválido → RF-57 (401, nunca 404).
- Ticket sin prioridad → RF-54 (`sla: null`, `priority: null`).
- Ticket sin técnico asignado → RF-54 (`assignee: null`).
- Ticket resuelto → RF-54 (`resolved_at` con la fecha de resolución y `sla` congelado en `cumplido` o `incumplido`).
- Ticket reabierto tras resolverse → RF-54 (`resolved_at: null` y SLA en curso).
- Solicitante que ya no existe en `identity` → RF-53 (`requester: null`, resto del detalle intacto).
- Solicitante con rol técnico o administrador → RF-53 (el objeto `requester` se resuelve igual; el rol no se expone).
- Listado de tickets propios y tickets a cargo → RF-55 (sin `requester` ni `resolved_at`).
- Respuesta de creación o de modificación del ticket → RF-55 (misma composición que el detalle).
- Detalle con parámetros de consulta desconocidos → RF-59 (200, se ignoran).
- Intento de usar el detalle para modificar el ticket → RF-58 y RF-60 (GET de solo lectura; no existe operación nueva).

## Fuera de alcance
- Listado de todos los tickets para técnicos y administradores, con búsqueda, filtros, orden y paginación (ADR-002 del frontend): otra historia.
- Historial de cambios y trazabilidad del ticket (HU-09).
- Comentarios y seguimiento del ticket (HU-07).
- Datos adicionales del solicitante (empresa, teléfono, cargo) o del técnico (correo, carga de trabajo).
- Permisos por empresa o por equipo; políticas de visibilidad distintas del rol.
- Interfaz de usuario del frontend: HU-20.
- Persistencia en PostgreSQL y contratos multitenant: tarea de integración posterior a TSK-025.
- Modificación de prioridad, estado o asignación desde el detalle: HU-03 y HU-04 no cambian.

## Criterios de finalización
- RF-51 a RF-60 verificados con pytest: visibilidad de cliente, técnico y administrador; 404 uniforme para cliente ajeno y para staff con ticket inexistente o identificador inválido; 401 antes que 404; objeto `requester` con `{id, name, email}` y sin rol, credenciales ni hash; `requester: null` cuando el solicitante no se resuelve; `resolved_at` nulo, fijado al resolver y descartado al reabrir; `sla` de HU-05 presente o nulo; resúmenes sin `requester` ni `resolved_at`.
- Comprobado que no aparecen operaciones, rutas ni permisos nuevos y que las reglas de modificación de HU-03 y HU-04 siguen intactas.
- Actualizadas las pruebas de HU-02 a HU-05 que afirman el conjunto exacto de campos o la ausencia de datos personales en el detalle, sin debilitar sus demás afirmaciones; la suite completa debe quedar en verde salvo los fallos preexistentes documentados en `MEMORY.md`.
- Nota de ampliación añadida a RF-16 de HU-02, `specs/project.md` actualizado, `codegraph sync` ejecutado y `MEMORY.md` al día.

## Decisiones tomadas (clarificación de 2026-11-02)
- Visibilidad: el cliente conserva el aislamiento de HU-02; técnico y administrador pueden abrir cualquier ticket, asignado o no. *Alternativas descartadas: limitar al técnico a sus tickets asignados (impediría revisar la cola sin asignar) y permitir el detalle a cualquier usuario autenticado (rompería el aislamiento).*
- Datos del solicitante: objeto `requester: {id, name, email}`, resuelto por contrato de `identity`, con `null` si no se resuelve. *Alternativas descartadas: solo `{id, name}` (el técnico no tendría canal de contacto) y mantener solo `requester_id` (no cumple la entrada «datos del solicitante»).*
- Alcance: solo el detalle; el listado completo de «Todos los tickets» (ADR-002) corresponde a otra historia. *Alternativa descartada: añadir aquí un listado para staff, que ampliaría el alcance de 4 horas y duplicaría un trabajo pendiente.*
- Contrato: `requester` y `resolved_at` se añaden a la respuesta completa de ticket (`TicketResponse`), compartida por creación, detalle y modificaciones, para no tener dos formas del mismo recurso. Los resúmenes no cambian. *Alternativa descartada: añadirlos solo en el detalle, con el mismo recurso devolviendo formas distintas según la operación.*
- `requester` se resuelve por un contrato nuevo de `identity` (vista `{id, name, email}`), sin que `tickets` acceda al repositorio de usuarios. *Alternativa descartada: que `tickets` importe el repositorio de `identity`, prohibido por la constitución.*
- Sin caché ni copia del nombre o correo en el ticket: se resuelven en cada respuesta, de modo que un cambio de nombre en `identity` se refleja de inmediato.

## Dudas abiertas
Sin dudas abiertas pendientes.
