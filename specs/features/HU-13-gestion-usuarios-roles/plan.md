# Plan HU-13 — Gestión de usuarios y roles

Spec aprobada: `specs/features/HU-13-gestion-usuarios-roles/spec.md`, RF-105–RF-124. HU-13 conserva una única fuente de requisitos y se entrega en el orden A → B → C. La migración multitenant TSK-025 ya existe; la persistencia funcional de los módulos permanece principalmente en memoria. La implementación no cambia ese alcance ni incorpora proveedor/configuración SMTP.

## 1. Orden y límites

| Orden | Paquete | Alcance | Dependencia |
|---|---|---|---|
| A | Cuentas, autenticación, invitaciones y roles frontend | Usuarios por tenant, estados/roles, invitaciones, migración compatible y guards existentes. | Ninguna. |
| B | RBAC/tenant de tickets y dashboards | Tickets, comentarios, historial, creación y dashboards actuales. | A completo. |
| C | Directorio y asignaciones | Directorio de técnicos activos y asignación/reasignación mediante la operación HTTP existente. | A y B completos. |

El índice y los tres archivos de lote contienen **10 tareas en total**, en orden de dependencia, con estimación de 20–30 minutos por tarea. Cada tarea comienza con pruebas focalizadas; el cierre de cada paquete incluye sus regresiones pertinentes. No se implementan pantallas nuevas de gestión de usuarios ni se rediseña la interfaz.

## 2. Módulos y capas afectadas

| Módulo/capa | Responsabilidad y RF cubiertos |
|---|---|
| `identity` — `domain` | Cuenta, estados, roles permitidos, validación/normalización, invariantes entre invitación y hash y regla de al menos un administrador activo. RF-107–RF-112, RF-118–RF-120, RF-123. |
| `identity` — `application` | Consultar/gestionar usuarios del tenant, autenticar, emitir/aceptar/rotar invitaciones, comprobar sesión y servir resúmenes de técnicos. Los datos de actor/rol/empresa provienen de sesión o token validado. RF-105–RF-112, RF-118–RF-121. |
| `identity` — `infrastructure` | Repositorios actuales, almacenamiento/hash de credenciales, sesiones e invitaciones, y envío por SMTP solo si la configuración existente está disponible. Añadir migración posterior a TSK-025; no reescribir `001` ni incorporar proveedor SMTP. RF-108–RF-111, RF-118–RF-120, RF-123. |
| `identity` — `interface` | Dependencia de sesión, contratos mínimos entre módulos, rutas de usuarios/invitaciones/directorio y traducción de errores HTTP. RF-105–RF-112, RF-117–RF-123. |
| `tickets` — `domain`/`application` | Autorizar por rol y por `ticket.company_id` persistido; mantener las reglas vigentes de ticket, autoría e historial. RF-105–RF-106, RF-113–RF-117, RF-122. |
| `tickets` — `infrastructure`/`interface` | Consultas y operaciones existentes de tickets, comentarios, historial y asignación; filtrar por tenant y traducir los errores/precedencias acordados. No acceder a tablas internas de `identity`. RF-105–RF-106, RF-113–RF-117, RF-121–RF-122. |
| `sla` y contratos entre `sla`/`tickets` | Aplicar alcance por empresa/rol a los agregadores existentes y a la proyección de `by_assignee`, sin cambiar contratos ni cálculo de SLA. RF-113–RF-115, RF-121. |
| Frontend existente | Reconocer los cuatro roles, reflejar permisos en guards, rutas, navegación y controles existentes; mostrar los avisos de entrega de invitación y directorio vacío en sus flujos existentes. No constituye autorización. RF-108, RF-114, RF-124. |
| Composición de la aplicación | Registrar/adaptar las rutas y dependencias existentes manteniendo los límites modulares. RF-105–RF-124 según superficie. |

## 3. Contratos entre módulos y superficies externas

