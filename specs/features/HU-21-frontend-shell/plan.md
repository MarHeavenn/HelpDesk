# Plan HU-21 — Estructura visual y navegación del sistema

Spec base: `specs/features/HU-21-frontend-shell/spec.md` (aprobada; RF-69 a RF-80).
Referencias: ADR-000 §2, §3 y §5; plan de referencia del frontend (`specs/frontend-mvp/plan.md`) §1, §2, §6, §8 y §11.
Alcance: scaffold del frontend, sesión real, armazón, navegación por rol, rutas y guards. No incluye el contenido de tickets, dashboards ni administración.

## 1. Stack y setup

- React 18.3 + TypeScript estricto + Vite, coherente con HU-20.
- Tailwind CSS 3.4 con tokens en `tailwind.config.ts` y variables CSS.
- React Router 6 (`BrowserRouter` + `Routes`).
- TanStack Query 5 para el estado del servidor (sesión y futuras vistas).
- `lucide-react` para iconos.
- Vitest + Testing Library + jsdom + `@testing-library/user-event` + `@testing-library/jest-dom`.
- Scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `test` (`vitest run`), `test:watch`, `lint`.
- `VITE_API_URL` por defecto `http://localhost:8000`. El frontend se abre en `http://localhost:5173` para que la cookie `SameSite=Lax` viaje a la API.
- Sin Recharts ni librerías de gráficos: HU-21 no dibuja gráficos.

## 2. Estructura del proyecto

```
frontend/
  index.html
  vite.config.ts
  tailwind.config.ts
  postcss.config.js
  tsconfig*.json
  src/
    main.tsx
    App.tsx
    index.css
    types/domain.ts
    api/httpClient.ts
    api/auth.api.ts
    context/AuthContext.tsx
    context/ToastContext.tsx
    lib/permissions.ts
    lib/strings.ts
    lib/dates.ts
    lib/cn.ts
    layout/AppShell.tsx
    layout/Sidebar.tsx
    layout/Topbar.tsx
    layout/MobileSidebar.tsx
    components/ui/PageHeader.tsx
    components/ui/Button.tsx
    components/ui/Avatar.tsx
    components/ui/Skeleton.tsx
    components/ui/ErrorState.tsx
    pages/LoginPage.tsx
    pages/PlaceholderPage.tsx
    pages/NotFoundPage.tsx
    routes.tsx
  tests/
    setup.ts
    helpers/renderApp.tsx
    api/httpClient.test.ts
    api/auth.api.test.ts
    context/AuthContext.test.tsx
    layout/AppShell.test.tsx
    layout/MobileSidebar.test.tsx
    pages/LoginPage.test.tsx
    routes/guards.test.tsx
```

La estructura es un subconjunto de la de la referencia del frontend: las páginas de dashboard, tickets y administración se añaden en sus historias.

## 3. Sesión y autenticación (RF-69, RF-76, RF-77, RF-80)

- `httpClient`: `fetch` con `credentials: 'include'`, `Content-Type: application/json`, base `VITE_API_URL`; lanza `ApiError { status, detail }` y normaliza `detail` string o lista de Pydantic.
- `auth.api`: `login(email, password)` → `POST /api/auth/login`; `me()` → `GET /api/auth/me`; `logout()` → `POST /api/auth/logout`.
- `AuthContext`: al montar llama a `me()`. Estados `loading | authenticated | anonymous | error`.
  - 200: guarda `{id, email, role}` (el `me` no devuelve nombre; el nombre se conserva del login o del `localStorage` por id).
  - 401: limpia y deja pasar a `/login`.
  - error de red/5xx: estado `error` con `retry`, sin borrar la sesión local.
- Login: formulario email/contraseña, estado de carga, error 401 «Correo o contraseña incorrectos», error 422 con el mensaje del backend. Al éxito guarda la identidad y navega a la primera ruta permitida.
- Logout: llama a `POST /api/auth/logout`, limpia contexto y `localStorage`, navega a `/login`. Un 401 posterior en cualquier petición dispara el mismo cierre.
- No se guardan contraseñas; el token es `HttpOnly` y el frontend nunca lo lee.

## 4. Permisos y navegación (RF-71, RF-73)

- `lib/permissions.ts` implementa la matriz de ADR-000 §5:

| Ruta | Administrador | Técnico | Cliente |
|---|---|---|---|
| `/` | sí | sí | no |
| `/tickets` | sí | sí | no |
| `/mis-tickets` | sí | sí | sí |
| `/tickets/nuevo` | sí | sí | sí |
| `/tecnicos` | sí | no | no |
| `/sla` | sí | no | no |
| `/usuarios` | sí | no | no |
| `/empresas` | sí | no | no |
| `/notificaciones` | sí | sí | sí |
| `/cuenta/perfil` | sí | sí | sí |

- `firstAllowedRoute(role)`: `/` para administrador y técnico; `/mis-tickets` para cliente.
- `navItems(role)`: lista filtrada con etiqueta, icono, ruta y `aria-label`.
- `RequireAuth`: sin sesión → `/login`; `RequireRole`: rol no permitido → primera ruta permitida con `state.denied = true`; el armazón muestra el aviso una vez.
- La matriz es la única fuente de navegación y acciones; no se consulta al backend para autorizar la navegación.

## 5. Rutas (RF-69, RF-73)

