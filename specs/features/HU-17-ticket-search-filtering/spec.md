# Spec HU-17 — Búsqueda y filtrado de tickets

Estado: aprobada e implementada con límites de validación declarados. RF-165–RF-178; plan y tareas ejecutados. Cierre, trazabilidad y verificaciones en `tasks.md`. No se declara validación completa de PostgreSQL.

## Contexto y objetivo

El sistema ya dispone de un listado único de tickets compartido por «Todos los tickets» y «Mis tickets», con búsqueda por identificador o título, filtros de prioridad, estado y técnico, paginación y conservación del contexto en la dirección de la vista. Sin embargo, ese listado no permite acotar por **solicitante** ni por **estado del SLA**, y la regla de combinación de criterios no está fijada como criterio de aceptación propio. El resultado es que localizar una solicitud concreta obliga a revisar páginas o a cruzar información de otras pantallas.

Esta historia consolida el comportamiento de búsqueda y filtrado como una sola regla verificable —todos los criterios activos se combinan con **Y** y solo se muestran coincidencias— y añade los dos criterios que faltan en **ambas vistas, solo para los roles que ya pueden consultarlas**. El usuario autoriza ampliar de forma aditiva la respuesta de lectura del listado con la información del solicitante necesaria para buscar por nombre, sin ampliar permisos, tickets accesibles ni aislamiento entre empresas. El objetivo es reducir el tiempo necesario para localizar las solicitudes que el técnico debe gestionar.

La caracterización T1 documentó exposición entre empresas en los listados general, de atención y de asignados, rechazos inconsistentes para cuentas sin empresa y la denegación al supervisor de la consulta que alimenta su vista ya autorizada. Este cambio incorpora su corrección conforme a HU-13 antes de ampliar la información de lectura: conservar permisos significa cumplir la política aprobada, no conservar accesos indebidos ni denegaciones contrarias a ella. También exige recuperar la verificación completa, actualmente interrumpida durante la recopilación de pruebas; no añade una funcionalidad de datos de demostración.

## Usuarios / actores

- **Técnico** (actor principal): localiza solicitudes dentro de los tickets que ya puede consultar según su alcance vigente, tanto en el listado general como en el de sus tickets.
- **Administrador**: usa los criterios en ambas vistas, conservando el alcance vigente de cada una.
- **Cliente**: usa búsqueda y filtros de estado, prioridad, solicitante y SLA solo en «Mis tickets», sobre sus propios tickets; no accede a «Todos los tickets» ni dispone del filtro de técnico.
- **Supervisor**: consulta los tickets de su empresa en «Todos los tickets», conforme a HU-13; no obtiene «Mis tickets» ni el filtro de técnico. Corregir la denegación de esa consulta hace efectiva una autorización existente, no crea un permiso nuevo.

## Historias de usuario

- H1: Como técnico, quiero buscar y filtrar tickets por identificador, título, estado, prioridad, solicitante, técnico asignado y estado del SLA, en «Todos los tickets» y en «Mis tickets», para localizar rápidamente las solicitudes que necesito gestionar.
- H2: Como técnico, quiero combinar varios criterios a la vez para acotar el resultado y no revisar coincidencias parciales.
- H3: Como técnico, quiero conservar los criterios aplicados al recargar o compartir la vista para retomar la búsqueda donde la dejé.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global nominal llega a RF-164 en `specs/features/HU-16-sla-breach-notifications/spec.md`. Esta historia usa RF-165 a RF-178; RF-175 recoge la ampliación aditiva de lectura autorizada tras QA y RF-176–RF-178 las correcciones de seguridad propuestas tras T1. HU-26, integrada desde `develop`, también usa RF-165–RF-172: citar siempre HU y RF conjuntamente. HU-24 usa RF-124–RF-132, números ya ocupados por HU-13/HU-19. Esta revisión no renumera requisitos aprobados.
>
> Trazabilidad: la búsqueda parcial por identificador o título, los filtros de prioridad, estado y técnico según rol, la combinación con Y, la conservación en la dirección y la paginación ya están implementados por HU-23 (RF-119 a RF-123) en el listado compartido por ambas vistas. HU-17 **no los redefine como capacidad nueva**: los conserva como criterios de no regresión y añade solicitante y estado del SLA. La composición cerrada del resumen de HU-23 RF-122 queda ampliada únicamente por la adición del solicitante autorizada en RF-175; sus campos previos y reglas de acceso se conservan. El catálogo de SLA es el ya vigente y confirmado por el usuario —«En tiempo», «En riesgo», «Cumplido» e «Incumplido»— más «Sin SLA» y el valor «Todos» que no filtra.
>
> Referencia normativa de acceso: HU-13 RF-105/RF-106, RF-113–RF-119, RF-123 y RF-124 prevalecen sobre descripciones anteriores incompatibles de HU-23. RF-176 responde a las fugas entre empresas de la evidencia T1, apartado 3; RF-177 a la discrepancia del supervisor; RF-178 a autenticación y cuentas sin empresa. La compatibilidad heredada es la de HU-13 RF-123: conservar cuentas y datos no concede acceso multitenant sin empresa. El bloqueo de verificación completa consta separadamente en la evidencia T1, apartado 4.

