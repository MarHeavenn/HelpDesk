# Spec HU-07 — Registrar seguimiento y comentarios del ticket
Estado: implementada

## Contexto y objetivo

HU-02 creó el ticket y HU-06 consolidó su detalle, pero el trabajo diario del equipo de soporte necesita dejar rastro de lo que se va haciendo: qué se revisó, qué se intentó y qué avance hay. HU-07 añade un seguimiento cronológico de comentarios asociados a cada ticket, de modo que técnicos y administradores registren avances y cualquier persona con acceso al ticket pueda reconstruir su atención sin depender de la memoria o de canales externos.

La historia se apoya en el detalle de HU-06 para no duplicar reglas de visibilidad: quien puede ver un ticket puede leer su seguimiento, y los roles de gestión pueden añadir notas. Los comentarios son un recurso propio del ticket, no una modificación de sus campos: registrar uno no cambia prioridad, estado, técnico, resolución ni SLA.

## Usuarios / actores

- Técnico (rol `tecnico`): registra avances y consulta el seguimiento de cualquier ticket visible, esté o no asignado a él (HU-06).
- Administrador (rol `administrador`): registra y consulta el seguimiento de cualquier ticket para supervisar la atención.
- Cliente (rol `cliente`): consulta el seguimiento de los tickets que creó, pero no registra comentarios.
- Visitante sin autenticación: 401, como en HU-01, HU-02 y HU-06.

## Historias de usuario

- H1: Como técnico, quiero registrar comentarios y avances en un ticket, para mantener actualizado el seguimiento de la solicitud.
- H2: Como técnico, quiero consultar el historial cronológico de comentarios, para entender qué se ha hecho antes de continuar la atención.
- H3: Como administrador, quiero supervisar los comentarios de cualquier ticket, para controlar la calidad y el avance del soporte.
- H4: Como cliente, quiero leer el seguimiento de mis propios tickets, para conocer el estado de mi solicitud sin acceder a tickets ajenos.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global de requisitos del proyecto, que llega a RF-60 en `specs/features/HU-06-ticket-detail/spec.md`, por lo que esta historia usa RF-61 a RF-70.

- RF-61: CUANDO un usuario autenticado con rol `tecnico` o `administrador` registre un comentario en un ticket existente y no cerrado mediante `POST /api/tickets/{ticket_id}/comments` con un contenido válido, EL SISTEMA responderá 201 con el comentario registrado, compuesto por `id`, `ticket_id`, `body`, `author` (`{id, name}`) y `created_at`. El autor se obtiene de la sesión autenticada, nunca del cuerpo de la petición, y el comentario queda asociado al ticket y a ese usuario. `created_at` lo genera el sistema.
- RF-62: EL SISTEMA exigirá que el contenido del comentario sea una cadena de texto estricta, obligatoria y no vacía tras el recorte, con una longitud de 1 a 2000 code points contada después del recorte; almacenará y devolverá el valor recortado. SI el contenido falta, no es texto, queda vacío tras el recorte, supera 2000 code points o el cuerpo incluye campos no documentados, ENTONCES EL SISTEMA responderá 422 sin crear el comentario ni alterar el ticket.
- RF-63: CUANDO un usuario autenticado con visibilidad sobre un ticket solicite su seguimiento mediante `GET /api/tickets/{ticket_id}/comments`, EL SISTEMA responderá 200 con todos los comentarios de ese ticket, sin paginación ni filtros, ordenados por fecha y hora de registro de forma ascendente (los más antiguos primero). SI dos comentarios comparten la misma fecha y hora, ENTONCES se conservará el orden en que fueron registrados. Un ticket sin comentarios devuelve 200 con una lista vacía. La consulta es de solo lectura.
- RF-64: EL SISTEMA aplicará al seguimiento la misma visibilidad que HU-06: un cliente solo puede consultar el de los tickets que creó; un técnico o un administrador puede consultar el de cualquier ticket existente, asignado o no. SI el ticket no existe, el identificador no tiene formato válido o el cliente no es su solicitante, ENTONCES EL SISTEMA responderá 404 uniforme con `{"detail": "ticket not found"}`, sin revelar la existencia de tickets ajenos ni devolver comentarios.
- RF-65: SI un usuario autenticado con rol `cliente` intenta registrar un comentario, ENTONCES EL SISTEMA responderá 404 uniforme, sin distinguir si el ticket existe, es propio o ajeno, y sin crear nada. No se usa 403 ni se introduce un código de error nuevo; la falta de permiso de escritura se oculta con el mismo 404 de las consultas no autorizadas.
- RF-66: SI el ticket está `Cerrado` y un usuario con rol de gestión intenta registrar un comentario, ENTONCES EL SISTEMA responderá 409 con `{"detail": "ticket is closed"}` sin crear el comentario. El listado de comentarios de un ticket cerrado sigue disponible con 200, porque el cierre impide añadir seguimiento pero no consultar el existente.
- RF-67: EL SISTEMA incluirá en cada comentario un objeto `author` con el identificador opaco y el nombre del usuario que lo registró (`{id, name}`), resuelto a través del contrato de `identity`. SI el autor no se puede resolver, ENTONCES `author` será `null` y el comentario se devolverá con normalidad, sin error. `author` nunca incluye correo, rol, contraseña, hash, token ni sesión.
- RF-68: EL SISTEMA no expondrá los comentarios dentro de las respuestas de ticket —creación, listado, detalle, prioridad, estado o asignación— ni en los resúmenes; solo en el subrecurso de comentarios. El cuerpo del comentario es contenido aportado por el usuario y se devuelve tal como quedó almacenado tras el recorte, sin interpretarlo ni filtrarlo. Los datos del autor se limitan a identificador y nombre.
- RF-69: EL SISTEMA no añadirá operaciones de edición, borrado, adjuntos, menciones ni notificaciones. Registrar un comentario no modificará prioridad, estado, técnico, `resolved_at` ni SLA del ticket, y el listado no mutará nada. Las únicas rutas nuevas son `POST` y `GET /api/tickets/{ticket_id}/comments`; los parámetros de consulta desconocidos del listado se ignoran en silencio, como en el resto de consultas del proyecto.
- RF-70: EL SISTEMA generará un identificador UUID opaco por comentario y expresará `created_at` en ISO 8601/RFC 3339 con offset UTC y microsegundos, igual que las fechas de HU-02, HU-05 y HU-06. La precedencia de errores será: sin sesión válida 401; después 404 por visibilidad o permiso; después 409 por ticket cerrado; y por último 422 por cuerpo inválido. Un cuerpo inválido nunca se evalúa antes que la existencia, la visibilidad o el estado del ticket.

