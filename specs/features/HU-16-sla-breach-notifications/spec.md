# Spec HU-16 — Notificaciones de incumplimiento de SLA
Estado: aprobada

## Contexto y objetivo

HU-05 calcula en vivo el estado del SLA de cada ticket (`en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`) y HU-10 reúne los tickets que requieren atención. HU-15 incorporó el centro de notificaciones interno, pero sus avisos solo cubren eventos de asignación, estado, resolución y reapertura: cuando un ticket está a punto de vencer o ya incumplió su SLA, nadie recibe un aviso dentro de la aplicación.

HU-16 conecta el cálculo de SLA con el mecanismo de notificaciones de HU-15 para avisar al administrador de la empresa y, cuando corresponda, al técnico responsable. Se evitan avisos duplicados para el mismo evento y se conserva un registro de cada evento notificado. No se introduce un segundo cálculo de SLA, un trabajo programado ni un canal externo: la alerta se deriva del mismo `get_ticket_sla` de HU-05 y se apoya en el sondeo de notificaciones que el frontend ya hace cada 30 segundos.

## Usuarios / actores

- **Administrador** (rol `administrador`): recibe las alertas de SLA de los tickets de su empresa y las consulta en la campana, en `/notificaciones` y en el panel del dashboard.
- **Técnico** (rol `tecnico`): recibe las alertas de los tickets que tiene asignados.
- **Supervisor** (rol `supervisor`): no es destinatario de las alertas, pero conserva la visibilidad de supervisión de HU-15 sobre las notificaciones de su empresa.
- **Cliente** (rol `cliente`): no recibe alertas de SLA; su solicitud sigue cubierta por HU-15.
- **Sistema**: genera la alerta y queda como actor del aviso; no existe una cuenta real asociada.
- **Visitante sin sesión**: 401 antes de cualquier otra comprobación.

## Historias de usuario

- H1: Como administrador, quiero recibir una notificación cuando un ticket de mi empresa esté próximo a incumplir o haya incumplido su SLA, para identificar oportunamente los casos que requieren seguimiento.
- H2: Como técnico, quiero recibir la misma alerta de los tickets que atiendo, para actuar antes de que venza el tiempo objetivo.
- H3: Como administrador, quiero que un mismo evento no genere avisos repetidos, para no llenar la bandeja con alertas duplicadas.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: HU-15 termina en RF-155. HU-16 usa RF-156 a RF-164.

- RF-156: EL SISTEMA derivará alertas de SLA **en el instante de la consulta** reutilizando el cálculo existente de HU-05 (`get_ticket_sla`), sin un segundo cálculo, umbral nuevo ni tarea programada:
  - solo considerará tickets activos, es decir, con estado distinto de `Resuelto` y `Cerrado`;
  - solo considerará tickets con prioridad y, por tanto, con SLA calculable;
  - SI el SLA está `en_riesgo` (`near_due`), ENTONCES generará una alerta de tipo `sla_near_due`;
  - SI el SLA está `incumplido` (`breached`), ENTONCES generará una alerta de tipo `sla_breached`;
  - un ticket `en_tiempo` o `cumplido` no generará alerta.

- RF-157: EL SISTEMA dirigirá cada alerta a:
  - todos los usuarios **activos** con rol `administrador` cuyo `company_id` coincida con el del ticket, incluido el ámbito sin empresa (`None`) para datos heredados de desarrollo;
  - el **técnico asignado** vigente del ticket, si existe;
  - sin repetir destinatarios cuando un administrador es también el técnico asignado;
  - nunca al solicitante, al supervisor ni al cliente por su rol.

  Los administradores desactivados no reciben alertas. SI no hay ningún destinatario resoluble, ENTONCES no se registra ninguna notificación.

