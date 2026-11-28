# Spec HU-18 — Métricas de gestión de soporte

Estado: aprobada

## Contexto y objetivo

El administrador necesita evaluar el volumen de trabajo, los casos que siguen pendientes y los tiempos de atención del servicio sin revisar los tickets individualmente. Esta historia permite consultar, sobre todo el historial autorizado, el total de tickets, los resueltos y pendientes, el tiempo promedio de resolución y el porcentaje de cumplimiento del SLA de resolución de los tickets finalizados. Las cifras procederán de los datos registrados y explicarán su alcance y sus muestras para no confundir ausencia de datos con un resultado de cero.

Esta consulta no sustituye los dashboards de HU-11 y HU-12. En particular, HU-12 combina tickets activos y finalizados y permite periodos; HU-18 mide el cumplimiento de resolución exclusivamente en finalizados evaluables, sin filtro temporal. Tampoco modifica las reglas de estados, resolución, reapertura, SLA ni autorización de las historias anteriores.

## Usuarios / actores

- **Administrador**: consulta las métricas sobre todos los tickets que tiene permiso de consultar, sin limitarse a los creados por él ni a un técnico.
- **Supervisor, técnico y cliente**: no reciben acceso a esta nueva consulta por esta historia; conservan sus permisos sobre tickets y dashboards existentes.
- **Persona sin sesión válida**: no accede a la consulta.

## Historias de usuario

- H1: Como administrador, quiero consultar métricas de gestión de soporte, para analizar el desempeño del servicio y los tiempos de atención.
- H2: Como administrador, quiero conocer qué datos participan en cada indicador y cuándo no existe una muestra evaluable, para interpretar correctamente el resultado.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: HU-18 usa RF-179–RF-191, a continuación de HU-17 RF-178. RF-191 incorpora la aclaración expresa del usuario sobre finalizados sin objetivo SLA conservado. Las referencias a otros requisitos incluyen su HU para evitar las colisiones históricas de numeración del proyecto.
>
> Referencias normativas: HU-13 RF-105/RF-106, RF-113 y RF-119 para autenticación y aislamiento; HU-17 RF-176–RF-178 para la precisión vigente del alcance de tickets; HU-08 RF-80 para resolución y reapertura; HU-05 y HU-14 RF-76 para las reglas existentes de SLA. «Global» significa el conjunto completo autorizado del administrador, no acceso entre empresas.

- **RF-179:** CUANDO un administrador con sesión válida y empresa asignada solicite las métricas, EL SISTEMA permitirá la consulta. SI no existe sesión válida, ENTONCES EL SISTEMA denegará el acceso con 401 antes de divulgar datos. SI la cuenta no tiene empresa o su rol no es administrador, ENTONCES EL SISTEMA denegará la nueva consulta con el 404 uniforme de recurso no visible, sin métricas ni información de tickets. La identidad, el rol y la empresa se obtendrán de la sesión, nunca de datos elegidos por quien consulta.

- **RF-180:** CUANDO el administrador consulte las métricas, EL SISTEMA considerará todo el historial de tickets autorizado por su empresa, sin filtro temporal, de solicitante, de técnico, de prioridad ni heredado de un listado o dashboard. Un ticket participará solo si su empresa registrada coincide con la empresa del administrador; los tickets ajenos o sin empresa no participarán en ningún conteo, muestra, promedio ni porcentaje, aunque su solicitante o técnico esté relacionado con el actor.

- **RF-181:** CUANDO se calculen las métricas, EL SISTEMA obtendrá el **total de tickets** contando una sola vez cada ticket del conjunto de RF-180, incluidos los tickets sin prioridad, sin SLA o sin técnico asignado. El total será un entero no negativo y no se limitará a los tickets de una página de resultados.

- **RF-182:** CUANDO se calculen los conteos por situación, EL SISTEMA contará como **resueltos** los tickets cuyo estado actual sea «Resuelto» o «Cerrado», y como **pendientes** todos los demás tickets del conjunto autorizado. Ambos conteos serán enteros no negativos, mutuamente excluyentes y su suma será igual al total. «Pendientes» es una agrupación de la métrica, no un nuevo estado del ticket.