## Requisitos no funcionales

- Separación de módulos y capas: la historia se implementa dentro del módulo `tickets` (entidad, validación, caso de uso, repositorio en memoria e interfaz), que es el núcleo de la gestión del ticket. No se crea un módulo nuevo ni se accede a estructuras internas de `identity`.
- Contrato de identidad: el nombre del autor se resuelve mediante el contrato público de `identity`; `tickets` no importa el repositorio de usuarios. La proyección expuesta se limita a `{id, name}`.
- Consistencia con HU-06: la visibilidad de lectura reutiliza exactamente la regla del detalle; el 404, el 401 y el formato de fechas no introducen variantes nuevas.
- Persistencia: repositorio en memoria, como el resto de módulos. La tabla `ticket_comments` ya existe en las migraciones, pero su conexión a PostgreSQL forma parte de la integración pendiente de todos los módulos.
- Sin dependencias nuevas, sin caché y sin complejidad innecesaria.
- Privacidad: no se exponen credenciales, roles ni correos del autor; el cuerpo no se registra en logs ni se devuelve fuera del subrecurso.

## Casos límite

- Ticket sin comentarios → RF-63 (200 con `[]`).
- Varios comentarios → RF-63 (orden ascendente; empate conserva el orden de registro).
- Comentarios de otro ticket → RF-63 (no se mezclan; cada listado filtra por `ticket_id`).
- Cliente consultando su ticket → RF-64 (200 con el seguimiento).
- Cliente consultando un ticket ajeno, inexistente o con identificador inválido → RF-64 (404 uniforme).
- Técnico consultando un ticket sin asignar o asignado a otro → RF-64 (200).
- Administrador consultando cualquier ticket → RF-64 (200).
- Cliente intentando registrar un comentario, incluso en su propio ticket → RF-65 (404 uniforme).
- Técnico o administrador comentando un ticket sin asignar o asignado a otro → RF-61 (201).
- Ticket `Cerrado` → RF-66 (`POST` 409, `GET` 200).
- Ticket `Abierto`, `En progreso` o `Resuelto` → RF-61/RF-66 (`POST` 201).
- Contenido ausente, no textual, vacío o solo espacios → RF-62 (422).
- Contenido de exactamente 2000 code points → RF-62 (201); 2001 → RF-62 (422).
- Contenido con espacios al inicio o al final → RF-62 (se recorta antes de validar y almacenar).
- Campo adicional en el cuerpo (por ejemplo, `author_id` o `created_at`) → RF-62 (422; el autor y la fecha no se aceptan del cliente).
- Autor que ya no se puede resolver en `identity` → RF-67 (`author: null`, comentario intacto).
- Petición sin sesión con identificador inválido o ticket cerrado → RF-70 (401 antes que 404/409/422).
- Ticket inexistente con cuerpo inválido → RF-70 (404 antes que 422).
- Ticket cerrado con cuerpo inválido → RF-70 (409 antes que 422).
- Listado con parámetros de consulta desconocidos → RF-69 (200, se ignoran).
- Registrar o listar comentarios y volver a consultar el detalle del ticket → RF-68/RF-69 (el ticket y su SLA no cambian).

