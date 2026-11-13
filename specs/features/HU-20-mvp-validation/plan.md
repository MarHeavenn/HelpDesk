# Plan HU-20 — Validación integral y despliegue del MVP

Spec base: `specs/features/HU-20-mvp-validation/spec.md` (Estado: borrador; RF-113 a RF-118).
Alcance: verificación y despliegue. **No se implementan funcionalidades nuevas**; los defectos críticos se corrigen y se cubren con pruebas.

## 1. Estrategia de validación

La validación se organiza por recorridos, no por módulos, para comprobar la integración real:

1. **Cliente**: login → crear ticket → verlo en «Mis tickets» → consultar su detalle.
2. **Administrador**: login → ver el ticket → asignarlo a un técnico → comprobar la prioridad y el SLA.
3. **Técnico**: login → ver el ticket asignado → cambiar prioridad → avanzar estado → registrar un comentario.
4. **Cierre**: el técnico resuelve y el administrador cierra; se comprueba `resolved_at` y el SLA congelado.
5. **Regresión**: suite de backend, suite de frontend, lint y build.

Cada paso se registra con: rol, acción, resultado esperado, resultado obtenido y evidencia (captura o salida de comando).

## 2. Casos de prueba mínimos

| ID | Rol | Acción | Resultado esperado | RF |
|---|---|---|---|---|
| CP-01 | Cliente | Iniciar sesión y crear un ticket | 201, ticket `Abierto`, sin técnico | RF-113 |
| CP-02 | Cliente | Abrir el ticket creado | Detalle propio con estado y sin acciones de edición | RF-113 |
| CP-03 | Administrador | Asignar el ticket a un técnico | 200, técnico visible en el detalle | RF-113 |
| CP-04 | Técnico | Cambiar prioridad y avanzar a `En progreso` | 200, SLA recalculado | RF-113 |
| CP-05 | Técnico | Registrar un comentario | 201, comentario visible en el seguimiento | RF-113 |
| CP-06 | Técnico | Resolver el ticket | 200, `Resuelto` | RF-113 |
| CP-07 | Administrador | Cerrar el ticket | 200, `Cerrado` y `resolved_at` | RF-113 |
| CP-08 | Administrador | Intentar modificar el ticket cerrado | 409, sin cambios | RF-113 |
| CP-09 | Público | Abrir la URL desplegada | Login accesible y API conectada | RF-115 |
| CP-10 | Equipo | Ejecutar suites y build | Todo en verde | RF-118 |

## 3. Entorno de despliegue

La decisión está abierta (ver dudas de la spec). El plan cubre las dos opciones razonables:

- **Local con Docker Compose** (`infra/docker-compose.yml`): PostgreSQL + backend + frontend; útil para la demo controlada y para reproducir el entorno.
- **Servidor académico o proveedor gratuito**: backend y frontend como servicios separados, PostgreSQL gestionado o contenedor; requiere configurar `VITE_API_URL`, CORS y cookies.

En ambos casos:

- Migraciones aplicadas antes de arrancar el backend.
- Variables de entorno para cadena de conexión, origen del frontend y secretos.
- Sin credenciales ni tokens en el repositorio.
- `VITE_API_URL` apunta a la API pública y el origen del frontend está permitido en CORS.
- La cookie de sesión se configura según el dominio: `SameSite=Lax` en mismo sitio; `Secure` y `SameSite=None` si frontend y API están en dominios distintos.

## 4. Corrección de defectos

- Un defecto es **crítico** si impide completar CP-01 a CP-08 o el login/despliegue.
- Cada corrección crítica sigue el flujo SDD de su historia: prueba en rojo, cambio mínimo, prueba en verde.
- Los defectos menores se registran en `MEMORY.md` o en la incidencia correspondiente, con impacto y workaround.
- No se cambia el alcance ni se añaden funcionalidades para ocultar un defecto.

## 5. Evidencia y documentación

- `README.md`: instalación, migraciones, arranque, variables de entorno, credenciales de desarrollo y URL de demo.
- `MEMORY.md`: estado del despliegue, decisiones, limitaciones conocidas y comandos ejecutados.
- Resultado de las suites y del build adjunto a la entrega o al PR.
- Capturas o notas del smoke manual en los cuatro recorridos.

## 6. Riesgos

- **El entorno elegido no permite cookies same-site.** Mitigación: documentar la configuración `SameSite`/`Secure` y probar el login en el dominio real.
- **Alcance incompleto de HU-13 a HU-19.** Mitigación: declarar las limitaciones y no presentar vistas mock como funcionalidad terminada.
- **Defectos críticos de última hora.** Mitigación: reservar tiempo para corregir y repetir el smoke; no desplegar con un flujo principal roto.
- **Diferencias entre local y desplegado.** Mitigación: ejecutar CP-09 a CP-10 en el entorno real, no solo en local.
