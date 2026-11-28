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

## Cambio propuesto — Datos demo con empresa (2026-11-26)

Estado del cambio: DEMO-1–7 y PERSIST-1–8 aprobados explícitamente por el usuario.
Plan ampliado y división por bloques pendientes de aprobación; sin implementación.

### Contexto y objetivo

Las cuentas de demostración actuales se crean sin empresa. El administrador de
plataforma puede gestionar empresas, pero no sustituye al administrador de
empresa para operar tickets ni consultar las métricas de HU-18. Se necesita
preparar ambos perfiles y un conjunto demo coherente al arrancar, sin repetir
altas manuales y sin modificar las reglas de autorización existentes.

### Requisitos del cambio

Los identificadores DEMO están acotados a este cambio de HU-26.

- DEMO-1: CUANDO arranque el entorno de demostración, EL SISTEMA dispondrá de
  un administrador de plataforma sin empresa, identificado por
  `admin@helpdesk.dev` con la configuración por defecto, para gestionar empresas
  y sus administradores mediante las capacidades existentes.
- DEMO-2: CUANDO arranque el entorno de demostración, EL SISTEMA dispondrá de
  una empresa demo y un administrador activo asociado a ella, identificado por
  `admin.empresa@helpdesk.dev` con la configuración por defecto, capaz de
  consultar los tickets y métricas de su empresa.
- DEMO-3: CUANDO prepare los datos demo, EL SISTEMA asociará el técnico, el
  cliente y los tickets de demostración a la misma empresa, conservando al
  administrador de plataforma fuera de ella y sin ampliar permisos entre empresas.
- DEMO-4: CUANDO se repita el arranque con datos demo existentes, EL SISTEMA
  reutilizará sus cuentas, empresa y tickets sin duplicarlos, restablecer
  contraseñas, reactivar cuentas deshabilitadas ni reiniciar el progreso de los
  tickets. Los registros demo creados por el arranque anterior sin empresa podrán
  recibir la asociación faltante; no se reasignarán registros de otra empresa.
- DEMO-5: SI una cuenta demo existente tiene un rol incompatible o pertenece a
  otra empresa, ENTONCES EL SISTEMA informará explícitamente del conflicto sin
  cambiar su rol, contraseña o empresa para forzar la demostración.
- DEMO-6: EL SISTEMA tomará las contraseñas demo de configuración externa,
  almacenará únicamente sus hashes y documentará los correos, los perfiles y
  las variables necesarias sin guardar secretos en el repositorio.
- DEMO-7: EL SISTEMA limitará esta preparación automática al arranque de
  demostración y desarrollo; no la ejecutará implícitamente en un arranque
  ordinario de producción ni modificará los flujos públicos de registro e invitación.

### Casos límite y fuera de alcance

- Primera ejecución y reinicios con datos persistentes: mismos registros lógicos,
  sin prometer conservación después de borrar deliberadamente el almacenamiento.
- Datos demo antiguos sin empresa: completar solo sus asociaciones faltantes;
  los registros ajenos al conjunto demo quedan intactos.
- Contraseña de configuración distinta al reiniciar: conservar la contraseña
  registrada; la preparación no es una operación de recuperación de acceso.
- Una cuenta o empresa deshabilitada no se reactiva por arrancar la demostración.
- No se crean roles nuevos ni un acceso de plataforma a todos los tickets.
- No se cambia HU-18, se despliega Render, se borra la base ni se corrige en este
  cambio la comprobación de salud del frontend.

### Criterios de finalización

- Pruebas de primera ejecución y repetición, incluidos datos demo heredados sin
  empresa, cuentas incompatibles y conservación de credenciales y progreso.
- Verificación de que el administrador de plataforma conserva sus capacidades
  de gestión y el administrador de empresa accede a tickets y métricas autorizados,
  sin acceso a datos de otras empresas.
- Arranque demo y variables documentados; pruebas sobre datos persistentes
  ejecutadas en el entorno autorizado o limitación explícita, sin afirmar
  persistencia verificada mediante pruebas exclusivamente en memoria.
- Plan y tareas aprobados antes de implementar; evidencia de pruebas reales y
  memoria actualizada al cerrar cada tarea.

### Dudas abiertas

El usuario rechazó regenerar tickets perdiendo su progreso al reiniciar:
la aplicación final debe almacenar los datos en la base de datos. La ampliación
siguiente sustituye expresamente esa alternativa; no se ha implementado todavía.

## Ampliación propuesta — Persistencia operativa completa (2026-11-26)

Estado: aprobada por el usuario con «apruebo». Identificadores PERSIST acotados a HU-26.

