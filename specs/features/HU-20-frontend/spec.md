# Spec HU-20 — Frontend del MVP HelpDesk
Estado: aprobada

> Aprobada el 2026-10-29 con la condición de que el frontend use el backend que ya existe y no dependa de endpoints ni tareas backend futuras. Las vistas sin endpoint se resuelven con datos mock etiquetados como «Demo». No se modifica el backend.

## Contexto y objetivo

El backend implementa HU-01 a HU-04 (identidad, tickets, prioridad/estado y asignación) y el frontend sigue vacío. El ADR `ADR-HelpDesk-frontend.md` define el prototipo v1.1: diez vistas con un layout común, tres roles, datos de ejemplo y una capa de servicios fácil de reemplazar. Esta historia construye esa interfaz y añade personalización del usuario: configuración de cuenta (perfil, notificaciones y seguridad) y personalización visual (modo claro/oscuro, color de acento y densidad).

El objetivo es disponer de una SPA navegable y verificable que use los contratos HTTP existentes para todo lo que el backend ya soporta (autenticación, creación y consulta de tickets propios, prioridad, estado, asignación y técnicos) y que complete con datos mock, claramente identificados, las vistas que aún no tienen endpoint (dashboard agregado, todos los tickets, configuración de SLA, usuarios/roles, empresas, notificaciones y edición de cuenta). Así el frontend no queda bloqueado esperando el backend completo y, cuando existan los endpoints faltantes, solo se sustituye la implementación del servicio correspondiente.

La interfaz no decide reglas de negocio: consume contratos HTTP para lo real y servicios mock tipados para lo pendiente; ninguna vista accede directamente a PostgreSQL ni a estructuras internas del backend.

## Usuarios / actores

- **Administrador**: inicia sesión con una cuenta real del backend; supervisa la operación, asigna tickets, configura SLA (demo), gestiona usuarios y empresas (demo).
- **Técnico**: inicia sesión con una cuenta real; atiende tickets asignados, consulta todos los tickets (demo), actualiza prioridad y estado.
- **Cliente**: se registra o inicia sesión con una cuenta real; crea tickets y consulta los suyos.
- **Usuario de demostración**: las cuentas demo del backend (`admin@helpdesk.dev`, `tecnico@helpdesk.dev`) y una cuenta cliente registrada desde `/login`. La pantalla de entrada precarga sus correos; la contraseña se toma de la consola del backend o de las variables de entorno de desarrollo.
- **Visitante sin sesión**: solo accede a `/login`; no ve datos ni rutas protegidas.

## Historias de usuario

- H1: Como usuario, quiero un layout consistente con sidebar, topbar y contenido para navegar por todas las secciones sin perder el contexto.
- H2: Como usuario, quiero que la navegación y las acciones disponibles dependan de mi rol para no ver opciones que no puedo usar.
- H3: Como administrador, quiero un dashboard con KPIs, gráficos y tickets recientes para supervisar la operación (demo mientras no exista el endpoint agregado).
- H4: Como administrador o técnico, quiero buscar, filtrar, ordenar y paginar todos los tickets para localizar rápidamente una solicitud (demo mientras no exista el listado global).
- H5: Como usuario, quiero consultar mis tickets reales (asignados o creados según mi rol) para dar seguimiento a mi trabajo.
- H6: Como usuario, quiero crear un ticket real con validación y ver el tiempo objetivo de SLA según la prioridad.
- H7: Como administrador, quiero ver la carga del equipo y asignar o reasignar tickets; la página es demo, pero la asignación real está disponible en el detalle de tickets reales.
- H8: Como administrador, quiero configurar los tiempos de SLA por prioridad (demo) y que el cambio se refleje al crear tickets.
- H9: Como administrador, quiero gestionar usuarios, roles y empresas (demo) con filtros y acciones de activación.
- H10: Como usuario, quiero un centro de notificaciones (demo) con filtros y acciones de lectura que actualice la campana.
- H11: Como usuario, quiero editar mi perfil, mi foto, mis preferencias de notificación y mi seguridad; la identidad viene del backend y la edición es local mientras no exista el endpoint.
- H12: Como usuario, quiero personalizar el tema (claro/oscuro/sistema), el color de acento y la densidad, y que se recuerde mi elección.
- H13: Como usuario, quiero iniciar y cerrar sesión con las cuentas reales del backend y cambiar de cuenta fácilmente.

## Alcance funcional

