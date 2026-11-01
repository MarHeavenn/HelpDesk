# Plan HU-20 — Frontend del MVP HelpDesk

Spec base: `specs/features/HU-20-frontend/spec.md` (Estado: aprobada; RF-41 a RF-68; decisiones D1–D12).
Restricción principal: **híbrido por vista**. API real para lo que ya existe en HU-01 a HU-04; mock etiquetado «Demo» para lo que el backend aún no expone. No se modifica el backend.

## 1. Stack y setup

- React 18.3 + TypeScript estricto + Vite.
- Tailwind CSS 3.4 con tokens en `tailwind.config.ts` y variables CSS para tema/acento/densidad.
- React Router 6 (`BrowserRouter` + `Routes`).
- TanStack Query 5 para estado servidor y caché; contextos para sesión, tema, SLA mock y toasts.
- `lucide-react` para iconos; Recharts 2 para el gráfico de barras y el donut.
- Vitest + Testing Library + jsdom + `@testing-library/user-event` + `@testing-library/jest-dom`.
- Fuente Inter (Google Fonts) con fallback `system-ui`.
- Scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `test` (`vitest run`), `test:watch`, `lint`.
- `VITE_API_URL` (por defecto `http://localhost:8000`). El frontend debe abrirse en `http://localhost:5173` para que la cookie de sesión sea same-site con la API; el backend ya permite ese origen por CORS.

## 2. Estructura del proyecto

```
frontend/
  index.html                  # script inline de tema (sin flash)
  vite.config.ts              # alias @/, proxy opcional, Vitest
  tailwind.config.ts
  postcss.config.js
  tsconfig*.json
  src/
    main.tsx
    App.tsx
    index.css                 # tokens, temas, densidad, base
    types/domain.ts           # Prioridad, EstadoTicket, EstadoSLA, Rol, TicketView, etc.
    api/
      httpClient.ts           # fetch + credentials + ApiError
      auth.api.ts
      tickets.api.ts
      technicians.api.ts
    mocks/
      seed.ts                 # seed coherente parametrizado por usuario
      store.ts                # store en memoria + mutaciones
      services/
        dashboard.mock.ts
        tickets.mock.ts
        technicians.mock.ts
        sla.mock.ts
        users.mock.ts
        companies.mock.ts
        notifications.mock.ts
    services/
      contracts.ts            # interfaces de servicios
      index.ts                # composición api + mock
    context/
      AuthContext.tsx
      ThemeContext.tsx
      SlaConfigContext.tsx
      ToastContext.tsx
    hooks/
      useMyTickets.ts
      useCreateTicket.ts
      useTicketActions.ts
      useDemoDashboard.ts
      useDemoTickets.ts
      useDemoTechnicians.ts
      useDemoSla.ts
      useDemoUsers.ts
      useDemoCompanies.ts
      useDemoNotifications.ts
    layout/
      AppShell.tsx
      Sidebar.tsx
      Topbar.tsx
      MobileSidebar.tsx
    components/
      ui/                     # Button, Card, Badge, Avatar, DataTable, Select, Modal, Toast, Skeleton, EmptyState, ErrorState, DemoBadge, PageHeader, ConfirmDialog, Tabs, Switch, Pagination, SearchInput
      tickets/                # TicketTable, TicketFilters, TicketDetailModal
      charts/                 # TicketActivityChart, SlaDonut
    pages/
      LoginPage.tsx
      DashboardPage.tsx
      TicketsPage.tsx
      MyTicketsPage.tsx
      CreateTicketPage.tsx
      TechniciansPage.tsx
      SlaPage.tsx
      UsersPage.tsx
      CompaniesPage.tsx
      NotificationsPage.tsx
      AccountLayout.tsx
      account/ProfilePage.tsx
      account/NotificationPreferencesPage.tsx
      account/SecurityPage.tsx
      account/AppearancePage.tsx
      StatusPage.tsx
      NotFoundPage.tsx
    lib/
      dates.ts
      strings.ts              # o i18n/es.ts
      permissions.ts
      theme.ts
      ticketMapper.ts
      localStore.ts
      cn.ts
  tests/
    setup.ts
    helpers/renderApp.tsx
    api/*.test.ts
    mocks/*.test.ts
    components/*.test.tsx
```

