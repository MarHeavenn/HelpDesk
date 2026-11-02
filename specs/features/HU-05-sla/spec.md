# Spec HU-05 — Configurar y controlar SLA por prioridad
Estado: implementada

## Contexto y objetivo
HU-02 creó el ticket y HU-03 incorporó la prioridad (`Crítica`, `Alta`, `Media` y `Baja`), pero el sistema todavía no mide el compromiso de atención. Esta historia incorpora el módulo `sla`: asigna a cada ticket el tiempo objetivo de su prioridad, cuenta el tiempo transcurrido desde la creación, calcula el tiempo restante, determina automáticamente el estado del SLA (en tiempo, próximo a vencer, incumplido o cumplido) y lo expone junto con el ticket. No introduce tareas programadas ni actualizaciones manuales: el estado se deriva de la fecha de creación, la prioridad vigente, el estado del ticket y el reloj del sistema cada vez que se consulta, de modo que siempre está actualizado sin intervención humana.

El documento general no fija el umbral de «próximo a vencer» y lo deja como decisión de negocio; esta spec lo fija en el 20 % del tiempo objetivo restante, coherente con el ADR-006 del frontend. HU-03 dejó abierta la tensión entre «el contador inicia al crear el ticket» y los tickets que nacen sin prioridad; esta spec la resuelve: un ticket sin prioridad no tiene SLA asignado (`sla` nulo) y, en cuanto se le fija una prioridad, el vencimiento se calcula desde su fecha de creación, de modo que el contador siempre empieza a contar al crear el ticket.

## Usuarios / actores
- Administrador: responsable de los tiempos objetivo de SLA por prioridad. En esta historia el sistema arranca con los cuatro valores iniciales del documento general; la modificación de esos tiempos desde la API o la interfaz corresponde a HU-14 y queda fuera de alcance. El administrador consulta el SLA como cualquier usuario que ya puede ver el ticket.
- Técnico: consulta el SLA de los tickets que ya puede ver por HU-02, HU-03 y HU-04; usa el tiempo restante, el estado y los indicadores para priorizar la atención. No configura tiempos ni puede alterar el SLA.
- Cliente: consulta el SLA de sus propios tickets, en la misma composición y con la misma visibilidad que HU-02. No configura ni altera nada.
- Visitante sin autenticación: no accede a ningún ticket ni a su SLA.

## Historias de usuario
- H1: Como administrador, quiero que el sistema aplique tiempos de SLA según la prioridad del ticket, para controlar automáticamente el cumplimiento de los tiempos de atención.
- H2: Como técnico, quiero ver el tiempo transcurrido, el tiempo restante y el estado del SLA de cada ticket, para priorizar la atención antes de incumplir el compromiso.
- H3: Como usuario, quiero que el estado del SLA se actualice solo, sin que nadie tenga que marcarlo, para confiar en el indicador que veo.

## Requisitos funcionales (criterios de aceptación en EARS)
> Numeración: se continúa la secuencia global de requisitos del proyecto, que llega a RF-40 en `specs/features/HU-04-assignment/spec.md`, por lo que esta historia usa RF-41 a RF-50. Fuente: tarjeta Trello «HU-05 — Configurar y controlar SLA por prioridad» y documento general del repositorio, sección 4 (HU-05). Las decisiones que fijan umbral, representación y comportamiento están en «Decisiones tomadas».

