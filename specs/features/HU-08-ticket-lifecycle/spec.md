# Spec HU-08 — Gestionar ciclo de vida del ticket
Estado: implementada

## Contexto y objetivo

HU-03 dejó el estado del ticket modificable por técnicos y administradores, pero sin reglas de secuencia: cualquier transición entre los cuatro estados era aceptable y el ticket `Cerrado` quedaba completamente inmutable, con la reapertura y la «acción autorizada» expresamente diferidas a esta historia. HU-08 cierra ese hueco: define el flujo del ciclo de vida, rechaza los cambios inconsistentes y ofrece una vía explícita y autorizada para reabrir un ticket cerrado.

La historia no crea estados nuevos ni cambia los cuatro del catálogo de HU-03 (`Abierto`, `En progreso`, `Resuelto`, `Cerrado`). Tampoco cambia la prioridad, la asignación, el solicitante ni el SLA: solo controla por qué estados puede pasar el ticket y deja constancia de cada cambio en el registro de modificaciones que alimentará el historial de HU-09. La reapertura reanuda el SLA y vuelve a habilitar las operaciones que el cierre bloqueaba (prioridad, asignación y comentarios), manteniendo la coherencia con HU-03, HU-04, HU-05 y HU-07.

## Usuarios / actores

- Técnico (rol `tecnico`): actualiza el estado de cualquier ticket visible (HU-06) siguiendo el flujo permitido; no puede reabrir un ticket cerrado.
- Administrador (rol `administrador`): actualiza el estado de cualquier ticket y es el único que puede reabrir un ticket `Cerrado`.
- Cliente (rol `cliente`): no actualiza estados ni reabre; recibe el 404 uniforme de HU-02/HU-03. Sigue consultando el estado vigente en sus tickets.
- Visitante sin autenticación: 401, como en el resto de operaciones de gestión.

## Historias de usuario

- H1: Como técnico, quiero mover un ticket de `Abierto` a `En progreso` y de `En progreso` a `Resuelto`, para reflejar el avance real de la atención.
- H2: Como técnico, quiero cerrar un ticket solo cuando esté resuelto, para no cerrar solicitudes que aún no han sido atendidas.
- H3: Como administrador, quiero reabrir un ticket cerrado cuando sea necesario, para corregir un cierre prematuro sin crear un ticket nuevo.
- H4: Como responsable de soporte, quiero que cada transición quede registrada con su responsable y su fecha, para conservar la trazabilidad (base de HU-09).

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global de requisitos del proyecto, que llega a RF-70 en `specs/features/HU-07-ticket-comments/spec.md`, por lo que esta historia usa RF-71 a RF-80. HU-08 sustituye la parte de RF-23 de HU-03 que declaraba «sin reglas de secuencia»; el resto de RF-21, RF-22 y RF-24 a RF-30 de HU-03 sigue vigente.