- **RF-183:** CUANDO exista al menos un ticket actualmente «Resuelto» o «Cerrado» con fechas de creación y resolución válidas, EL SISTEMA calculará el **tiempo promedio de resolución** como la suma de las duraciones entre creación y resolución dividida entre el número de esos tickets. Las fechas deberán estar presentes, representar instantes interpretables y comparables, y la resolución no podrá ser anterior a la creación; una duración cero será válida. La muestra del promedio no exigirá prioridad, asignación ni SLA. El cálculo usará tiempo transcurrido continuo, sin descontar pausas ni restringirse al horario laboral, y no sustituirá la resolución por el cierre.

- **RF-184:** SI un ticket finalizado no tiene fechas válidas conforme a RF-183, ENTONCES EL SISTEMA lo excluirá únicamente de la muestra del promedio y de cualquier evaluación de SLA que necesite esas fechas, sin quitarlo del total ni del conteo de resueltos. SI la muestra del promedio queda vacía, ENTONCES EL SISTEMA mostrará «Sin datos», no una duración cero. No inferirá ni rellenará fechas de resolución a partir del cierre, del historial o del momento de la consulta.

- **RF-185:** CUANDO se determine la muestra del **cumplimiento de SLA de resolución**, EL SISTEMA incluirá solo tickets actualmente «Resuelto» o «Cerrado» con fechas válidas de RF-183, un objetivo SLA de resolución conservado y válido, y un SLA de resolución evaluable conforme a HU-05/HU-14, con la exclusión específica de RF-191. La evaluación usará exclusivamente el objetivo conservado del ticket, nunca la política vigente como sustituto de un objetivo ausente. Los tickets pendientes, los finalizados sin objetivo conservado, los demás tickets sin SLA evaluable y el SLA de primera respuesta no participarán en la muestra ni en el numerador.

- **RF-186:** CUANDO la muestra de SLA de RF-185 no esté vacía, EL SISTEMA calculará el **porcentaje de cumplimiento de SLA de resolución** como `100 × tickets de la muestra resueltos en plazo / tickets de la muestra`. El vencimiento será la creación más el objetivo de resolución conservado del ticket; un ticket cumplirá si su resolución es anterior o igual a ese vencimiento y no cumplirá si es posterior. El porcentaje estará entre 0 y 100 y se presentará redondeado a dos decimales. SI la muestra está vacía, incluso porque todos los finalizados carecen de objetivo conservado, ENTONCES EL SISTEMA mostrará «Sin datos», sin atribuir cumplimiento o incumplimiento y sin división por cero. Un cero con muestra evaluable significará que ninguno cumplió; no significará ausencia de datos.

- **RF-187:** CUANDO se consulte después de un cierre, un retroceso desde «Resuelto» a «En progreso» o una reapertura, EL SISTEMA calculará las métricas con el estado y los datos de resolución vigentes. Cerrar conservará la misma duración de resolución; retroceder o reabrir hará que el ticket cuente como pendiente y deje de participar en ambas muestras de finalizados. Si vuelve a resolverse, participará una sola vez usando su creación original y la nueva resolución registrada, no como una resolución adicional ni como la suma de ciclos.

- **RF-188:** CUANDO se genere un resultado de métricas, EL SISTEMA derivará todos sus indicadores y muestras del mismo conjunto autorizado de datos de esa consulta, manteniendo `total = resueltos + pendientes`. La consulta será de solo lectura: no alterará tickets, fechas, prioridades, asignaciones, historial ni SLA y no generará notificaciones. Una consulta posterior reflejará los cambios registrados que afecten al resultado, sin exigir actualización en tiempo real.

- **RF-189:** CUANDO se presente un resultado válido, EL SISTEMA mostrará juntos el total, resueltos, pendientes, promedio de resolución y porcentaje de cumplimiento, con etiquetas en español y unidad explícita para la duración y el porcentaje. Explicará que el alcance es todo el historial autorizado, que «Resueltos» incluye «Cerrados», que el promedio termina en la resolución y que el porcentaje solo considera finalizados con SLA evaluable. Mostrará el número de tickets usados en cada muestra y cuántos finalizados se excluyeron de ella, de modo que no se interpreten esas muestras como el total de tickets. La conversión de unidad o el redondeo de presentación no redondeará previamente las duraciones individuales usadas para obtener el promedio.