- **Identidad → módulos consumidores:** sesión autenticada con identidad, rol y empresa asignada, sin aceptar empresa del cuerpo. La empresa faltante se resuelve con el 404 uniforme de la operación multitenant. Cuenta activa, aceptación y credenciales se verifican antes de conceder acceso. RF-105, RF-106, RF-119.
- **Usuarios → API:** usuario con forma exacta `{id,name,email,phone,company_id,role,status,invitation_status}`. `company_id` lo fija el actor/tenant y es de solo lectura. Sin contraseñas, hashes, tokens, enlaces, secretos ni sesión en respuestas. Unicidad de correo global y conflicto genérico. RF-107–RF-112, RF-121.
- **Invitaciones → SMTP y API:** alta, reenvío explícito y PATCH que cambia correo de una cuenta pendiente y provoca reenvío responden `{user,email_status}`. Valores: `sent` ante entrega exitosa, `failed` si SMTP configurado falla, `not-attempted` si SMTP no está configurado (situación actual). Los tres conservan el código HTTP de éxito y el estado `active`/`pending`; no hay header `Invitation-Delivery`. `email_status` no aparece en lista/detalle, otros PATCH ni aceptación. Para `failed`, UI presenta literalmente: «La cuenta y la invitación se crearon correctamente, pero hubo un problema al enviar el correo electrónico. Por favor, utiliza la opción de 'Reenviar invitación' desde el panel más tarde.» Para `not-attempted`: «No se pudo enviar el correo porque el servicio aún no está configurado». RF-108, RF-110, RF-118, RF-120–RF-121.
- **Cuentas existentes y migración:** nueva migración después de TSK-025, válida con `001` aplicada y en instalación limpia; las cuentas previas se conservan y quedan `accepted`, con sus hashes, roles, empresas y estado activo previo. Un fallo impide iniciar la aplicación y deja esquema y datos previos intactos. RF-123.
- **Tickets ↔ identidad:** `tickets` consume contratos mínimos para actor y resúmenes; no consulta repositorios/tablas internas de `identity`. El tenant se determina exclusivamente por el `company_id` almacenado en el ticket. Al crear, empresa y solicitante se fijan desde la sesión. RF-105–RF-106, RF-113–RF-117.
- **Dashboards:** se reutilizan `GET /api/dashboard/tickets` y `GET /api/dashboard/sla` y sus agregadores actuales. Admin/supervisor reciben tickets de su empresa; técnico, solo asignados propios de su empresa; cliente recibe 404. `by_assignee` contiene únicamente los técnicos permitidos por tenant/rol, incluidos los de cero tickets para admin/supervisor. Esquema y métricas HU-11/HU-12, periodos y cálculo/configuración HU-14 se conservan. RF-113–RF-115, RF-121.
- **Directorio:** `GET /api/technicians` conserva array exacto `{id,name}` de técnicos activos de la empresa. Una consulta autorizada sin resultados devuelve `[]`; el frontend detecta el array vacío y muestra que aún no hay técnicos, sin indicador adicional. Los no autorizados conservan el 404 uniforme. RF-114, RF-121, RF-124.
- **Asignación:** RF-122 se aplica a la operación HTTP existente de HU-04; no se cambia ruta ni método. Se valida actor y visibilidad/tenant del ticket antes de elegibilidad; la vista mínima de identidad determina si el técnico está activo y pertenece a la empresa. RF-121–RF-122.
- **Frontend:** guards/rutas anidadas heredan los permisos de su ruta principal y siguen sujetos a autorización del ticket. La matriz de permisos refleja UX; la API continúa siendo la frontera de seguridad. RF-124.

## 4. Estrategia de pruebas

- **Backend:** tests de dominio/aplicación y `pytest` con FastAPI `TestClient` para todo contrato HTTP. Usar clientes/sesiones separados por rol, fixtures reseteables y al menos dos empresas con relaciones requester/assignee cruzadas, además de una cuenta sin empresa. Verificar códigos, payloads exactos, redacción, orden de errores y ausencia de efectos parciales. No se afirma que pruebas hayan sido ejecutadas durante esta fase de planificación.
- **Migración:** probar `001` seguida de la nueva migración e instalación limpia; preservar cuentas antiguas como `accepted` sin alterar hash/rol/empresa/estado activo; rechazar estados inconsistentes; forzar fallo y verificar que la aplicación no inicia y que esquema y datos previos no cambian.
- **Concurrencia:** pruebas de integración con varias conexiones/instancias independientes para aceptación de invitación, aceptación frente a desactivación y preservación de al menos un administrador activo. La cobertura no puede limitarse a locks en memoria ni a concurrencia dentro de un único proceso.
- **Invitaciones:** probar sin SMTP configurado, con entrega exitosa y con SMTP configurado que falla; comprobar el estado JSON exacto, éxito HTTP, forma del objeto `user`, ausencia de `Invitation-Delivery`, campo fuera de respuestas no aplicables y posibilidad de reintento. Verificar en pruebas frontend, con Vitest/Testing Library existente, los dos mensajes literales aprobados.
- **Tickets/dashboards:** con `TestClient`, verificar permisos por rol, `ticket.company_id` como tenant autoritativo, 401/404/409/422 según precedencia, y que rechazos no mutan ticket, comentario, asignación o historial. Los dos dashboards deben conservar exactamente esquema/métricas existentes, filtrar relaciones cruzadas, cubrir técnicos sin tickets, `days` 7/30/90 y no alterar cálculo/configuración SLA.
- **Directorio/asignación:** probar array vacío exacto y UI que detecta `[]`; distinguirlo del 404 por rol. Probar la operación HTTP existente de HU-04, sin cambiar ruta/método, con UUID inválido, técnico cruzado/inexistente, inactivo y usuario no técnico, sin revelar tenant y sin cambios en rechazos.
- **Frontend:** Vitest/Testing Library para sesión de cuatro roles, guards/rutas anidadas, rutas permitidas/prohibidas, controles existentes, avisos de invitación y directorio vacío. Ejecutar build/regresión frontend al cerrar los paquetes visibles; el frontend no sustituye pruebas de autorización backend.