- RF-71: EL SISTEMA admitirá mediante `PUT /api/tickets/{ticket_id}/status` únicamente estas transiciones: `Abierto` → `En progreso`; `En progreso` → `Resuelto`; `Resuelto` → `Cerrado`; y `Resuelto` → `En progreso` como retroceso permitido antes del cierre. La reapertura de `Cerrado` se realiza exclusivamente con `POST /api/tickets/{ticket_id}/reopen` (RF-76). Cualquier otro par de estados distintos no es una transición válida, incluidos los saltos `Abierto` → `Resuelto`, `Abierto` → `Cerrado` y `En progreso` → `Cerrado`, y los retrocesos `En progreso` → `Abierto` y `Resuelto` → `Abierto`.
- RF-72: CUANDO un usuario con permisos de gestión (RF-24 de HU-03) solicite una transición válida de RF-71 sobre un ticket existente y no cerrado, EL SISTEMA actualizará el estado, conservará la información actualizada del ticket, responderá 200 con la información completa del ticket —el mismo contrato de `TicketResponse` de HU-02 a HU-07— y registrará la modificación con el ticket, el campo `status`, el valor anterior, el valor nuevo, el usuario responsable obtenido de la sesión y la fecha y hora generada por el sistema, con el criterio de RF-26 de HU-03. La transición no modificará prioridad, técnico responsable, solicitante, título, descripción ni fecha de creación.
- RF-73: SI un usuario con permisos de gestión solicita un estado distinto del vigente que pertenece al catálogo pero no figura como transición válida en RF-71, ENTONCES EL SISTEMA responderá 409 con `{"detail": "invalid status transition"}`, sin modificar el ticket, sin alterar `resolved_at` ni el SLA y sin generar registro.
- RF-74: SI un usuario con permisos de gestión solicita el mismo estado que el ticket ya tiene y el ticket no está `Cerrado`, ENTONCES EL SISTEMA responderá 200 con el ticket sin modificar, sin generar registro y sin alterar `resolved_at`. En un ticket `Cerrado` prevalece RF-75: incluso solicitar `Cerrado` responde 409.
- RF-75: SI un usuario con permisos de gestión intenta actualizar el estado de un ticket `Cerrado` mediante `PUT /api/tickets/{ticket_id}/status` —con cualquier valor, incluido el ya vigente o uno inválido—, ENTONCES EL SISTEMA responderá 409 con `{"detail": "ticket is closed"}`, sin modificar el ticket y sin generar registro. La única vía autorizada para sacar un ticket de `Cerrado` es la reapertura de RF-76.
- RF-76: CUANDO un usuario autenticado con rol `administrador` solicite `POST /api/tickets/{ticket_id}/reopen` sobre un ticket existente en estado `Cerrado`, EL SISTEMA responderá 200 con la información completa del ticket en estado `Abierto`, descartará `resolved_at` para que el SLA vuelva a evolucionar desde la creación (criterio de HU-05), y registrará la modificación `Cerrado` → `Abierto` con el usuario responsable de la sesión y la fecha y hora del sistema. La reapertura no modificará prioridad, técnico responsable, solicitante, título, descripción ni fecha de creación.
- RF-77: SI un usuario autenticado sin rol `administrador` (técnico o cliente) solicita la reapertura, o si el ticket no existe o el identificador no tiene formato válido, ENTONCES EL SISTEMA responderá 404 con el cuerpo uniforme `{"detail": "ticket not found"}`, sin reabrir y sin revelar la existencia del ticket. SI el ticket existe, el actor es administrador y el ticket no está `Cerrado`, ENTONCES EL SISTEMA responderá 409 con `{"detail": "ticket is not closed"}`, sin modificar el ticket. La reapertura no requiere cuerpo: cualquier cuerpo enviado se ignora y no se valida.
- RF-78: EL SISTEMA aplicará la autorización y la precedencia de errores de HU-03 a las operaciones de esta historia: sin sesión válida responde 401 antes que cualquier otra comprobación; un cliente recibe 404 uniforme antes de resolver el ticket; un ticket inexistente o un identificador inválido responde 404; un ticket `Cerrado` en `PUT /status` responde 409 antes de validar el cuerpo; y un cuerpo inválido responde 422. En un ticket no cerrado, un valor de estado fuera del catálogo o un cuerpo con campos extra o tipos no textuales responde 422 (RF-29 de HU-03), y solo un valor válido del catálogo que no sea una transición permitida responde 409 (RF-73). En la reapertura la precedencia es 401 > 404 (rol, existencia o formato) > 409 (ticket no cerrado). No se usa 403 ni 400.
- RF-79: EL SISTEMA no expondrá el registro de modificaciones ni añadirá campos, estados, rutas o parámetros no documentados: `TicketResponse` y los resúmenes conservan exactamente su contrato, no se añade `allowed_transitions` ni ningún indicador de transiciones posibles, y la única ruta nueva es `POST /api/tickets/{ticket_id}/reopen`. `PUT /api/tickets/{ticket_id}/status` mantiene su forma y su cuerpo mono-campo estricto.
- RF-80: EL SISTEMA mantendrá la coherencia con las historias anteriores: `Resuelto` fija `resolved_at` y congela el SLA; `Resuelto` → `Cerrado` conserva el instante de resolución; `Resuelto` → `En progreso` y la reapertura descartan `resolved_at` y reanudan el SLA (HU-05); un ticket `Cerrado` sigue siendo inmutable para prioridad (HU-03), asignación (HU-04) y comentarios (HU-07); tras la reapertura esas tres operaciones vuelven a estar disponibles sobre el ticket en `Abierto`; y los identificadores, formatos de fecha y mensajes de error se mantienen.

## Requisitos no funcionales

- Separación de capas y módulos: la tabla de transiciones y la validación viven en `tickets/domain` y `tickets/application`; la interfaz solo traduce errores a HTTP. No se crea un módulo nuevo ni se accede a estructuras internas de otros módulos.
- Coherencia con HU-03: se reutilizan el catálogo, `is_valid_uuid_format`, `get_modifiable_ticket`, `TicketNotFoundError`, `TicketClosedError`, el registro de modificaciones y la composición de `TicketResponse`. La reapertura sigue el patrón de autorización de `get_assignable_ticket` (rol privilegiado con 404 uniforme).
- Sin cambios en la autenticación, en los roles existentes ni en el contrato de identidad.
- Sin dependencias nuevas, sin estados nuevos, sin control de concurrencia y sin complejidad innecesaria.
- Trazabilidad interna: cada transición efectiva (incluida la reapertura) deja un registro acumulativo; el registro no se expone en esta historia (HU-09).
- Sin cambios de persistencia: todo sigue en memoria; la integración con PostgreSQL continúa pendiente y no forma parte de la historia.

