# Spec HU-12 — Dashboard de cumplimiento de SLA

Estado: borrador

## Contexto y objetivo

HU-11 entrega el volumen y la distribución de tickets, pero no responde si el equipo está cumpliendo los tiempos de atención. El sistema ya tiene prioridades (HU-03) y una configuración inicial de SLA por prioridad en la base de datos (TSK-025), aunque los módulos todavía no leen esa configuración. Sin un indicador agregado, el administrador no puede saber cuántos tickets están en tiempo, próximos a vencer o incumplidos, ni qué porcentaje del servicio cumple el SLA.

Esta historia añade un panel de cumplimiento de SLA con datos reales: un contrato HTTP de solo lectura que evalúa los tickets con prioridad y una vista con el porcentaje de cumplimiento, los conteos por estado de SLA y el desglose por prioridad. No configura los tiempos de SLA (HU-14), no genera alertas (HU-10/HU-16) y no modifica tickets.

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

> Numeración: se continúa la secuencia global del proyecto; esta historia usa RF-93 a RF-104. Fuente: tarjeta Trello «HU-12 — Dashboard de cumplimiento de SLA» y ADR-001. El panel sustituye el donut con datos mock de HU-20 (RF-51) y se apoya en la prioridad de HU-03, la asignación de HU-04 y la configuración inicial de SLA de TSK-025.

- RF-93: EL SISTEMA expondrá `GET /api/dashboard/sla`, que responderá 200 con el resumen de cumplimiento. SI la petición llega sin sesión válida, ENTONCES responderá 401 con el contrato de error de HU-01. SI el rol es `cliente`, ENTONCES responderá 404 uniforme, sin devolver datos.
- RF-94: EL SISTEMA aceptará el parámetro opcional `days` con los valores `7`, `30` o `90`. SI se omite, ENTONCES usará `30`. SI se envía otro valor, ENTONCES responderá 422 con el contrato de error de validación. El periodo filtrará los tickets por fecha y hora de creación dentro de los últimos `days` días respecto de `generated_at`, incluido el límite inferior y excluidos los tickets con fecha futura.
- RF-95: EL SISTEMA evaluará cada ticket con prioridad usando el tiempo objetivo de SLA de su prioridad: `Crítica` 120 minutos, `Alta` 240 minutos, `Media` 720 minutos y `Baja` 1440 minutos. MIENTRAS HU-14 no permita configurar los tiempos, estos valores serán la política por defecto del módulo de SLA. Un ticket sin prioridad no se evaluará y se contará en `sin_sla`.
- RF-96: CUANDO un ticket evaluado esté en estado `Abierto` o `En progreso`, EL SISTEMA calculará su estado de SLA en el instante `generated_at`:
  - `incumplido` si `generated_at` es posterior a la fecha límite (`created_at` + tiempo objetivo);
  - `en_riesgo` si no está incumplido y el tiempo restante es menor o igual al 20 % del tiempo objetivo;
  - `en_tiempo` en los demás casos.
- RF-97: CUANDO un ticket evaluado esté en estado `Resuelto` o `Cerrado`, EL SISTEMA lo clasificará como `cumplido` si su fecha de resolución es anterior o igual a la fecha límite, y como `incumplido` si es posterior. La fecha de resolución se registra cuando el ticket pasa a `Resuelto` o `Cerrado` y se limpia si el ticket vuelve a `Abierto` o `En progreso`. SI un ticket cerrado no tiene fecha de resolución registrada, ENTONCES se contará como `cumplido` y se informará en `closed_without_resolved_at` para no ocultar la limitación.
- RF-98: EL SISTEMA devolverá: `total_evaluated`, `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido`, `sin_sla`, `compliance_percentage`, `by_priority`, `generated_at`, `period_days` y `threshold_percent`. `total_evaluated` será la suma de `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`. `compliance_percentage` será `(en_tiempo + cumplido) / total_evaluated * 100`, redondeado a dos decimales; SI `total_evaluated` es cero, ENTONCES será `0.0`. `threshold_percent` será `20`.
- RF-99: EL SISTEMA devolverá `by_priority` con una entrada por cada prioridad del catálogo (`Crítica`, `Alta`, `Media`, `Baja`), incluidas las que no tengan tickets, con los conteos `en_tiempo`, `en_riesgo`, `cumplido`, `incumplido` y su `compliance_percentage`. La suma de los conteos de `by_priority` será igual a `total_evaluated`. Los tickets sin prioridad solo aparecerán en `sin_sla`.
- RF-100: EL SISTEMA aplicará el mismo alcance por rol que HU-11: el administrador evalúa todos los tickets; el técnico evalúa únicamente los asignados a él. Para el mismo rol y el mismo instante, `total_evaluated + sin_sla` será igual al total de tickets del alcance de HU-11, sin contradicciones entre ambos paneles.
- RF-101: SI no hay tickets evaluables en el periodo, ENTONCES EL SISTEMA responderá 200 con todos los conteos en cero, `compliance_percentage` en `0.0`, `by_priority` con las cuatro prioridades en cero y `sin_sla` con el número de tickets sin prioridad del periodo. No se producirá división por cero ni error.
- RF-102: CUANDO un administrador o un técnico abra `/`, EL SISTEMA mostrará el panel «Cumplimiento de SLA» con: el porcentaje de cumplimiento al centro de un donut, la leyenda con los conteos de en tiempo, en riesgo, cumplidos e incumplidos, el selector de periodo 7/30/90 días (30 por defecto) y una nota con los tickets sin SLA excluidos. El panel se actualizará al cambiar el periodo. SI el rol es `cliente`, ENTONCES será redirigido a `/mis-tickets`.
- RF-103: EL SISTEMA mostrará los estados de carga, vacío y error del panel. MIENTRAS carga, mostrará un esqueleto. SI no hay tickets evaluables, mostrará «No hay tickets evaluables en este periodo». SI la petición falla por red o por el servidor, mostrará un mensaje y el botón «Reintentar»; SI responde 401, ENTONCES redirigirá a `/login`. La leyenda no dependerá solo del color: incluirá texto y valores, y el panel será usable de 360 a 1440 px.
- RF-104: EL SISTEMA no usará datos mock ni etiqueta «Demo» en este panel. El cálculo se hará sobre la fuente real de tickets y la política de SLA vigente, sin almacenar el resultado en una tabla nueva ni modificar los tickets durante la consulta.