| Vista | Ruta | Roles | Fuente de datos |
|---|---|---|---|
| Dashboard | `/` | Administrador, Técnico (Cliente redirige) | Mock «Demo» (ADR-001) |
| Todos los tickets | `/tickets` | Administrador, Técnico | Mock «Demo» (ADR-002) |
| Mis tickets | `/mis-tickets` | Todos | API real (propios/asignados) |
| Crear ticket | `/tickets/nuevo` | Todos | API real (alta) + mock (SLA) |
| Técnicos y asignaciones | `/tecnicos` | Administrador | Mock «Demo» + API real para técnicos |
| Configuración de SLA | `/sla` | Administrador | Mock «Demo» (ADR-006) |
| Usuarios y roles | `/usuarios` | Administrador | Mock «Demo» (ADR-007) |
| Empresas y clientes | `/empresas` | Administrador | Mock «Demo» (ADR-008) |
| Notificaciones | `/notificaciones` | Todos | Mock «Demo» (ADR-009) |
| Configuración de cuenta | `/cuenta/perfil`, `/cuenta/notificaciones`, `/cuenta/seguridad`, `/cuenta/apariencia` | Todos | API real (identidad) + local (edición) |
| Estados del sistema | `/estado` | Todos | Placeholder «Próximamente» |
| Entrada | `/login` | Visitante | API real (login/registro) |

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global del proyecto, que llega a RF-40 en `specs/features/HU-04-assignment/spec.md`; esta historia usa RF-41 a RF-68. Los detalles visuales y de contenido de cada vista se toman de `ADR-HelpDesk-frontend.md` y sus criterios de aceptación se incorporan como requisitos. Las vistas marcadas «Demo» usan datos mock y muestran una etiqueta visible; las demás usan los contratos HTTP reales.