- RF-158: EL SISTEMA evitará avisos duplicados para el mismo evento. Como máximo existirá una alerta por combinación de ticket, tipo de alerta, destinatario y fecha de vencimiento (`due_at`) del SLA:
  - repetir la consulta o el sondeo no crea una segunda alerta;
  - `sla_near_due` y `sla_breached` del mismo ticket son eventos distintos y pueden coexistir;
  - SI cambia el vencimiento del SLA (por cambio de prioridad, de la configuración de tiempos objetivo o por reapertura), ENTONCES el nuevo vencimiento se considera un evento nuevo y puede generar una nueva alerta;
  - las alertas ya generadas no se borran ni se marcan como resueltas cuando el ticket pasa a `Resuelto`, `Cerrado` o `cumplido`: permanecen como registro histórico.

- RF-159: EL SISTEMA registrará cada alerta con el mismo contrato de notificación de HU-15:
  - identificador UUID opaco, `type` (`sla_near_due` o `sla_breached`), ticket `{id, title}`, destinatario `{id, name|null}`, actor del sistema `{id: "system", name: "Sistema"}`, `previous_value` en `null`, `new_value` con la fecha de vencimiento del SLA en ISO 8601 con offset UTC, `created_at` con el instante del análisis y `read_at` en `null` hasta que el destinatario la lea;
  - nunca incluirá correo, rol, credenciales ni datos internos del usuario;
  - la clave interna de deduplicación no forma parte del contrato HTTP.

- RF-160: EL SISTEMA ejecutará el análisis de alertas de forma perezosa antes de responder las consultas de notificaciones, de modo que el sondeo existente las descubra sin un programador:
  - antes de `GET /api/notifications` y de `GET /api/notifications/unread-count`;
  - con un único instante de referencia para todos los tickets del análisis;
  - con este ámbito según el rol del actor: `administrador` y `supervisor`, todos los tickets de su misma empresa; `tecnico`, los tickets asignados a él; `cliente`, ninguno;
  - de forma idempotente: repetir la consulta no duplica alertas ni modifica tickets;
  - sin sesión válida, 401 antes de cualquier análisis.

- RF-161: EL SISTEMA mantendrá las cuatro rutas existentes de `/api/notifications` sin añadir endpoints de SLA:
  - `GET /api/notifications` incluirá las alertas visibles según RF-157 y la visibilidad de HU-15;
  - `GET /api/notifications/unread-count` contará las alertas propias no leídas;
  - `POST /api/notifications/{id}/read` y `POST /api/notifications/read-all` funcionarán igual que en HU-15;
  - los tipos nuevos se documentarán en OpenAPI sin cambiar la forma de `NotificationResponse`.

- RF-162: EL FRONTEND mostrará las alertas de SLA en las superficies existentes, sin una página nueva:
  - ampliará la unión de tipos con `sla_near_due` y `sla_breached`;
  - mostrará las etiquetas «SLA por vencer» y «SLA incumplido» y mensajes en español con la fecha de vencimiento;
  - usará iconos distintos y accesibles para ambos tipos;
  - las verá en la campana, en `/notificaciones` y en el panel de novedades del dashboard;
  - mostrará «Sistema» como actor de estas alertas;
  - conservará el sondeo cada 30 segundos y el refresco al recuperar el foco, sin WebSockets;
  - mantendrá los estados de carga, vacío, error y 401 de HU-15.

- RF-163: La implementación respetará la arquitectura:
  - las alertas vivirán dentro del módulo `tickets`, reutilizando su repositorio de notificaciones;
  - `tickets` calculará el SLA solo mediante el contrato `sla/interface/contract.py`;
  - la resolución de administradores se hará mediante un contrato público de `identity` que devuelva solo identificadores y nombres, sin acceder a sus tablas ni estructuras internas;
  - la composición de repositorios y contratos ocurrirá en `interface` y `main.py`;
  - no se añadirán dependencias nuevas.

- RF-164: La verificación cubrirá backend y frontend:
  - pruebas de dominio, caso de uso, API y flujo con pytest y `TestClient`;
  - pruebas de utilidades, página, panel y campana con Vitest y Testing Library;
  - `npm test`, `npm run build`, `npm run lint` y la suite del backend en verde en modo memoria, salvo las pruebas que requieren PostgreSQL.