## Fuera de alcance

- Editar o borrar comentarios, moderación y auditoría de cambios sobre comentarios.
- Diferenciar notas internas de comentarios visibles para el cliente; en esta historia todos los comentarios del ticket comparten la visibilidad de HU-06.
- Adjuntos, imágenes, menciones, etiquetas, reacciones o texto enriquecido.
- Notificaciones por correo o en la aplicación (HU-16 y HU-17).
- Historial de cambios de prioridad, estado o asignación (HU-09).
- Incluir los comentarios dentro de `GET /api/tickets/{ticket_id}` o de cualquier otra respuesta de ticket.
- Paginación, búsqueda, filtros u orden configurable del listado.
- Interfaz de usuario del frontend (HU-20).
- Persistencia en PostgreSQL y contratos multitenant de comentarios: integración posterior a TSK-025, igual que en el resto de módulos.

## Criterios de finalización

- RF-61 a RF-70 verificados con pytest, con pruebas unitarias de dominio/aplicación y pruebas de API con `TestClient`: creación válida por técnico y administrador; 201 con `id`, `ticket_id`, `body`, `author` y `created_at`; autor tomado de la sesión; 422 para contenido inválido o campos extra; listado vacío, ascendente y estable ante empates; visibilidad de cliente, técnico y administrador; 404 uniforme; 409 en ticket cerrado con `GET` disponible; `author: null` cuando no se resuelve; 401 antes que 404/409/422; el ticket y su SLA no cambian al comentar.
- Comprobado que no se añaden rutas fuera de `POST/GET /api/tickets/{ticket_id}/comments`, que no cambia `TicketResponse` ni ningún contrato de HU-02 a HU-06, y que no se modifican las reglas de prioridad, estado o asignación.
- La suite completa queda en verde salvo los fallos preexistentes documentados en `MEMORY.md`; `codegraph sync` ejecutado; `specs/project.md` y `MEMORY.md` actualizados.

## Decisiones tomadas (clarificación de 2026-11-02)

- Escritura: técnico y administrador. *Alternativas descartadas: solo técnico (el administrador supervisa y también debe poder dejar constancia) y permitir al cliente (convertiría la historia en una conversación y ampliaría permisos no pedidos).*
- Lectura: misma visibilidad que HU-06. *Alternativas descartadas: notas internas solo para el personal (el cliente perdería el seguimiento de su solicitud) y visibilidad limitada al autor (rompería la reconstrucción del historial).*
- Contrato: subrecurso `POST/GET /api/tickets/{ticket_id}/comments`. *Alternativas descartadas: embeber los comentarios en el detalle (cambiaría el contrato de HU-06 y cargaría comentarios en respuestas que no los necesitan) y ofrecer ambas formas (duplicaría el listado).*
- Ticket cerrado: bloquear la escritura con 409 y permitir la lectura. *Alternativa descartada: permitir comentar después del cierre, que contradice la inmutabilidad del ticket cerrado en HU-03/HU-04.*
- Validación: contenido recortado de 1 a 2000 code points y autor `{id, name}`. *Alternativas descartadas: 1-5000 (el límite de la descripción es para tickets, no para notas de seguimiento) y devolver el correo del autor (dato personal innecesario y contrario al criterio de HU-06).*
- Persistencia: en memoria, como el resto de módulos. *Alternativa descartada: conectar solo los comentarios a PostgreSQL, que rompería la uniformidad y adelantaría una integración pendiente de todo el backend.*
- El autor se resuelve en cada consulta y no se copia en el comentario, de modo que un cambio de nombre se refleja de inmediato; si el usuario desaparece, `author` es `null`.
- El empate de `created_at` conserva el orden de registro para que el listado sea determinista sin inventar un orden por identificador.

## Dudas abiertas

Sin dudas abiertas pendientes. Las decisiones que fijan los valores y comportamientos concretos de estos RF están registradas en "Decisiones tomadas".