- RF-41: EL SISTEMA mostrará en todas las rutas autenticadas un layout compartido con sidebar fijo, topbar y área de contenido, conforme a ADR-000 §3: logo, tarjeta del espacio de trabajo (Acme Solutions / Plan Business), navegación principal, sección «ESPACIO DE TRABAJO», pie «HelpDesk v1.1 · Prototipo», buscador global con atajo ⌘K, campana con indicador de no leídas, avatar/nombre/rol con menú y botón flotante de ayuda. El ítem activo se resaltará y la navegación reflejará el rol de la sesión real (RF-65). En viewports menores a 1024 px el sidebar se convertirá en un drawer accesible y el contenido mantendrá el ancho máximo de cada vista.
- RF-42: EL SISTEMA expondrá las rutas del alcance funcional y aplicará la matriz de permisos de RF-65. SI un visitante sin sesión intenta acceder a una ruta protegida, ENTONCES será redirigido a `/login`. SI un usuario autenticado intenta acceder a una ruta no permitida para su rol, ENTONCES será redirigido a la primera ruta permitida (`/` para administrador y técnico, `/mis-tickets` para cliente) y verá un aviso «No tienes permiso para acceder a esta sección». Las rutas desconocidas mostrarán una pantalla 404 con enlace a la ruta permitida.
- RF-43: EL SISTEMA usará la autenticación real del backend: `POST /api/auth/login`, `GET /api/auth/me` y `POST /api/auth/logout`, con cookie de sesión (`credentials: include`) y sin almacenar contraseñas en el frontend. La pantalla `/login` tendrá email y contraseña, accesos demo que precargan los correos `admin@helpdesk.dev` y `tecnico@helpdesk.dev`, y un formulario de registro de cliente (`POST /api/auth/register` con rol `cliente`) que luego inicia sesión. Al recargar, la sesión se validará con `/api/auth/me`; si es inválida, se redirigirá a `/login`. El rol activo proviene siempre de la sesión real, no de un selector de rol. «Cambiar de cuenta» cerrará la sesión y volverá a `/login`.
- RF-44: EL SISTEMA separará la fuente de datos por vista. Usará la API real para autenticación, `GET /api/tickets`, `POST /api/tickets`, `GET /api/tickets/{id}`, `GET /api/assignments/mine`, `GET /api/technicians`, `PUT /api/tickets/{id}/priority`, `PUT /api/tickets/{id}/status` y `PUT /api/tickets/{id}/assignee`. Usará datos mock para dashboard, todos los tickets, la página de técnicos y asignaciones, SLA, usuarios, empresas, notificaciones y edición de cuenta. Las vistas mock mostrarán una etiqueta «Demo» y no mezclarán sus identificadores con los tickets reales. Los servicios expondrán interfaces tipadas con implementaciones `api` y `mock`, seleccionadas por vista, y ningún componente llamará a `fetch` directamente. La URL del backend se configurará con `VITE_API_URL` (por defecto `http://127.0.0.1:8000`).
- RF-45: EL SISTEMA usará los tokens de ADR-000 §4 y componentes reutilizables: `Button`, `Card`, `Badge` (prioridad, estado, SLA y rol), `Avatar`, `DataTable`, `Select`, `Modal`, `Toast`, `Skeleton`, `EmptyState`, `ErrorState`, `DemoBadge` y `PageHeader`. Los badges de prioridad, estado y SLA usarán los colores, puntos y textos del ADR; los avatares mostrarán iniciales o foto; las tablas tendrán encabezados en mayúsculas, hover y scroll horizontal. «Todos los tickets» y «Mis tickets» compartirán la misma tabla, filtros y paginación sin duplicar código, adaptando la fuente de datos.
- RF-46: CADA vista contemplará los estados transversales de ADR-000 §7: carga (skeletons), vacío (icono + texto + CTA cuando aplique), error (mensaje + botón «Reintentar») y sin permiso (redirección + aviso). En las vistas reales, un 401 redirigirá a `/login`; un 404, 409 o 422 se mostrará como error o toast sin romper la vista. Los estados serán verificables con respuestas mock vacías o fallidas y con un cliente API falso en las pruebas.
- RF-47: EL SISTEMA cumplirá WCAG 2.1 AA en contraste, foco visible, etiquetas accesibles (`aria-label`, `aria-labelledby`), navegación por teclado, modales con foco atrapado y cierre con ESC, toasts anunciados (`role="status"`), acciones de tabla enfocables y errores de formulario asociados (`aria-describedby`). El atajo Cmd/Ctrl+K enfocará el buscador correspondiente a la vista.
- RF-48: EL SISTEMA será usable en 360, 768, 1024 y 1440 px: sidebar en drawer en móvil, KPIs de 4 a 2 a 1 columnas, gráficos apilados, tablas con scroll horizontal, formularios de una columna en móvil y modales a pantalla completa en móvil.
- RF-49: Toda la interfaz estará en español y las cadenas estarán centralizadas en un archivo de textos tipado. Las fechas usarán `Intl.DateTimeFormat('es-CO')` con la zona horaria del usuario: en tablas «Hoy, HH:mm», «Ayer, HH:mm» o «d MMM, HH:mm»; en notificaciones «Hace 8 min», «Hace 1 h», «Ayer».
- RF-50: EL SISTEMA permitirá personalizar la apariencia por usuario: modo Claro/Oscuro/Sistema (por defecto Sistema), color de acento (Índigo por defecto, Azul, Verde y Violeta) y densidad Cómoda/Compacta (por defecto Cómoda). Los cambios se aplicarán de inmediato mediante variables CSS, se persistirán en `localStorage` por identificador de usuario y se restaurarán al recargar sin parpadeo de tema. El modo Sistema seguirá `prefers-color-scheme` en vivo. El botón de tema del topbar alternará Claro/Oscuro y la configuración completa estará en `/cuenta/apariencia`, con acción «Restablecer apariencia». El contraste texto/fondo y texto/acento cumplirá AA en ambos modos.
- RF-51: CUANDO un administrador o técnico abra `/`, EL SISTEMA mostrará el dashboard de ADR-001 con datos mock y etiqueta «Demo»: sobretítulo con la fecha, saludo por hora, subtítulo, 4 KPIs, gráfico de barras con selector 7/30/90 días, donut de SLA con leyenda, 3 métricas secundarias y tabla de 5 tickets recientes. Para el técnico, los datos mock se limitarán a los tickets asignados a su identificador real dentro del seed; para el administrador, al conjunto completo. El botón «+ Crear ticket» navegará a `/tickets/nuevo` y «Ver todos» a `/tickets`. SI el rol es cliente, ENTONCES será redirigido a `/mis-tickets`.
- RF-52: CUANDO un administrador o técnico abra `/tickets`, EL SISTEMA mostrará la vista de ADR-002 con datos mock y etiqueta «Demo»: buscador por ID o título con debounce de 300 ms, filtros de prioridad, estado y técnico, orden (más recientes, más antiguos, prioridad, SLA más próximo), contador de resultados, tabla paginada (10 por página) y pie «Mostrando X–Y de Z». Los filtros se reflejarán en la query string y serán compartibles; sin resultados se mostrará «No encontramos tickets con esos filtros» y «Limpiar filtros». El técnico verá todos los tickets mock; el cliente no accede (RF-42).
- RF-53: CUANDO el usuario elija «Ver detalle» en un ticket, EL SISTEMA mostrará un modal con la información disponible y las acciones permitidas. Para tickets reales, usará `GET /api/tickets/{id}` si el ticket es propio; para tickets asignados ajenos, mostrará el resumen disponible y una nota de que la descripción no está expuesta por el backend. Para tickets mock, mostrará el detalle completo del seed. Las acciones permitidas serán: asignar técnico (solo administrador, API real para tickets reales y mock para tickets demo), cambiar estado y cambiar prioridad (administrador y técnico, API real o mock según el origen), con confirmación o toast y actualización de la tabla. La ruta `/tickets/:id` queda fuera de alcance. El menú ⋯ de cada fila ofrecerá las acciones permitidas y se cerrará con ESC o clic fuera.
- RF-54: CUANDO un usuario abra `/mis-tickets`, EL SISTEMA mostrará sus tickets reales con la tabla y los filtros de RF-52, sin etiqueta «Demo»: para técnico, `GET /api/assignments/mine` (asignados a él); para administrador, `GET /api/tickets` (creados por él, porque el backend no tiene tickets asignados a administradores); para cliente, `GET /api/tickets` (creados por él). Para el cliente se ocultará el filtro de técnico y las acciones de asignación. El título y subtítulo serán los de ADR-003 y el ítem «Mis tickets» estará activo en el sidebar.
- RF-55: CUANDO un usuario abra `/tickets/nuevo`, EL SISTEMA mostrará el formulario de ADR-004: título (5–120 caracteres), descripción (mínimo 20), prioridad (Media por defecto) y texto del tiempo objetivo de SLA leído de la configuración mock global, que cambiará al cambiar la prioridad. Al enviar: validación inline, foco en el primer error, botón «Creando...», alta real con `POST /api/tickets` (estado Abierto, sin técnico, solicitante de la sesión), intento de fijar la prioridad con `PUT /api/tickets/{id}/priority` si el rol es administrador o técnico, y toast «Ticket TCK-XXXXXX creado» con redirección a `/mis-tickets`. Para el cliente, la prioridad elegida se conserva como metadato local porque el backend no le permite fijarla; la UI la muestra y el ticket real queda sin prioridad hasta que un administrador o técnico la establezca. Cancelar con cambios pedirá confirmación. El ticket nuevo aparecerá en «Mis tickets».
- RF-56: CUANDO un administrador abra `/tecnicos`, EL SISTEMA mostrará ADR-005 con datos mock y etiqueta «Demo»: pendientes de asignación derivados del seed, píldora de prioridad alta, disponibilidad del equipo con la carga de cada técnico, tabla de asignación con búsqueda y filtros, columna ACCIÓN con select de técnicos más «Sin asignar» y menú ⋯. La lista de técnicos podrá tomarse de `GET /api/technicians` cuando esté disponible, pero la asignación de la tabla demo se resolverá en el mock. Cambiar el select asignará de forma optimista en el mock, mostrará el toast «Ticket asignado a {nombre}» y actualizará tabla, cargas, pendientes y badge del sidebar; si falla, revertirá y mostrará error. «Registrar técnico» abrirá un modal con nombre, correo y especialidad, validará y dará de alta al técnico en el directorio mock; el nuevo técnico aparecerá en los selects y en la disponibilidad. La asignación real de tickets reales se realizará desde el detalle del ticket con `PUT /api/tickets/{id}/assignee` (RF-53). Solo administrador.
- RF-57: CUANDO un administrador abra `/sla`, EL SISTEMA mostrará ADR-006 con datos mock y etiqueta «Demo»: banner informativo y cuatro filas (Crítica 2 h, Alta 4 h, Media 12 h, Baja 24 h por defecto) con input numérico y unidad (Minutos/Horas/Días). «Guardar cambios» estará deshabilitado sin cambios; validará enteros mayores que 0 y advertirá sin bloquear si la secuencia Crítica ≤ Alta ≤ Media ≤ Baja no se cumple. Guardar actualizará la configuración mock global, mostrará «SLA actualizado» y el texto de `/tickets/nuevo` para tickets nuevos; Cancelar restaurará los valores guardados. Solo administrador.
- RF-58: CUANDO un administrador abra `/usuarios`, EL SISTEMA mostrará ADR-007 con datos mock y etiqueta «Demo»: directorio con filtros de rol y estado, subtítulo dinámico y tabla con avatar, nombre, correo, rol, empresa, estado y acciones. «Nuevo usuario» y «Editar» abrirán un modal con nombre, correo, rol y empresa; validará campos obligatorios, formato de correo y correo único; al guardar actualizará la tabla y, si es el usuario de la sesión, el topbar. Desactivar/Activar pedirá confirmación, cambiará la píldora y no permitirá desactivar al último administrador ni cambiar su propio rol. Solo administrador.
- RF-59: CUANDO un administrador abra `/empresas`, EL SISTEMA mostrará ADR-008 con datos mock y etiqueta «Demo»: grid de 3 a 2 a 1 columnas con tarjetas de empresa (avatar, nombre, plan, estado, usuarios y tickets derivados). «Nueva empresa» y «Editar» abrirán un modal con nombre, plan y estado; desactivar pedirá confirmación e informará del impacto; el estado vacío mostrará «Aún no hay empresas» y el CTA «Nueva empresa». Solo administrador.
- RF-60: CUANDO un usuario abra `/notificaciones`, EL SISTEMA mostrará ADR-009 con datos mock y etiqueta «Demo»: pestañas Todas/No leídas/SLA, orden más recientes/antiguas, ítems con icono, título, etiqueta, detalle, tiempo relativo y acción «Marcar como leída»; las no leídas tendrán fondo y la campana mostrará el punto rojo con el conteo. «Marcar todas como leídas» actualizará la lista y la campana. La pestaña SLA filtrará `sla_riesgo` y `sla_incumplido`; cada pestaña tendrá su estado vacío. Clic en el ID del ticket navegará a la lista filtrada por ese ID (`/tickets?q=...` o `/mis-tickets?q=...`). Las notificaciones se filtrarán por el identificador y rol de la sesión real dentro del seed mock.
- RF-61: CUANDO un usuario abra `/cuenta/perfil`, EL SISTEMA mostrará ADR-010 con la identidad real de la sesión (`GET /api/auth/me` más el nombre devuelto por el login): sub-navegación Perfil/Notificaciones/Seguridad/Apariencia y tarjeta de perfil con avatar, nombre, rol, botón «Cambiar foto», campos nombre y correo, «Cerrar sesión» y «Guardar perfil». Guardar estará deshabilitado sin cambios; validará nombre no vacío y correo; al guardar mostrará «Perfil actualizado» y actualizará topbar y sidebar. La edición de nombre/correo y la foto serán locales (el backend no expone actualización de perfil en esta iteración) y se persistirán por identificador de usuario; se indicará que el cambio no se guarda en el backend. «Cambiar foto» permitirá elegir una imagen local (PNG/JPG, máximo 2 MB), previsualizarla, guardarla como data URL y quitarla; no habrá subida al servidor. No habrá selector de rol demo porque el rol proviene de la sesión real; en su lugar se mostrará «Cambiar de cuenta» (cerrar sesión y volver a `/login`).
- RF-62: CUANDO un usuario abra `/cuenta/notificaciones`, EL SISTEMA mostrará switches para SLA próximo a vencer, SLA incumplido, nueva asignación y ticket resuelto. Los cambios se guardarán al instante por identificador de usuario y mostrarán un toast; no enviarán correos reales en el prototipo.
- RF-63: CUANDO un usuario abra `/cuenta/seguridad`, EL SISTEMA mostrará el cambio de contraseña (actual, nueva y confirmar) con validación (mínimo 8 caracteres, coincidencia y distinta de la actual) y un listado de sesiones activas (sesión actual y otra) con opción de cerrar la otra. El cambio de contraseña será simulado y no almacenará contraseñas en texto plano; el cierre de otra sesión pedirá confirmación y mostrará un toast. No se modificará la contraseña real del backend en esta iteración.
- RF-64: CUANDO el usuario elija «Cerrar sesión» desde el menú del topbar o desde el perfil, EL SISTEMA llamará a `POST /api/auth/logout`, limpiará la sesión local, redirigirá a `/login` y mostrará el formulario de acceso. SI no hay sesión válida, cualquier ruta protegida redirigirá a `/login`.
- RF-65: EL SISTEMA aplicará exactamente la matriz de ADR-000 §5 usando el rol de la sesión real: Dashboard para administrador y técnico (cliente redirige a `/mis-tickets`); Todos los tickets para administrador y técnico; Mis tickets, Crear ticket, Notificaciones y Cuenta para todos; Técnicos, SLA, Usuarios y Empresas solo para administrador. Las acciones de asignar (administrador), cambiar estado o prioridad (administrador y técnico) y crear, editar, desactivar o configurar (administrador) se ocultarán o deshabilitarán para roles sin permiso, y las rutas no permitidas redirigirán con aviso. La matriz es la fuente de permisos en esta iteración; no se consulta al backend para autorizar la navegación.
- RF-66: EL SISTEMA mantendrá dos conjuntos de datos separados y coherentes: los tickets reales del backend y el seed mock de las vistas «Demo». Dentro de cada conjunto, cada ticket referenciará un solicitante, una empresa y un técnico existentes; los conteos de empresa, usuarios, tickets, KPIs, cargas, pendientes, badges y donut se derivarán de los datos correspondientes; no habrá números hardcodeados contradictorios. Las mutaciones reales (crear, prioridad, estado, asignación) actualizarán las vistas reales; las mutaciones mock actualizarán las vistas demo. No se mezclarán identificadores reales y mock en una misma tabla. El seed mock se generará en memoria y se reiniciará al recargar; las preferencias (tema, perfil local, avatar y preferencias de notificación) persistirán por usuario.
- RF-67: EL SISTEMA se verificará con Vitest + Testing Library (jsdom) mediante `npm run test` y compilará con `npm run build` (TypeScript estricto + Vite). Las pruebas cubrirán autenticación y guards, shell y navegación por rol, tema (modo, acento, densidad y persistencia), dashboard demo, filtros/búsqueda/paginación demo, mis tickets reales por rol, crear ticket real (validación, SLA, alta y prioridad), detalle y acciones reales/demo, asignación demo y real, SLA, usuarios, empresas, notificaciones, perfil/avatar, preferencias, seguridad y logout. El cliente HTTP se sustituirá por un fake en las pruebas para no depender del backend. No se afirmará una prueba que no se haya ejecutado.
- RF-68: EL SISTEMA no modificará el backend ni accederá a PostgreSQL. Usará los endpoints existentes de HU-01 a HU-04 para las vistas reales y datos mock para las vistas sin endpoint, sin bloquear el desarrollo del frontend por tareas backend futuras. Los servicios expondrán interfaces tipadas y serán sustituibles por implementaciones HTTP cuando existan los endpoints faltantes. No se almacenarán contraseñas en texto plano ni secretos en el repositorio. Las credenciales de desarrollo se introducen en `/login` o se configuran fuera del repositorio.

