# Spec HU-21 — Estructura visual y navegación del sistema

Estado: borrador

## Contexto y objetivo

El backend ya expone autenticación (HU-01) y la gestión de tickets (HU-02 a HU-04), pero el frontend no tiene código: `frontend/src` solo contiene un marcador. Sin una estructura común, cada vista tendría que resolver por su cuenta el armazón, la navegación, la sesión y el control de acceso, con riesgo de pantallas inconsistentes y de duplicar reglas de permisos.

Esta historia construye la base reutilizable del frontend: la pantalla de acceso, el armazón compartido (barra lateral, encabezado y área de contenido), la navegación filtrada por el rol real de la sesión y las rutas protegidas. No implementa el contenido funcional de tickets, dashboards ni administración; esas historias se apoyan en esta estructura.

HU-13 (gestión de usuarios y roles) todavía no está implementada. Por eso las rutas de administración que dependen de ella existen como marcadores «Próximamente» y la navegación se deriva del rol real de la sesión, no de un selector de rol.

## Usuarios / actores

- Visitante sin sesión: solo puede acceder a la pantalla de acceso; cualquier otra ruta lo devuelve allí.
- Cliente (rol `cliente`): accede a sus tickets, a crear ticket, a notificaciones y a su cuenta.
- Técnico (rol `tecnico`): accede al dashboard, a todos los tickets, a sus tickets, a crear ticket, a notificaciones y a su cuenta.
- Administrador (rol `administrador`): accede además a técnicos, SLA, usuarios y empresas.

## Historias de usuario

- H1: Como usuario del sistema, quiero una interfaz organizada y una navegación clara para acceder fácilmente a las funcionalidades de DeskHelp.
- H2: Como usuario, quiero que la plataforma me muestre solo las secciones que mi rol permite, para no perder tiempo en opciones que no puedo usar.
- H3: Como usuario, quiero que la estructura se mantenga consistente entre pantallas, para reconocer siempre dónde estoy y cómo volver.
- H4: Como usuario, quiero poder usar la navegación en computadora y en móvil, para trabajar desde cualquier tamaño de pantalla.
- H5: Como usuario, quiero cerrar sesión de forma segura desde el encabezado, para terminar mi trabajo sin dejar la sesión abierta.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: se continúa la secuencia global del proyecto, que llega a RF-68 en `specs/frontend-mvp/spec.md` (especificación de referencia del frontend); esta historia usa RF-69 a RF-80. Fuente: tarjeta Trello «HU-21 — Diseñar la estructura visual y navegación del sistema» y ADR-000 (`ADR-HelpDesk-frontend.md`, secciones 2, 3 y 5). Esta historia sustituye, para el armazón y la navegación, lo previsto en la referencia (RF-41, RF-42, RF-64 y RF-65); no cambia el resto de la referencia.

