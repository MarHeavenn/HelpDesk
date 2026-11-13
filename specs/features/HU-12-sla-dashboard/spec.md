# Spec HU-12 — Dashboard de cumplimiento de SLA

Estado: aprobada

## Contexto y objetivo

HU-11 entrega el volumen y la distribución de tickets, pero no responde si el equipo está cumpliendo los tiempos de atención. El módulo `sla` de HU-05 ya calcula el SLA de cada ticket con prioridad (tiempos objetivo por prioridad, umbral de riesgo del 20 % y congelación al resolver) y HU-14 ya permite configurar esos tiempos. Sin un indicador agregado, el administrador no puede saber cuántos tickets están en tiempo, próximos a vencer o incumplidos, ni qué porcentaje del servicio cumple el SLA.

Esta historia añade un panel de cumplimiento de SLA con datos reales: un contrato HTTP de solo lectura que reutiliza el cálculo existente del módulo `sla` y una vista con el porcentaje de cumplimiento, los conteos por estado de SLA y el desglose por prioridad. No duplica el cálculo ni la política, no configura tiempos (HU-14), no genera alertas (HU-10/HU-16) y no modifica tickets.

## Usuarios / actores

- Administrador (rol `administrador`): actor principal. Ve el cumplimiento de toda la organización.
- Técnico (rol `tecnico`): ve el cumplimiento de los tickets que tiene asignados, coherente con el alcance de HU-11.
- Cliente (rol `cliente`): no accede; recibe 404 en el contrato y redirección en la interfaz.
- Visitante sin sesión: no accede; recibe 401 en el contrato y redirección en la interfaz.

## Historias de usuario

- H1: Como administrador, quiero saber qué porcentaje de los tickets evaluados cumple el SLA para medir el desempeño del equipo.
- H2: Como administrador, quiero distinguir los tickets en tiempo, próximos a vencer e incumplidos para anticipar problemas.
- H3: Como administrador, quiero ver el cumplimiento por prioridad para detectar qué tipo de solicitudes se está atendiendo peor.
- H4: Como técnico, quiero ver el cumplimiento de mis tickets asignados para priorizar mi trabajo.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global del proyecto; esta historia usa RF-93 a RF-104. Fuente: tarjeta Trello «HU-12 — Dashboard de cumplimiento de SLA» y ADR-001. El panel sustituye el donut con datos mock de la referencia del frontend (RF-51) y reutiliza el cálculo del módulo `sla` de HU-05 y la configuración administrable de HU-14.

- RF-93: EL SISTEMA expondrá `GET /api/dashboard/sla`, que responderá 200 con el resumen de cumplimiento. SI la petición llega sin sesión válida, ENTONCES responderá 401 con el contrato de error de HU-01. SI el rol es `cliente`, ENTONCES responderá 404 uniforme, sin devolver datos.
- RF-94: EL SISTEMA aceptará el parámetro opcional `days` con los valores `7`, `30` o `90`. SI se omite, ENTONCES usará `30`. SI se envía otro valor, ENTONCES responderá 422 con el contrato de error de validación. El periodo filtrará los tickets por fecha y hora de creación dentro de los últimos `days` días respecto de `generated_at`, incluido el límite inferior y excluidos los tickets con fecha futura.
- RF-95: EL SISTEMA evaluará cada ticket con prioridad usando el tiempo objetivo vigente de su prioridad, leído de la configuración administrable de HU-14 (`GET/PUT /api/sla/policies`; semilla inicial `Crítica` 120, `Alta` 240, `Media` 720 y `Baja` 1440 minutos) a través del cálculo existente del módulo `sla` (`calculate_ticket_sla` / `target_minutes_for`). No se duplicará la política ni se almacenará una copia. Un ticket sin prioridad no se evaluará y se contará en `sin_sla`.
- RF-96: CUANDO un ticket evaluado esté en estado `Abierto` o `En progreso`, EL SISTEMA reutilizará el cálculo de SLA de HU-05 (`calculate_sla` / `get_ticket_sla`) en el instante `generated_at`, sin un segundo cálculo:
  - `incumplido` si `generated_at` es igual o posterior a la fecha límite (`created_at` + tiempo objetivo);
  - `en_riesgo` si no está incumplido y el tiempo restante es menor o igual al 20 % del tiempo objetivo (`RISK_THRESHOLD_RATIO = 0.20`);
  - `en_tiempo` en los demás casos.