- **RF-190:** MIENTRAS se obtienen las métricas, EL SISTEMA indicará que están cargando sin presentar cifras provisionales como resultados reales. SI la consulta autorizada no tiene tickets, ENTONCES EL SISTEMA mostrará total, resueltos y pendientes en cero, ambos indicadores de muestras vacías como «Sin datos» y un aviso de ausencia de tickets. SI la consulta falla, ENTONCES EL SISTEMA mostrará un estado de error distinguible del vacío y permitirá reintentar sin sustituir el fallo por ceros ni por «Sin datos». SI la sesión deja de ser válida, ENTONCES EL SISTEMA aplicará el tratamiento de sesión expirada existente sin seguir mostrando métricas protegidas.

- **RF-191:** SI un ticket actualmente «Resuelto» o «Cerrado» tiene fechas válidas pero carece de objetivo SLA de resolución conservado, ENTONCES EL SISTEMA lo excluirá del numerador y del denominador del porcentaje SLA de HU-18, manteniéndolo en el volumen y en la muestra del promedio. CUANDO cambie posteriormente la configuración de SLA sin cambiar los datos registrados del ticket, EL SISTEMA mantendrá esa exclusión y los resultados de HU-18: no reconstruirá el objetivo ausente con la política vigente, no volverá evaluable ese finalizado por ese cambio y tampoco recalculará con la nueva política el cumplimiento de los finalizados con objetivo conservado. Esta regla de elegibilidad es exclusiva de HU-18 y no modifica el cálculo general de SLA ni los dashboards anteriores.

## Requisitos no funcionales

- **Confidencialidad y mínimo privilegio:** la autorización y el aislamiento se comprobarán también al obtener los datos, no solo al mostrar u ocultar controles. La consulta no expondrá detalles de tickets, nombres de personas, correos, credenciales ni datos de otras empresas.
- **Consistencia temporal:** las duraciones y comparaciones de SLA se basarán en instantes, independientemente de la zona horaria de presentación. No habrá duraciones negativas, porcentajes no finitos ni divisiones por cero.
- **Datos reales y trazabilidad de significado:** los indicadores procederán de los registros disponibles, sin valores simulados ni supuestos de cumplimiento para datos ausentes. Las definiciones y tamaños de muestra serán visibles junto con las métricas.
- **Accesibilidad:** los valores, unidades, vacíos y errores tendrán representación textual, no dependerán exclusivamente del color y serán accesibles mediante teclado y tecnologías de asistencia.
- **Compatibilidad:** se conservarán los permisos y el significado de las métricas de HU-11 y HU-12, sus periodos y el cálculo de SLA vigente. HU-18 no reinterpretará sus porcentajes como si fueran el nuevo indicador.

## Casos límite

