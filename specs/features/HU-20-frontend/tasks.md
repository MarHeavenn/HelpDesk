# Tareas HU-20 — Frontend del MVP HelpDesk

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde. Verificación: `npm run test` y `npm run build` desde `frontend/`.
Fuente de datos: híbrido por vista (API real donde existe; mock «Demo» donde falta). No se modifica el backend.

## Incremento 1 — Fundaciones y personalización visual

- [ ] **T1. Scaffold del frontend y tooling.** RF-67, RF-68
  - Hecho cuando: `frontend/` tiene Vite + React 18 + TS estricto + Tailwind 3.4 + Router 6 + TanStack Query 5 + Vitest/RTL configurados; alias `@/`; scripts `dev`, `build`, `test`, `lint`; `npm run build` compila el esqueleto y `npm run test` ejecuta un test trivial.
- [ ] **T2. Tipos, textos, fechas y permisos.** RF-49, RF-65
  - Hecho cuando: `types/domain.ts` define `Prioridad`, `EstadoTicket`, `EstadoSLA`, `Rol`, `TicketView`, `AuthUser`, filtros y DTOs; `lib/strings.ts` centraliza los textos en español; `lib/dates.ts` formatea con `es-CO` («Hoy/Ayer/d MMM» y relativas); `lib/permissions.ts` implementa la matriz del ADR-000 §5 y tiene tests.
- [ ] **T3. Seed mock coherente y store en memoria.** RF-44, RF-66
  - Hecho cuando: `mocks/seed.ts` genera 3 empresas, usuarios/técnicos, ~30 tickets, SLA y notificaciones con referencias válidas y fechas relativas deterministas; el usuario real se incorpora por id/rol; `mocks/store.ts` permite listar/filtrar/crear/actualizar/asignar y deriva contadores; tests de integridad (referencias, conteos, determinismo, sin ids duplicados) en verde.
- [ ] **T4. Servicios mock de las vistas demo.** RF-44, RF-51 a RF-60, RF-66
  - Hecho cuando: los servicios de dashboard, tickets demo, técnicos/asignaciones, SLA, usuarios, empresas y notificaciones devuelven promesas tipadas, aplican filtros/orden/paginación y validaciones (correo único, último admin, SLA > 0, notificaciones); los contadores derivados coinciden con el store; tests de servicios en verde.
- [x] **T5. Cliente HTTP real, servicios API y mappers.** RF-43, RF-44, RF-53, RF-55
  - Hecho cuando: `httpClient` usa `credentials: include`, `VITE_API_URL`, maneja 401/404/409/422 y `detail` string/lista; `auth.api`, `tickets.api` y `technicians.api` cubren los endpoints de HU-01 a HU-04; `ticketMapper` convierte DTOs a `TicketView` (prioridades/estados, `displayId`, SLA, empresa, metadatos locales); tests con `fetch` fake en verde.
- [ ] **T6. Autenticación real, login y guards.** RF-43, RF-64, RF-65
  - Hecho cuando: `AuthContext` valida la sesión con `me()`, guarda el usuario y limpia en 401; `/login` permite email/contraseña, precarga correos demo y registra clientes; logout llama a la API y redirige; `RequireAuth`/`RequireRole` redirigen según la matriz; tests de login, registro, sesión persistida, 401 y guards en verde.
- [ ] **T7. Tema y personalización visual.** RF-50
  - Hecho cuando: `ThemeContext` aplica modo/accento/densidad con variables CSS, sigue `prefers-color-scheme`, persiste por usuario y restablece; el script inline evita el flash; `/cuenta/apariencia` permite configurar y previsualizar; el botón del topbar alterna claro/oscuro; tests de persistencia, modo sistema, reset y atributos en `<html>` en verde.
- [ ] **T8. AppShell, sidebar, topbar y responsive.** RF-41, RF-47, RF-48
  - Hecho cuando: el layout muestra logo, espacio de trabajo, navegación filtrada por rol, ítem activo, sección inferior, pie, buscador global con ⌘K, campana, menú de usuario, botón de ayuda y drawer móvil; el foco y los `aria-label` son correctos; tests de navegación por rol, atajo, drawer y menú en verde.