## Requisitos no funcionales

- **Accesibilidad**: WCAG 2.1 AA, foco visible, contraste, teclado y lectores de pantalla (RF-47).
- **Responsive**: 360–1440 px sin pérdida de funcionalidad (RF-48).
- **Rendimiento percibido**: skeletons en cargas, mutaciones optimistas donde el ADR lo pide y sin recargas completas de página; sin dependencias innecesarias.
- **Mantenibilidad**: TypeScript estricto, componentes y servicios separados por responsabilidad, textos centralizados y sin lógica de negocio en las vistas.
- **Seguridad**: sin contraseñas en texto plano, sin secretos en el repositorio, cookie de sesión del backend y sin acceso directo a la base de datos.
- **Compatibilidad**: últimas versiones de Chrome, Edge, Firefox y Safari; fuente Inter con fallback `system-ui`.
- **Pruebas**: Vitest + Testing Library y build de producción en verde (RF-67).
- **Datos**: API real para lo existente y seed mock coherente para lo pendiente; preferencias persistentes por usuario; etiqueta «Demo» visible en las vistas mock.
- **Configuración**: `VITE_API_URL` para la URL del backend; sin credenciales en el repositorio.

## Casos límite

- Sin sesión o cookie inválida: `/login`; cualquier ruta protegida redirige a `/login`; `/login` no muestra datos.
- Login con credenciales incorrectas: error inline; el formulario conserva el correo y limpia la contraseña.
- Registro de cliente con correo existente o datos inválidos: error inline; no se crea la cuenta.
- Backend caído o inaccesible en una vista real: estado de error con «Reintentar»; las vistas demo siguen funcionando.
- 401 durante una operación real: se limpia la sesión y se redirige a `/login` con aviso.
- 404/409/422 en una operación real (ticket cerrado, prioridad inválida, técnico inválido): toast o error inline sin perder la vista.
- Cambio de rol en una ruta no permitida: redirección a la primera ruta permitida y aviso.
- Cliente que intenta abrir `/`, `/tickets`, `/tecnicos`, `/sla`, `/usuarios` o `/empresas`: redirección con aviso.
- Técnico que intenta abrir `/tecnicos`, `/sla`, `/usuarios` o `/empresas`: redirección con aviso.
- Listados sin resultados, sin tickets, sin técnicos, sin usuarios, sin empresas o sin notificaciones: estado vacío con CTA cuando aplique.
- Búsqueda con debounce, filtros combinados sin resultados, query string inválida o página fuera de rango: se normaliza y se muestra el estado vacío o la primera página.
- Ticket sin técnico: avatar gris «?» y texto «Sin asignar»; ticket cerrado: acciones de asignación/estado/prioridad deshabilitadas o con error.
- Asignación optimista fallida en la vista demo: se revierte el cambio y se muestra un toast de error.
- Ticket real recién creado por un cliente: aparece como Abierto y Sin asignar; la prioridad elegida se muestra desde el metadato local y el backend queda sin prioridad.
- Ticket real asignado a un técnico: el detalle muestra el resumen disponible y una nota de que la descripción no está expuesta; las acciones de prioridad/estado funcionan.
- Formulario de ticket con título corto, descripción corta, prioridad inválida o campos vacíos: errores inline y foco en el primer error.
- Cancelar creación con cambios: confirmación de descarte; sin cambios, vuelve atrás sin preguntar.
- SLA con valor cero, negativo, decimal o no numérico: error de validación; secuencia no creciente: advertencia sin bloquear.
- Usuario demo con correo duplicado, correo inválido, campos vacíos o intento de desactivar al último administrador: error y sin cambio.
- Empresa demo desactivada: confirmación e impacto informado; sus usuarios y tickets siguen visibles en el prototipo.
- Notificaciones demo: pestaña vacía, marcar todas sin no leídas, marcar una ya leída o clic en un ticket inexistente: sin error fatal y con estado coherente.
- Perfil: nombre vacío, correo inválido, avatar no imagen, mayor de 2 MB o error de lectura: error y sin cambio.
- Seguridad: contraseña actual incorrecta, nueva corta, confirmación distinta o igual a la actual: error; cambio simulado correcto: toast.
- Tema: modo Sistema sin `prefers-color-scheme`, cambio de preferencia del sistema en vivo, `localStorage` corrupto o vacío: se usan los valores por defecto sin romper la app.
- Densidad compacta: tablas y formularios siguen siendo legibles y accesibles.
- Atajo ⌘K/Ctrl+K dentro de un input: no debe interferir con la escritura; en `/tickets` y `/mis-tickets` enfoca el buscador local; en el resto, el global.
- Modal: ESC, clic fuera, foco atrapado y retorno del foco al elemento que lo abrió.
- Sidebar en móvil: se abre/cierra con teclado y clic fuera, y no bloquea el contenido.
- Datos mock reiniciados al recargar: la sesión, el tema, el perfil local y las preferencias se conservan; los cambios de dominio mock no.
- `localStorage` no disponible o lleno: la app funciona con valores por defecto y avisa solo si es necesario.

