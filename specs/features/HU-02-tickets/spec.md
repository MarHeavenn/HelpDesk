# Spec HU-02 — Crear y consultar tickets
Estado: borrador para revisión QA

## Contexto y objetivo
Permitir que un usuario autenticado registre solicitudes de soporte como tickets y consulte su información y su estado, de modo que cada solicitud quede trazable desde el momento en que se reporta y su autor pueda conocer en qué situación se encuentra su atención. Esta historia es el núcleo del sistema: los módulos de asignación (HU-04) y SLA (HU-05) se apoyarán en el ticket creado aquí. Se asume como existente la identidad autenticada de HU-01 (`identity`): "usuario autenticado" significa identidad resuelta por la sesión de HU-01; esta historia no rediseña ni modifica la autenticación.

## Usuarios / actores
- Cliente: crea tickets y consulta los suyos (actor principal de la historia).
- Usuario autenticado con otro rol (técnico o administrador): por decisión de revisión, los criterios de aceptación que dicen "un usuario autenticado" se interpretan literalmente, de modo que cualquier usuario con sesión válida crea tickets y consulta los suyos, sin autorización por rol ni capacidades adicionales en esta historia.
- Visitante sin autenticación: no puede crear ni consultar tickets.

## Historias de usuario
- H1: Como usuario autenticado, quiero crear un ticket con un título y una descripción para reportar mi solicitud de soporte.
- H2: Como usuario autenticado, quiero consultar el listado de los tickets que he creado para conocer mis solicitudes.
- H3: Como usuario autenticado, quiero visualizar la información completa y el estado de un ticket mío para conocer cómo va su atención.

## Requisitos funcionales (criterios de aceptación en EARS)
> Numeración: se continúa la secuencia global de requisitos del proyecto, que hasta ahora llega a RF-10 en `specs/features/HU-01-authentication/spec.md`, por lo que esta historia usa RF-11 a RF-20. `specs/project.md` no contiene numeración RF propia. Las decisiones que fijan los valores concretos de estos RF están en "Decisiones tomadas".

- RF-11: CUANDO un usuario autenticado solicite crear un ticket con título y descripción que cumplan las reglas de validación (RF-12), EL SISTEMA creará el ticket con el estado inicial `Abierto`, registrará automáticamente la fecha y hora de creación y responderá 201 con el ticket creado, incluido su identificador único. Cualquier usuario con sesión válida, sea cual sea su rol, dispone de esta capacidad.
- RF-12: EL SISTEMA aplicará estas reglas de validación a la creación de un ticket y responderá 422 sin crear el ticket cuando alguna se incumpla:
  - RF-12.1: título y descripción obligatorios y de tipo cadena de texto. Cualquier valor JSON de otro tipo (número, booleano, objeto, lista o nulo) se rechaza con 422 sin convertirlo ni coaccionarlo a texto, porque no se permite crear un ticket sin título ni sin descripción y porque esta historia adopta la misma política estricta de campos ya aplicada en HU-01.
  - RF-12.2: título de 1 a 200 caracteres y descripción de 1 a 5000 caracteres, rechazando el valor que quede vacío o compuesto solo por espacios. La longitud se cuenta en caracteres (code points), no en bytes.
  - RF-12.3: recorte del inicio y del final con la misma semántica que `strip()` sin argumentos, es decir, eliminando los caracteres que cuentan como espacio en blanco (espacios, tabuladores, saltos de línea y separadores de espacio Unicode) y sin eliminar los que no lo son (por ejemplo, U+200B); el recorte se aplica tanto al validar como antes de almacenar, de modo que el valor recortado es el que se valida y el que se guarda. Esta es la única definición del recorte en la historia y las demás secciones se remiten a ella.
  - RF-12.4: la solicitud admite únicamente los campos de título y descripción; cualquier campo adicional no documentado del cuerpo de la creación (estado, prioridad, técnico asignado, solicitante, identificador, fecha y hora de creación o cualquier otro) se rechaza con 422 sin crear el ticket.
  - RF-12.5: no se aplica ninguna regla de deduplicación; títulos y descripciones repetidos son válidos y dan lugar a tickets distintos.