## Casos límite

- `Abierto` → `En progreso`, `En progreso` → `Resuelto`, `Resuelto` → `Cerrado` y `Resuelto` → `En progreso` → RF-71/RF-72 (200, cambio y registro).
- `Abierto` → `Resuelto`, `Abierto` → `Cerrado`, `En progreso` → `Cerrado`, `En progreso` → `Abierto`, `Resuelto` → `Abierto` → RF-73 (409 `invalid status transition`, sin cambio ni registro).
- Repetir el estado vigente en `Abierto`, `En progreso` o `Resuelto` → RF-74 (200 sin cambio ni registro).
- Repetir `Cerrado` o pedir cualquier otro estado en un ticket cerrado → RF-75 (409 `ticket is closed`).
- `Resuelto` → `En progreso` → RF-72 y RF-80 (200; `resolved_at` se descarta y el SLA se reanuda).
- `En progreso` → `Resuelto` → RF-72 y RF-80 (200; `resolved_at` se fija y el SLA se congela).
- `Resuelto` → `Cerrado` → RF-72 y RF-80 (200; `resolved_at` se conserva).
- Reapertura de un ticket cerrado por un administrador → RF-76 (200, `Abierto`, `resolved_at: null`, SLA reanudado, registro `Cerrado` → `Abierto`).
- Reapertura por un técnico o por un cliente → RF-77 (404 uniforme, sin cambios).
- Reapertura de un ticket inexistente o con identificador inválido → RF-77 (404 uniforme).
- Reapertura de un ticket `Abierto`, `En progreso` o `Resuelto` → RF-77 (409 `ticket is not closed`).
- Reapertura con un cuerpo cualquiera → RF-77 (se ignora; 200 si procede).
- Reapertura sin sesión válida → RF-78 (401 antes que 404/409).
- Actualizar el estado sin sesión válida, con identificador inválido, ticket inexistente, ticket cerrado o cuerpo inválido → RF-78 (401 primero).
- Actualizar el estado como cliente, con cualquier cuerpo → RF-78 (404 uniforme).
- Actualizar el estado de un ticket cerrado con cuerpo inválido o estado fuera del catálogo → RF-75/RF-78 (409 `ticket is closed` antes que 422).
- Actualizar el estado de un ticket no cerrado con un valor fuera del catálogo o campos extra → RF-78 (422, sin cambio ni registro).
- Actualizar el estado de un ticket no cerrado con un valor válido pero no permitido y campos extra → RF-78 (422 por el cuerpo antes que el 409 de la transición).
- Tras reabrir: fijar prioridad, asignar técnico y registrar comentarios → RF-80 (operaciones disponibles de nuevo; antes del cierre respondían 409).
- Detalle y listado tras cualquier transición → RF-72/RF-79 (estado vigente; sin campos nuevos ni registro expuesto).
- Reintentar la misma transición tras completarla (por ejemplo `En progreso` → `Resuelto` dos veces) → RF-74 (200 sin cambio ni registro en el segundo intento).

## Fuera de alcance

- Consulta pública del historial de cambios y su trazabilidad detallada (HU-09); en esta historia el registro solo se almacena.
- Estados nuevos (`Cancelado`, `Pendiente`, etc.), subestados, motivos de cierre o campos de resolución.
- Transiciones automáticas por tiempo, SLA o asignación; cierre automático.
- Restringir la actualización de estado al técnico asignado: sigue vigente RF-24 de HU-03 (cualquier técnico o administrador, sobre cualquier ticket).
- Reapertura por técnicos o clientes, reapertura masiva o reapertura automática.
- Notificaciones de cambios de estado (HU-15/HU-16), dashboards (HU-11/HU-12) y búsqueda o filtros (HU-17).
- Endpoint o campo que exponga las transiciones permitidas (`allowed_transitions`).
- Cambios en la prioridad, la asignación, los comentarios o el SLA más allá de la coherencia descrita en RF-80.
- Interfaz de usuario del frontend (HU-20).
- Persistencia en PostgreSQL, control de concurrencia, versionado o bloqueos.