## Fuera de alcance

- Cambios en el backend, nuevos endpoints o conexión a PostgreSQL (RF-68).
- Endpoints faltantes: listado global de tickets, dashboard agregado, SLA, usuarios/roles, empresas, notificaciones y actualización de perfil/contraseña. Se mockean con etiqueta «Demo».
- Selector de rol para demostración del ADR-010: la sesión es real y el rol no se puede cambiar sin cambiar de cuenta (RF-43 y RF-61).
- Ruta de detalle `/tickets/:id`; el detalle se muestra en un modal (RF-53).
- Detalle completo de tickets ajenos asignados para técnicos (HU-06): el backend no lo expone; se muestra el resumen disponible.
- Comentarios, adjuntos, historial de cambios, reapertura, cierre y ciclo de vida avanzado (HU-06 a HU-09).
- Motor real de SLA, cálculo automático de vencimientos, alertas por correo y notificaciones push (HU-05, HU-10, HU-15 y HU-16).
- Persistencia de datos de dominio mock entre recargas o en base de datos.
- Subida de avatar a un servidor; la foto se guarda localmente como data URL (RF-61).
- Cambio real de contraseña o gestión real de sesiones; son simulados (RF-63).
- Multiempresa real con aislamiento de datos; el prototipo muestra varias empresas en un mismo espacio.
- Internacionalización a otros idiomas; solo español.
- Pruebas E2E con navegador (Playwright/Cypress); la verificación es con Vitest + Testing Library y smoke manual.
- Despliegue, CI/CD y configuración de producción.

