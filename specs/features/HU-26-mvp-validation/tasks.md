# Tareas HU-26 — Validación integral y despliegue del MVP

Orden de dependencia. Cada tarea deja evidencia verificable; no se declara una
prueba como superada sin su salida o captura.

- [x] **T1. Infraestructura local reproducible.** RF-168, RF-169
  - Hecho cuando: existen `backend/Dockerfile`, `frontend/Dockerfile` y un
    `infra/docker-compose.yml` con `db`, `api` y `web`; las migraciones se aplican
    antes de arrancar; `.env.example` documenta las variables sin secretos;
    CORS y `VITE_API_URL` apuntan a `localhost`. Si Docker no está disponible,
    el bloqueo queda registrado con la salida del comando.

- [x] **T2. Matriz de casos y guía de ejecución.** RF-166, RF-170
  - Hecho cuando: `README.md` contiene CP-01 a CP-16 con rol/acción/resultado,
    instrucciones de arranque con Docker, credenciales de desarrollo y
    limitaciones conocidas; no hay cifras ni funcionalidades inventadas.

- [x] **T3. Recorrido del flujo principal.** RF-165, RF-171
  - Hecho cuando: CP-01 a CP-08 se ejecutan contra la API real y PostgreSQL, con
    evidencia por paso; cualquier defecto crítico detectado se registra con RF/CP.

- [x] **T4. Validación de módulos nuevos y paneles.** RF-166, RF-171
  - Hecho cuando: CP-09 a CP-12 cubren empresas, usuarios, notificaciones y
    paneles SLA/alertas, con sus resultados y limitaciones documentadas.

- [x] **T5. Corrección de defectos críticos.** RF-167
  - Hecho cuando: todo defecto que impide CP-01 a CP-12 está corregido y cubierto
    por una prueba automatizada o una comprobación reproducible; se referencia
    el RF/CP detectado. Si no hay defectos críticos, se documenta tal cual.

- [x] **T6. Arranque, smoke final y cierre.** RF-168, RF-171, RF-172
  - Hecho cuando: CP-13 a CP-16 se repiten en el entorno levantado; se ejecutan
    y registran suites backend/frontend, lint, build y smoke manual; la spec
    queda con veredicto RF por RF y `MEMORY.md`/`specs/project.md` actualizados.