- RF-13: EL SISTEMA generará para cada ticket un identificador único de tipo UUID (identificador opaco) y lo devolverá tanto en la respuesta de creación como en las consultas de listado y detalle. La unicidad exigible y verificable es la del identificador: cada ticket creado tiene un identificador distinto del de cualquier otro ticket.
- RF-14: EL SISTEMA asociará cada ticket al usuario autenticado que lo creó, a partir de la identidad de la sesión (HU-01) y nunca de un dato enviado por el cliente, y mantendrá esa asociación inmutable durante la vida del ticket.
- RF-15: CUANDO un usuario autenticado solicite el listado de los tickets que ha creado, EL SISTEMA responderá 200 con únicamente los tickets cuyo solicitante es ese usuario, ordenados por fecha y hora de creación de forma descendente (los más recientes primero), sin paginación y sin filtros, y con un resumen por ticket que incluye su identificador, su título, su estado y su fecha y hora de creación, y que no incluye la descripción. Si dos tickets comparten la misma fecha y hora de creación, ese empate no fija ningún orden entre ellos. Los parámetros de consulta desconocidos se ignoran en silencio en todas las operaciones de consulta de esta historia: no filtran, no alteran el resultado y no producen error; la prohibición de campos no documentados de RF-12.4 se refiere al cuerpo de la creación y no a la cadena de consulta. Esta es la única enunciación de esa regla y el resto de la spec se remite a ella.
- RF-16: CUANDO un usuario autenticado solicite la información completa de un ticket que él creó, EL SISTEMA responderá 200 con la información completa del ticket: identificador, título, descripción, estado almacenado (hoy siempre `Abierto`, porque ninguna otra historia lo modifica), fecha y hora de creación e identificador opaco (UUID) del solicitante, obtenido de la sesión autenticada. El detalle no incluye nombre, correo ni ningún otro dato personal del solicitante; esto no debilita el aislamiento, ya que solo se accede a tickets propios, y evita que esta historia necesite datos personales ajenos a la propiedad del ticket.
- RF-17: SI un usuario autenticado solicita un ticket que no existe, que pertenece a otro usuario o cuyo identificador no tiene un formato de identificador válido, ENTONCES EL SISTEMA responderá 404 en todos esos casos, sin revelar la existencia de tickets ajenos y sin devolver ningún dato de un ticket que el solicitante no creó. Los parámetros de consulta desconocidos se tratan igual que en RF-15.
- RF-18: SI una petición de creación o de consulta de tickets llega sin autenticación válida (sin sesión, con sesión inválida, revocada o expirada), ENTONCES EL SISTEMA la rechazará con 401, reutilizando el contrato de identidad ya existente de HU-01, sin introducir mecanismos alternativos de autenticación. La autenticación se evalúa antes que la resolución del recurso: sin sesión válida la respuesta es 401 aunque el identificador solicitado sea inexistente o tenga un formato inválido.
- RF-19: MIENTRAS un ticket exista, EL SISTEMA conservará su estado sin cambios en esta historia: todo ticket se crea con el estado inicial `Abierto` y en HU-02 el estado es informativo y de solo lectura. HU-02 no define el catálogo de estados ni transiciones: la modificación del estado y la prioridad corresponden a HU-03 y las transiciones del ciclo de vida a HU-08.
- RF-20: EL SISTEMA garantizará el aislamiento entre usuarios en todas las operaciones de esta historia: ningún usuario puede crear un ticket a nombre de otro, listar tickets ajenos ni conocer el contenido de un ticket que no creó. La única regla de visibilidad es la propiedad del ticket: HU-02 no implementa visibilidad por organización o empresa; el modelo de empresas/clientes y sus usuarios corresponde a HU-19 y no se adelanta aquí.