## Requisitos no funcionales

- **Arquitectura**: sin módulo nuevo; alertas en `tickets`, SLA por contrato y administradores por contrato de `identity`.
- **Rendimiento**: el análisis recorre solo los tickets del ámbito del actor y se ejecuta como máximo una vez por consulta de notificaciones; con el sondeo de 30 s es suficiente para el MVP.
- **Consistencia**: un único `now` por análisis; deduplicación determinista por ticket, tipo, destinatario y vencimiento.
- **Privacidad**: cada usuario ve las alertas según la visibilidad de HU-15; el contador y las acciones de lectura solo afectan a las propias.
- **Accesibilidad**: etiquetas e iconos con texto alternativo, foco visible y navegación por teclado heredados de HU-15.
- **Mantenibilidad**: textos centralizados, cliente HTTP tipado y casos de uso separados de la interfaz.

## Casos límite

- Ticket sin prioridad → sin SLA y sin alerta.
- Ticket `en_tiempo` → sin alerta.
- Ticket `en_riesgo` → una alerta `sla_near_due` por destinatario.
- Ticket `incumplido` → una alerta `sla_breached` por destinatario.
- Ticket que pasa de `en_riesgo` a `incumplido` → dos alertas distintas, una de cada tipo.
- Ticket resuelto o cerrado → no genera alertas nuevas, aunque el SLA se haya incumplido antes de resolver.
- Ticket reabierto con un vencimiento distinto → puede generar una nueva alerta.
- Cambio de prioridad o de la configuración de SLA que mueve `due_at` → nuevo evento.
- Repetir la consulta de notificaciones → sin duplicados.
- Empresa sin administrador activo → solo se avisa al técnico asignado.
- Ticket sin técnico asignado → solo se avisa a los administradores.
- Administrador que además es el técnico asignado → una sola alerta.
- Administrador desactivado → no recibe alertas.
- Supervisor → no recibe alertas, pero ve las de su empresa por supervisión.
- Cliente → no recibe alertas de SLA.
- Ámbito sin empresa (`company_id` `None`) → se trata como un ámbito propio para datos heredados de desarrollo.
- Actor sin sesión → 401 antes de analizar.
- Fallo de red en el frontend → se conserva el estado anterior y se puede reintentar; un 401 cierra la sesión.

## Fuera de alcance

- Correo electrónico, SMS, notificaciones push y cualquier servicio externo.
- WebSockets, SSE, colas, cron o tareas programadas.
- Nuevos umbrales de SLA o un segundo cálculo distinto de HU-05.
- Notificar al solicitante o al cliente sobre el SLA.
- Preferencias de notificación, silenciar tipos o configurar destinatarios por empresa.
- Edición, borrado o reenvío de alertas.
- Persistencia en PostgreSQL y cambios de esquema.
- Cambios en `TicketResponse`, en el cálculo de SLA o en las reglas de ticket.
- Pruebas E2E y despliegue.

## Criterios de finalización

- Todos los RF-156 a RF-164 tienen al menos una prueba automatizada.
- La suite del backend queda en verde en modo memoria; las pruebas de PostgreSQL siguen omitidas si Docker no está activo.
- `npm test`, `npm run build` y `npm run lint` en verde.
- `specs/features/HU-16-sla-breach-notifications/` contiene `spec.md`, `plan.md` y `tasks.md`; la spec y el plan quedan en `implementada`/`implementado` al cerrar.
- `specs/project.md` y `MEMORY.md` reflejan el estado final y se ejecuta `codegraph sync`.
- Demostración local: `dev_server.py` siembra tickets de ejemplo con SLA próximo a vencer e incumplido, y las alertas se ven en la campana, en `/notificaciones` y en el dashboard al iniciar sesión como administrador y como técnico.

## Dudas abiertas

Sin dudas pendientes. Las decisiones de destinatarios (administrador activo de la empresa y técnico asignado), generación perezosa en las consultas de notificaciones, deduplicación por vencimiento y no re-notificar al solicitante se registran como supuestos de esta spec.