## 3. Modelo y mapeo (API ↔ UI)

**Tipos de UI** (`types/domain.ts`): `Prioridad = 'critica' | 'alta' | 'media' | 'baja'`; `EstadoTicket = 'abierto' | 'en_progreso' | 'resuelto' | 'cerrado'`; `EstadoSLA = 'en_tiempo' | 'en_riesgo' | 'cumplido' | 'incumplido'`; `Rol = 'administrador' | 'tecnico' | 'cliente'`.

`TicketView` normaliza ambos orígenes:
```ts
interface TicketView {
  id: string;                 // UUID real o id mock
  displayId: string;          // "TCK-000128" / "TCK-A1B2C3"
  source: 'api' | 'mock';
  title: string;
  description?: string;
  priority: Prioridad | null;
  status: EstadoTicket;
  assignee: { id: string; name: string } | null;
  requesterId?: string;
  requesterName?: string;
  companyId?: string;
  companyName?: string;
  createdAt: string;
  sla: EstadoSLA | null;
  slaDueAt?: string;
  resolvedAt?: string;
}
```

- **Mapeo API → UI** (`lib/ticketMapper.ts`):
  - Prioridades backend `"Crítica" | "Alta" | "Media" | "Baja"` ↔ slugs de UI.
  - Estados backend `"Abierto" | "En progreso" | "Resuelto" | "Cerrado"` ↔ slugs de UI.
  - `displayId` = `TCK-` + primeros 6 caracteres hex del UUID en mayúsculas.
  - `sla` se calcula con la configuración mock de SLA y `created_at`: vencido → `incumplido`; menos del 20 % del tiempo restante → `en_riesgo`; resto → `en_tiempo`; resuelto/cerrado → `cumplido` salvo metadato local de resolución tardía.
  - `companyName` se resuelve por el correo de la sesión (mapeo demo: `admin@helpdesk.dev`/`tecnico@helpdesk.dev` → Acme Solutions; cliente → Grupo Norte); si no se conoce, `—`.
  - `requesterName` = nombre de la sesión para tickets propios; `—` para asignados ajenos (el resumen del backend no lo expone).
  - Metadatos locales por ticket (`helpdesk.ticketMeta.<id>`): prioridad elegida por un cliente, empresa y `resolvedAt` local. Se fusionan al mapear.
- **Mapeo mock → UI**: el seed ya produce `TicketView` con todos los campos; no hay llamadas HTTP.

## 4. Capa API real (`src/api/`)

- `httpClient.ts`: `request<T>(path, { method, body })` con `credentials: 'include'`, `Content-Type: application/json`, base `VITE_API_URL`, timeout/abort opcional. Lanza `ApiError { status, detail }`; normaliza `detail` string o lista de Pydantic. Si `status === 401`, notifica a `AuthContext` para limpiar sesión.
- `auth.api.ts`: `login(email, password)` → `POST /api/auth/login`; `me()` → `GET /api/auth/me`; `register(name, email, password)` → `POST /api/auth/register` con `role: "cliente"`; `logout()` → `POST /api/auth/logout`.
- `tickets.api.ts`: `listMine()` → `GET /api/tickets`; `listAssigned()` → `GET /api/assignments/mine`; `create({title, description})` → `POST /api/tickets`; `get(id)` → `GET /api/tickets/{id}`; `setPriority(id, priority)`; `setStatus(id, status)`; `assign(id, assigneeId)`.
- `technicians.api.ts`: `list()` → `GET /api/technicians` (solo admin).
- La cookie es `HttpOnly`; el frontend nunca lee el token. La sesión se valida con `me()` al arrancar.
- Errores: 401 → logout + `/login`; 404/409/422 → `ApiError` para toast/error inline; red/5xx → estado de error con reintento.

## 5. Capa mock (`src/mocks/`)