- RF-41: EL SISTEMA dispondrá de una configuración de tiempo objetivo de SLA para cada una de las cuatro prioridades del catálogo de HU-03 (`Crítica`, `Alta`, `Media` y `Baja`), con los valores iniciales del documento general: `Crítica` 120 minutos (2 horas), `Alta` 240 minutos (4 horas), `Media` 720 minutos (12 horas) y `Baja` 1440 minutos (24 horas). La configuración es global e interna en esta historia: el sistema la usa para asignar el tiempo a cada ticket, pero no la expone ni la modifica mediante ninguna operación pública. La consulta y la modificación de los tiempos por parte del administrador corresponden a HU-14. La coincidencia con la prioridad es exacta, con el mismo catálogo de RF-21 de HU-03, y no existe prioridad por defecto: un ticket sin prioridad no recibe ningún tiempo objetivo.
- RF-42: MIENTRAS un ticket no tenga prioridad fijada, EL SISTEMA no le asignará SLA: todas las respuestas que devuelvan ese ticket incluirán `sla` nulo y no calcularán tiempo objetivo, fecha de vencimiento, tiempo transcurrido, tiempo restante ni estado. La creación de HU-02 no cambia (el ticket nace sin prioridad) y un ticket sin prioridad sigue siendo válido y consultable con normalidad.
- RF-43: CUANDO un ticket tenga prioridad, EL SISTEMA le asignará el tiempo objetivo que la configuración (RF-41) define para esa prioridad y calculará automáticamente, en cada consulta y sin intervención manual:
  - RF-43.1: la fecha y hora de inicio del SLA, que es siempre la fecha y hora de creación del ticket, con independencia del momento en que se fijó la prioridad.
  - RF-43.2: la fecha y hora de vencimiento, que es la de inicio más el tiempo objetivo.
  - RF-43.3: el tiempo transcurrido, medido desde la fecha y hora de inicio hasta el instante de referencia de la consulta.
  - RF-43.4: el tiempo restante mientras el SLA esté vigente y el ticket no esté resuelto, medido desde el instante de referencia hasta el vencimiento. Cuando el SLA ya está incumplido o el ticket está resuelto, el tiempo restante es cero.
- RF-44: EL SISTEMA incluirá el SLA calculado en todas las respuestas que devuelvan un ticket —creación, listado, detalle, fijación de prioridad, actualización de estado y asignación o reasignación— con la misma composición en todas ellas. El SLA se representará como un objeto con: tiempo objetivo en minutos (`target_minutes`), fecha y hora de inicio (`started_at`), fecha y hora de vencimiento (`due_at`), tiempo transcurrido en minutos (`elapsed_minutes`), tiempo restante en minutos (`remaining_minutes`), estado (`status`) e indicadores booleanos `near_due` (próximo a vencer) y `breached` (incumplido). Cuando el ticket no tiene prioridad, el valor es `null` (RF-42). El SLA no añade ni altera los demás campos del ticket de HU-02, HU-03 y HU-04.
- RF-45: EL SISTEMA determinará el estado del SLA con estas reglas, evaluadas automáticamente en cada consulta:
  - RF-45.1: MIENTRAS el ticket no esté resuelto y el instante de referencia sea anterior al vencimiento, el estado será `en_riesgo` cuando el tiempo que falte para vencer sea menor o igual al 20 % del tiempo objetivo y mayor que cero, y `en_tiempo` en cualquier otro caso anterior al vencimiento.
  - RF-45.2: CUANDO el ticket no esté resuelto y el instante de referencia sea igual o posterior al vencimiento, el estado será `incumplido`.
  - RF-45.3: CUANDO el ticket se resuelva en su vencimiento o antes, el estado será `cumplido`; cuando se resuelva después del vencimiento, será `incumplido` (RF-46).
  - RF-45.4: los indicadores son derivados del estado: `near_due` es verdadero exactamente cuando el estado es `en_riesgo` y `breached` es verdadero exactamente cuando el estado es `incumplido`, también para un SLA resuelto fuera de plazo.