- [ ] **T9. Componentes compartidos.** RF-45, RF-46, RF-47
  - Hecho cuando: existen `Button`, `Card`, `Badge`, `Avatar`, `DataTable`, `Select`, `SearchInput`, `Pagination`, `Tabs`, `Switch`, `Modal`, `ConfirmDialog`, `Toast`, `Skeleton`, `EmptyState`, `ErrorState`, `DemoBadge` y `PageHeader` con estilos del ADR, accesibilidad y tests de render/interacción.
- [ ] **T10. Routing completo, `/estado`, 404 y cierre del incremento.** RF-42, RF-46, RF-67, RF-68
  - Hecho cuando: todas las rutas del alcance existen, `/estado` muestra el placeholder, `*` muestra 404, las rutas no permitidas redirigen con aviso; `npm run test` y `npm run build` en verde; smoke manual del shell y login.

## Incremento 2 — Tickets reales y demo

- [ ] **T11. Dashboard demo.** RF-51
  - Hecho cuando: `/` muestra fecha/saludo, 4 KPIs, gráfico 7/30/90, donut de SLA, 3 métricas y 5 recientes con datos del seed y etiqueta «Demo»; el técnico ve solo sus tickets mock; el cliente redirige a `/mis-tickets`; el selector de rango recarga con skeleton; tests de KPIs/leyendas/redirección en verde.
- [ ] **T12. Todos los tickets demo.** RF-52
  - Hecho cuando: `/tickets` muestra la tabla del ADR-002 con búsqueda debounce, filtros combinables, orden, contador, paginación de 10, query string y estados vacío/error; las acciones de fila abren el detalle mock; tests de filtros, búsqueda, orden, paginación y URL en verde.
- [x] **T13. Mis tickets reales.** RF-54
  - Hecho cuando: `/mis-tickets` usa `GET /api/assignments/mine` para técnico y `GET /api/tickets` para admin/cliente; muestra tabla/filtros/orden/paginación; el cliente no ve filtro de técnico ni asignación; estados de carga/vacío/error; tests con `FakeApiClient` por rol en verde.
- [x] **T14. Crear ticket real.** RF-55
  - Hecho cuando: `/tickets/nuevo` valida título 5–120 y descripción ≥ 20, muestra el SLA de la prioridad, crea con `POST /api/tickets`, fija prioridad con `PUT .../priority` si es admin/técnico, guarda la prioridad local si es cliente, muestra toast y redirige a `/mis-tickets`; cancelar con cambios confirma; tests de validación, SLA, alta, prioridad y descarte en verde.
- [x] **T15. Detalle y acciones de ticket reales (MVP reducido).** RF-53
  - Hecho cuando: el modal muestra los campos disponibles según la fuente, permite cambiar prioridad/estado (admin/técnico) y asignar (admin), actualiza la tabla y muestra toast; en tickets reales usa la API y en demo el store; tickets cerrados deshabilitan acciones; tests de apertura, acciones, errores y cierre por ESC en verde.
- [x] **T16. Pruebas y cierre del MVP reducido.** RF-53 a RF-57, RF-67
  - Hecho cuando: `npm run test` y `npm run build` en verde; smoke manual de dashboard, todos, mis tickets, crear y detalle; `MEMORY.md` actualizado.

## Incremento 3 — Administración demo

- [x] **T17. Técnicos y asignaciones reales (MVP reducido).** RF-56
  - Hecho cuando: `/tecnicos` muestra pendientes, prioridad alta, disponibilidad/carga, tabla con búsqueda/filtros y select inline; asignar/desasignar actualiza de forma optimista tabla, cargas, pendientes y badge, con toast y rollback en error; «Registrar técnico» valida y da de alta; la lista real de técnicos se usa cuando está disponible; tests de asignación, rollback, alta y contadores en verde.
