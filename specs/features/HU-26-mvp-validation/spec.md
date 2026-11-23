# Spec HU-26 — Validación integral y despliegue del MVP

Estado: aprobada

## Contexto y objetivo

Las historias HU-01 a HU-24 están implementadas: el backend expone autenticación,
tickets, SLA, notificaciones, usuarios y empresas; el frontend consume esos
contratos reales e incluye dashboards, vistas de tickets y paneles de alertas.
Sin embargo, nunca se ha recorrido el sistema completo de punta a punta sobre
una Base de datos PostgreSQL, y el repositorio no contiene todavía una forma
reproducible de arrancar backend, frontend y datos a la vez: el
`infra/docker-compose.yml` solo levanta PostgreSQL, no hay Dockerfile para la
API ni para la SPA, y el `README.md` describe un estado anterior del proyecto.

Esta historia no añade funcionalidad. Su entregable es evidencia de que lo
construido funciona junto y un entorno local reproducible, accesible por URL,
para la demostración académica. La tarjeta Trello `ygMlFn1L` la denomina
«Validación integral y despliegue del MVP» y la tiene en «En desarrollo».

> Nota de numeración: esta spec existía como `HU-20-mvp-validation` (RF-113 a
> RF-118) antes de que la tarjeta se renombrara a HU-26. Se traslada a esta
> carpeta y se renumeran sus requisitos a RF-165–RF-172 para no colisionar con
> RF-144–RF-164 (HU-15/HU-16).

## Usuarios / actores

- Administrador / administrador de plataforma: recorre el flujo, asigna,
  supervisa SLA y cierra; gestiona empresas y cuentas.
- Técnico: atiende el ticket asignado, cambia prioridad y estado, comenta.
- Cliente: inicia sesión, crea un ticket y consulta su estado.
- Equipo de desarrollo: ejecuta pruebas, corrige defectos y prepara el entorno.
- Evaluador de la demostración: accede a la URL local con las cuentas de prueba.

## Historias de usuario

- H1: Como administrador, quiero una versión funcional y desplegada del sistema
  para validar el flujo completo y demostrar el MVP.
- H2: Como equipo, quiero casos de prueba repetibles para detectar regresiones
  antes de la entrega.
- H3: Como evaluador, quiero acceder al MVP desde una URL local con
  instrucciones claras.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-165: EL SISTEMA permitirá recorrer el flujo principal completo sobre la API
  real y PostgreSQL: inicio de sesión del cliente, alta de ticket, inicio de
  sesión del administrador, asignación a un técnico, inicio de sesión del
  técnico, cambio de prioridad y estado, registro de seguimiento, consulta de
  SLA y alertas, resolución y cierre; cada paso tendrá el resultado esperado y
  no dejará la aplicación en un estado inconsistente.

- RF-166: EL SISTEMA incluirá casos de prueba para los módulos incorporados
  después del MVP inicial: alta y estado de empresas (HU-19), consulta y roles
  de usuarios (HU-13), centro de notificaciones y campana (HU-15/HU-16) y
  paneles de SLA y alertas (HU-11/HU-12/HU-24). Los casos declararán rol,
  acción, resultado esperado y resultado obtenido; lo que no esté disponible se
  documentará como limitación, no como funcionamiento terminado.

- RF-167: SI durante la validación aparece un defecto que impide completar
  RF-165 o RF-166, ENTONCES se corregirá antes de cerrar la historia y se añadirá
  o ajustará una prueba automatizada que lo cubra. Los defectos menores se
  registrarán con impacto y workaround, sin bloquear la entrega.

- RF-168: EL SISTEMA se arrancará de forma reproducible con un único
  `docker compose` que levante PostgreSQL, el backend y el frontend, con
  Dockerfiles para la API y la SPA, las migraciones aplicadas antes de aceptar
  peticiones y una URL local documentada (`http://localhost:8080` para la
  interfaz, `http://localhost:8000` para la API). Cada servicio tendrá una
  comprobación de salud y el arranque fallará de forma explícita si la base de
  datos no está disponible.

- RF-169: EL ENTORNO de demostración tomará toda la configuración sensible de
  variables de entorno (`POSTGRES_PASSWORD`, contraseñas demo, `VITE_API_URL`,
  orígenes CORS) y no guardará contraseñas, tokens ni secretos en el
  repositorio ni en el bundle del frontend. `.env.example` documentará las
  variables sin valores reales; CORS permitirá el origen `http://localhost:8080`
  y la cookie de sesión funcionará con `SameSite=Lax` al compartir host
  `localhost`.

- RF-170: EL SISTEMA contará con una matriz de casos de prueba funcionales y una
  guía de ejecución que cubra instalación, migraciones, arranque con Docker,
  credenciales de desarrollo, flujo principal, comprobación de los módulos
  nuevos y limitaciones conocidas.

- RF-171: LA ENTREGA incluirá el resultado de ejecutar —en este entorno— la
  suite de backend, la suite de frontend, `npm run lint`, `npm run build`, el
  smoke manual de API y el recorrido por la interfaz desplegada. No se declarará
  una prueba como superada sin evidencia de su ejecución; si Docker no está
  disponible, se documentará el bloqueo y no se afirmará el despliegue.

- RF-172: EL CIERRE de esta historia dejará `README.md`, `specs/project.md` y
  `MEMORY.md` actualizados con la URL, los comandos, los resultados y las
  limitaciones, y una validación RF por RF con veredicto explícito.

## Requisitos no funcionales

- Reproducibilidad: desde una copia limpia, `docker compose up` debe levantar
  el MVP completo sin pasos manuales ocultos.
- Seguridad: secretos fuera del repositorio, CORS limitado al origen local del
  frontend y sin credenciales de producción.