- RF-46: CUANDO el estado del ticket pase a `Resuelto` o a `Cerrado`, EL SISTEMA fijará la fecha y hora de resolución del ticket y congelará el SLA en ese instante: el estado del SLA se calculará comparando la resolución con el vencimiento (RF-45.3) y dejará de evolucionar con el reloj. El paso de `Resuelto` a `Cerrado` conservará la fecha y hora de resolución original, y el ticket `Cerrado` seguirá siendo inmutable según HU-03. SI un ticket `Resuelto` vuelve a `Abierto` o a `En progreso`, ENTONCES EL SISTEMA descartará la fecha y hora de resolución y reanudará el cálculo con el reloj, la fecha de inicio y la prioridad vigente, sin reiniciar el contador: el tiempo transcurrido sigue contándose desde la creación.
- RF-47: CUANDO cambie la prioridad de un ticket, EL SISTEMA actualizará automáticamente el tiempo objetivo y el vencimiento al de la nueva prioridad, manteniendo la fecha y hora de inicio en la creación del ticket y conservando el tiempo ya transcurrido. La actualización se aplicará también a un ticket `Resuelto` (HU-03 permite cambiar su prioridad): el vencimiento se recalculará con el nuevo tiempo objetivo y el estado se volverá a determinar contra la fecha y hora de resolución ya registrada. El cambio de técnico asignado no altera el SLA.
- RF-48: EL SISTEMA mantendrá el SLA actualizado sin intervención manual: no habrá operaciones para fijar, pausar, reiniciar ni corregir el estado del SLA, ni tareas programadas ni procesos en segundo plano. El estado, el tiempo transcurrido y el tiempo restante se derivarán de los datos del ticket y del reloj del sistema en el momento de cada consulta, de modo que dos consultas separadas en el tiempo puedan devolver valores distintos sin que nadie haya modificado el ticket.
- RF-49: EL SISTEMA mostrará el SLA únicamente junto con tickets que el usuario ya puede ver según HU-02, HU-03 y HU-04, sin introducir nuevas operaciones, rutas, permisos ni formas de acceso. Un cliente verá el SLA de sus propios tickets y no el de tickets ajenos; un técnico o administrador lo verá en las respuestas de las operaciones que ya tienen permitidas. La configuración de tiempos (RF-41) no se expone por ninguna operación pública.
- RF-50: EL SISTEMA expresará los tiempos en minutos enteros y las fechas y horas en ISO 8601/RFC 3339 con offset UTC y microsegundos, coherente con HU-02. El tiempo transcurrido y el tiempo restante se truncan a minutos completos; el tiempo restante nunca es negativo. El estado se determina con las duraciones exactas, no con los minutos redondeados, para que los límites del 20 % y del vencimiento sean estables. El instante de referencia es el reloj del sistema y solo las pruebas pueden sustituirlo; ninguna entrada de la API permite fijarlo.

## Requisitos no funcionales
- Separación de módulos y capas: el cálculo del SLA vive en el módulo `sla` (dominio y aplicación); `tickets` compone el resultado en su capa de interfaz mediante un contrato, sin que `sla` acceda a las estructuras internas de `tickets` ni a sus tablas. Las reglas de negocio no se implementan en los controladores HTTP (`docs/constitution.md`, `AGENTS.md`).
- Sin dependencias nuevas ni complejidad innecesaria: no se añaden librerías, tareas programadas, colas, cachés ni almacenamiento del estado calculado. La configuración de SLA es un singleton en memoria con los cuatro valores iniciales; la persistencia en PostgreSQL (`sla_policies` y `ticket_sla` de TSK-025) queda para la tarea de integración ya prevista.
- Consistencia de los contratos existentes: se conservan las rutas, los códigos y las reglas de HU-02, HU-03 y HU-04; el único cambio de contrato es la incorporación del campo `sla` a las respuestas de ticket. No se usa 400 ni 403 ni se introducen nuevos códigos de error.
- Rendimiento suficiente: el cálculo es aritmético y no realiza consultas adicionales por ticket; el listado sigue devolviendo los tickets en una sola operación.
- Zona horaria: todas las fechas y horas se almacenan y comparan en UTC; la conversión a la zona del usuario corresponde al frontend.