- `/login` pública.
- Layout protegido con `RequireAuth` + `AppShell` + `<Outlet />`.
- Rutas: `/`, `/tickets`, `/mis-tickets`, `/tickets/nuevo`, `/tecnicos`, `/sla`, `/usuarios`, `/empresas`, `/notificaciones`, `/cuenta` (redirige a `/cuenta/perfil`), `/cuenta/perfil`, `*`.
- Las rutas sin contenido implementado usan `PlaceholderPage` con título y «Próximamente» (RF-78).
- `*` muestra 404 con enlace a la primera ruta permitida; si no hay sesión, el guard redirige antes a `/login`.

## 6. Armazón, responsive y accesibilidad (RF-70, RF-72, RF-74, RF-75, RF-79)

- `AppShell`: `Sidebar` fijo en ≥1024 px; `Topbar`; `<main>` con `PageHeader` y contenido.
- `Sidebar`: logo «HelpDesk», tarjeta del espacio de trabajo, navegación filtrada, sección inferior y pie «HelpDesk v1.1 · Prototipo».
- `Topbar`: buscador global con atajo ⌘K/Ctrl+K (en esta historia enfoca el buscador; la navegación a listas llega con HU-23), campana (sin conteo real todavía), avatar/nombre/rol con menú, botón de ayuda.
- `MobileSidebar`: botón de apertura, capa oscura, cierre con Escape, foco atrapado y retorno de foco. El drawer se cierra al cambiar de ruta y al cruzar el umbral de 1024 px.
- `PageHeader`: título, subtítulo y acciones; único punto de cabecera de las páginas.
- Tokens CSS: colores, tipografía, radios, espaciado y alturas; `Button`, `Avatar`, `Skeleton`, `ErrorState` reutilizables.
- Accesibilidad: enlace «Saltar al contenido», `nav`/`header`/`main`, `aria-current="page"`, `aria-expanded`/`aria-controls` en el drawer, foco visible y contraste AA.

## 7. Estrategia de pruebas (RF-69 a RF-80)

- `tests/setup.ts`: `jest-dom`, mock de `matchMedia`, `ResizeObserver` y limpieza de `localStorage`/DOM.
- `tests/helpers/renderApp.tsx`: `MemoryRouter`, `AuthContext` con un `FakeAuthApi` inyectado, `QueryClient` con `retry: false`.
- `httpClient`: éxito, `credentials: 'include'`, 401, 404, 409, 422, `detail` string/lista y error de red.
- `auth.api` y `AuthContext`: login, `me` al montar, sesión persistida, 401, error de red con reintento y logout.
- `LoginPage`: validación, credenciales incorrectas, éxito y redirección por rol.
- `AppShell`: navegación visible por rol, ítem activo, menú de usuario, logout y aviso de denegación.
- `MobileSidebar`: apertura, cierre con Escape y capa, foco atrapado y retorno.
- `guards`: visitante → `/login`, usuario autenticado en `/login` → ruta permitida, rol no permitido → redirección con aviso, ruta desconocida → 404.
- `PlaceholderPage`: título y «Próximamente», sin datos inventados.
- Cobertura RF por RF en la cabecera de cada archivo de prueba.

## 8. Cobertura RF por parte

| Parte | RF |
|---|---|
| Scaffold, tokens y componentes base | RF-79 |
| Sesión, login, logout y 401 | RF-69, RF-76, RF-77, RF-80 |
| Matriz de permisos y navegación | RF-71, RF-73 |
| Armazón y PageHeader | RF-70, RF-72 |
| Drawer y accesibilidad | RF-74, RF-75 |
| Rutas y marcadores | RF-69, RF-78 |
| Pruebas y build | RF-69 a RF-80 |

## 9. Decisiones justificadas

- **D1. Reutilizar el stack y la estructura de la referencia del frontend.** Evita dos configuraciones de frontend y permite que HU-11/HU-12/HU-22/HU-23/HU-24 se añadan sin refactor. *Alternativa descartada: otro framework o Create React App*, cambia el ADR y añade deuda.
- **D2. Autenticación real, sin selector de rol.** El rol viene de la sesión de HU-01. *Alternativa descartada: selector demo*, incompatible con permisos reales.
- **D3. Guards por matriz, no por render condicional disperso.** Una sola fuente de permisos. *Alternativa descartada: condicionales por página*, duplica reglas y permite rutas no autorizadas.
- **D4. Marcadores en lugar de datos inventados.** Las secciones sin backend no simulan funcionalidad. *Alternativa descartada: mocks por sección*, confunde el estado real y adelanta historias ajenas.
- **D5. Drawer propio con foco atrapado, sin librería de UI.** Menos dependencias y control de accesibilidad. *Alternativa descartada: Radix/Headless UI*, añade dependencia no justificada para un solo panel.

## 10. Riesgos y supuestos

- **Cookie same-site**: frontend en `localhost:5173` y API en `localhost:8000`; no mezclar `127.0.0.1` con `localhost`.
- **Backend en memoria**: al reiniciar el backend se pierden usuarios y sesiones; el frontend vuelve a `/login`.
- **`me` no devuelve nombre**: se conserva el del login en `localStorage` por id; si falta, se muestra el correo.
- **HU-13 pendiente**: usuarios y empresas quedan como marcadores; no se implementa su contenido.
- **Sin campana real**: el icono existe, pero el conteo de notificaciones llega con HU-24.
- **Buscador global**: en esta historia solo enfoca el campo; la navegación con resultados llega con HU-23.
- **Tailwind/React/Router mayores**: se fijan versiones compatibles con la referencia del frontend para evitar breaking changes.

## 11. Dudas abiertas

- Ninguna. El contenido de las páginas marcador y el buscador global se completan en sus historias.
