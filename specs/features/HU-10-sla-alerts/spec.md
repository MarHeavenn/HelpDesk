# Spec HU-10 — Alertas SLA
Estado: implementada

## Contexto y objetivo
HU-05 incorporó el módulo `sla`: asigna a cada ticket el tiempo objetivo de su prioridad y, en cada consulta, deriva el estado del SLA (`en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`) y los indicadores booleanos `near_due` (próximo a vencer) y `breached` (incumplido). Esos indicadores se exponen dentro de cada respuesta de ticket, pero el sistema todavía no ofrece al equipo de soporte una vista que reúna, de una vez, los tickets que exigen atención por SLA: el técnico tendría que recorrer los tickets uno a uno para saber cuáles están a punto de vencer o ya incumplidos.

Esta historia incorpora el mecanismo de alertas: un listado de «tickets que requieren atención» —próximos a vencer o incumplidos— para que el técnico priorice antes de superar el tiempo establecido. El listado **se apoya por completo en el cálculo de SLA ya existente** de HU-05 (RF-43 a RF-45): no introduce un segundo cálculo, una tarea programada ni notificaciones push o por correo. Se trata de una consulta derivada que, en el instante de pedirla, selecciona los tickets activos cuyo SLA está `en_riesgo` o `incumplido` y los devuelve ordenados por urgencia.

La historia de usuario pide que «los umbrales de alerta puedan definirse para el MVP». El umbral de «próximo a vencer» ya está definido en HU-05 como el 20 % del tiempo objetivo restante (`RISK_THRESHOLD_RATIO`, con `≤` y `> 0`). Decisión confirmada por el usuario: esta spec **reutiliza ese umbral fijo como el umbral de alerta del MVP**, sin añadir una configuración nueva ni adelantar la configuración pública de HU-14, que queda diferida a HU-14.

## Usuarios / actores
- Técnico (rol `tecnico`): actor principal. Consulta el listado de tickets que requieren atención por SLA —próximos a vencer o incumplidos— para priorizar su trabajo, con independencia de si el ticket está asignado a él o a otro.
- Administrador (rol `administrador`): consulta el mismo listado para supervisar la carga de trabajo y los incumplimientos del equipo.
- Cliente (rol `cliente`): no accede al listado de atención. Su visibilidad no cambia: sigue viendo solo sus propios tickets (HU-02) y, en ellos, el objeto `sla` (HU-05). Su intento de consultar el listado se responde con 404 uniforme, sin revelar datos.
- Visitante sin autenticación: 401, como en HU-01 y HU-02.

## Historias de usuario
- H1: Como técnico, quiero consultar el listado de tickets cuyo SLA está próximo a vencer o ya incumplido, para priorizar su atención antes de superar el tiempo establecido.
- H2: Como administrador, quiero consultar ese mismo listado, para supervisar qué solicitudes corren riesgo o ya incumplieron.
- H3: Como usuario, quiero que el listado se derive en vivo del SLA ya calculado, para que refleje la situación real sin que nadie tenga que marcarlo ni actualizarlo.

## Requisitos funcionales (criterios de aceptación en EARS)
> Numeración: se continúa la secuencia global de requisitos del proyecto, que llega a RF-60 en `specs/features/HU-06-ticket-detail/spec.md`, por lo que esta historia usa RF-61 a RF-69. (Las historias HU-07, HU-08 y HU-09 no tienen spec propia todavía; HU-10 continúa la secuencia global directamente desde RF-60.) Fuente: tarjeta Trello «HU-10 — Implementar alertas SLA» y documento general del repositorio, secciones 2 y 4. Las decisiones de alcance están en «Decisiones tomadas».

- RF-61: EL SISTEMA considerará que un ticket «requiere atención» exactamente cuando, en el instante de la consulta, se cumplen a la vez: (a) el ticket no está `Resuelto` ni `Cerrado` (su estado es `Abierto` o `En progreso`), y (b) su SLA —calculado por HU-05, RF-43 a RF-45— tiene el indicador `near_due` verdadero (próximo a vencer) o `breached` verdadero (incumplido). Un ticket sin prioridad (`sla` nulo, RF-42 de HU-05) no requiere atención y no forma parte del listado. Un ticket `Resuelto` o `Cerrado` no forma parte del listado aunque su SLA esté congelado en `incumplido`, porque ya no exige atención.

- RF-62: CUANDO un usuario autenticado con rol de gestión (`tecnico` o `administrador`) solicite el listado de tickets que requieren atención, EL SISTEMA responderá 200 con la colección de todos los tickets del sistema que requieren atención según RF-61, con independencia de quién los creó y de si están asignados o no. La consulta es de solo lectura: no muta tickets ni registros.