## Casos límite
- Ticket recién creado, sin prioridad → RF-42 (`sla: null` en creación, listado y detalle).
- Ticket al que se fija la prioridad inmediatamente después de crearlo → RF-43 (tiempo restante igual al objetivo, `en_tiempo`).
- Ticket creado varias horas antes de que se le fije la prioridad → RF-43.1 y RF-47 (el tiempo transcurrido incluye el periodo sin prioridad; puede nacer ya `en_riesgo` o `incumplido`).
- Ticket cuya prioridad cambia de `Baja` a `Crítica` → RF-47 (el vencimiento se recalcula desde la creación con 120 minutos; si ya pasaron más de 2 horas, queda `incumplido`).
- Ticket cuya prioridad cambia de `Crítica` a `Baja` → RF-47 (el vencimiento se aleja; el estado puede pasar de `incumplido` a `en_tiempo`, porque el compromiso vigente es el de la nueva prioridad).
- Ticket sin prioridad al que se le fija prioridad y luego se le cambia → RF-42, RF-47 (primero aparece el SLA y luego se recalcula).
- Ticket con exactamente el 20 % del tiempo objetivo restante → RF-45.1 (`en_riesgo`, porque el umbral es «menor o igual»).
- Ticket con algo más del 20 % restante → RF-45.1 (`en_tiempo`).
- Ticket consultado exactamente en su vencimiento, sin resolver → RF-45.2 (`incumplido`, porque el límite es «igual o posterior»).
- Ticket resuelto exactamente en su vencimiento → RF-45.3 y RF-46 (`cumplido`, porque el límite es «en su vencimiento o antes»).
- Ticket resuelto antes del vencimiento → RF-45.3 y RF-46 (`cumplido`); consultado mucho después sigue `cumplido` (el SLA está congelado).
- Ticket resuelto después del vencimiento → RF-45.3 y RF-46 (`incumplido`); `breached` verdadero.
- Ticket `Resuelto` que pasa a `Cerrado` → RF-46 (conserva la fecha de resolución y el estado del SLA).
- Ticket `Resuelto` que vuelve a `En progreso` → RF-46 (se descarta la resolución y el SLA vuelve a evolucionar desde la creación).
- Ticket `Resuelto` al que se le cambia la prioridad → RF-47 (nuevo vencimiento, estado recalculado contra la resolución ya registrada).
- Ticket `Cerrado` con cualquier intento de cambio de prioridad o estado → HU-03 (409, sin efecto sobre el SLA).
- Ticket `Abierto` o `En progreso` con SLA ya incumplido → RF-45.2 (permanece `incumplido` hasta que se resuelva o cambie la prioridad).
- Asignación o reasignación de técnico → RF-47 (el SLA no cambia).
- Listado con tickets con prioridad y sin prioridad → RF-44 (cada elemento con su objeto `sla` o `null`).
- Cliente que consulta sus tickets → RF-49 (ve el SLA de los suyos; no obtiene acceso a tickets ajenos).
- Intento de consultar o modificar la configuración de SLA por la API → RF-41 y RF-49 (no existe operación pública en esta historia).

## Fuera de alcance
- Consulta y modificación públicas de los tiempos de SLA por prioridad (API y UI de configuración): HU-14. En HU-05 solo existen los valores iniciales y la capacidad interna de consultarlos.
- Alertas, notificaciones y correos por SLA próximo a vencer o incumplido: HU-10 y HU-16.
- Dashboard, métricas y reportes de cumplimiento: HU-11, HU-12 y HU-18.
- Persistencia en PostgreSQL de políticas y SLA por ticket (`sla_policies`, `ticket_sla`): tarea de integración posterior a TSK-025.
- Políticas por empresa o por cliente, calendarios laborales, festivos, pausas por espera del cliente o por cambio de estado, y SLA por técnico o por tipo de ticket.
- Historial o auditoría de los cambios del SLA y de la configuración.
- Ajuste manual del estado del SLA, prórrogas, reinicios y correcciones.
- Interfaz de usuario del frontend: HU-20 (el contrato HTTP de esta historia queda listo para que el frontend lo consuma).
- Cambios en la creación, la autenticación, la prioridad, el estado o la asignación distintos de los exigidos por RF-46 y RF-47.