- RF-165: CUANDO el usuario aplique uno o varios criterios de búsqueda o filtrado disponibles para su rol y vista, EL SISTEMA mostrará únicamente los tickets que satisfagan **simultáneamente todos** los criterios activos: **(identificador O título) Y estado Y prioridad Y solicitante Y técnico asignado Y estado del SLA**, omitiendo los criterios no activos o no disponibles. Esta regla regirá en «Todos los tickets» y «Mis tickets» solo para los roles autorizados en cada vista. Un criterio sin valor, vacío o en su valor por defecto («Todos») no restringirá el resultado. El contador de resultados y la paginación se calcularán sobre el subconjunto filtrado de la vista y nunca sobre el total del listado completo.

- RF-166: CUANDO se introduzca un término de búsqueda, EL SISTEMA mostrará los tickets cuyo identificador **o** título contenga ese término de forma parcial, sin distinguir mayúsculas de minúsculas y sin considerar los espacios de los extremos. Ambas coincidencias constituirán un único criterio agrupado, combinado mediante Y con los demás criterios activos. El término podrá incluir o no el prefijo «#» del identificador y ambos casos producirán la misma coincidencia sobre el identificador. Un término vacío, compuesto solo por espacios o compuesto solo por «#» no restringirá el resultado. La búsqueda no se aplicará a la descripción, a los comentarios ni al historial.

- RF-167: CUANDO se elija un estado del ticket, EL SISTEMA mostrará únicamente los tickets cuyo estado coincida exactamente con el elegido, entre los estados oficiales vigentes «Abierto», «En progreso», «Resuelto» y «Cerrado». Sin elección o con «Todos» el criterio no restringirá. SI el estado recibido en la dirección no pertenece al catálogo, ENTONCES EL SISTEMA lo normalizará a «Todos», sin error ni vaciado forzado del resultado y conservando los demás criterios válidos.

- RF-168: CUANDO se elija una prioridad, EL SISTEMA mostrará únicamente los tickets cuya prioridad coincida exactamente con la elegida, entre las prioridades oficiales vigentes «Crítica», «Alta», «Media» y «Baja». Sin elección o con «Todos» el criterio no restringirá. Un ticket sin prioridad no coincidirá con ninguna prioridad concreta y, respecto de este criterio, solo aparecerá con «Todos». SI la prioridad recibida en la dirección no pertenece al catálogo, ENTONCES EL SISTEMA la normalizará a «Todos», sin error ni vaciado forzado del resultado y conservando los demás criterios válidos.

- RF-169: CUANDO un técnico o administrador elija un técnico asignado en una vista ya autorizada para su rol, EL SISTEMA mostrará únicamente los tickets asignados a ese técnico; con la opción «Sin asignar» mostrará únicamente los tickets que no tengan técnico. Sin elección o con «Todos» el criterio no restringirá. Un técnico concreto nunca devolverá tickets sin asignar y «Sin asignar» nunca devolverá tickets con técnico. EL SISTEMA mantendrá el filtro de técnico disponible solo para técnicos y administradores: no lo ofrecerá al cliente ni al supervisor, ni lo habilitará por recibir una dirección compartida.