- **Sin tickets autorizados:** total, resueltos y pendientes en cero; promedio y cumplimiento «Sin datos»; tamaños de muestra cero. No es un error de autorización.
- **Solo pendientes:** total igual a pendientes; resueltos cero y ambas muestras vacías, aunque los pendientes tengan SLA en tiempo o incumplido.
- **Los cuatro estados actuales:** «Resuelto» y «Cerrado» cuentan como resueltos; «Abierto» y «En progreso» como pendientes. Un ticket cerrado no se cuenta dos veces.
- **Tickets antiguos o situados fuera de los periodos de los dashboards:** siguen incluidos; cambiar un periodo o filtro de otra consulta no altera HU-18.
- **Ticket sin prioridad, SLA o técnico:** sigue contando en volumen. Si está finalizado y tiene fechas válidas participa en el promedio, aunque no pueda participar en SLA.
- **Resolución ausente, no interpretable, no comparable o anterior a creación:** el ticket finalizado sigue siendo resuelto en volumen, pero queda fuera de las muestras que requieran esas fechas. No se convierte una duración negativa en cero.
- **Creación y resolución en el mismo instante:** duración cero válida, distinta de «Sin datos»; cumplimiento sujeto al SLA aplicable.
- **Cierre posterior a resolución:** no alarga la duración ni cambia por sí mismo el cumplimiento. No se necesita la fecha de cierre para sustituir un dato de resolución ausente.
- **SLA justo en el vencimiento:** resolución exactamente en plazo cumple; resolución posterior no cumple, aunque la diferencia no se vea tras redondear la presentación.
- **Finalizado sin resolución al que HU-12 atribuye cumplimiento por compatibilidad:** HU-18 lo excluye de su muestra; no hereda ese supuesto ni modifica HU-12.
- **Objetivo conservado al resolver y cambio posterior de configuración:** el porcentaje de HU-18 mantiene el vencimiento derivado del objetivo conservado; cambiar la política sin cambiar los datos del ticket no altera su cumplimiento.
- **Finalizado con fechas válidas pero sin objetivo conservado:** participa en volumen y promedio, pero no en numerador ni denominador del porcentaje SLA de HU-18, aunque exista una política vigente para su prioridad. Un cambio posterior de configuración no lo vuelve evaluable ni rellena el objetivo ausente.
- **Todos los finalizados sin objetivo conservado:** volumen y promedio se calculan con los datos válidos; cumplimiento «Sin datos», muestra SLA cero y exclusiones SLA iguales al número de finalizados.
- **Retroceso o reapertura y nueva resolución:** cambia de resuelto a pendiente y después vuelve a resuelto; nunca se cuenta por eventos ni se reinicia la creación para calcular la duración.
- **Muestras distintas:** un finalizado con fechas válidas pero sin SLA puede aumentar la muestra del promedio sin aumentar la de cumplimiento. La falta de una muestra no impide presentar la otra.
- **Ninguno o todos los evaluables cumplen:** 0 % o 100 %, respectivamente, con muestra positiva; ninguno se confunde con «Sin datos».
- **Ejemplo de referencia:** cinco tickets autorizados: dos pendientes; un resuelto en 60 minutos con objetivo conservado de 60; un cerrado en 120 minutos con objetivo conservado de 60; y un cerrado sin resolución registrada. Resultado: total 5, resueltos 3, pendientes 2, promedio 90 minutos sobre 2 tickets y cumplimiento 50 % sobre 2 tickets; cada muestra excluye 1 finalizado.
- **Comprobación documental de objetivo ausente y configuración posterior:** tres finalizados autorizados con fechas válidas y duraciones de 60, 120 y 180 minutos; los dos primeros conservan un objetivo de 60 minutos y el tercero no conserva objetivo, aunque su prioridad tenga una política vigente de 240 minutos. Resultado esperado: total 3, resueltos 3, pendientes 0; promedio 120 minutos sobre 3 tickets, sin exclusiones; cumplimiento 50 % sobre 2 tickets, con 1 finalizado excluido. Cambiar después la política a 30 minutos, sin cambiar los tickets, debe conservar exactamente esos resultados y muestras. Consultando únicamente el tercer ticket como conjunto autorizado: total 1, resueltos 1, promedio 180 minutos sobre 1 ticket y cumplimiento «Sin datos» sobre 0 tickets, antes y después del cambio.
- **Dos empresas con relaciones de solicitante o asignado cruzadas:** ninguna cifra ni exclusión revela tickets ajenos; la empresa registrada del ticket es la referencia. Los registros sin empresa tampoco participan.
- **Cuenta sin empresa, rol no autorizado o sesión inválida:** denegación sin métricas, no resultado vacío exitoso. El acceso que un supervisor o técnico conserva a otros dashboards no habilita esta consulta.
- **Cambios durante o entre consultas:** cada resultado mantiene sus invariantes; la consulta siguiente incorpora el estado registrado. No se promete actualización en tiempo real ni reconstrucción histórica de resultados anteriores.
- **Fallo de consulta:** no se representa como historial vacío ni como cumplimiento cero; el reintento puede recuperar el resultado real.

## Fuera de alcance