## Requisitos no funcionales

- Solo lectura: el contrato no modifica tickets, no crea registros de SLA y no envía notificaciones.
- Autorización por rol de sesión, coherente con HU-11; sin autorización por empresa en esta iteración.
- Fechas y horas en UTC, comparadas como instantes; la interfaz las presenta en la zona del usuario.
- Redondeo del porcentaje a dos decimales, sin `NaN` ni `Infinity`.
- El contrato no expone descripciones, correos ni credenciales.
- Sin dependencias nuevas para el cálculo; la interfaz reutiliza los componentes, el cliente HTTP y el sistema de periodos de HU-20/HU-21.
- La política de SLA por defecto debe quedar aislada para que HU-14 la sustituya sin cambiar el contrato del panel.

## Casos límite

- Ticket sin prioridad: se cuenta en `sin_sla`, no en `total_evaluated`.
- Ticket cerrado sin fecha de resolución: se cuenta como `cumplido` y se informa en `closed_without_resolved_at`.
- Ticket justo en la fecha límite: `en_tiempo` si sigue abierto y `cumplido` si se resolvió en ese instante; no se considera incumplido.
- Ticket justo en el 20 % restante: `en_riesgo`.
- Ticket reabierto: se limpia la fecha de resolución y vuelve a evaluarse como abierto.
- Cambio de prioridad: la fecha límite se recalcula con la prioridad vigente y la fecha de creación.
- Periodo sin tickets evaluables pero con tickets sin prioridad: `total_evaluated` en cero, `compliance_percentage` en `0.0` y `sin_sla` con su conteo.
- Periodo con `days=7` y tickets creados justo en el límite: se incluyen.
- Un técnico sin tickets asignados: todos los conteos en cero, sin error.

## Fuera de alcance

- Configurar o editar los tiempos de SLA (HU-14).
- Alertas, notificaciones o correos por SLA próximo a vencer o incumplido (HU-10, HU-16).
- Gráfico de actividad, tiempo medio de resolución, primera respuesta o métricas por técnico (HU-18, HU-24).
- Programación de revisiones periódicas o jobs en segundo plano: el cálculo es bajo demanda.
- Persistencia del resultado o de la fecha de resolución en PostgreSQL; se usa la fuente de tickets vigente.
- Políticas de SLA por empresa distintas de la política por defecto.
- Datos mock o etiqueta «Demo».

## Criterios de finalización

- El contrato responde 200, 401, 404 y 422 según RF-93 y RF-94, con los campos, las fórmulas y las invariantes de RF-98 a RF-101.
- Las pruebas cubren: en tiempo, en riesgo, incumplido abierto, cumplido, incumplido cerrado, sin prioridad, cerrado sin fecha de resolución, cambio de prioridad, reapertura, periodo 7/30/90, dataset vacío, administrador, técnico con alcance propio, cliente sin acceso y sesión inválida.
- El panel `/` consume el contrato real, muestra donut, leyenda, porcentaje, selector de periodo y nota de `sin_sla`, y cubre carga, vacío y error.
- `pytest` del backend y `npm run test`/`npm run build` del frontend pasan.
- `MEMORY.md` queda actualizado con el estado y las decisiones.

## Decisiones de alcance adoptadas

1. **Datos reales, sin mock.** El panel sustituye el donut mock de HU-20 RF-51.
2. **Cuatro estados de SLA.** `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`; el porcentaje de cumplimiento suma `en_tiempo + cumplido` sobre el total evaluado. `en_riesgo` todavía no es incumplimiento.
3. **Umbral de riesgo del 20 %.** Un ticket está en riesgo cuando le queda el 20 % o menos de su tiempo objetivo. El valor se devuelve en `threshold_percent` para que la interfaz no lo duplique.
4. **Política por defecto 2/4/12/24 horas.** Se toma de los valores iniciales de TSK-025; HU-14 la hará configurable. La fuente queda aislada en el módulo de SLA.
5. **La fecha de resolución se registra en el ticket.** Es un campo aditivo, necesario para distinguir cumplido de incumplido en tickets cerrados. No cambia los contratos existentes de HU-03.
6. **Panel dentro de `/`.** Se muestra junto al dashboard de tickets, conforme a ADR-001; no se crea una ruta nueva en esta historia.
7. **Periodo por defecto de 30 días.** Coherente con ADR-001 («Últimos 30 días»); el selector permite 7, 30 y 90.
8. **Mismo alcance por rol que HU-11.** Administrador global; técnico solo sus asignados; cliente sin acceso.

## Dudas abiertas

- Ninguna pendiente. Si el equipo prefiere una ruta propia para el detalle de SLA, se cambia en esta spec antes de implementar; el contrato HTTP no cambia.