- RF-170: EL SISTEMA ofrecerá en ambas vistas, solo a los roles que ya pueden consultarlas, un campo de **texto libre** para acotar por solicitante, sin desplegable, directorio ni autocompletado de personas. Un campo vacío o compuesto solo por espacios no restringirá, incluidos los tickets cuyo solicitante no sea identificable. CUANDO se escriba un texto no vacío en ese campo, EL SISTEMA mostrará únicamente los tickets cuyo **nombre del solicitante** contenga ese texto de forma parcial, sin distinguir mayúsculas de minúsculas y sin considerar los espacios de los extremos; el correo del solicitante no participará en la coincidencia y no se exigirá el nombre completo. Los tickets cuyo solicitante no sea identificable quedarán excluidos con un término no vacío. El criterio se combinará con el resto mediante Y. Si dos o más solicitantes distintos contienen el término, se mostrarán los tickets de todos ellos que cumplan los demás criterios. El criterio operará solo sobre tickets que el actor ya puede consultar: no revelará solicitantes ni tickets fuera de su alcance ni ampliará el conjunto accesible.

- RF-171: CUANDO se elija un estado del SLA, EL SISTEMA mostrará únicamente los tickets cuyo **estado concreto de negocio del SLA** en los datos de la consulta coincida exactamente con el elegido, entre «En tiempo», «En riesgo», «Cumplido» e «Incumplido», sin agrupar estados por nivel, color ni señal visual: «En tiempo» y «Cumplido» serán distintos aunque compartan presentación. CUANDO se elija «Sin SLA», EL SISTEMA mostrará únicamente los tickets cuyo SLA esté ausente o sea nulo en el listado; actualmente son los tickets sin prioridad, sin introducir otras causas ni reglas de cálculo. Ninguno de los cuatro estados devolverá tickets sin SLA. Sin elección o con «Todos» el criterio no restringirá y permitirá también los tickets sin SLA. El filtro y la presentación usarán los mismos datos de SLA de la consulta, sin un segundo cálculo; se conservará la actualización existente del listado y no se añadirá actualización automática ni en tiempo real.

- RF-172: EL SISTEMA reflejará en la dirección de la vista todos los criterios activos y disponibles para el rol —término de búsqueda, estado, prioridad, técnico cuando corresponda, texto de solicitante, estado del SLA, orden y página— en «Todos los tickets» y en «Mis tickets», solo donde el actor esté autorizado. Recargar o compartir esa dirección reproducirá los criterios y, si no cambian los datos ni la autorización del actor, el mismo resultado. SI un valor de estado, prioridad o SLA recibido en la dirección es desconocido o inválido, ENTONCES EL SISTEMA normalizará únicamente ese criterio a «Todos», conservando los demás criterios válidos y sin error ni vaciado forzado. Los demás valores inválidos se normalizarán a su valor por defecto vigente, y una página no numérica, anterior a la primera o posterior a la última se normalizará a la primera página, sin romper la vista. Un criterio de técnico recibido por un rol sin ese filtro no se aplicará. CUANDO cambie cualquier criterio, EL SISTEMA volverá a la primera página conservando el orden elegido.

- RF-173: SI la vista no contiene tickets antes de aplicar criterios, ENTONCES EL SISTEMA mostrará el vacío base «No hay tickets», aunque existan filtros activos; este vacío tendrá precedencia sobre el vacío por filtros y conservará el comportamiento base existente. SI la vista contiene tickets antes de aplicar criterios y el subconjunto filtrado está vacío, ENTONCES EL SISTEMA mostrará «No hay coincidencias», el mensaje «No encontramos tickets con esos filtros» y la acción «Limpiar filtros». CUANDO se active «Limpiar filtros», EL SISTEMA vaciará el término de búsqueda y el texto de solicitante, restablecerá estado, prioridad, técnico cuando corresponda y estado del SLA a «Todos», y volverá a la primera página conservando el orden. Limpiar desde «Sin SLA» restablecerá el criterio de SLA a «Todos», no a «Sin SLA». SI no hay ningún criterio activo, ENTONCES EL SISTEMA no mostrará la acción de limpiar.

- RF-174: EL SISTEMA aplicará esta búsqueda y filtrado sobre el listado único ya compartido por «Todos los tickets» y «Mis tickets», exclusivamente en las vistas autorizadas para cada rol, sin crear rutas, pantallas, permisos, alcances ni criterios de acceso nuevos, y sin etiqueta «Demo» ni datos simulados. El conjunto filtrable será el autorizado por HU-13 y precisado en RF-176–RF-178, no el que una exposición indebida permita recibir; ninguna combinación de criterios ni dirección compartida podrá ampliarlo. La adición de información del solicitante de RF-175 respetará esa autorización y el aislamiento entre empresas. La interfaz mantendrá los estados de carga, error y sesión expirada ya existentes.