## 5. Cobertura por paquete

| Paquete/parte | RF |
|---|---|
| A — esquema, cuentas, invitaciones, autenticación y contratos | RF-105–RF-112, RF-117–RF-123 |
| A — roles, guards, avisos existentes | RF-108, RF-124 |
| B — tickets, comentarios, historial y creación | RF-105–RF-106, RF-113–RF-117, RF-121 |
| B — dashboards y controles frontend existentes | RF-113–RF-117, RF-121, RF-124 |
| C — directorio y asignaciones | RF-105–RF-106, RF-114, RF-121–RF-122, RF-124 |

## 6. Decisiones y alternativas descartadas

1. **Una HU, paquetes A → B → C, máximo 10 tareas totales.** Conserva la secuencia aprobada y un origen único de RF. Alternativa descartada: crear HU o requisitos nuevos; el trabajo se descompone en tareas dentro de HU-13.
2. **`ticket.company_id` almacenado determina el tenant.** Alternativa descartada: inferirlo del solicitante o asignado, lo que habilitaría acceso por relaciones cruzadas.
3. **Reglas de autorización en dominio/aplicación y traducción HTTP en interfaz.** Alternativa descartada: lógica de negocio en controladores o acceso directo a tablas privadas de otro módulo.
4. **Nueva migración posterior a TSK-025; no modificar `001`.** Mantiene compatibilidad de migración y cuentas anteriores. Alternativa descartada: reescribir la migración inicial.
5. **Reutilizar operaciones y agregadores existentes.** Se preservan los endpoints/dashboard de HU-11/HU-12 y la operación de asignación de HU-04 (incluidos ruta y método). Alternativa descartada: crear rutas, agregadores o métricas paralelas.
6. **SMTP opcional según configuración ya disponible.** Sin configuración (estado actual), informar `not-attempted`; con configuración, informar `sent` o `failed` según entrega. En todos los casos se conserva el éxito de la operación y no se introduce proveedor/configuración. Alternativa descartada: rechazar alta/actualización ante falta o fallo de SMTP, o exponer el estado en un header.
7. **Permisos frontend solo como reflejo de UX.** Se modifican guards/controles existentes sin nuevas pantallas. Alternativa descartada: confiar en el frontend como seguridad o ampliar el alcance visual.
8. **`pytest` + `TestClient` y Vitest existente.** Cubre API, reglas y comportamiento visible. Alternativa descartada: pruebas manuales como evidencia única o incorporar un runner/dependencia nueva.

## 7. Riesgos y controles

- Los módulos funcionales son mayormente en memoria; la migración valida compatibilidad de esquema, no convierte por sí sola toda la persistencia.
- La concurrencia debe verificarse con instancias/conexiones independientes; los locks locales no satisfacen la spec.
- Los casos de aislamiento usarán datos cruzados deliberadamente y comprobarán que errores no revelan existencia, rol o tenant ajenos.
- Los contratos de entrega diferencian falta de configuración (`not-attempted`) de fallo con SMTP configurado (`failed`); revisar la presencia exclusiva de `email_status` en las tres respuestas aplicables.
- Los agregadores existentes pueden filtrar nombres/counts por relaciones; los tests comprobarán toda la respuesta, no solo el total.
- Los mensajes de interfaz son textos contractuales exactos; la navegación/guard no concede acceso a un ticket sin autorización backend.