## Criterios de finalización

- RF-41 a RF-68 verificados con pruebas automatizadas de Vitest + Testing Library y, cuando aplique, con comprobaciones de los servicios mock y del cliente HTTP fake.
- `npm run test` en verde y `npm run build` en verde (TypeScript estricto + Vite), sin errores de consola en el smoke manual.
- Las vistas reales funcionan contra el backend de desarrollo: login, logout, sesión persistida, mis tickets, crear ticket, prioridad/estado, asignación y técnicos.
- Las diez vistas del ADR y `/estado` son navegables con las cuentas reales; la matriz de permisos se cumple y las rutas no permitidas redirigen con aviso.
- Las vistas mock muestran la etiqueta «Demo» y su seed es coherente: los contadores de dashboard, sidebar, empresas, técnicos y notificaciones se derivan de los mismos datos y no hay números contradictorios.
- La personalización funciona: modo claro/oscuro/sistema, acento y densidad se aplican al instante, se recuerdan por usuario tras recargar y cumplen contraste AA; el perfil local, avatar y preferencias de notificación persisten; el cambio de contraseña y las sesiones son simulados sin almacenar contraseñas.
- Los estados de carga, vacío, error y sin permiso están implementados y son visibles en al menos una vista cada uno.
- La UI está en español, las fechas se formatean con `es-CO` y las cadenas están centralizadas.
- El README y `MEMORY.md` se actualizan con las instrucciones de ejecución del frontend, las credenciales demo y el estado de la historia.