- **Seed único y determinista** (`seed.ts`), parametrizado por `AuthUser` y `now`:
  - 3 empresas: Acme Solutions (Business), Grupo Norte (Starter), Órbita Studio (Business).
  - Usuarios fijos: María González (admin), Diego Ruiz/Ana Torres/Luis Vega (técnicos), Carlos Mendoza/Elena Castro (clientes). El usuario real de la sesión se incorpora con su id, nombre, correo y rol; su empresa se resuelve por el mapeo demo.
  - ~30 tickets repartidos en empresas, prioridades, estados y fechas relativas (últimos 90 días), con SLA, `resolvedAt`, `slaDueAt`, solicitante y técnico válidos. Si el rol es técnico, varios tickets se asignan a su id real; si es cliente, varios se crean con su id real.
  - Configuración SLA por defecto: Crítica 2 h, Alta 4 h, Media 12 h, Baja 24 h.
  - ~12 notificaciones por rol/usuario, con tipos `sla_riesgo`, `sla_incumplido`, `asignacion`, `resuelto`, leídas/no leídas y tickets existentes.
  - 2 sesiones activas mock para la página de seguridad.
- **Store en memoria** (`store.ts`): arrays + operaciones `listTickets(filters)`, `createTicket`, `updatePriority`, `updateStatus`, `assignTicket`, `listTechnicians`, `createTechnician`, `listUsers`, `createUser`, `updateUser`, `toggleUser`, `listCompanies`, `createCompany`, `updateCompany`, `toggleCompany`, `listNotifications`, `markRead`, `markAllRead`, `getSlaConfig`, `updateSlaConfig`. Sin persistencia de dominio; se reinicia al recargar o al cambiar de usuario.
- **Servicios mock** (`services/*.mock.ts`): devuelven promesas con latencia `0` en test y ~150 ms en desarrollo; validan reglas de la vista (correo único, último admin, SLA positivo, etc.) y lanzan errores tipados que la UI muestra como toast/error.
- **Contadores derivados**: dashboard (KPIs, gráfico, donut, métricas), sidebar (pendientes), empresas (usuarios/tickets), técnicos (carga) y notificaciones (no leídas) se calculan del mismo store. No hay números hardcodeados.
- **Aislamiento**: los ids mock y los ids reales nunca se mezclan en una tabla; las vistas demo usan solo el store mock y las reales solo la API.

## 6. Estado global

- `AuthContext`: `user: AuthUser | null`, `isLoading`, `login`, `register`, `logout`, `refresh`. Al montar llama a `me()`; guarda `{id, name, email, role}` en `localStorage` (`helpdesk.user`) para conservar el nombre (el `me` del backend no lo devuelve). Si `me()` falla con 401, limpia y redirige a `/login`.
- `ThemeContext`: `mode`, `accent`, `density`, `resolvedTheme`, setters y `reset`. Aplica `data-theme`, `data-accent`, `data-density` en `<html>`; escucha `matchMedia('(prefers-color-scheme: dark)')` cuando `mode = system`.
- `SlaConfigContext`: configuración mock global (`helpdesk.slaConfig`), `update`, `reset`; la consumen `/sla` y `/tickets/nuevo`.
- `ToastContext`: `toast.success/error/info`, viewport accesible, auto-dismiss ~4 s.
- `QueryClient`: `staleTime` 30 s, `retry` 1; claves por recurso y por fuente (`['tickets','mine']`, `['tickets','demo',filters]`, etc.). Las mutaciones invalidan las claves afectadas.
- `useAuth` expone `can(action)` a partir de `lib/permissions.ts`.

## 7. Tema y personalización

