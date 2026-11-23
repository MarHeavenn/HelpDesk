# Plan HU-26 — Validación integral y despliegue del MVP

Estado: aprobado

Spec base: `specs/features/HU-26-mvp-validation/spec.md` (RF-165 a RF-172).
Alcance: verificación y despliegue local. **No se implementan funcionalidades
nuevas**; los defectos críticos se corrigen y se cubren con pruebas.

## 1. Arquitectura del entorno

Un único `infra/docker-compose.yml` ampliado con tres servicios:

| Servicio | Imagen / build | Puerto | Comprobación de salud |
|---|---|---|---|
| `db` | `postgres:16` | 55432 | `pg_isready` (ya existe) |
| `api` | `backend/Dockerfile` (FastAPI + uvicorn) | 8000 | `GET /health` |
| `web` | `frontend/Dockerfile` (Vite + nginx) | 8080 | `GET /` |

- La API depende de `db` con `condition: service_healthy`; aplica migraciones
  antes de arrancar y siembra las cuentas demo de forma idempotente.
- El bundle del frontend recibe `VITE_API_URL=http://localhost:8000` en tiempo
  de construcción; nginx sirve la SPA y reenvía las rutas a `index.html`.
- CORS permite `http://localhost:8080`; la cookie `SameSite=Lax` viaja entre
  `localhost:8080` y `localhost:8000` por compartir host.
- `POSTGRES_PASSWORD` y las contraseñas demo se leen de variables de entorno con
  valores por defecto solo de desarrollo; se documentan en `.env.example` sin
  secretos reales.

## 2. Estrategia de validación

Recorridos, no módulos aislados, para comprobar la integración real:

1. **Cliente**: login → crear ticket → «Mis tickets» → detalle propio.
2. **Administrador**: login → dashboard → asignar ticket → comprobar SLA →
   usuarios y empresas.
3. **Técnico**: login → ticket asignado → prioridad → estado → comentario →
   notificaciones.
4. **Cierre**: resolver como técnico, cerrar como administrador, comprobar
   `resolved_at` y SLA congelado.
5. **Paneles**: alertas de SLA y notificaciones visibles en el dashboard.
6. **Regresión**: suites de backend y frontend, lint y build.

Cada paso se registra con rol, acción, resultado esperado, obtenido y evidencia
(salida de comando o captura).

## 3. Casos de prueba mínimos

| ID | Rol | Acción | Resultado esperado | RF |
|---|---|---|---|---|
| CP-01 | Cliente | Login y alta de ticket | 201, `Abierto`, sin técnico | RF-165 |
| CP-02 | Cliente | Ver «Mis tickets» y detalle propio | Solo sus tickets, sin acciones de edición | RF-165 |
| CP-03 | Admin | Dashboard y asignación | Métricas reales; técnico visible en el detalle | RF-165, RF-166 |
| CP-04 | Técnico | Prioridad y paso a `En progreso` | 200, SLA recalculado y señal visible | RF-165, RF-166 |
| CP-05 | Técnico | Comentario | 201, visible en seguimiento | RF-165 |
| CP-06 | Técnico | Resolver | 200, `Resuelto`, `resolved_at` fijado | RF-165 |
| CP-07 | Admin | Cerrar | 200, `Cerrado`, SLA congelado | RF-165 |
| CP-08 | Admin | Modificar ticket cerrado | 409, sin cambios | RF-165 |
| CP-09 | Admin | Empresas: alta, estado y administrador | Catálogo real, sin secretos en la respuesta | RF-166 |
| CP-10 | Admin | Usuarios: consulta, rol y estado | Roles aplicados, último admin protegido | RF-166 |
| CP-11 | Técnico | Campana y `/notificaciones` | Avisos visibles, marcar como leída | RF-166 |
| CP-12 | Admin | Panel de alertas y cumplimiento SLA | Cifras derivadas de la API, sin «Demo» | RF-166 |
| CP-13 | Público | Abrir `http://localhost:8080` | Login accesible y API conectada | RF-168, RF-169 |
| CP-14 | Equipo | `docker compose up --build` desde copia limpia | Los tres servicios sanos y migraciones aplicadas | RF-168 |
| CP-15 | Equipo | Ejecutar suites, lint y build | Todo en verde o bloqueo documentado | RF-171 |
| CP-16 | Equipo | Repetir CP-01..CP-13 en el entorno levantado | Evidencia registrada | RF-171 |

## 4. Corrección de defectos

- Crítico: impide CP-01 a CP-12, el login o el arranque con Docker.
- Cada corrección sigue el flujo SDD de su historia: prueba en rojo, cambio
  mínimo, prueba en verde, referencia al RF/CP que lo detectó.
- Los defectos menores se registran en `MEMORY.md` con impacto y workaround.

## 5. Evidencia y documentación

- `README.md`: sustituye el estado obsoleto; instalar, migrar, arrancar con
  Docker, URLs, credenciales de desarrollo, recorridos y limitaciones.
- `MEMORY.md`: estado del despliegue, comandos ejecutados y resultados.
- Matriz CP-01..CP-16 con resultado y evidencia, y validación RF por RF.

## 6. Riesgos

- **Docker no disponible en el entorno de trabajo**: no se puede afirmar el
  despliegue; se documenta y se entregan los archivos listos (RF-171).
- **Puertos ocupados**: 5432 queda reservado para otro contenedor; usar 55432.
- **CORS/cookie**: si se cambia `localhost` por otra dirección, ajustar
  `VITE_API_URL`, CORS y `SameSite`; se documenta.
- **Datos demo en PostgreSQL**: la semilla debe ser idempotente y no borrar
  cuentas persistidas.