- Trazabilidad: cada defecto crítico corregido queda relacionado con el RF o la
  prueba que lo detectó.
- Sin cambios de alcance: no se añaden funcionalidades de HU-01 a HU-24 para
  ocultar defectos.

## Casos límite

- Docker o el daemon no disponibles: RF-168 no se puede verificar; se documenta
  el bloqueo y no se afirma despliegue.
- Migraciones pendientes o BD no saludable: el backend no arranca en estado
  inconsistente; el compose espera al `healthcheck` de PostgreSQL.
- Origen del frontend distinto del CORS configurado: el login falla con error
  claro y se documenta en la guía.
- Cuenta demo sin datos o ya existente en PostgreSQL: el flujo de alta funciona
  igual y la semilla reutiliza cuentas persistentes sin cambiar su contraseña.
- Ticket cerrado durante la validación: no se modifica; se usa la reapertura solo
  si el flujo lo requiere.
- Defecto crítico detectado después del arranque: se corrige, se vuelve a
  construir la imagen y se repite el smoke.

## Fuera de alcance

- Proveedores de nube, servidores académicos, alta disponibilidad o escalado.
- Pruebas de carga, penetración o auditoría de accesibilidad externa.
- Cambios funcionales en HU-01 a HU-24.
- Notificaciones push, correo real (HU-15/HU-16 usan entrega simulada sin SMTP)
  e internacionalización.

## Criterios de finalización

- RF-165 a RF-172 verificados con evidencia: salida de comandos, matriz de casos
  y resultados del recorrido.
- MVP arrancado con Docker y accesible en las URL documentadas, con migraciones
  aplicadas.
- Suites, lint, build y smoke en verde o con el bloqueo documentado.
- Documentación y memoria actualizadas; veredicto final de la spec.

## Dudas abiertas

Ninguna. El usuario decidió: despliegue local con Docker, renombrar y renumerar
la spec, trabajar en `feature/HU-26-mvp-validation` desde `develop` y validar el
flujo principal junto con los módulos nuevos.

## Validación (2026-11-23)

| RF | Evidencia | Resultado |
|---|---|---|
| RF-165 | `smoke_manual.py`: 93 comprobaciones en verde (cliente → alta → asignación → prioridad/estado/comentario → SLA → resolución → cierre → reapertura → logout). Suites backend/frontend en verde | PASADO en memoria; no repetido sobre PostgreSQL desplegado |
| RF-166 | Suites backend (1574) y frontend (236) cubren empresas, usuarios, notificaciones y paneles; el smoke cubre el flujo de tickets | PASADO como cobertura automatizada; recorrido manual en entorno desplegado no ejecutado |
| RF-167 | Dos defectos corregidos y cubiertos (ver detalle abajo) | PASADO |
| RF-168 | `backend/Dockerfile`, `frontend/Dockerfile`, `nginx.conf` y compose completo; `docker-compose config -q` sin errores | PARCIAL: configuración lista, arranque no ejecutado |
| RF-169 | `.env.example` sin secretos; `POSTGRES_PASSWORD` obligatorio; CORS `http://localhost:8080`; `VITE_API_URL` como arg de build | PASADO |
| RF-170 | `README.md`: CP-01..CP-16, arranque con Docker, cuentas demo, variables y limitaciones | PASADO |
| RF-171 | Backend **1574 passed / 40 skipped**; frontend **34 archivos / 236 pruebas**; `npm run lint` y `npm run build` correctos; smoke **93/93** | PASADO; CP-13/14/16 sin evidencia por bloqueo de Docker |
| RF-172 | Spec, plan, tareas, `specs/project.md`, `README.md` y `MEMORY.md` actualizados | PASADO |

### Defectos críticos corregidos (RF-167)

1. `backend/tests/test_dev_server_seed.py` importaba `DEMO_TICKETS`,
   `seed_demo_client` y una firma antigua de `seed_demo_tickets`, lo que rompía
   la recolección de toda la suite backend. Se reescribió contra la API actual
   (`SLA_DEMO_TICKETS`, `seed_sla_demo_client`, `seed_sla_demo_tickets`) con
   `now` fijo: **2 pruebas en verde**. Relacionado con RF-171.
2. `backend/smoke_manual.py` daba por supuestos el registro sin empresa y que
   técnico/admin no veían tickets ajenos en el listado principal, ambos
   cambiados por HU-13/HU-19. Se asignó una empresa de prueba a las cuentas y se
   reordenaron las modificaciones del técnico tras la asignación:
   **93 comprobaciones en verde**. Relacionado con RF-165/RF-166.

### Bloqueo para el despliegue (RF-168)

El entorno de trabajo tiene Docker CLI 19.03.1 y `docker-compose` 1.24.1, pero
**el daemon no está en ejecución** (`docker ps` → `open //./pipe/docker_engine:
El sistema no puede encontrar el archivo especificado`) y no está instalado
Docker Desktop. Por tanto no se ejecutaron CP-13, CP-14 ni CP-16 y **no se afirma
que el MVP esté arrancado ni accesible**. La sintaxis del compose sí se validó
con `docker-compose -f infra/docker-compose.yml config -q` (sin salida = OK).
En un equipo con Docker en ejecución, basta con copiar `.env.example` a
`infra/.env`, definir `POSTGRES_PASSWORD` y ejecutar `docker-compose -f
infra\docker-compose.yml up --build -d`.

**Veredicto: spec parcialmente cumplida.** La validación funcional y la
infraestructura están listas y verificadas; el despliegue real queda pendiente
de un entorno con daemon de Docker. No se declara superado ningún caso sin
evidencia de ejecución.
