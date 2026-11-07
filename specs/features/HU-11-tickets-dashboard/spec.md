# Spec HU-11 — Dashboard de tickets

Estado: borrador

## Contexto y objetivo

HU-02, HU-03 y HU-04 ya permiten crear, priorizar, cambiar de estado y asignar tickets, pero la información solo se consulta ticket por ticket o en listados. Un administrador no tiene una vista agregada que responda cuántos tickets hay, cómo se distribuyen por estado y prioridad y cómo se reparte la carga entre los técnicos.

Esta historia añade un dashboard de tickets con datos reales: un contrato HTTP de solo lectura que agrega los tickets existentes y una vista de entrada que muestra los indicadores, las distribuciones y los tickets recientes. No crea, modifica ni asigna tickets; tampoco calcula SLA, que corresponde a HU-12.

## Usuarios / actores

- Administrador (rol `administrador`): actor principal. Ve la operación completa de la organización.
- Técnico (rol `tecnico`): ve el dashboard limitado a los tickets que tiene asignados, conforme a ADR-001.
- Cliente (rol `cliente`): no accede al dashboard; se le redirige a sus tickets.
- Visitante sin sesión: no accede; recibe 401 en el contrato y redirección en la interfaz.

## Historias de usuario

- H1: Como administrador, quiero ver el volumen total de tickets para dimensionar la operación.
- H2: Como administrador, quiero ver la distribución de tickets por estado y por prioridad para detectar acumulaciones y urgencias.
- H3: Como administrador, quiero ver la carga por técnico y los tickets sin asignar para redistribuir el trabajo.
- H4: Como administrador, quiero ver los últimos tickets registrados para revisar la actividad reciente.
- H5: Como técnico, quiero ver un resumen de mis tickets asignados para conocer mi carga.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global del proyecto; esta historia usa RF-81 a RF-92. Fuente: tarjeta Trello «HU-11 — Dashboard de tickets» y ADR-001. Sustituye el dashboard con datos mock de HU-20 (RF-51): el dashboard pasa a usar datos reales. El gráfico de actividad con rangos 7/30/90 días de ADR-001 queda para HU-24; esta historia solo entrega los conteos y los recientes.

- RF-81: EL SISTEMA expondrá `GET /api/dashboard/tickets`, que responderá 200 con un resumen agregado de tickets. SI la petición llega sin sesión válida, ENTONCES responderá 401 con el mismo contrato de error de HU-01. SI el rol es `cliente`, ENTONCES responderá 404 uniforme, sin devolver datos ni revelar la existencia de tickets.
- RF-82: CUANDO un administrador solicite el resumen, EL SISTEMA agregará todos los tickets existentes en el sistema, sin filtrar por solicitante ni por técnico.
- RF-83: CUANDO un técnico solicite el resumen, EL SISTEMA agregará únicamente los tickets cuyo técnico responsable sea ese usuario. Los tickets sin asignar y los asignados a otros técnicos no formarán parte de sus conteos.
- RF-84: EL SISTEMA devolverá en el resumen: `total_tickets`, `by_status`, `by_priority`, `by_assignee`, `recent_tickets` y `generated_at`. Los conteos serán números enteros no negativos y `generated_at` será la fecha y hora UTC de generación en formato ISO 8601.
- RF-85: EL SISTEMA devolverá `by_status` con una entrada por cada estado del catálogo (`Abierto`, `En progreso`, `Resuelto`, `Cerrado`), incluidos los estados con cero tickets. La suma de los conteos de `by_status` será igual a `total_tickets`.
- RF-86: EL SISTEMA devolverá `by_priority` con una entrada por cada prioridad del catálogo (`Crítica`, `Alta`, `Media`, `Baja`) y una entrada `sin_prioridad` para los tickets que aún no tienen prioridad. La suma de los conteos de `by_priority` será igual a `total_tickets`. La prioridad `sin_prioridad` no se confundirá con una prioridad del catálogo.
- RF-87: EL SISTEMA devolverá `by_assignee` con una entrada por cada técnico registrado y una entrada `sin_asignar` para los tickets sin técnico responsable. Cada entrada incluirá el identificador del técnico (`null` en `sin_asignar`), su nombre y el número de tickets. Un técnico sin tickets aparecerá con conteo cero. La suma de `by_assignee` será igual a `total_tickets`. Para un técnico que consulta, `by_assignee` contendrá únicamente su propia entrada y `sin_asignar` quedará en cero, porque su resumen solo incluye sus tickets asignados.
- RF-88: EL SISTEMA devolverá `recent_tickets` con los cinco tickets más recientes por fecha y hora de creación, ordenados de más reciente a más antiguo. Cada elemento incluirá identificador, título, prioridad (o `null`), estado, técnico responsable (identificador y nombre, o `null`) y fecha y hora de creación. No incluirá la descripción. Un empate de fecha no fija orden entre los empatados.
- RF-89: EL SISTEMA calculará todos los conteos a partir del mismo conjunto de tickets y en la misma operación, de modo que las invariantes de RF-85, RF-86 y RF-87 se cumplan siempre. No habrá cifras fijas ni valores contradictorios entre secciones.
- RF-90: SI no existe ningún ticket en el alcance del usuario, ENTONCES EL SISTEMA responderá 200 con `total_tickets` en cero, todas las entradas de `by_status`, `by_priority` y `by_assignee` en cero y `recent_tickets` vacío. No se producirá división por cero ni error.
- RF-91: CUANDO un administrador o un técnico abra `/`, EL SISTEMA mostrará el dashboard con: cuatro indicadores (total de tickets, abiertos, en atención y resueltos), la distribución por estado, la distribución por prioridad, la carga por técnico con los tickets sin asignar y una tabla con los cinco tickets recientes. El botón «+ Crear ticket» navegará a `/tickets/nuevo` y «Ver todos» a `/tickets`. SI el rol es `cliente`, ENTONCES será redirigido a `/mis-tickets`.
- RF-92: EL SISTEMA mostrará los estados de carga, vacío y error del dashboard. MIENTRAS carga, mostrará esqueletos en lugar de cifras. SI no hay tickets, mostrará un estado vacío con el texto «Aún no hay tickets» y un enlace a crear ticket. SI la petición falla por red o por el servidor, mostrará un mensaje y el botón «Reintentar»; SI responde 401, ENTONCES redirigirá a `/login`. El dashboard será usable de 360 a 1440 px, con los indicadores en 4, 2 o 1 columna y las tablas con desplazamiento horizontal, y cumplirá las reglas de accesibilidad de RF-75 de HU-21.