## 8. Remediación propuesta tras la validación final

Esta iteración no cambia la spec ni añade RF. Queda bloqueada para aprobación
explícita antes de llamar a un implementer. Su objetivo es cerrar las dos
brechas de validación de RF-111, RF-118 y RF-120:

1. **Concurrencia real y determinista.** Añadir pruebas de integración que
   ejecuten aceptación frente a desactivación y aceptación frente a
   rotación/reenvío mediante repositorios y conexiones PostgreSQL
   independientes. Cada escenario usará barreras/eventos para arrancar ambas
   operaciones sobre el mismo estado, una pausa controlada después de que una
   operación adquiera el lock y una liberación explícita; no se usará
   `sleep` como mecanismo de sincronización ni se considerará suficiente
   invocar las funciones secuencialmente. Las aserciones comprobarán que el
   resultado observado corresponde a una serialización válida, que como
   máximo una aceptación consume el token, y que el estado persistente final
   es único y coherente.
2. **Errores de infraestructura en `_invitation_lock`.** Distinguir la
   ausencia intencionada de configuración PostgreSQL en tests/unitario del
   entorno de desarrollo de un fallo de conexión, lock o esquema cuando
   PostgreSQL está configurado. Con PostgreSQL configurado, cualquier fallo
   debe abortar la operación, salir de la transacción y evitar toda mutación
   en memoria; no se permite continuar mediante fallback.

### Módulos, capas y contratos afectados

- `identity/application`: contrato de bloqueo de invitaciones y propagación de
  errores; cubre RF-111, RF-118 y RF-120 sin cambiar sus respuestas de dominio.
- `identity/infrastructure`: conexiones/repositorios independientes en las
  pruebas y verificación del estado persistente compartido.
- `identity/interface`: regresión con `TestClient` para confirmar que un error
  de infraestructura no produce aceptación ni cambio parcial. No se define un
  nuevo código HTTP en esta propuesta.

### Estrategia de pruebas de la remediación

- Tests primero con `pytest`, conexiones PostgreSQL independientes y
  `TestClient` para el contrato HTTP; saltar únicamente si `DATABASE_URL` no
  está configurada, nunca ante un fallo de una base configurada.
- Coordinar workers mediante `threading.Barrier` o eventos y puntos de
  instrumentación controlados por el test, con limpieza por fixture. No usar
  `sleep` como sincronización.
- Cubrir ambos órdenes de aceptación↔desactivación y aceptación↔
  rotación/reenvío; comprobar serialización válida, como máximo una aceptación,
  token viejo inválido y estado final leído desde una tercera conexión.
- Probar fallo de conexión/lock/esquema con PostgreSQL configurado y verificar
  excepción propagada, rollback y agregado en memoria sin cambios. La
  configuración ausente conserva únicamente el fallback permitido para
  unitarios.
- Al cerrar: pytest focalizado, suite backend, Vitest y build frontend,
  registrando resultados reales.

### Decisiones y alternativas descartadas

1. Distinguir configuración ausente de infraestructura fallida; se rechaza
   capturar `Exception` indiscriminadamente porque oculta fallos operativos.
2. Usar barreras/eventos y conexiones independientes; se rechazan sleeps,
   llamadas secuenciales y locks en memoria como evidencia de concurrencia.
3. Mantener la remediación dentro de HU-13; se rechaza crear una nueva HU o
   modificar RF.

## 9. Dependencias y exclusiones

- SMTP no está configurado actualmente. Se soporta la configuración que eventualmente esté disponible, sin incorporar proveedor ni definir credenciales.
- La asociación de cuentas autorregistradas sin empresa queda fuera de HU-13; sí se permite `company_id = NULL` en el esquema y se exige 404 en operaciones multitenant.
- No se convierte la persistencia de todos los módulos a PostgreSQL, no se crean pantallas de gestión ni rutas nuevas, y no se alteran la política/cálculo de SLA ni contratos HU-11/HU-12.
- No se cambia ruta/método de asignación de HU-04 ni se modifica el flujo de tickets fuera de los permisos especificados.
- La implementación de la remediación espera aprobación explícita de esta
  propuesta y sus tareas; hasta entonces no se llama a implementer.