## Requisitos no funcionales
- Autorización y aislamiento: toda operación de esta historia exige identidad autenticada, con independencia del rol, y verificará la propiedad del ticket; la pertenencia del ticket al usuario se valida en cada consulta, no solo en el listado.
- Consistencia de entrada y de errores: los rechazos seguirán la estructura de error consistente ya adoptada en HU-01 (`{"detail": <mensaje>}`), sin exponer detalles internos ni datos de otros usuarios. Los códigos de esta historia son 201 y 200 en los caminos válidos y 401, 404 y 422 en los rechazos; no se introduce el 400 "datos inválidos" del ejemplo del documento general.
- Los detalles exactos de los cuerpos de respuesta y la representación de la fecha y hora de creación (formato preciso y zona horaria) se definirán en el contrato de la planificación, sin contradecir los códigos, campos y comportamientos exigidos en estos RF.
- Reglas de negocio fuera de la capa de comunicación y separación de responsabilidades entre capas y módulos, con la prohibición de acceso directo a las tablas internas de otros módulos (`docs/constitution.md` y `AGENTS.md`).
- Sin complejidad innecesaria: no se añadirán reglas de negocio, campos ni dependencias no exigidos por los criterios de aceptación de esta historia.

## Casos límite
- Creación con título ausente, vacío o compuesto solo por espacios (tras el recorte) → RF-12.1 y RF-12.2 (422, sin crear ticket).
- Creación con descripción ausente, vacía o compuesta solo por espacios (tras el recorte) → RF-12.1 y RF-12.2 (422, sin crear ticket).
- Creación con título o descripción de un tipo JSON distinto de la cadena de texto (número, booleano, objeto, lista o nulo) → RF-12.1 (422 sin coerción a texto, sin crear el ticket).
- Creación con un título o una descripción que quedan vacíos al aplicar el recorte de RF-12.3, porque solo contienen caracteres de espacio en blanco → RF-12.2 y RF-12.3 (422, sin crear ticket).
- Creación con U+200B al inicio o al final → RF-12.3 (no cuenta como espacio en blanco: no se elimina y su presencia se resuelve con RF-12.2).
- Creación con título de 1 carácter y descripción de 1 carácter tras el recorte → RF-12.2 (válidos, 201).
- Creación con título de 200 caracteres o descripción de 5000 caracteres tras el recorte → RF-12.2 (válidos, límite incluido, 201).
- Creación con título de 201 caracteres o descripción de 5001 caracteres tras el recorte → RF-12.2 (422, sin crear ticket).
- Creación con título o descripción con caracteres fuera del alfabeto latino (acentos, símbolos o emoji) dentro del límite → RF-12.2 (201: el límite se cuenta en caracteres y no en bytes).
- Creación con espacios, tabuladores o saltos de línea al inicio y al final que dejan el valor dentro de los límites tras el recorte → RF-12.3 (201, y el valor almacenado es el recortado).
- Creación con campos adicionales no documentados en el cuerpo (estado, prioridad, técnico asignado, solicitante, identificador, fecha y hora de creación o cualquier otro) → RF-12.4 (422, sin crear ticket).
- Creación con título y descripción idénticos a los de otro ticket, del mismo usuario o de otro → RF-12.5 (permitido: se crean ambos tickets, con identificadores distintos por RF-13).
- Creación por parte de un usuario con rol técnico o administrador → RF-11 (201, misma capacidad que el cliente; sin autorización por rol en esta historia).
- Creación o consulta sin sesión, con sesión inválida o expirada → RF-18 (401, mismo comportamiento que en HU-01).
- Consulta con sesión inválida y con un identificador inexistente o de formato inválido → RF-18 (401: la autenticación se evalúa antes que la resolución del recurso, nunca 404).
- Listado de un usuario sin tickets creados → RF-15 (200 con colección vacía).
- Listado con varios tickets propios, creados en momentos distintos → RF-15 (200 con solo los del usuario autenticado y ordenados por fecha y hora de creación descendente).
- Listado con dos tickets propios creados en la misma fecha y hora → RF-15 (200 con ambos, sin afirmar orden entre ellos: el empate no fija orden).
- Listado con parámetros de consulta desconocidos (por ejemplo `?status=Abierto&page=2`) → RF-15 (200, ignorados sin error).
- Listado o detalle mientras el usuario tiene sesión válida propia y existen tickets de otros usuarios → RF-15, RF-17 y RF-20 (los ajenos nunca aparecen ni se filtran).
- Detalle de un ticket propio → RF-16 (200 con información completa e identificador del solicitante, sin nombre, correo ni otros datos personales).
- Detalle de un ticket inexistente → RF-17 (404).
- Detalle con un identificador cuyo formato no es válido → RF-17 (404, mismo comportamiento que "no existe").
- Detalle de un ticket existente que pertenece a otro usuario → RF-17 (404, sin revelar su existencia y sin filtrar ningún dato del ticket ajeno).
- Detalle con parámetros de consulta desconocidos → RF-17 (mismo tratamiento que RF-15).
- Creación de dos tickets válidos → RF-13 (identificadores UUID únicos y distintos).
- Concurrencia: dos creaciones simultáneas del mismo usuario → RF-13 (identificadores distintos) y RF-15 (ambas aparecen en el listado; si comparten fecha y hora, el empate no fija orden y las pruebas no deben afirmar orden entre ambas).
- Cualquier operación de esta historia sobre un ticket existente → RF-19 (su estado permanece `Abierto`; HU-02 no lo modifica).