- RF-63: EL SISTEMA permitirá consultar el listado de atención únicamente a los usuarios autenticados con rol de gestión (`tecnico` o `administrador`), tomando el rol y la identidad de la sesión de HU-01, nunca de la petición. SI un usuario autenticado sin permiso (cliente) intenta consultarlo, ENTONCES EL SISTEMA responderá 404 uniforme, sin devolver ningún dato, con el mismo criterio de no revelación de HU-03 (RF-24) y HU-04 (RF-38). SI la petición llega sin sesión válida, ENTONCES EL SISTEMA responderá 401 antes de resolver nada (precedencia 401 > 404, como HU-06 RF-57).

- RF-64: EL SISTEMA devolverá cada elemento del listado de atención con la misma composición de resumen de HU-04 y HU-06 (`{id, title, priority, status, assignee, sla, created_at}`), donde `sla` es el objeto de HU-05 (RF-44) con su composición completa de ocho campos: tiempo objetivo en minutos (`target_minutes`), fecha y hora de inicio (`started_at`), fecha y hora de vencimiento (`due_at`), tiempo transcurrido en minutos (`elapsed_minutes`), tiempo restante en minutos (`remaining_minutes`), estado (`status`) e indicadores booleanos `near_due` (próximo a vencer) y `breached` (incumplido). Por RF-61, todo ticket del listado tiene prioridad y, por tanto, `sla` nunca es `null` en esta respuesta. No se añaden campos nuevos, ni la descripción, ni `requester` ni `resolved_at`: la composición es idéntica a la de los demás listados de resumen.

- RF-65: EL SISTEMA ordenará el listado de atención por urgencia: por fecha y hora de vencimiento (`sla.due_at`) ascendente, de modo que los tickets ya incumplidos (vencidos antes del instante de referencia) aparezcan primero y, entre los próximos a vencer, primero el que antes vence. SI dos tickets comparten la misma fecha y hora de vencimiento, ENTONCES el empate no fija orden entre ellos.

- RF-66: EL SISTEMA no declarará parámetros de consulta, paginación ni filtros para el listado de atención: los parámetros de consulta desconocidos se ignoran en silencio (misma regla que RF-15 de HU-02). Una colección vacía es una respuesta válida (200). La búsqueda, el filtrado y la paginación corresponden a HU-17.

- RF-67: EL SISTEMA reutilizará el cálculo de SLA existente de HU-05 para detectar los tickets próximos a vencer e incumplidos, sin introducir un segundo cálculo ni duplicar la lógica: el umbral de «próximo a vencer» es el ya fijado en HU-05 —el 20 % del tiempo objetivo restante, con `≤` y `> 0` (RF-45.1)— y los indicadores `near_due` y `breached` son exactamente los de HU-05 (RF-45.4). Para el MVP ese umbral es un valor único definido en el módulo `sla` (una constante interna, sin operación pública de lectura ni de escritura). La configuración pública de tiempos y umbrales corresponde a HU-14.

- RF-68: EL SISTEMA derivará el listado en el momento de cada consulta, con el reloj del sistema y sin almacenar alertas, estados ni copias: no habrá tareas programadas, procesos en segundo plano ni notificaciones push o por correo (HU-15 y HU-16). El paso del tiempo o cualquier cambio en un ticket (prioridad, estado o asignación) se refleja en la siguiente consulta, de modo que un ticket puede entrar o salir del listado sin intervención humana (mismo principio de actualización automática que RF-48 de HU-05).

- RF-69: EL SISTEMA expresará las fechas y horas del listado en ISO 8601/RFC 3339 con offset UTC y microsegundos (coherente con HU-02 y HU-05), usará un único instante de referencia para calcular el SLA de todo el listado (como hacen los listados actuales de HU-05) y no permitirá fijar ese instante desde la API: solo las pruebas pueden sustituirlo.

## Requisitos no funcionales
- Separación de módulos y capas: el listado se compone en el módulo `tickets` (que posee el repositorio de tickets) llamando al contrato de `sla` (`get_ticket_sla`) para obtener el estado y los indicadores de cada ticket, igual que hace HU-05 al componer las respuestas de ticket. `sla` no accede a las estructuras internas de `tickets` ni a su repositorio. La regla de negocio «qué ticket requiere atención» no se implementa en los controladores HTTP (`docs/constitution.md`, `AGENTS.md`).
- Sin dependencias nuevas ni complejidad innecesaria: no se añaden librerías, tareas programadas, colas, cachés ni almacenamiento del estado calculado. El listado no persiste nada.
- Consistencia de contratos: se conservan las rutas, los códigos y las reglas de HU-02 a HU-06; el único cambio de contrato es la nueva operación de listado de atención. No se usan 400 ni 403 ni se introducen códigos de error nuevos: 200 en el camino válido y 401 y 404 en los rechazos.
- Privacidad y mínimo privilegio: el listado es de solo lectura y no añade visibilidad al cliente; los elementos no incluyen datos personales del solicitante (`requester`), la descripción ni credenciales.
- Rendimiento suficiente: el listado calcula el SLA de cada ticket en una sola pasada sobre el repositorio de tickets, sin consultas adicionales por ticket y con un único instante de referencia compartido.
- Zona horaria: todas las fechas y horas se almacenan y comparan en UTC; la conversión a la zona del usuario corresponde al frontend.