- Filtros temporales o de otro tipo, comparaciones entre periodos, tendencias, gráficos de actividad y desgloses por técnico, solicitante, prioridad o empresa.
- Exportación, informes descargables, envío programado o almacenamiento de resultados históricos de métricas.
- Tiempo hasta cierre, primera respuesta, satisfacción, productividad individual y métricas adicionales a las cinco solicitadas.
- Cómputo por eventos de resolución, acumulación de ciclos de reapertura o reconstrucción de fechas y políticas históricas.
- Nuevos estados, reglas de ciclo de vida, calendarios laborales, pausas o cambios en la configuración y cálculo del SLA.
- Corrección automática de datos incompletos, asociación implícita de empresa y ampliación de permisos entre empresas.
- Conceder estas nuevas métricas a otros roles o retirarles los dashboards que ya tienen autorizados.
- Sustituir o cambiar los indicadores y periodos de HU-11/HU-12; actualización automática o en tiempo real.

## Criterios de finalización

- Verificar RF-179–RF-191 individualmente con resultados esperados para conjuntos conocidos, incluido el ejemplo de referencia, las fórmulas, las muestras independientes y la identidad `total = resueltos + pendientes`.
- Comprobar autenticación, acceso solo del administrador y aislamiento con al menos dos empresas, relaciones cruzadas, cuentas sin empresa y tickets sin empresa; ninguna métrica, tamaño de muestra o exclusión incorporará datos no autorizados.
- Comprobar los cuatro estados, tickets sin prioridad/asignación/SLA, datos de resolución ausentes o inválidos, duración cero, igualdad y superación del vencimiento, y diferencias entre fecha de resolución y cierre.
- Verificar los resultados de la comprobación documental de objetivo ausente: inclusión en volumen/promedio, exclusión de numerador y denominador SLA, muestras y exclusiones diferenciadas, y «Sin datos» cuando ningún finalizado conserve objetivo. Repetir tras cambiar la configuración sin modificar tickets: no deben cambiar las muestras ni los indicadores ni reconstruirse objetivos; tampoco deben cambiar el cálculo general ni los dashboards anteriores.
- Comprobar cierre, retroceso, reapertura, nueva resolución y los efectos vigentes de cambios de configuración o prioridad sobre el SLA, sin reconstruir ciclos ni modificar datos durante la consulta.
- Comprobar presentación comprensible de las cinco métricas, alcance, unidades, muestras y exclusiones; verificar carga, vacío, «Sin datos», fallo, reintento y sesión expirada sin resultados ficticios.
- Comprobar que todo el historial autorizado participa con independencia de páginas, filtros y periodos de otras vistas, y que los dashboards y permisos existentes mantienen su comportamiento.
- La spec deberá superar la revisión y recibir aprobación explícita del usuario antes de elaborar el plan y las tareas; su aprobación no acredita implementación ni pruebas ejecutadas.

## Dudas abiertas

No quedan dudas de negocio abiertas con las aclaraciones recibidas. Decisiones confirmadas:

1. **Alcance global e histórico:** todos los tickets que el administrador puede consultar, sin filtro temporal y sin ampliar su autorización.
2. **Clasificación y duración:** resueltos son los actualmente «Resuelto» o «Cerrado»; pendientes son los demás. El promedio usa creación y resolución válidas, nunca cierre.
3. **SLA de finalizados:** solo resolución de los actualmente resueltos o cerrados con SLA evaluable; sin pendientes ni primera respuesta; sin muestra se muestra «Sin datos».
4. **Objetivo SLA no conservado — aclaración expresa tras QA:** el usuario eligió «Excluir del SLA». El finalizado con fechas válidas pero sin objetivo conservado queda fuera del porcentaje de HU-18 y sigue en volumen/promedio. No se usa la política vigente como sustituto; un cambio posterior de configuración no lo vuelve evaluable ni reconstruye el indicador. Esta decisión no cambia las reglas generales de SLA ni los dashboards anteriores.

Las reglas generales de resolución, reapertura, congelación del SLA y aislamiento citadas son antecedentes vigentes; la exclusión específica de RF-191 es la nueva decisión de elegibilidad para HU-18. Las diferencias con el indicador de HU-12 son intencionadas y no autorizan cambiar aquella historia. Tras corregir el hallazgo, QA consideró la spec aprobable sin bloqueos y el usuario la aprobó explícitamente con «si». Los requisitos permanecen sin cambios; posteriormente el usuario aprobó también el plan y las tareas explícitamente con «si», habilitando su implementación por tarea.
