# Tareas HU-11 — Dashboard de tickets

Orden de dependencia. 20–30 min por tarea (si una crece, se divide). Tests primero (en rojo), luego implementación hasta verde.
Verificación backend: `backend\.venv\Scripts\python.exe -m pytest` desde `backend/`. Verificación frontend: `npm run test` y `npm run build` desde `frontend/`.
Prerrequisito: HU-21 (scaffold, cliente HTTP, AuthContext, AppShell y ruta `/`).

- [ ] **T1. Repositorio y contrato de técnicos.** RF-82, RF-87
  - Hecho cuando: `InMemoryTicketRepository.list_all()` devuelve una copia de los tickets; `identity` expone `get_technician_directory()` (id + nombre, sin correo) para el agregado; tests de instantánea y de directorio en verde.
- [ ] **T2. Agregación de tickets.** RF-84, RF-85, RF-86, RF-88, RF-89, RF-90
  - Hecho cuando: `tickets/application/dashboard.py` produce el DTO con total, estados con cero, prioridades con `sin_prioridad`, técnicos con `sin_asignar`, recientes y `generated_at`; una sola pasada; tests unitarios de totales, ceros, `None`, orden y dataset vacío en verde.
- [ ] **T3. Router y autorización.** RF-81, RF-82, RF-83
  - Hecho cuando: `GET /api/dashboard/tickets` responde 401 sin sesión, 404 para cliente, 200 para administrador (global) y 200 para técnico (solo asignados); esquemas Pydantic con la composición del plan; tests de API con `TestClient` en verde.
- [ ] **T4. Tipos, servicio y hook del frontend.** RF-84 a RF-90
  - Hecho cuando: `types/dashboard.ts` define el contrato; `dashboard.api.ts` consume el endpoint con `httpClient`; `useTicketsDashboard` usa TanStack Query con claves y `retry` coherentes; tests con `FakeApiClient` de éxito, 401, 404 y error de red en verde.
- [ ] **T5. KPIs y distribuciones.** RF-91
  - Hecho cuando: `/` muestra los cuatro KPIs y las tarjetas de distribución por estado, prioridad y técnico con conteos y porcentajes; los porcentajes toleran total cero; tests de valores y leyendas en verde.
- [ ] **T6. Tickets recientes, enlaces y estados.** RF-88, RF-91, RF-92
  - Hecho cuando: la tabla muestra los cinco recientes con ID, título, prioridad, estado, técnico y fecha; «+ Crear ticket» y «Ver todos» navegan; hay esqueletos, vacío con CTA y error con «Reintentar»; un 401 cierra sesión; tests de tabla, enlaces y estados en verde.
- [ ] **T7. Alcance por rol, responsive y accesibilidad.** RF-83, RF-91, RF-92
  - Hecho cuando: el administrador ve todo, el técnico solo su carga y el cliente es redirigido; KPIs 4/2/1 columnas, tarjetas apiladas y tabla con scroll; encabezados, etiquetas y foco conformes a RF-75 de HU-21; tests de rol y responsive en verde.
- [ ] **T8. Cierre, build y smoke.** RF-81 a RF-92
  - Hecho cuando: `pytest` del backend y `npm run test`/`npm run build` pasan; smoke manual con administrador y técnico; `MEMORY.md` actualizado; no hay RF sin cubrir o se documenta la brecha.