- RF-97: CUANDO un ticket evaluado esté en estado `Resuelto` o `Cerrado`, EL SISTEMA reutilizará el cálculo de SLA de HU-05, que congela el resultado con `resolved_at` y el objetivo aplicado al resolver (`resolved_target_minutes`, HU-14): `cumplido` si la fecha de resolución es anterior o igual a la fecha límite, e `incumplido` si es posterior. La fecha de resolución ya la registra y limpia el ciclo de vida del ticket (HU-05/HU-08); HU-12 no la modifica. SI un ticket en estado `Resuelto` o `Cerrado` no tiene fecha de resolución registrada, ENTONCES se contará como `cumplido` y se informará en `closed_without_resolved_at` para no ocultar la limitación.
- RF-98: EL SISTEMA devolverá: `total_evaluated`, `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`, `sin_sla`, `compliance_percentage`, `by_priority`, `generated_at`, `period_days` y `threshold_percent`. `total_evaluated` será la suma de `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`. `compliance_percentage` será `(en_tiempo + cumplido) / total_evaluated * 100`, redondeado a dos decimales; SI `total_evaluated` es cero, ENTONCES será `0.0`. `threshold_percent` será `20`, obtenido de `RISK_THRESHOLD_RATIO` del módulo `sla`.
- RF-99: EL SISTEMA devolverá `by_priority` con una entrada por cada prioridad del catálogo (`Crítica`, `Alta`, `Media`, `Baja`), incluidas las que no tengan tickets, con los conteos `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido` y su `compliance_percentage`. La suma de los conteos de `by_priority` será igual a `total_evaluated`. Los tickets sin prioridad solo aparecerán en `sin_sla`.
- RF-100: EL SISTEMA aplicará el mismo alcance por rol que HU-11: el administrador evalúa todos los tickets; el técnico evalúa únicamente los asignados a él. `total_evaluated + sin_sla` será igual al número de tickets del alcance del actor creados dentro del periodo; ese número es un subconjunto del `total_tickets` de HU-11, que no filtra por periodo. Para el mismo rol e instante, ningún ticket del periodo quedará fuera de `total_evaluated + sin_sla` ni se contará dos veces.
- RF-101: SI no hay tickets evaluables en el periodo, ENTONCES EL SISTEMA responderá 200 con todos los conteos en cero, `compliance_percentage` en `0.0`, `by_priority` con las cuatro prioridades en cero y `sin_sla` con el número de tickets sin prioridad del periodo. No se producirá división por cero ni error.
- RF-102: CUANDO un administrador o un técnico abra `/`, EL SISTEMA mostrará el panel «Cumplimiento de SLA» con: el porcentaje de cumplimiento al centro de un donut, la leyenda con los conteos de en tiempo, en riesgo, cumplidos e incumplidos, el selector de periodo 7/30/90 días (30 por defecto) y una nota con los tickets sin SLA excluidos. El panel se actualizará al cambiar el periodo. SI el rol es `cliente`, ENTONCES será redirigido a `/mis-tickets`.
- RF-103: EL SISTEMA mostrará los estados de carga, vacío y error del panel. MIENTRAS carga, mostrará un esqueleto. SI no hay tickets evaluables, mostrará «No hay tickets evaluables en este periodo». SI la petición falla por red o por el servidor, mostrará un mensaje y el botón «Reintentar»; SI responde 401, ENTONCES redirigirá a `/login`. La leyenda no dependerá solo del color: incluirá texto y valores, y el panel será usable de 360 a 1440 px.
- RF-104: EL SISTEMA no usará datos mock ni etiqueta «Demo» en este panel. El cálculo se hará sobre la fuente real de tickets y la política de SLA vigente, reutilizando el módulo `sla`, sin almacenar el resultado en una tabla nueva ni modificar los tickets durante la consulta.

## Requisitos no funcionales

- Solo lectura: el contrato no modifica tickets, no crea registros de SLA y no envía notificaciones.
- Reutilización: el cálculo y los estados de SLA viven en el módulo `sla` (HU-05/HU-14); HU-12 no duplica `calculate_sla`, `RISK_THRESHOLD_RATIO` ni la política de tiempos.
- Separación de módulos: la agregación vive en `sla/application`; los datos de tickets llegan por un contrato de lectura de `tickets/interface`; `sla` no accede a las tablas internas de `tickets`.
- Consistencia con HU-05/HU-14: un cambio de política afecta a los tickets activos en la siguiente consulta; los tickets resueltos conservan el objetivo congelado al resolver. Un cambio de prioridad en un ticket resuelto lo re-congela con la configuración vigente para la nueva prioridad.
- Autorización por rol de sesión, coherente con HU-11; sin autorización por empresa en esta iteración.
- Fechas y horas en UTC, comparadas como instantes; la interfaz las presenta en la zona del usuario.
- Redondeo del porcentaje a dos decimales, sin `NaN` ni `Infinity`.
- El contrato no expone descripciones, correos ni credenciales.
- Sin dependencias nuevas para el cálculo; la interfaz reutiliza los componentes, el cliente HTTP y el sistema de periodos de la referencia del frontend/HU-21.

## Casos límite

