# Tareas HU-21 — Estructura visual y navegación del sistema

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde. Verificación: `npm run test` y `npm run build` desde `frontend/`.
No se modifica el backend.

- [x] **T1. Scaffold y tooling del frontend.** RF-79
  - Hecho cuando: `frontend/` tiene Vite + React 18 + TS estricto + Tailwind 3.4 + Router 6 + TanStack Query 5 + Vitest/RTL configurados; alias `@/`; scripts `dev`, `build`, `test`, `lint`; `npm run build` compila el esqueleto y `npm run test` ejecuta un test trivial.
- [x] **T2. Tipos, textos, fechas y matriz de permisos.** RF-71, RF-75
  - Hecho cuando: `types/domain.ts` define `Rol`, `AuthUser` y las rutas; `lib/strings.ts` centraliza los textos en español; `lib/dates.ts` formatea con `es-CO`; `lib/permissions.ts` implementa la matriz de RF-71 con `firstAllowedRoute`, `navItems` y `canView`; tests de matriz y rutas por rol en verde.
- [x] **T3. Cliente HTTP y capa de autenticación.** RF-69, RF-76, RF-80
  - Hecho cuando: `httpClient` usa `credentials: 'include'`, `VITE_API_URL`, maneja 401/404/409/422 y `detail` string/lista; `auth.api` cubre `login`, `me` y `logout`; `AuthContext` valida la sesión al montar, distingue `loading/authenticated/anonymous/error`, limpia en 401 y conserva el nombre del login; tests con `fetch` fake en verde.
- [x] **T4. Pantalla de acceso.** RF-77
  - Hecho cuando: `/login` muestra email/contraseña, validación, estado de carga y errores 401/422 en español; al éxito guarda la identidad y redirige a la primera ruta permitida; un usuario autenticado que abre `/login` es redirigido; no se guardan contraseñas; tests de validación, credenciales incorrectas y éxito en verde.
- [x] **T5. AppShell, Sidebar, Topbar y PageHeader.** RF-70, RF-72, RF-79
  - Hecho cuando: el armazón muestra logo, espacio de trabajo, navegación filtrada por rol, sección inferior, pie, buscador con ⌘K/Ctrl+K, campana, avatar/nombre/rol con menú, botón de ayuda y `PageHeader`; el ítem activo usa `aria-current="page"`; tests de render y navegación por rol en verde.
- [ ] **T6. Routing, guards y 404.** RF-69, RF-71, RF-73
  - Hecho cuando: todas las rutas de RF-69 existen; `RequireAuth` redirige a `/login`; `RequireRole` redirige a la primera ruta permitida con aviso una vez; `*` muestra 404 con enlace de salida; `/cuenta` redirige a `/cuenta/perfil`; tests de visitante, login autenticado, rol denegado y ruta desconocida en verde.
- [ ] **T7. Drawer móvil y accesibilidad.** RF-74, RF-75
  - Hecho cuando: en <1024 px el sidebar se abre con un botón, se cierra con Escape/capa/ruta, atrapa el foco y lo devuelve; el contenido ocupa el ancho; existe enlace «Saltar al contenido», regiones semánticas, `aria-expanded`/`aria-controls`, foco visible y etiquetas accesibles; tests de apertura, cierre y foco en verde.
- [ ] **T8. Páginas marcador y estados de sesión.** RF-78, RF-80
  - Hecho cuando: Técnicos, SLA, Usuarios, Empresas y Notificaciones muestran título, «Próximamente» y enlace de salida, sin datos ni acciones falsas; el armazón muestra carga mientras valida la sesión y error con «Reintentar» si falla la red, sin borrar la sesión salvo 401; tests en verde.
- [ ] **T9. Logout y cierre de sesión.** RF-76
  - Hecho cuando: «Cerrar sesión» del menú y de `/cuenta/perfil` llama a `POST /api/auth/logout`, limpia contexto y `localStorage`, redirige a `/login` y no deja contenido protegido; un 401 posterior repite el cierre; tests de logout y 401 en verde.
- [ ] **T10. Pruebas de cierre, build y smoke.** RF-69 a RF-80
  - Hecho cuando: `npm run test` y `npm run build` pasan; smoke manual con las tres cuentas en 360, 768, 1024 y 1440 px; `MEMORY.md` actualizado; no hay RF sin cubrir o se documenta la brecha.