## Decisiones de alcance adoptadas

- **D1 — Autenticación real, sin selector de rol demo.** El rol proviene de la sesión del backend; `/login` ofrece email/contraseña, accesos demo que precargan correos y registro de cliente. «Cambiar de cuenta» cierra sesión y vuelve a `/login`. *Alternativa descartada: mantener el selector de rol del ADR-010*, que no puede cambiar el rol de una sesión real sin volver a autenticarse.
- **D2 — Híbrido por vista.** API real para autenticación, mis tickets, crear ticket, detalle propio, prioridad/estado, asignación y técnicos; mock para dashboard, todos los tickets, página de técnicos/asignaciones, SLA, usuarios, empresas, notificaciones y edición de cuenta. Las vistas mock muestran «Demo». *Alternativa descartada: mock total*, que no aprovecha el backend existente; *alternativa descartada: registro local de tickets reales*, más complejo y con datos sembrados por el navegador.
- **D3 — «Mis tickets» del administrador muestra los tickets creados por él.** El backend no tiene tickets asignados a administradores; `GET /api/tickets` devuelve los creados por la sesión. El técnico usa `GET /api/assignments/mine` y el cliente `GET /api/tickets`. *Alternativa descartada: dejar la vista vacía para el administrador*, que no aporta valor en la demo.
- **D4 — La prioridad del cliente se guarda como metadato local.** El backend no permite a un cliente fijar prioridad; el formulario la conserva en el frontend y la muestra, mientras el ticket real queda sin prioridad hasta que un administrador o técnico la establezca. *Alternativa descartada: ocultar la prioridad al cliente*, que contradice el ADR-004; *alternativa descartada: llamar al endpoint de prioridad como cliente*, que devuelve 404.
- **D5 — El detalle de tickets reales muestra lo que el backend expone.** Para tickets propios se usa `GET /api/tickets/{id}`; para asignados ajenos se muestra el resumen y una nota de que la descripción no está disponible (HU-06 fuera de alcance). *Alternativa descartada: inventar la descripción*, que falsearía datos reales.
- **D6 — Identificadores amigables.** Los tickets reales muestran `TCK-` más los primeros caracteres del UUID; los tickets mock usan identificadores secuenciales del seed. La UI nunca mezcla ambos orígenes en una misma tabla. *Alternativa descartada: mostrar el UUID completo*, menos legible y alejado del ADR.
- **D7 — Etiqueta «Demo» visible.** Toda vista mock muestra una etiqueta junto al título y, cuando aplica, una nota de que el backend aún no expone esa funcionalidad. *Alternativa descartada: ocultar el origen de los datos*, que confundiría datos reales con demo.
- **D8 — Datos mock en memoria y preferencias en `localStorage`.** El seed se reinicia al recargar; la sesión, el tema, el perfil local, el avatar y las preferencias de notificación persisten por usuario. *Alternativa descartada: persistir todo el store mock*, que añade versionado y datos obsoletos sin mejorar la demostración.
- **D9 — Personalización visual con modo, acento y densidad.** Se añade `/cuenta/apariencia` y un botón de tema en el topbar; el modo Sistema sigue `prefers-color-scheme`. *Alternativa descartada: limitarse a claro/oscuro*, que no cubre la personalización solicitada.
- **D10 — La foto de perfil es local.** Se acepta PNG/JPG de hasta 2 MB, se guarda como data URL por usuario y se puede quitar; no se sube a ningún servidor. *Alternativa descartada: solo iniciales*, que reduce la personalización; *alternativa descartada: subida real*, fuera de alcance sin backend.
- **D11 — El cambio de contraseña y las sesiones son simulados.** No se almacenan contraseñas en texto plano ni se modifica la contraseña real del backend. *Alternativa descartada: guardar una contraseña mock*, contraria a la constitución.
- **D12 — La verificación es con Vitest + Testing Library y smoke manual.** El cliente HTTP se sustituye por un fake en las pruebas; no se añaden pruebas E2E ni un runner adicional. *Alternativa descartada: solo pruebas manuales*, que no permitirían verificar los RF de forma reproducible.

