# Spec HU-23 — Vistas de tickets con filtros

Estado: aprobada (implementada; smoke manual ejecutado el 2026-11-13)

## Contexto y objetivo

El frontend ya muestra el dashboard real, el alta de ticket real y el detalle de ticket se aborda en HU-22. Faltan las dos vistas de listado: «Todos los tickets» (administrador y técnico) y «Mis tickets» (los tres roles). El backend solo expone los tickets propios (`GET /api/tickets`) y los asignados (`GET /api/assignments/mine`); no existe un listado global. Esta historia añade ese contrato de lectura y conecta ambas vistas a datos reales, con búsqueda, filtros, orden, paginación y estados de carga, vacío y error, sin datos mock ni etiqueta «Demo».

## Usuarios / actores

- **Administrador**: consulta todos los tickets del sistema y los que él creó.
- **Técnico**: consulta todos los tickets y los asignados a él.
- **Cliente**: consulta solo los tickets que creó; no accede a «Todos los tickets».

## Historias de usuario

- H1: Como administrador o técnico, quiero ver todos los tickets con filtros para localizar rápidamente una solicitud.
- H2: Como usuario, quiero ver mis tickets (creados o asignados según mi rol) para darles seguimiento.
- H3: Como usuario, quiero conservar los filtros en la URL para compartir o recargar la vista sin perder el contexto.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global llega a RF-118 en `specs/features/HU-20-mvp-validation/spec.md`; esta historia usa RF-119 a RF-123. El detalle de ticket y sus acciones viven en `specs/features/HU-22-create-edit-tickets/` (RF-109 a RF-111) y no se duplican aquí.

- RF-119: CUANDO un administrador o un técnico abra `/tickets`, EL SISTEMA mostrará todos los tickets reales del sistema con una tabla de identificador amigable, título, prioridad, estado, técnico, SLA y fecha de creación; búsqueda por identificador o título con debounce de 300 ms, filtros combinables de prioridad, estado y técnico, orden por más recientes, más antiguos, prioridad o SLA más próximo, contador de resultados y paginación de 10 por página con el texto «Mostrando X–Y de Z». Los filtros, el orden y la página se reflejarán en la query string.
- RF-120: CUANDO un usuario abra `/mis-tickets`, EL SISTEMA mostrará sus tickets reales con la misma tabla y filtros: el técnico consulta `GET /api/assignments/mine`; el administrador y el cliente consultan `GET /api/tickets`. El cliente no verá el filtro de técnico ni acciones de asignación. La vista no llevará etiqueta «Demo».
- RF-121: EL SISTEMA cubrirá los estados transversales en ambas vistas: esqueleto mientras carga; vacío sin tickets con acción «Crear ticket»; vacío por filtros con «No encontramos tickets con esos filtros» y «Limpiar filtros»; error de red con «Reintentar»; y 401 con cierre de sesión y vuelta a `/login`. Una página fuera de rango o un valor de filtro inválido se normalizará a la primera página o al valor «todos», sin romper la vista.
- RF-122: EL SISTEMA expondrá `GET /api/tickets/all` para administrador y técnico, con el resumen exacto `{id, title, priority, status, assignee, sla, created_at}` y orden por `created_at` descendente. Sin sesión válida responderá 401; un cliente recibirá 404 uniforme sin revelar tickets. La regla de acceso vivirá en la capa de aplicación, no en el controlador HTTP.
- RF-123: La interfaz será accesible (WCAG 2.1 AA), responsive de 360 a 1440 px, estará en español, centralizará los textos y usará un único componente de listado para ambas vistas sin duplicar tabla, filtros ni paginación. Se verificará con pytest, Vitest + Testing Library, `npm run lint` y `npm run build`.

## Requisitos no funcionales

- **Accesibilidad**: etiquetas asociadas, foco visible, navegación por teclado y contador anunciado con `role="status"`.
- **Rendimiento percibido**: debounce de búsqueda, sin recargas completas y con caché de TanStack Query.
- **Mantenibilidad**: filtros, orden y paginación como funciones puras reutilizables; cliente HTTP tipado y textos centralizados.
- **Seguridad**: la sesión viaja por cookie; el cliente nunca recibe el listado global.

## Casos límite

- Listado global vacío y listado personal vacío.
- Búsqueda sin resultados y filtros combinados sin resultados.
- `page` no numérica, negativa, cero o fuera de rango; `priority`, `status` o `sort` desconocidos.
- Tickets sin prioridad (sin SLA) al ordenar por SLA: quedan al final.
- Tickets sin técnico: se muestran como «Sin asignar» y se pueden filtrar por «Sin asignar».
- Error de red y reintento; 401 durante la consulta.
- Rol cliente que fuerza `/tickets`: redirección con aviso.
- Técnico con tickets asignados y tickets creados por él: «Mis tickets» muestra solo los asignados.

## Fuera de alcance

- Detalle de ticket y acciones (HU-22, RF-109 a RF-111).
- Edición, reapertura, historial, comentarios desde el listado.
- Paginación en servidor, exportación y filtros por fecha.
- Datos mock o etiqueta «Demo».
- Pruebas E2E.

## Criterios de finalización

- RF-119 a RF-123 verificados con pytest y con Vitest + Testing Library.
- `npm run test`, `npm run lint` y `npm run build` en verde; pytest del backend en verde.
- Smoke manual con administrador, técnico y cliente: listado global, mis tickets por rol, filtros, orden, paginación y apertura del detalle. Ejecutado el 2026-11-13 con la API real (90 comprobaciones) y la interfaz real en Chrome headless (27), en verde.
- `tasks.md` y `MEMORY.md` actualizados.

## Dudas abiertas

Sin dudas abiertas: el usuario aprobó datos reales con endpoint nuevo y detalle en modal.