## Criterios de finalización

- RF-71 a RF-80 verificados con pytest, con pruebas unitarias de dominio/aplicación y pruebas de API con `TestClient`: las cuatro transiciones válidas; todas las transiciones inválidas; repetición del estado vigente; 409 `invalid status transition`; 409 `ticket is closed`; reapertura por administrador con 200, `Abierto`, `resolved_at: null`, SLA reanudado y registro; 404 uniforme para técnico/cliente, ticket inexistente o identificador inválido; 409 `ticket is not closed`; cuerpo de reapertura ignorado; 401 antes que 404/409/422; 422 por catálogo o cuerpo inválido; y coherencia con prioridad, asignación, comentarios y SLA antes y después de la reapertura.
- Comprobado que `TicketResponse` y los resúmenes no cambian, que no se expone el registro de modificaciones y que la única ruta nueva es `POST /api/tickets/{ticket_id}/reopen`.
- Actualizadas las pruebas de HU-03 a HU-07 que realizaban saltos de estado ahora inválidos (por ejemplo `Abierto` → `Resuelto`, `Abierto` → `Cerrado` o `En progreso` → `Cerrado`), recorriendo el flujo permitido sin debilitar sus afirmaciones.
- La suite completa queda en verde salvo los fallos preexistentes documentados en `MEMORY.md`; `codegraph sync` ejecutado; `specs/project.md`, `MEMORY.md` y las notas de ampliación de HU-03 actualizados.

## Decisiones tomadas (clarificación de 2026-11-02)

- Flujo lineal estricto con un retroceso: `Abierto` → `En progreso` → `Resuelto` → `Cerrado`, más `Resuelto` → `En progreso`. *Alternativas descartadas: permitir saltos hacia delante (facilitaría cierres sin resolución y debilitaría la validación que pide la historia) y mantener la libertad de HU-03 (no cumpliría el objetivo de controlar las transiciones).*
- Reapertura mediante ruta propia `POST /api/tickets/{ticket_id}/reopen`, solo para administradores: hace explícita la «acción autorizada» que anunció HU-03, mantiene intacto el 409 de `PUT /status` sobre tickets cerrados y evita una precedencia especial para leer el cuerpo antes de decidir el estado. *Alternativas descartadas: reabrir con `PUT /status {"status": "Abierto"}` (mezcla la transición normal con la excepción y complica la precedencia) y no permitir reapertura (dejaría sin cumplir la acción autorizada prevista).*
- Estado destino de la reapertura: `Abierto`, sin técnico en progreso. *Alternativa descartada: `En progreso`, que asumiría que el caso sigue en manos del técnico.*
- Transición inválida: 409 `{"detail": "invalid status transition"}`, distinto del 409 `{"detail": "ticket is closed"}`. *Alternativas descartadas: 422 (mezcla estado del recurso con validación de entrada) y 403 (código no usado en el proyecto y no es una falta de permisos).*
- Repetir el estado vigente en un ticket no cerrado: 200 sin cambio ni registro, como en HU-03. En un ticket cerrado prevalece el 409 de inmutabilidad. *Alternativa descartada: 409, que rompería el contrato ya probado sin aportar beneficio.*
- No se expone `allowed_transitions`: el resultado de la operación (200/409) comunica la validez y no se altera el contrato de ticket de HU-02 a HU-07. *Alternativa descartada: añadir la lista al detalle, que obligaría a cambiar todas las pruebas de composición exacta.*
- Precedencia en `PUT /status`: 401 > 404 > 409 por ticket cerrado > 422 por cuerpo o catálogo > 409 por transición inválida. El 409 de transición solo se evalúa con un valor válido del catálogo, porque sin un destino válido no hay transición que juzgar. *Alternativa descartada: 409 antes que 422 también para valores fuera del catálogo, que confundiría un error de entrada con un conflicto de estado.*
- El registro de la reapertura reutiliza `TicketModification` (`status`, `Cerrado` → `Abierto`, actor de sesión y fecha del sistema), de modo que HU-09 lo verá sin un formato nuevo.
- La reapertura no requiere cuerpo; un cuerpo enviado se ignora. *Alternativa descartada: exigir un cuerpo vacío estricto, que añadiría un 422 sin valor para una operación sin datos.*
- Se actualizarán las pruebas existentes que hacían saltos ahora inválidos, recorriendo el flujo permitido; no se debilita ninguna afirmación.

## Dudas abiertas

Sin dudas abiertas pendientes. Las decisiones que fijan el grafo, la reapertura y la precedencia están registradas en «Decisiones tomadas».