### Contexto y objetivo

Disponer de una base de datos y de tablas no garantiza que la operación real
las utilice. Actualmente hay repositorios operativos en memoria, mientras otros
sincronizan escrituras pero conservan lecturas locales. La versión final debe
recuperar los datos de negocio registrados después de reiniciar o recrear el
backend, manteniendo el almacenamiento de la base de datos.

### Requisitos

- PERSIST-1: CUANDO la aplicación confirme una operación de negocio exitosa,
  EL SISTEMA conservará sus datos en PostgreSQL y los recuperará mediante sus
  consultas normales después de reiniciar el backend, sin depender de objetos
  retenidos por el proceso anterior.
- PERSIST-2: EL SISTEMA conservará los tickets completos, incluidas empresa,
  solicitante, descripción, prioridad, estado, asignación, fechas de creación
  y resolución y objetivo de SLA conservado, sin recalcular ni restablecer sus
  valores por arrancar de nuevo.
- PERSIST-3: EL SISTEMA conservará comentarios y los registros que alimentan el
  historial de tickets, incluidas asignaciones y cambios de estado o prioridad,
  con sus autores y fechas originales y con el orden y visibilidad vigentes.
- PERSIST-4: EL SISTEMA conservará notificaciones, sus destinatarios, estado de
  lectura y claves de deduplicación; reiniciar no convertirá notificaciones
  leídas en pendientes ni duplicará una alerta ya registrada para el mismo evento.
- PERSIST-5: EL SISTEMA recuperará las empresas, cuentas, asociaciones, estados,
  credenciales e invitaciones registradas y la configuración de SLA vigente
  desde el almacenamiento persistente, respetando sus permisos y vencimientos.
  Cambiar la configuración no modificará los objetivos de tickets ya resueltos.
- PERSIST-6: SI una escritura no puede confirmarse en la base de datos, ENTONCES
  EL SISTEMA no responderá como si hubiera guardado el cambio ni sustituirá el
  almacenamiento por memoria silenciosamente. Las modificaciones que constituyan
  una operación indivisible conservarán su consistencia ante un fallo.
- PERSIST-7: CUANDO se preparen los datos demo de DEMO-1–7 con registros ya
  existentes, EL SISTEMA recuperará sus identificadores y progreso persistidos;
  no recreará tickets ya registrados ni alterará sus fechas, estados, historial
  o contraseñas para restaurar el ejemplo inicial.
- PERSIST-8: EL SISTEMA mantendrá los contratos públicos y el aislamiento por
  empresa existentes; listados, detalle, historial, notificaciones y métricas
  reflejarán los datos persistidos autorizados también después de reiniciar.

### Límites y compatibilidad

- Sin nuevos roles ni reglas de negocio de tickets, SLA o autorización.
- La conservación exigida supone mantener el almacenamiento de PostgreSQL:
  eliminar sus datos deliberadamente no equivale a reiniciar la aplicación.
- No es posible recuperar retroactivamente información que solo estuvo en la
  memoria de un proceso ya detenido. No se inventarán sus fechas ni su historial.
- Las sesiones se rigen por su política de autenticación vigente; esta ampliación
  no promete mantener una sesión abierta después del reinicio.
- La memoria podrá seguir siendo un adaptador explícito de pruebas; no será
  la fuente operativa de datos de la versión final.
- La preparación automática de datos demo continúa separada del arranque
  ordinario de producción. No se activa ni configura Render en este cambio.
- No se borrarán ni reasignarán datos existentes de otras empresas. Los cambios
  de esquema necesarios deberán preservar los datos previamente almacenados.

### Criterios de finalización

- Probar sobre PostgreSQL real el flujo de alta, asignación, comentario, cambio
  de prioridad/estado, resolución, cierre y reapertura; reiniciar los repositorios
  o procesos y comprobar por HTTP la conservación de sus valores e historial.
- Verificar cuentas y empresas previamente creadas y no pertenecientes al demo,
  la configuración de SLA, lectura de notificaciones y deduplicación entre reinicios.
- Arrancar el entorno demo dos veces conservando la base, comprobar ambos
  administradores y que los cambios hechos durante la primera ejecución persisten.
- Probar fallos de escritura, consistencia y aislamiento entre dos empresas;
  las métricas de HU-18 conservarán fórmulas y muestras sobre datos recuperados.
- Ejecutar regresiones automatizadas y migraciones de instalación y actualización
  sin borrar datos. No declarar persistencia verificada con pruebas solo en memoria.
- Por su alcance transversal, dividir el plan en bloques dependientes si excede
  diez tareas; aprobar cada bloque antes de implementarlo.