## Criterios de finalización
- RF-41 a RF-50 verificados con pruebas automatizadas con pytest: valores iniciales por prioridad, `sla: null` sin prioridad, inicio en la creación, vencimiento calculado, tiempo transcurrido y restante, estados `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`, umbral exacto del 20 %, límites del vencimiento y de la resolución, congelación al resolver, reapertura, cambio de prioridad y actualización automática con el paso del tiempo.
- Comprobado que el campo `sla` aparece con la misma composición en creación, listado, detalle, prioridad, estado y asignación, y que los tickets sin prioridad devuelven `sla: null`.
- Comprobado que no existen operaciones públicas de configuración ni de ajuste manual del SLA y que la configuración no se filtra en ninguna respuesta.
- Comprobado que la visibilidad no cambia: el cliente solo ve el SLA de sus tickets y los permisos de HU-03 y HU-04 siguen intactos.
- Actualizadas las pruebas de HU-02, HU-03 y HU-04 que afirman el conjunto exacto de campos de las respuestas de ticket, porque el contrato incorpora `sla`; la suite completa debe quedar en verde salvo los fallos preexistentes documentados en `MEMORY.md`.
- Ejecutado `codegraph sync` y actualizado `MEMORY.md` al terminar.

## Decisiones tomadas (clarificación de 2026-11-02)
- Configuración: solo los valores iniciales del documento general (120/240/720/1440 minutos), en un singleton global en memoria. La API y la UI de configuración se difieren a HU-14; el criterio «el sistema permite configurar» se cumple en esta historia con la configuración interna y sus valores iniciales. *Alternativa descartada: incluir aquí `GET/PUT /api/sla/policies`, que adelantaría HU-14 y ampliaría el alcance de 8 horas.*
- Ticket sin prioridad: `sla` nulo mientras no se fije prioridad; al fijarla, el vencimiento se calcula desde la fecha de creación. *Alternativas descartadas: iniciar el contador al fijar la prioridad (contradice el criterio de aceptación) y exigir prioridad en la creación (cambiaría el contrato de HU-02/HU-03).*
- Umbral de «próximo a vencer»: 20 % del tiempo objetivo restante, con `≤` y `> 0`, coherente con el ADR-006 del frontend y con la nota de diseño del documento general. *Alternativas descartadas: 10 % (aviso más tardío) y umbral fijo de 30 minutos (desproporcionado para Crítica).*
- Exposición: dentro de las respuestas de ticket, con la misma composición en todas ellas. *Alternativa descartada: endpoint aparte por ticket, que obligaría a una llamada por elemento en el listado.*
- Resolución: el SLA se congela al pasar a `Resuelto` o `Cerrado`, con `cumplido` si la resolución es en el vencimiento o antes e `incumplido` si es después. Se añade la fecha y hora de resolución al ticket; al reabrir se descarta y el SLA se reanuda desde la creación. *Alternativa descartada: no congelar, con lo que un ticket resuelto acabaría «incumplido» con el paso del tiempo.*
- Estado del SLA: cuatro valores alineados con el ADR-006 del frontend (`en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`), más los indicadores booleanos `near_due` y `breached` exigidos por las salidas de la historia.
- Persistencia: en memoria y global, coherente con los módulos actuales; la integración con las tablas de TSK-025 queda para la tarea de integración. *Alternativa descartada: cablear `company_id` y PostgreSQL ahora, que multiplicaría el alcance.*
- Arquitectura: `sla` expone un cálculo puro sobre los datos del ticket (creación, prioridad, estado y resolución) y `tickets` lo compone en su capa de interfaz; así `sla` no accede a las estructuras internas de `tickets` y se evita una dependencia circular. *Alternativa descartada: que `sla` consulte el repositorio de tickets, que acoplaría el módulo a sus estructuras internas.*
- Efecto de un cambio futuro de configuración sobre tickets existentes: se decidirá en HU-14; en esta historia la configuración no cambia en tiempo de ejecución, por lo que el tiempo objetivo es siempre el de la prioridad vigente.

## Dudas abiertas
Sin dudas abiertas pendientes.
