# Tareas HU-20 — Validación integral y despliegue del MVP

Orden de dependencia. Cada tarea debe dejar evidencia verificable. No se declara una prueba como superada sin su salida o captura.
Verificación: suites de backend y frontend, `npm run lint`, `npm run build` y smoke manual del flujo principal.

- [ ] **T1. Definir los casos de prueba y el entorno.** RF-113, RF-115, RF-117
  - Hecho cuando: existe la matriz de CP-01 a CP-10 con rol, acción, resultado esperado y RF; está decidido el entorno de despliegue (local, académico o proveedor) y documentadas las variables de entorno y la configuración de CORS/cookies.

- [ ] **T2. Recorrer el flujo principal en local.** RF-113, RF-118
  - Hecho cuando: con las tres cuentas se completa CP-01 a CP-08; cada paso tiene evidencia; los defectos encontrados quedan registrados con su impacto.

- [ ] **T3. Corregir defectos críticos y cubrirlos con pruebas.** RF-114, RF-118
  - Hecho cuando: todo defecto que impide el flujo principal está corregido; cada corrección tiene una prueba automatizada o una comprobación manual reproducible; las suites de backend y frontend están en verde.

- [ ] **T4. Desplegar el MVP y validar el acceso público.** RF-115, RF-116
  - Hecho cuando: el backend y el frontend están accesibles por URL; las migraciones están aplicadas; el login funciona desde el dominio del frontend; no hay secretos en el repositorio; `VITE_API_URL` y CORS apuntan al entorno correcto.

- [ ] **T5. Smoke final, documentación y cierre.** RF-117, RF-118
  - Hecho cuando: CP-01 a CP-10 se repiten en el entorno desplegado; `README.md` explica instalación, migraciones, arranque, credenciales de desarrollo, URL y limitaciones; `MEMORY.md` resume el estado; el build de producción y las suites están en verde.