## Fuera de alcance
- Catálogo de estados y transiciones del ciclo de vida, y gestión de la prioridad (HU-03 y HU-08); en HU-02 solo existe el estado inicial `Abierto` y es de solo lectura.
- Asignación de tickets a técnicos y visibilidad de tickets ajenos por rol (HU-04).
- Configuración y control de SLA (HU-05).
- Detalle ampliado del ticket para técnicos y comentarios/seguimiento (HU-06 y HU-07).
- Historial y trazabilidad de cambios (HU-09), alertas (HU-10), dashboard (HU-11), notificaciones (HU-15 y HU-16).
- Paginación, búsqueda y filtrado avanzado del listado de tickets (HU-17).
- Visibilidad por organización o empresa, incluido el modelo de empresas/clientes y sus usuarios (HU-19); HU-02 solo contempla la propiedad del ticket.
- Autorización por rol y gestión administrativa de usuarios (HU-04 y HU-13).
- Edición, cierre o eliminación de tickets.
- Registro, inicio y cierre de sesión y cualquier cambio en la autenticación (HU-01, ya implementada).
- Interfaz de usuario del frontend, mientras no haya un runner de pruebas acordado.

## Criterios de finalización
- RF-11 a RF-20 verificados con pruebas automatizadas con datos de prueba: creación válida (201 con identificador UUID único, estado `Abierto` y fecha y hora generados por el sistema), tipo de título y descripción restringido a cadena de texto sin coerción, validación con los valores frontera de 1-200 y 1-5000 caracteres contados en caracteres tras el recorte, rechazo con 422 de título o descripción ausentes, vacíos, no textuales o solo espacios, de campos adicionales del cuerpo y del solicitante enviado por el cliente, creación permitida para cualquier rol autenticado, listado 200 con únicamente los tickets propios y ordenado por fecha y hora de creación descendente (incluidos el caso de lista vacía y el de parámetros de consulta desconocidos ignorados), detalle 200 completo de un ticket propio, 404 en ticket inexistente, con identificador de formato inválido y ajeno, y 401 en creación y consultas sin autenticación válida.
- Comprobada la composición de las respuestas: el resumen del listado contiene identificador, título, estado y fecha y hora de creación y no contiene la descripción; el detalle contiene identificador, título, descripción, estado, fecha y hora de creación e identificador del solicitante, y no contiene nombre, correo ni otros datos personales; y el detalle devuelve el estado almacenado, que en esta historia es inmutable y hoy siempre `Abierto`.
- Comprobado que la asociación del ticket con el usuario proviene de la identidad autenticada y no de la entrada, y que dos usuarios distintos no ven ni consultan los tickets del otro (aislamiento verificado con dos sesiones simultáneas en la misma prueba).
- Comprobado que la fecha y hora de creación y el estado inicial `Abierto` no pueden ser fijados por el cliente, que ninguna operación de esta historia cambia el estado del ticket y que ningún rechazo usa 400.
- Comprobado que dos tickets con el mismo título y descripción se crean sin error y con identificadores distintos, y que dos tickets con la misma fecha y hora no requieren un orden definido en el listado (las pruebas no afirman orden entre ellos).