- Variables CSS en `index.css`: `--color-primary`, `--color-primary-hover`, `--color-primary-soft`, `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-success`, `--color-warning`, `--color-danger`, `--color-info`, `--radius-card`, `--space-card`, `--table-row-py`.
- `[data-theme="dark"]` redefine superficies/texto; `[data-accent="indigo|blue|green|violet"]` redefine primario (verde `#047857` para contraste AA con texto blanco); `[data-density="compact"]` reduce paddings y altura de fila sin bajar la tipografía de 12 px.
- Script inline en `index.html`: lee `helpdesk.user` y `helpdesk.theme.<id>` (o defaults) y fija los atributos antes de pintar, evitando el flash.
- Topbar: botón sol/luna que alterna claro/oscuro (fija `mode` a `light`/`dark`).
- `/cuenta/apariencia`: modo (Claro/Oscuro/Sistema), acento (4 opciones), densidad (Cómoda/Compacta), vista previa y «Restablecer apariencia».
- Persistencia por `user.id`; `localStorage` envuelto en `try/catch` (modo privado/cuota).

## 8. Routing y permisos

- `/login` público. Layout protegido con `RequireAuth` + `AppShell` + `<Outlet />`.
- Rutas: `/`, `/tickets`, `/mis-tickets`, `/tickets/nuevo`, `/tecnicos`, `/sla`, `/usuarios`, `/empresas`, `/notificaciones`, `/cuenta` (redirige a `/cuenta/perfil`), `/cuenta/perfil`, `/cuenta/notificaciones`, `/cuenta/seguridad`, `/cuenta/apariencia`, `/estado`, `*`.
- `RequireRole`: si el rol no está permitido, `<Navigate to={fallback} replace state={{ denied: true }} />`; el layout muestra el toast de aviso una vez.
- `lib/permissions.ts`: matriz de ADR-000 §5 y helpers `canViewAllTickets`, `canAssign`, `canManageSla`, etc. Es la única fuente de permisos de navegación/acciones.
- Sidebar: ítems filtrados por rol; badge de pendientes solo para admin; campana con conteo de no leídas (mock) para todos.
- Cmd/Ctrl+K: en `/tickets` y `/mis-tickets` enfoca el buscador local; en el resto, el global. El buscador global navega a `/tickets?q=...` o `/mis-tickets?q=...` según el rol.

## 9. Componentes compartidos

- `Button` (primary/secondary/ghost/danger, loading), `Card`, `PageHeader`, `DemoBadge`.
- `Badge` con variantes de prioridad, estado, SLA y rol (colores/puntos del ADR).
- `Avatar` (iniciales o foto, tamaños, color de fondo).
- `DataTable` genérica: columnas, filas, loading (skeleton), empty, acciones, `onRowClick`, scroll horizontal, encabezados en mayúsculas.
- `Select`, `SearchInput` (icono + badge ⌘K + debounce), `Pagination`, `Tabs`, `Switch`.
- `Modal` accesible (foco atrapado, ESC, backdrop, retorno de foco) y `ConfirmDialog`.
- `Toast` (`role="status"`), `Skeleton`, `EmptyState`, `ErrorState`.
- `TicketTable`, `TicketFilters`, `TicketDetailModal`, `TicketActivityChart`, `SlaDonut`.
- Todos los textos desde `lib/strings.ts` (o `i18n/es.ts`); fechas desde `lib/dates.ts`.

## 10. Vistas y fuente de datos

| Vista | Fuente | Notas |
|---|---|---|
| `/login` | API real | Email/contraseña, accesos demo que precargan correos, registro de cliente, tema. |
| `/` Dashboard | Mock «Demo» | KPIs, gráfico 7/30/90, donut, métricas y recientes; scope por rol; cliente redirige. |
| `/tickets` | Mock «Demo» | Búsqueda/filtros/orden/paginación/query string; acciones mock; detalle mock. |
| `/mis-tickets` | API real | Técnico: `assignments/mine`; admin: `tickets` creados; cliente: `tickets` creados; filtros/orden/paginación en cliente. |
| `/tickets/nuevo` | API real + SLA mock | `POST /tickets`; prioridad real para admin/técnico, metadato local para cliente; redirect a `/mis-tickets`. |
| `/tecnicos` | Mock «Demo» + API técnicos | Cargas/pendientes/assignment mock; lista de técnicos real si está disponible; asignación real desde detalle de ticket real. |
| `/sla` | Mock «Demo» | Formulario 4 prioridades, validación, guardar/cancelar, efecto en crear ticket. |
| `/usuarios` | Mock «Demo» | Filtros, alta/edición, activar/desactivar, último admin. |
| `/empresas` | Mock «Demo» | Grid, alta/edición, activar/desactivar, métricas derivadas. |
| `/notificaciones` | Mock «Demo» | Pestañas, orden, marcar leída/todas, campana, enlaces a listas. |
| `/cuenta/*` | API real + local | Identidad real; perfil/avatar/prefs/seguridad locales; tema; logout real. |
| `/estado` | Placeholder | «Próximamente». |