- RF-175: CUANDO el usuario autorizado consulte un listado de tickets, EL SISTEMA incluirá en la respuesta de lectura la información del solicitante necesaria para filtrar por su nombre cuando sea identificable, y representará su ausencia cuando no lo sea. Esta ampliación será **aditiva**: conservará los campos, su significado y las reglas de acceso aprobadas de HU-13, sin introducir cambios incompatibles ni ampliar otros contratos. La adición no expondrá correo, credenciales ni datos personales innecesarios para este filtro, ni información de solicitantes de tickets ajenos al alcance autorizado.

- RF-176: CUANDO un actor autorizado consulte cualquiera de los listados existentes que devuelven resúmenes de tickets —consulta visible, general, de asignados o de atención—, EL SISTEMA devolverá únicamente tickets cuya empresa almacenada coincida con la empresa del actor obtenida de su sesión, además de satisfacer el alcance propio del listado y del rol. El cliente solo podrá consultar tickets de los que sea solicitante dentro de su empresa; el listado de asignados conservará además la selección por el actor asignado, y el de atención sus condiciones vigentes de atención y orden. Los tickets de otra empresa o sin empresa quedarán excluidos de estas consultas multitenant, aunque su solicitante o técnico asignado esté relacionado con el actor; tampoco se expondrán sus nombres, SLA ni otros datos del resumen. Ningún criterio de búsqueda o dato recibido permitirá seleccionar o suplantar otra empresa.

- RF-177: CUANDO un administrador, supervisor o técnico con empresa consulte «Todos los tickets», EL SISTEMA permitirá la consulta de los tickets de su empresa conforme a HU-13, sin limitarla a los creados o asignados al actor. SI el actor es cliente, ENTONCES EL SISTEMA conservará la denegación uniforme de la consulta general. El supervisor no obtendrá «Mis tickets», filtro de técnico ni otras capacidades no autorizadas por HU-13; el cliente seguirá solo con su vista personal sin filtro de técnico. Esta corrección no ampliará los roles habilitados para el listado de atención ni alterará las demás reglas específicas de cada listado.

- RF-178: SI una consulta a cualquiera de estos listados llega sin sesión válida, ENTONCES EL SISTEMA responderá 401 antes de resolver o divulgar datos. SI la sesión es válida pero la cuenta no tiene empresa, o el rol no está autorizado para la consulta, ENTONCES EL SISTEMA responderá con el mismo 404 observable de recurso no visible establecido para esa operación, sin datos ni cambios; una cuenta sin empresa no recibirá una colección exitosa, aunque estuviera vacía. CUANDO una consulta autorizada dentro de la empresa no tenga tickets coincidentes con el alcance del listado, EL SISTEMA conservará la respuesta exitosa con colección vacía, diferenciándola de una denegación. Se conservarán las cuentas y datos heredados conforme a HU-13 RF-123, sin asignarles empresa implícitamente, cambiar sus credenciales ni convertir esa compatibilidad en una excepción de acceso multitenant.

## Requisitos no funcionales

- **Alcance de datos**: el filtrado y la adición del nombre del solicitante respetan la autorización normativa de HU-13; las fugas y denegaciones contrarias a ella se corrigen mediante RF-176–RF-178, no se conservan como compatibilidad. Un criterio sin coincidencias sobre una consulta autorizada no produce un error y los vacíos se distinguen conforme a RF-173.
- **Respuesta percibida**: al escribir o cambiar un criterio, los resultados se actualizan sin recargar la página y sin perder el foco ni el texto introducido.
- **Accesibilidad**: todos los criterios tendrán etiqueta asociada, serán operables por teclado y el cambio del número de resultados se anunciará como estado para tecnologías de asistencia. La vista seguirá siendo usable de 360 a 1440 px.
- **Consistencia de vocabulario**: las etiquetas visibles de estado, prioridad y estado del SLA —incluida «Sin SLA»— serán las ya centralizadas en la aplicación; no se introducirán sinónimos ni catálogos paralelos.
- **Coherencia entre vistas**: los criterios disponibles para el rol se comportan igual en ambas vistas autorizadas; el resultado siempre se limita a los tickets que esa vista ya expone al actor.

## Casos límite