## Revisión 2026-11-10 — datos reales y alta de ticket

- **Las vistas con backend disponible usan datos reales y no llevan etiqueta «Demo».** Aplica al dashboard de tickets (RF-81 a RF-92 de HU-11, ya con `GET /api/dashboard/tickets`), al panel de SLA (HU-12) y al alta de ticket (T14). Las decisiones D2, D7 y D8 siguen vigentes solo para las vistas que aún no tienen endpoint.
- **La validación del alta sigue el contrato de HU-02**, no los límites del ADR-004: título de 1 a 200 caracteres y descripción de 1 a 5000, contados en code points tras recortar (RF-12.2 y RF-12.3). *Motivo: el backend rechaza con 422 fuera de ese rango y el formulario debe anticipar el mismo criterio.*
- **D4 se ajusta:** el cliente no elige prioridad en el formulario (el backend no se la acepta y no se guarda ningún metadato local que simule haberla fijado); ve una nota de que un administrador o técnico la definirá. Administrador y técnico sí eligen prioridad y esta se persiste con `PUT /api/tickets/{id}/priority`.
- **El tiempo objetivo de SLA del formulario solo lo ve el administrador**, porque `GET /api/sla/policies` está restringido a ese rol (HU-14). El técnico conserva el selector de prioridad sin leer la política.

## Dudas abiertas

Sin dudas abiertas pendientes. Las decisiones D1 a D12 cierran las ambigüedades del ADR y del alcance acordado con el usuario. Las brechas del backend (listado global, dashboard agregado, SLA, usuarios, empresas, notificaciones, perfil/seguridad y detalle de tickets ajenos) quedan documentadas y se cubren con mock etiquetado como «Demo».