## 11. Estrategia de pruebas (Vitest + Testing Library)

- `tests/setup.ts`: `@testing-library/jest-dom/vitest`, mock de `matchMedia`, `ResizeObserver`, `scrollTo`, `URL.createObjectURL`; limpieza de `localStorage` y del DOM entre tests.
- `tests/helpers/renderApp.tsx`: providers reales con un `FakeApiClient` inyectado (auth, tickets, técnicos) y el store mock; `MemoryRouter` con la ruta inicial; `QueryClient` con `retry: false`.
- `tests/api/*.test.ts`: `httpClient` (éxito, error 401/404/409/422, `credentials`), auth, tickets y técnicos; el `fetch` se sustituye por un fake.
- `tests/mocks/*.test.ts`: integridad del seed (referencias, conteos, determinismo), filtros/orden/paginación, mutaciones, SLA, usuarios (último admin/correo único), empresas, notificaciones y derivación de contadores.
- `tests/components/*.test.tsx`: login/registro y guards; shell y navegación por rol; tema (modo/acento/densidad/persistencia/no flash); dashboard demo; tickets demo (búsqueda/filtros/paginación); mis tickets reales por rol; crear ticket (validación, SLA, alta y prioridad); detalle/acciones reales y demo; asignación demo/real; SLA; usuarios; empresas; notificaciones; perfil/avatar; preferencias; seguridad; logout.
- Recharts: mock de `ResizeObserver` y contenedor con tamaño fijo; se afirman leyendas/etiquetas, no el SVG exacto.
- Cobertura RF por RF en la cabecera de cada archivo de prueba (mapa RF→test).
- `npm run test` y `npm run build` deben pasar; smoke manual con backend real y con las tres cuentas.

## 12. Incrementos y cobertura RF

**Incremento 1 — Fundaciones y personalización visual (RF-41 a RF-50, RF-65 a RF-68)**
- Setup, estructura, tokens y Tailwind.
- Tipos, mappers, seed mock y store.
- Cliente HTTP real y servicios API/mock.
- Auth real, Theme, SLA mock, Toast y QueryClient.
- AppShell, sidebar, topbar, routing y guards.
- Componentes compartidos.
- `/login`, `/estado`, 404 y `/cuenta/apariencia`.
- Pruebas de fundaciones y build.

**Incremento 2 — Tickets reales y demo (RF-51 a RF-55, RF-66)**
- Dashboard demo.
- Todos los tickets demo (tabla/filtros/paginación).
- Mis tickets reales por rol.
- Crear ticket real con SLA mock y prioridad.
- Detalle y acciones reales/demo.
- Pruebas y build.

**Incremento 3 — Administración demo (RF-56 a RF-59, RF-65, RF-66)**
- Técnicos y asignaciones demo + lista real de técnicos.
- SLA demo.
- Usuarios y roles demo.
- Empresas demo.
- Pruebas de contadores cruzados y build.

**Incremento 4 — Notificaciones y cuenta (RF-60 a RF-64, RF-50, RF-65, RF-66)**
- Notificaciones demo y campana.
- Perfil real + edición local + avatar.
- Preferencias de notificación.
- Seguridad simulada.
- Apariencia integrada y logout real.
- Pruebas finales, smoke, README y MEMORY.

## 13. Decisiones justificadas (con alternativa descartada)