- Término de búsqueda con solo espacios, solo «#» o con mayúsculas y minúsculas mezcladas.
- Término que coincide con el identificador pero no con el título, y viceversa: ambas coincidencias siguen sujetas mediante Y a los demás criterios activos.
- Texto de solicitante vacío o compuesto solo por espacios: no restringe.
- Texto de solicitante con mayúsculas y minúsculas mezcladas o con espacios en los extremos: coincide con el nombre igual que el texto recortado y en minúsculas.
- Dos solicitantes distintos cuyo nombre contiene el término: aparecen los tickets de ambos.
- Texto que solo coincide con el correo del solicitante y no con su nombre: no produce coincidencias.
- Texto de solicitante sin coincidencias: vacío por filtros solo si la vista base tiene tickets; si no, vacío base, sin revelar solicitantes ajenos.
- Solicitante no identificable o ausente: el ticket permanece elegible con el texto de solicitante vacío o solo espacios y queda excluido con un término no vacío, sin error y sujeto a los demás criterios.
- Ticket sin prioridad: aparece con «Sin SLA» y con «Todos», nunca con los cuatro estados de SLA ni con una prioridad concreta.
- SLA ausente o nulo: coincide con «Sin SLA» y permite «Todos», sujeto al resto de criterios; no se introducen otras causas de ausencia ni reglas nuevas. Ticket con SLA: nunca aparece con «Sin SLA».
- Ticket sin técnico: no aparece bajo un técnico concreto; sí bajo «Sin asignar», solo para los roles con ese filtro.
- Ticket resuelto o cerrado cuyo SLA está congelado como «Cumplido» o «Incumplido».
- Tickets con SLA «En tiempo» y «Cumplido» que comparten color o señal visual: solo coincide el estado concreto elegido, nunca ambos por compartir presentación.
- En «Mis tickets» del cliente, un texto de solicitante distinto del propio cliente no produce resultados.
- Cliente que recibe una dirección de «Todos los tickets» o con filtro de técnico: no obtiene acceso a esa vista ni se le aplica dicho filtro. El supervisor conserva sus autorizaciones existentes y no obtiene el filtro de técnico.
- Combinación de todos los criterios disponibles sin coincidencias, en cualquiera de las vistas autorizadas.
- Dirección con criterios desconocidos, vacíos o con estado, prioridad o SLA fuera del catálogo: cada uno de estos tres criterios inválidos pasa a «Todos» y los restantes criterios válidos se conservan.
- Dirección con página no numérica, cero o posterior a la última página del resultado filtrado.
- Vista base vacía con y sin filtros activos: «No hay tickets»; vista base no vacía con subconjunto vacío: «No hay coincidencias».
- Limpiar filtros después de una búsqueda sin resultados, incluida «Sin SLA»: todos los selectores disponibles vuelven a «Todos», los textos quedan vacíos y la página vuelve a la primera, conservando el orden.
- Sesión expirada durante una consulta del listado.
- Alta o cambio de un ticket por otro usuario mientras la vista está abierta: el resultado se actualiza en la siguiente consulta, sin prometer actualización en tiempo real.
- Cambio del SLA entre consultas: el filtrado usa el estado concreto de los datos de cada consulta, coherente con la actualización existente, sin recalcular desde colores ni añadir actualización automática.
- Consumidores actuales del listado: la adición del solicitante no elimina ni cambia los campos existentes, respeta los tickets autorizados por HU-13 y no añade correo ni credenciales; no se exige conservar tickets previamente expuestos sin autorización.
- Dos empresas con solicitante o técnico del actor vinculados a un ticket de otra empresa: ninguna consulta de resúmenes revela ese ticket ni sus datos relacionados.
- Listado de asignados con tickets propios y ajenos asignados al mismo actor: solo incluye los de su empresa. Listado de atención con tickets que cumplen sus condiciones en ambas empresas: solo incluye los de la empresa autorizada.
- Supervisor con empresa que consulta la vista general y su consulta de datos: acceso efectivo a los tickets de su empresa, sin habilitar vista personal ni filtro técnico.
- Los cuatro roles con sesión válida pero sin empresa: 404 uniforme en cada consulta multitenant de resúmenes, tanto con datos presentes como con colección potencialmente vacía. Sin sesión válida prevalece 401.
- Cuenta heredada sin empresa y ticket heredado sin empresa en presencia de datos multitenant: conservar los registros no permite incluirlos en un ámbito empresarial ni inferir su empresa a partir de solicitante/asignado.
- Actor con empresa y permiso vigente pero sin tickets en el alcance de la consulta: respuesta exitosa vacía y estado visual base, no 404.

## Fuera de alcance