## Requisitos no funcionales

- Solo lectura: el contrato no admite cuerpo, no modifica tickets y no escribe registros.
- Autorización por rol de sesión, sin autorización por empresa en esta iteración.
- Los conteos se derivan de la fuente de tickets existente; no se duplican ni se almacenan en una tabla nueva.
- El contrato no expone descripciones, correos, credenciales ni datos personales distintos del nombre del técnico.
- Las fechas se devuelven en ISO 8601 con zona UTC, coherentes con los contratos de HU-02 a HU-04.
- Sin dependencias nuevas para el agregado; la interfaz puede reutilizar los componentes y el cliente HTTP de HU-20/HU-21.

## Casos límite

- Tickets sin prioridad: se agrupan en `sin_prioridad` y no se descartan.
- Tickets sin asignar: se agrupan en `sin_asignar`.
- Tickets cerrados: siguen contando en el total y en su estado, como en los listados de HU-02.
- Técnicos registrados sin tickets: aparecen con cero en el resumen del administrador.
- Un técnico que consulta: no ve tickets de otros ni tickets sin asignar.
- Dataset vacío: ceros y listas vacías, sin error.
- Muchos tickets: el agregado se resuelve en una sola pasada, sin una consulta por técnico ni por estado.
- Cambios concurrentes mientras se calcula: el resumen refleja una instantánea; no se exige consistencia transaccional en esta iteración.

## Fuera de alcance

- Cálculo de SLA, cumplimiento, riesgos o incumplimientos (HU-12).
- Gráfico de actividad con rangos 7/30/90 días, tiempo medio de resolución y primera respuesta (HU-24 y HU-18).
- Filtros, búsqueda, paginación o exportación del dashboard.
- Crear, editar, asignar o cerrar tickets desde el dashboard.
- Datos mock o etiqueta «Demo»: el dashboard usa datos reales.
- Persistencia del agregado en PostgreSQL; se calcula sobre la fuente de tickets vigente.
- Métricas por empresa o comparación entre organizaciones.

## Criterios de finalización

- El contrato responde 200, 401 y 404 según RF-81, con los campos y las invariantes de RF-84 a RF-90.
- Las pruebas cubren administrador con datos completos, técnico con alcance propio, cliente sin acceso, sesión inválida, dataset vacío, tickets sin prioridad y sin asignar, y técnicos con cero tickets.
- La vista `/` consume el contrato real, muestra los indicadores, distribuciones y recientes, y cubre carga, vacío, error y redirección del cliente.
- `pytest` del backend y `npm run test`/`npm run build` del frontend pasan.
- `MEMORY.md` queda actualizado con el estado y las decisiones.

## Decisiones de alcance adoptadas

1. **Datos reales, sin mock.** El dashboard deja de usar el seed mock de HU-20 RF-51. La fuente es el contrato de RF-81.
2. **Administrador global; técnico con alcance propio.** Se mantiene la matriz de ADR-001 y HU-20 RF-51: el técnico ve solo sus tickets asignados.
3. **Cliente sin acceso.** Se responde 404 uniforme en el contrato y redirección en la interfaz, coherente con el criterio de no revelación del proyecto.
4. **Prioridad y asignación vacías son categorías explícitas.** `sin_prioridad` y `sin_asignar` evitan que los totales no cuadren.
5. **Sin rango de fechas en esta historia.** El gráfico de actividad y sus rangos quedan en HU-24; el dashboard entrega el estado actual.
6. **Sin tabla de agregados.** Los conteos se calculan en memoria sobre la fuente de tickets; la integración con PostgreSQL es una tarea aparte y no cambia el contrato.

## Dudas abiertas

- Ninguna pendiente. El diseño visual exacto de las tarjetas y la tabla se concreta en el plan, reutilizando ADR-001 y los componentes de HU-20/HU-21.