## Contrato observable (referencia)
> La ruta es una referencia; el plan fija la definitiva y garantiza que no colisione con `GET /api/tickets/{ticket_id}` (por ejemplo, declarándola antes de la ruta dinámica o con un prefijo propio). Los cuerpos de error mantienen la estructura `{"detail": <mensaje>}` de HU-01 y HU-02.

| Operación | Éxito | Rechazos |
|---|---|---|
| Listar tickets que requieren atención (solo `tecnico` y `administrador`; `GET /api/tickets/requiring-attention`, referencia) | 200 con la colección de resúmenes (composición de RF-64), ordenada por `sla.due_at` ascendente; 200 con colección vacía; parámetros de consulta desconocidos ignorados | 401 sin sesión; 404 uniforme para clientes |

## Casos límite
- Ticket `Abierto` con SLA `en_riesgo` (`near_due` verdadero) → RF-61 y RF-62 (aparece en el listado).
- Ticket `En progreso` con SLA `en_riesgo` (`near_due` verdadero) → RF-61 y RF-62 (aparece en el listado; simétrico del caso `Abierto`).
- Ticket `En progreso` con SLA `incumplido` (`breached` verdadero) → RF-61 y RF-62 (aparece; ya superó el vencimiento sin resolverse).
- Ticket `Abierto` con SLA `en_tiempo` → RF-61 (no aparece).
- Ticket sin prioridad (`sla` nulo) → RF-61 (no aparece, aunque esté `Abierto`).
- Ticket `Resuelto` con SLA `cumplido` → RF-61 (no aparece).
- Ticket `Resuelto` o `Cerrado` con SLA `incumplido` (resuelto fuera de plazo) → RF-61 (no aparece: ya no exige atención).
- Ticket `Resuelto` que vuelve a `En progreso` (reapertura, HU-05 RF-46) y su SLA queda `en_riesgo` o `incumplido` → RF-61 (vuelve a aparecer en la siguiente consulta).
- Ticket que pasa de `Baja` a `Crítica` y queda `incumplido` (HU-05 RF-47) → RF-61 (aparece tras el cambio).
- Ticket al que se fija prioridad y nace ya `en_riesgo` o `incumplido` (creado hace horas sin prioridad, HU-05) → RF-61 (aparece desde la primera consulta posterior).
- Ticket que estaba `en_riesgo` y se resuelve antes del vencimiento → RF-61 (desaparece en la siguiente consulta: su SLA queda `cumplido`).
- Cliente que consulta el listado de atención → RF-63 (404 uniforme, sin datos, sin revelar existencia de tickets).
- Consulta sin sesión válida → RF-63 (401, antes que cualquier resolución).
- Técnico o administrador con el sistema sin tickets que requieran atención → RF-62 y RF-66 (200 con colección vacía).
- Varios tickets próximos a vencer e incumplidos → RF-65 (los incumplidos primero por su `due_at` más temprano; entre próximos a vencer, el de vencimiento más próximo primero).
- Dos tickets con la misma fecha de vencimiento → RF-65 (el empate no fija orden; las pruebas no afirman orden entre ambos).
- Listado con parámetros de consulta desconocidos (por ejemplo `?status=Abierto&page=2`) → RF-66 (200, ignorados sin error).
- Ticket sin técnico asignado con SLA en riesgo → RF-61 y RF-62 (aparece igual: la atención no depende de la asignación).
- Consulta del listado no muta ningún ticket ni registro → RF-62 y RF-68 (solo lectura).