- RF-69: EL SISTEMA expondrá las rutas `/login`, `/`, `/tickets`, `/mis-tickets`, `/tickets/nuevo`, `/tecnicos`, `/sla`, `/usuarios`, `/empresas`, `/notificaciones`, `/cuenta/perfil` y una ruta comodín para direcciones desconocidas. SI un visitante sin sesión válida solicita una ruta distinta de `/login`, ENTONCES será redirigido a `/login` sin mostrar el contenido protegido. SI un usuario con sesión válida solicita `/login`, ENTONCES será redirigido a la primera ruta permitida para su rol.
- RF-70: CUANDO un usuario autenticado acceda a cualquier ruta protegida, EL SISTEMA mostrará un armazón compartido con barra lateral, encabezado y área de contenido. La barra lateral contendrá el logotipo y nombre «HelpDesk», la tarjeta del espacio de trabajo, la navegación principal, una sección inferior y el pie «HelpDesk v1.1 · Prototipo». El encabezado contendrá el buscador global con atajo ⌘K/Ctrl+K, la campana de notificaciones, el avatar, el nombre y el rol del usuario con su menú, y el botón de ayuda. El área de contenido alojará la vista activa sin duplicar el armazón.
- RF-71: EL SISTEMA filtrará la navegación según el rol real de la sesión: el administrador verá Dashboard, Todos los tickets, Mis tickets, Crear ticket, Técnicos, SLA, Usuarios, Empresas, Notificaciones y Cuenta; el técnico verá Dashboard, Todos los tickets, Mis tickets, Crear ticket, Notificaciones y Cuenta; el cliente verá Mis tickets, Crear ticket, Notificaciones y Cuenta. Los ítems no permitidos no se renderizarán, no se deshabilitarán y no se anunciarán a lectores de pantalla. La matriz de permisos será la única fuente de verdad para la navegación y las acciones.
- RF-72: CUANDO el usuario navegue entre secciones, EL SISTEMA resaltará el ítem activo con `aria-current="page"`, mostrará en el área de contenido el título y el subtítulo de la sección, y conservará la misma estructura, espaciado y tipografía. El ítem activo no se marcará solo por color: incluirá además un indicador visual y el atributo accesible.
- RF-73: SI un usuario autenticado intenta acceder a una ruta no permitida para su rol, ENTONCES EL SISTEMA lo redirigirá a la primera ruta permitida (`/` para administrador y técnico, `/mis-tickets` para cliente) y mostrará una vez el aviso «No tienes permiso para acceder a esta sección». SI la ruta no existe, ENTONCES mostrará una pantalla 404 con un enlace a la primera ruta permitida, sin revelar datos de la aplicación.
- RF-74: MIENTRAS el ancho de la ventana sea menor a 1024 px, EL SISTEMA convertirá la barra lateral en un panel deslizante accesible: un botón la abrirá, una capa oscura y la tecla Escape la cerrarán, el foco quedará atrapado mientras esté abierta y volverá al botón que la abrió. El contenido ocupará el ancho disponible y el encabezado conservará el acceso al menú, la campana y el usuario. En anchos mayores la barra lateral permanecerá visible y fija.
- RF-75: EL SISTEMA cumplirá WCAG 2.1 AA en el armazón: navegación completa por teclado, foco visible, enlace «Saltar al contenido», regiones semánticas (`nav`, `header`, `main`), etiquetas accesibles en botones e iconos, `aria-expanded` en el menú móvil y contraste mínimo de texto y controles en los temas claro y oscuro.
- RF-76: CUANDO el usuario autenticado abra el menú del encabezado, EL SISTEMA mostrará su nombre, correo y rol reales, y las acciones «Mi perfil» y «Cerrar sesión». «Cerrar sesión» llamará al cierre de sesión real del backend, limpiará la sesión local y redirigirá a `/login`. SI una petición posterior responde 401 por sesión inválida, ENTONCES el sistema limpiará la sesión local y redirigirá a `/login` sin dejar contenido protegido visible.
- RF-77: CUANDO un visitante abra `/login`, EL SISTEMA mostrará un formulario de correo y contraseña, un botón de acceso, el estado de carga y los errores de credenciales o de validación en español. El acceso usará la autenticación real de HU-01 y, si es correcto, guardará la identidad de la sesión y redirigirá a la primera ruta permitida según el rol. El formulario no almacenará contraseñas en el navegador ni en el código.
- RF-78: MIENTRAS una sección no tenga su funcionalidad implementada (Técnicos, SLA, Usuarios, Empresas y Notificaciones), EL SISTEMA mostrará una página marcador con el título de la sección, el texto «Próximamente» y un enlace a la primera ruta permitida. El marcador no simulará datos, no mostrará cifras inventadas y no permitirá acciones que aparenten estar disponibles.
- RF-79: EL SISTEMA aplicará un conjunto único de tokens visuales (colores, tipografía, radios, espaciado y alturas) al armazón y a las páginas, de modo que una vista nueva no defina su propio marco ni duplique estilos de cabecera. El encabezado de página será un componente compartido con título, subtítulo y espacio para acciones.
- RF-80: MIENTRAS se valide la sesión al arrancar, EL SISTEMA mostrará un estado de carga del armazón en lugar de contenido protegido. SI la validación falla por un error de red o del servidor, ENTONCES mostrará un estado de error con la acción «Reintentar» y no borrará la sesión local salvo que la respuesta sea 401.