- **D1. Híbrido por vista, no mock total ni registro local de tickets reales.** Aprovecha los endpoints existentes sin inventar un backend paralelo; las vistas sin endpoint se marcan «Demo». *Alternativa descartada: mock total*, no usa el backend; *alternativa descartada: sembrar tickets reales desde el frontend*, requiere credenciales de varias cuentas y un registro local frágil.
- **D2. Autenticación real con cookie, sin selector de rol demo.** El rol es el de la sesión; «Cambiar de cuenta» cierra sesión. *Alternativa descartada: selector de rol del ADR-010*, incompatible con una sesión real.
- **D3. Normalización `TicketView` y mappers.** Las vistas no conocen DTOs del backend ni del mock; un solo contrato de UI. *Alternativa descartada: usar los DTOs del backend en los componentes*, acopla la UI al backend y duplica ramas por origen.
- **D4. Metadatos locales para lo que el backend no expone** (prioridad del cliente, empresa, SLA, `resolvedAt`). Se guardan por ticket en `localStorage` y se fusionan al mapear. *Alternativa descartada: inventar campos en el backend*, fuera de alcance.
- **D5. IDs amigables derivados del UUID y IDs secuenciales en mock.** Mantiene la estética del ADR sin colisiones entre fuentes. *Alternativa descartada: UUID completo*, menos legible.
- **D6. Etiqueta «Demo» visible y nota en vistas mock.** Transparencia sobre el origen de los datos. *Alternativa descartada: ocultar el origen*, confunde datos reales con demo.
- **D7. Seed determinista parametrizado por usuario y fecha.** Reproducible en pruebas y coherente con el rol real. *Alternativa descartada: datos aleatorios*, pruebas frágiles y contadores inconsistentes.
- **D8. Tema con variables CSS y persistencia por usuario.** Cambio inmediato, sin re-render global y con contraste AA. *Alternativa descartada: clases Tailwind dinámicas por tema*, más difícil de mantener y propensa a clases no generadas.
- **D9. Pruebas con `FakeApiClient` inyectado, sin MSW.** Menos dependencias y control total de errores/carga. *Alternativa descartada: MSW*, añade configuración y no aporta para este alcance.
- **D10. Recharts 2 y React 18/Router 6/Tailwind 3.4.** Versiones estables compatibles con el ADR y con el ecosistema de pruebas. *Alternativa descartada: últimas versiones mayores*, riesgo de breaking changes innecesarios.

## 14. Riesgos y supuestos

- **Cookie same-site**: el frontend debe abrirse en `http://localhost:5173` y la API en `http://localhost:8000`; si se usa `127.0.0.1` en uno y `localhost` en otro, la cookie `SameSite=Lax` no viaja. Se documenta en README y se usa `VITE_API_URL=http://localhost:8000`.
- **Backend en memoria**: al reiniciar el backend se pierden usuarios/tickets reales y la sesión deja de ser válida; el frontend redirige a `/login`. Las vistas demo no se ven afectadas.
- **Credenciales demo**: las contraseñas de admin/técnico las imprime `dev_server.py` o se fijan por variables de entorno; no se guardan en el repositorio. El cliente demo se registra desde `/login`.
- **Recharts en jsdom**: requiere mock de `ResizeObserver`; los tests afirman leyendas/etiquetas, no el SVG.
- **Tailwind/React/Router mayores**: se fijan versiones compatibles con el ADR para evitar breaking changes.
- **`localStorage`**: puede fallar por cuota o modo privado; todas las lecturas/escrituras van en `try/catch` y la app usa defaults.
- **Fechas relativas**: el seed acepta `now` para que las pruebas sean deterministas; la app usa la fecha actual.
- **Tamaño del bundle**: Recharts y las vistas se pueden dividir con `React.lazy` si el build supera el umbral; no es requisito inicial.
- **Datos reales vs demo**: no se mezclan en una misma tabla; la etiqueta «Demo» y los `source` del `TicketView` lo garantizan.

## 15. Dudas abiertas

Sin dudas abiertas pendientes. Las decisiones D1–D12 de la spec y D1–D10 de este plan cierran el alcance. Las brechas del backend quedan documentadas y cubiertas con mock «Demo»; la integración futura solo sustituye la implementación del servicio correspondiente.