- Cambios incompatibles de los contratos existentes y ampliaciones de lectura distintas de la información del solicitante autorizada en RF-175.
- Buscar por descripción, comentarios o historial.
- Desplegable, directorio, autocompletado de solicitantes o cualquier catálogo de personas para el filtro de solicitante.
- Coincidencia del filtro de solicitante por correo, por identificador de usuario o exacta del nombre completo: la coincidencia es parcial sobre el nombre.
- Búsqueda difusa, tolerante a acentos o a errores de escritura.
- Filtros por fecha, por empresa u otros criterios no enumerados.
- Exportación de resultados, guardado de búsquedas y vistas personalizadas.
- Cambios de permisos o alcances distintos de los ya aprobados en HU-13; sí se incluye corregir su incumplimiento en los listados de RF-176–RF-178. No se autoriza asociación automática de empresas, eliminación de datos heredados ni excepciones nuevas de acceso.
- Habilitar «Todos los tickets» al cliente o habilitar el filtro de técnico a clientes o supervisores.
- Nuevos estados, causas de ausencia o reglas de cálculo del SLA; agrupar estados de negocio por color o nivel visual; añadir actualización automática o en tiempo real.
- Rediseño del listado, nuevas rutas o nuevas pantallas.
- Pruebas de extremo a extremo.
- Crear o ampliar funcionalidades de carga de datos de demostración para resolver el bloqueo de verificación.

## Criterios de finalización

- RF-165 a RF-178 verificados uno por uno mediante pruebas automatizadas, con al menos una comprobación por criterio y vista autorizada para el rol; combinación **(identificador O título) Y demás criterios**; ausencia del filtro de técnico para cliente y supervisor; y cumplimiento de las autorizaciones de HU-13 por rol y empresa.
- Comprobaciones de solicitante: coincidencia parcial sobre el nombre sin distinguir mayúsculas ni espacios periféricos, sin coincidencia por correo ni exigencia del nombre completo; solicitantes con nombres coincidentes y solicitante no identificable con término vacío y no vacío.
- Comprobaciones de SLA: los cuatro estados de negocio por separado, incluidos «En tiempo» frente a «Cumplido» aunque compartan color; «Sin SLA» para SLA ausente o nulo; «Todos» sin restricción; y datos de consulta consistentes sin nueva actualización automática.
- Comprobaciones de dirección y vacíos: estado, prioridad y SLA inválidos normalizados individualmente a «Todos» conservando los demás criterios válidos; precedencia de «No hay tickets» con filtros activos; «No hay coincidencias» solo sobre base no vacía; y limpieza completa a «Todos», textos vacíos y primera página conservando el orden.
- No regresión de HU-23 RF-119 a RF-123 en las vistas y roles autorizados: búsqueda, filtros existentes según rol, conservación en la dirección, contador, paginación y estados de carga, vacío, error y sesión expirada; la única ampliación del resumen de lectura es la adición autorizada del solicitante de RF-175, sin cambios incompatibles ni exposición de correo o credenciales.
- Comprobación manual con técnico y administrador sobre datos reales en ambas vistas: criterios individuales y combinados, dirección compartida y recargada, limpieza a «Todos», «Sin SLA» y coincidencia parcial del nombre; comprobación del cliente solo en su vista personal sin filtro de técnico, y de que el supervisor conserva sus capacidades existentes sin ese filtro.
- Correcciones de RF-176–RF-178 verificadas en todas las consultas de resúmenes con dos empresas, relaciones de solicitante/asignado cruzadas, los cuatro roles, cuenta sin empresa, ticket sin empresa, ausencia de sesión y listado autorizado vacío. Se comprueba tanto la exclusión de datos ajenos como el acceso efectivo del supervisor a su vista general, sin ampliar su acceso a otras vistas o controles.
- Compatibilidad de cuentas y datos heredados verificada conforme a HU-13 RF-123, sin cambios implícitos de empresa, credenciales o autoría; los contratos exactos de lectura conservan los campos previos y solo la adición autorizada de RF-175.
- Antes de ampliar la lectura con solicitante, deben estar verificadas las correcciones de seguridad de RF-176–RF-178. La evidencia T1 sigue siendo una caracterización bloqueada, no una validación ni una corrección completada.
- La suite completa debe poder recopilar y ejecutar sus pruebas sin depender de símbolos inexistentes ni excluir los casos que causaron el bloqueo. Para declarar la historia cumplida debe finalizar en verde, registrando entorno, resultados y cualquier omisión justificada; no se acepta relajar expectativas de seguridad, ocultar fallos mediante exclusiones ni presentar pruebas focalizadas como ejecución completa. Recuperar esta verificación es un prerrequisito técnico, no una funcionalidad de datos de demostración.
- `specs/project.md` y el índice de historias reflejan HU-17 al aprobarse la spec.