## Requisitos no funcionales

- Responsive de 360 a 1440 px sin pérdida de funcionalidad (ADR-000 §3).
- Accesibilidad WCAG 2.1 AA (RF-75) y textos de interfaz en español.
- La sesión y el rol provienen siempre de la autenticación real; no se introduce un selector de rol ni un modo demo de identidad.
- Sin reglas de negocio en los componentes: la navegación y las acciones se derivan de la matriz de permisos y de los datos que expone el backend.
- Sin dependencias nuevas que no estén justificadas por el armazón, el enrutamiento, el estado del servidor o las pruebas.

## Casos límite

- Sesión expirada o revocada mientras el usuario navega: la siguiente petición devuelve 401 y el sistema vuelve a `/login`.
- Usuario autenticado que abre `/login`: se redirige a su ruta permitida sin mostrar el formulario.
- Ruta inexistente o mal escrita: 404 con enlace de salida, sin mensajes técnicos.
- Drawer móvil abierto y cambio de ruta: el panel se cierra y el foco no queda atrapado.
- Ventana que cruza el umbral de 1024 px con el drawer abierto: el estado móvil se descarta y la barra lateral vuelve a su posición fija.
- Usuario sin nombre visible en la sesión: se muestra el correo como respaldo, sin inventar un nombre.
- Error de red al validar la sesión: estado de error con reintento; no se redirige a `/login` salvo 401.

## Fuera de alcance

- Contenido funcional de tickets, dashboards, administración y cuenta (HU-11, HU-12, HU-22, HU-23, HU-24 y las historias de backend correspondientes).
- Gestión real de usuarios y roles (HU-13): las rutas de usuarios y empresas quedan como marcadores.
- Personalización de tema, acento y densidad (referencia del frontend, RF-50).
- Registro de clientes desde la pantalla de acceso: esta historia solo implementa el acceso; el registro pertenece a HU-01 y a la pantalla de acceso.
- Selector de rol para demostración.
- Cambios en el backend, en los contratos de autenticación o en la base de datos.

## Criterios de finalización

- Las rutas de RF-69 existen y respetan los guards de sesión y rol.
- La navegación de RF-71 coincide con la matriz de permisos y está cubierta por pruebas para los tres roles.
- El armazón, el drawer móvil, el foco y las etiquetas accesibles se verifican con pruebas de interacción y una comprobación manual en 360, 768, 1024 y 1440 px.
- El acceso, la sesión persistida y el cierre de sesión reales funcionan contra el backend de HU-01.
- `npm run test` y `npm run build` pasan en `frontend/`.
- `MEMORY.md` queda actualizado con el estado y las decisiones.

## Decisiones de alcance adoptadas

1. **La autenticación es real.** El rol y la identidad salen de `GET /api/auth/me`; no hay selector de rol. El cierre de sesión usa `POST /api/auth/logout`.
2. **La navegación se deriva del rol, no de la ruta.** Las rutas no permitidas redirigen con aviso; los ítems no permitidos no se renderizan.
3. **Las secciones sin backend se muestran como marcadores.** No se inventan datos ni se adelanta el contenido de HU-11, HU-12, HU-22, HU-23 o HU-24.
4. **El armazón es único para todas las vistas autenticadas.** Las páginas solo aportan su encabezado y su contenido.
5. **El umbral móvil es 1024 px**, conforme a ADR-000 §3.

## Dudas abiertas

- Ninguna pendiente. La ubicación exacta de las rutas de marcador y el contenido de las páginas de HU-11/HU-12 se concretan en sus propias specs.