## Fuera de alcance
- Notificaciones push, correo o cualquier envío activo de alertas (HU-15 y HU-16): HU-10 solo ofrece el listado consultable.
- Configuración pública de tiempos y umbrales de SLA por parte del administrador (API y UI): HU-14. En HU-10 el umbral es el valor fijo de HU-05.
- Interfaz de usuario del frontend para el listado: HU-20 (el contrato HTTP queda listo para que el frontend lo consuma).
- Dashboard, métricas y reportes de cumplimiento (HU-11, HU-12 y HU-18).
- Búsqueda, filtrado, orden configuración por el usuario y paginación (HU-17).
- Alertas en tiempo real (websockets, sondeo programado) o cualquier mecanismo que requiera proceso en segundo plano.
- Inclusión de tickets `Resuelto`/`Cerrado` incumplidos en el listado (decisión: solo activos).
- Historial o auditoría de alertas generadas.
- Persistencia en PostgreSQL de políticas y SLA (`sla_policies`, `ticket_sla`): tarea de integración posterior a TSK-025.
- Cambios en la creación, la autenticación, la prioridad, el estado, la asignación o el cálculo de SLA distintos de la nueva operación de listado.

## Criterios de finalización
- RF-61 a RF-69 verificados con pruebas automatizadas con pytest: definición de «requiere atención» (activo con `near_due` o `breached`), exclusión de `Resuelto`/`Cerrado` y de tickets sin prioridad, visibilidad solo para `tecnico` y `administrador` con 404 uniforme para clientes y 401 sin sesión, composición de resumen idéntica a la de HU-04/HU-06 (sin `requester` ni descripción), orden por `sla.due_at` ascendente, colección vacía válida, parámetros de consulta desconocidos ignorados, reutilización del cálculo de HU-05 (sin segundo cálculo ni umbral nuevo) y actualización en vivo sin estado persistido.
- Comprobado que el listado se apoya en el cálculo existente (`get_ticket_sla`) y no introduce lógica de SLA nueva; que el umbral es el 20 % de HU-05 y no existe operación pública para leerlo ni modificarlo.
- Comprobado que no se añaden operaciones, rutas, permisos ni códigos de error nuevos más allá del listado, y que las reglas de HU-02 a HU-06 siguen intactas.
- Comprobado que la consulta es de solo lectura y que un único instante de referencia se usa para todo el listado.
- `specs/project.md` actualizado (HU-10 con su spec), `codegraph sync` ejecutado y `MEMORY.md` al día al terminar.

## Decisiones tomadas (clarificación de 2026-11-02, confirmada por el usuario)
- Mecanismo: un listado derivado y consultable, no una notificación activa. *Alternativa descartada: notificaciones push/correo o tareas programadas, que corresponden a HU-15/HU-16 y añadirían infraestructura fuera del alcance del MVP.*
- Umbral de alerta (confirmada por el usuario): se reutiliza el umbral de «próximo a vencer» de HU-05 (20 % del tiempo objetivo restante, `≤` y `> 0`), sin añadir configuración nueva en este MVP; la configuración pública y modificable queda diferida a HU-14. *Alternativa descartada: introducir un umbral configurable en tiempo de ejecución, que adelantaría HU-14 y duplicaría el concepto ya resuelto en HU-05.*
- Alcance del listado (confirmada por el usuario): solo tickets activos (`Abierto`/`En progreso`) cuyo SLA está `en_riesgo` o `incumplido`; los `Resuelto`/`Cerrado` se excluyen aunque estén incumplidos, porque no exigen atención. *Alternativa descartada: incluir los resueltos fuera de plazo, que es material de reporte (HU-11/HU-12), no de priorización.*
- Visibilidad (confirmada por el usuario): técnicos y administradores (roles de gestión), coherente con HU-06 (RF-51); los clientes reciben 404 uniforme y sin sesión 401. *Alternativa descartada: limitar al técnico a sus tickets asignados, que impediría revisar la cola sin asignar, igual que HU-06.*
- Composición de los elementos: el resumen ya existente (`{id, title, priority, status, assignee, sla, created_at}`), porque `sla` ya contiene `status`, `near_due`, `breached`, `due_at` y `remaining_minutes`. *Alternativa descartada: una composición nueva con campos de alerta dedicados, que duplicaría información ya presente en `sla`.*
- Orden: por `sla.due_at` ascendente (más urgente primero: los incumplidos ya vencieron y quedan primeros). *Alternativa descartada: orden por fecha de creación descendente (como los demás listados), que no refleja la urgencia.*
- Ubicación del listado: se compone en `tickets` usando el contrato de `sla`, sin que `sla` importe `tickets` (evita dependencia circular, mismo criterio que HU-05). La ruta definitiva la fija el plan sin colisionar con `GET /api/tickets/{ticket_id}`.

## Dudas abiertas
Sin dudas abiertas pendientes. Las tres dudas iniciales (umbral configurable, alcance del listado y visibilidad) fueron resueltas por el usuario y sus decisiones quedan reflejadas en «Decisiones tomadas» y en los RF-61, RF-63 y RF-67.