## Decisiones tomadas (revisión de 2026-10-17)
- Identificador único: UUID opaco, coherente con los identificadores de usuario ya implementados en HU-01. Se descarta el esquema legible con prefijo y secuencia (`TCK-000001`) que aparece en el ejemplo del documento general.
- Estado inicial: `Abierto`, fijo para todo ticket nuevo. HU-02 no define el catálogo de estados ni las transiciones (HU-03 y HU-08).
- Roles: cualquier usuario autenticado (cliente, técnico o administrador) crea tickets y consulta los suyos; no hay autorización por rol en HU-02.
- Visibilidad: únicamente los tickets creados por el usuario autenticado. HU-02 no implementa visibilidad por organización o empresa: el modelo de empresas/clientes y sus usuarios corresponde a HU-19 y no se adelanta aquí.
- Listado: orden por fecha y hora de creación descendente, sin paginación y sin filtros (corresponden a HU-17). Los empates de fecha y hora no fijan orden y las pruebas no deben afirmar orden en ese caso.
- Consultas: dos operaciones separadas; el listado devuelve el resumen (identificador, título, estado y fecha y hora de creación, sin descripción) y el detalle la información completa del ticket (identificador, título, descripción, estado, fecha y hora de creación e identificador UUID del solicitante, sin datos personales).
- Validaciones: título y descripción obligatorios y de tipo cadena de texto, sin coerción desde otros tipos JSON; título de 1 a 200 caracteres y descripción de 1 a 5000, contados en caracteres (code points) y no en bytes; el recorte es el definido en RF-12.3 (semántica de `strip()`), aplicado al validar y antes de almacenar.
- Campos adicionales: se prohíben todos los campos no documentados del cuerpo de la creación, que admite únicamente título y descripción y responde 422 ante cualquier otro campo. La prohibición no aplica a la cadena de consulta: el tratamiento de los parámetros de consulta desconocidos es el enunciado en RF-15.
- Duplicados: se permiten tickets con el mismo título y descripción, incluso del mismo usuario; no hay regla de deduplicación.
- Errores: 404 tanto si el ticket no existe como si pertenece a otro usuario, y también para un identificador con formato inválido; la autenticación se evalúa antes que la resolución del recurso, de modo que sin sesión válida la respuesta es 401 aunque el identificador sea inexistente o inválido; para datos inválidos se mantiene únicamente 422, sin introducir el 400 "datos inválidos" del ejemplo del documento general.
- Diferido a la planificación técnica: estructura exacta de los cuerpos de respuesta y de error, y representación de la fecha y hora de creación (formato preciso y zona horaria). Se cerrará en el contrato de la API sin contradecir los códigos, campos y comportamientos exigidos en estos RF.

## Dudas abiertas
Sin dudas abiertas pendientes. Las decisiones que fijan los valores y comportamientos concretos de estos RF están registradas en "Decisiones tomadas".