- Ticket sin prioridad: se cuenta en `sin_sla`, no en `total_evaluated`.
- Ticket cerrado sin fecha de resolución: se cuenta como `cumplido` y se informa en `closed_without_resolved_at`.
- Ticket justo en la fecha límite: `incumplido` si sigue abierto (`generated_at >= due_at`) y `cumplido` si se resolvió en ese instante (`resolved_at <= due_at`).
- Ticket justo en el 20 % restante: `en_riesgo`.
- Ticket reabierto: se limpia la fecha de resolución y el objetivo congelado; vuelve a evaluarse como abierto con la política vigente.
- Cambio de prioridad en un ticket activo: la fecha límite se recalcula con la prioridad vigente y la fecha de creación.
- Cambio de prioridad en un ticket resuelto: se conserva `resolved_at` y se re-congela el objetivo con la configuración vigente para la nueva prioridad.
- Cambio de política sin cambiar la prioridad de un ticket resuelto: el SLA permanece congelado con `resolved_target_minutes`.
- Periodo sin tickets evaluables pero con tickets sin prioridad: `total_evaluated` en cero, `compliance_percentage` en `0.0` y `sin_sla` con su conteo.
- Periodo con `days=7` y tickets creados justo en el límite: se incluyen.
- Un técnico sin tickets asignados: todos los conteos en cero, sin error.

## Fuera de alcance

- Configurar o editar los tiempos de SLA (HU-14).
- Alertas, notificaciones o correos por SLA próximo a vencer o incumplido (HU-10, HU-16).
- Gráfico de actividad, tiempo medio de resolución, primera respuesta o métricas por técnico (HU-18, HU-24).
- Programación de revisiones periódicas o jobs en segundo plano: el cálculo es bajo demanda.
- Persistencia del resultado agregado; la fecha de resolución ya existe en el ticket (HU-05) y se usa la fuente de tickets vigente.
- Políticas de SLA por empresa distintas de la política global de HU-14.
- Datos mock o etiqueta «Demo».

## Criterios de finalización

- El contrato responde 200, 401, 404 y 422 según RF-93 y RF-94, con los campos, las fórmulas y las invariantes de RF-98 a RF-101.
- La implementación reutiliza `calculate_ticket_sla`, `TicketSlaSnapshot`, `RISK_THRESHOLD_RATIO` y los estados de SLA de HU-05, sin duplicar el dominio ni la política de HU-14.
- Las pruebas cubren: en tiempo, en riesgo, incumplido abierto, cumplido, incumplido cerrado, sin prioridad, cerrado sin fecha de resolución, cambio de prioridad, reapertura, cambio de política en ticket activo y resuelto, periodo 7/30/90, dataset vacío, administrador, técnico con alcance propio, cliente sin acceso y sesión inválida.
- El panel `/` consume el contrato real, muestra donut, leyenda, porcentaje, selector de periodo y nota de `sin_sla`, y cubre carga, vacío y error.
- `pytest` del backend y `npm run test`/`npm run build` del frontend pasan.
- `MEMORY.md` queda actualizado con el estado y las decisiones.

## Decisiones de alcance adoptadas

1. **Datos reales, sin mock.** El panel sustituye el donut mock de la referencia del frontend RF-51.
2. **Cuatro estados de SLA.** `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`; el porcentaje de cumplimiento suma `en_tiempo + cumplido` sobre el total evaluado. `en_riesgo` todavía no es incumplimiento.
3. **Umbral de riesgo del 20 %.** Se reutiliza `RISK_THRESHOLD_RATIO` del módulo `sla`; el valor se devuelve en `threshold_percent` para que la interfaz no lo duplique.
4. **Política vigente administrada por HU-14.** La semilla es 2/4/12/24 horas; HU-12 la lee a través de `target_minutes_for`/`calculate_ticket_sla` en cada consulta, sin duplicarla ni cachearla.
5. **La fecha de resolución ya existe en el ticket.** HU-05 la registra y la limpia; HU-12 solo la consume. No se añade un campo nuevo ni se cambia el contrato de HU-03.
6. **Panel dentro de `/`.** Se muestra junto al dashboard de tickets, conforme a ADR-001; no se crea una ruta nueva en esta historia.
7. **Periodo por defecto de 30 días.** Coherente con ADR-001 («Últimos 30 días»); el selector permite 7, 30 y 90.
8. **Mismo alcance por rol que HU-11.** Administrador global; técnico solo sus asignados; cliente sin acceso.
9. **Reutilización del módulo SLA.** No se crea `sla/domain/sla.py` ni un `evaluate_sla` paralelo: el dashboard llama a `calculate_ticket_sla` y usa `TicketSlaSnapshot` y los estados de HU-05.
10. **Contrato de lectura de tickets.** `tickets/interface/sla_contract.py` expone solo los campos que necesita el dashboard; `sla` no importa el repositorio ni el dominio de `tickets`.

## Dudas abiertas

- Ninguna pendiente. Si el equipo prefiere una ruta propia para el detalle de SLA, se cambia en esta spec antes de implementar; el contrato HTTP no cambia.