- [x] **T18. Configuración de SLA real (MVP reducido).** RF-57
  - Hecho cuando: `/sla` muestra banner y 4 filas con valor/unidad, valida enteros > 0, advierte secuencia no creciente, guarda/cancela, muestra toast y actualiza el texto de `/tickets/nuevo`; tests de validación, guardado, cancelación y efecto en crear ticket en verde.
- [ ] **T19. Usuarios y roles demo.** RF-58
  - Hecho cuando: `/usuarios` filtra por rol/estado, muestra subtítulo dinámico y tabla; alta/edición valida obligatorios, correo y unicidad; activar/desactivar confirma y cambia la píldora; no permite desactivar al último admin ni cambiar su propio rol; tests de filtros, alta, edición, unicidad y último admin en verde.
- [ ] **T20. Empresas y clientes demo.** RF-59
  - Hecho cuando: `/empresas` muestra grid 3→2→1 con plan, estado, usuarios y tickets derivados; alta/edición valida; activar/desactivar confirma e informa impacto; estado vacío con CTA; tests de métricas, alta, edición y toggle en verde.
- [ ] **T21. Pruebas y cierre del incremento 3.** RF-56 a RF-59, RF-66, RF-67
  - Hecho cuando: `npm run test` y `npm run build` en verde; smoke manual de las 4 vistas; contadores cruzados coherentes; `MEMORY.md` actualizado.

## Incremento 4 — Notificaciones y cuenta

- [ ] **T22. Centro de notificaciones demo y campana.** RF-60
  - Hecho cuando: `/notificaciones` muestra pestañas Todas/No leídas/SLA, orden, ítems con icono/etiqueta/tiempo relativo, marcar una/todas, estados vacíos y enlaces a listas; la campana del topbar refleja el conteo no leído y se actualiza; tests de filtros, orden, lectura y campana en verde.
- [ ] **T23. Perfil real, avatar y cambio de cuenta.** RF-61, RF-64
  - Hecho cuando: `/cuenta/perfil` muestra la identidad real, permite editar nombre/correo (local, con aviso de que no se guarda en backend), subir/quitar avatar local (≤ 2 MB), guardar con validación y actualizar topbar; «Cambiar de cuenta» y «Cerrar sesión» llaman al logout real y redirigen a `/login`; tests de perfil, avatar, validación y logout en verde.
- [ ] **T24. Preferencias de notificación.** RF-62
  - Hecho cuando: `/cuenta/notificaciones` muestra 4 switches, guarda al instante por usuario, muestra toast y persiste tras recargar; tests de persistencia y toggles en verde.
- [ ] **T25. Seguridad simulada.** RF-63
  - Hecho cuando: `/cuenta/seguridad` valida contraseña actual/nueva/confirmar (≥ 8, coincidencia, distinta), simula el cambio con toast, lista 2 sesiones y permite cerrar la otra con confirmación; no guarda contraseñas; tests de validación, cambio y cierre de sesión en verde.
- [ ] **T26. Apariencia integrada y pulido del tema.** RF-50
  - Hecho cuando: `/cuenta/apariencia` está conectada al `ThemeContext`, el botón del topbar alterna claro/oscuro, el reset funciona y el contraste AA se cumple en ambos modos y los 4 acentos; tests de integración y smoke visual en verde.
- [ ] **T27. Pruebas finales del incremento 4.** RF-60 a RF-64, RF-67
  - Hecho cuando: `npm run test` y `npm run build` en verde; smoke manual de notificaciones y las 4 pestañas de cuenta; `MEMORY.md` actualizado.
- [ ] **T28. Cierre de HU-20: validación RF por RF, README y memoria.** RF-41 a RF-68
  - Hecho cuando: se recorre la spec RF por RF con su test o comprobación manual; `npm run test` y `npm run build` en verde; README documenta instalación, `VITE_API_URL`, arranque del backend, credenciales demo y registro de cliente; `MEMORY.md` resume el estado; no hay RF sin cubrir o se documenta la brecha.