## Dudas abiertas

**Resueltas**

1. Alcance de las vistas: el filtrado y la búsqueda aplican a «Todos los tickets» y a «Mis tickets» únicamente para sus roles autorizados por HU-13; el cliente continúa solo en «Mis tickets», y el supervisor consulta la vista general de su empresa sin obtener vista personal ni filtro técnico (RF-165, RF-172, RF-174, RF-177).
2. Forma del filtro de solicitante: campo de texto libre, no desplegable ni directorio (RF-170; el fuera de alcance excluye el catálogo de personas).
3. Opción de SLA para tickets sin SLA: se incluye «Sin SLA» como opción explícita (RF-171, RF-173).
4. Catálogo de estado del SLA: «En tiempo», «En riesgo», «Cumplido» e «Incumplido», más «Todos» que no filtra (RF-171). Coincide con los literales ya usados por la aplicación.
5. Regla de coincidencia del texto de solicitante: coincidencia parcial sobre el **nombre**, sin distinguir mayúsculas de minúsculas y sin considerar los espacios de los extremos; el correo no participa y no se exige el nombre completo (RF-170, opción a confirmada).
6. Ampliación de lectura autorizada expresamente tras QA: incluir información del solicitante necesaria para buscar por nombre, de forma aditiva, sin cambios incompatibles, sin correo ni credenciales y sin ampliar permisos o aislamiento (RF-175; amplía únicamente la composición cerrada de HU-23 RF-122).
7. Filtro de técnico solo para técnicos y administradores en sus vistas autorizadas; cliente y supervisor no lo obtienen, tampoco por una dirección compartida (RF-169, RF-172).
8. Estado, prioridad y SLA inválidos en la dirección se normalizan individualmente a «Todos», sin error ni vaciado forzado y conservando los demás criterios válidos (RF-167, RF-168, RF-172).
9. SLA significa estado concreto de negocio de la consulta, no nivel o color visual; «En tiempo» y «Cumplido» no se agrupan. Se conserva la actualización existente sin nueva actualización automática (RF-171).
10. «Sin SLA» significa SLA ausente o nulo en el listado, actualmente sin prioridad; no se añaden causas ni reglas de cálculo (RF-171).
11. El vacío base «No hay tickets» tiene precedencia incluso con filtros activos; «No hay coincidencias» requiere una base no vacía y un subconjunto filtrado vacío (RF-173).
12. Solicitante no identificable: el ticket sigue siendo elegible con texto de solicitante vacío y queda excluido con término no vacío (RF-170).
13. La búsqueda constituye **(identificador O título)** y se combina mediante Y con los demás criterios; limpiar restablece todos los selectores disponibles, incluido SLA, a «Todos», nunca a «Sin SLA» (RF-165, RF-166, RF-173).
14. Cambio aprobado tras T1: corregir aislamiento y acceso en todas las consultas de resúmenes conforme a HU-13, incluida la consulta general del supervisor, sin crear derechos distintos de los normativos (RF-176–RF-178). El usuario aprobó explícitamente el diff y el prerrequisito de verificación; la revisión de plan y tareas requiere su propia aprobación.
15. Compatibilidad heredada: HU-13 RF-123 conserva cuentas y datos, pero HU-13 RF-106/RF-119 no permite a una cuenta sin empresa ejecutar operaciones multitenant. No se crea una excepción ni se asigna empresa implícitamente (RF-178).
16. Recuperar la recopilación y ejecución completa de pruebas es una condición de verificación; no exige inventar una funcionalidad de semillas o datos de demostración. Los resultados de T1 permanecen como evidencia previa y no se declaran resueltos con este cambio documental.

No quedan dudas de negocio abiertas. La versión revisada, el plan y las tareas fueron aprobados y ejecutados; R1 resolvió los bloqueos históricos P1/T1 antes de añadir el solicitante. La implementación y los límites de validación se resumen en `tasks.md`; no quedan aprobaciones de implementación pendientes ni se afirma una verificación de persistencia no ejecutada.
