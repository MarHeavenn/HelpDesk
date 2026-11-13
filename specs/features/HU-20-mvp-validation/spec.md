# Spec HU-20 — Validación integral y despliegue del MVP
Estado: borrador

## Contexto y objetivo

Las historias de backend y las primeras historias de frontend están implementadas, pero el MVP todavía no se ha recorrido de punta a punta ni se ha desplegado en un entorno accesible para la demostración académica. Esta historia valida el flujo completo de gestión de tickets, corrige los defectos críticos que aparezcan y prepara el despliegue del MVP. No añade funcionalidades nuevas: su entregable es evidencia de que lo construido funciona junto.

## Usuarios / actores

- **Administrador**: recorre el flujo completo, asigna tickets, supervisa SLA y valida el cierre.
- **Técnico**: atiende un ticket asignado, actualiza prioridad/estado y registra seguimiento.
- **Cliente**: inicia sesión, crea un ticket y consulta su estado.
- **Equipo de desarrollo**: ejecuta las pruebas, corrige defectos y prepara el entorno.
- **Evaluador de la demostración**: accede al MVP desplegado con las cuentas de desarrollo.

## Historias de usuario

- H1: Como administrador, quiero disponer de una versión funcional y desplegada del sistema para validar el flujo completo y demostrar el MVP.
- H2: Como equipo, quiero ejecutar un conjunto de casos de prueba repetible para detectar regresiones antes de la entrega.
- H3: Como evaluador, quiero acceder al MVP desde un entorno accesible con instrucciones claras.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global llega a RF-112 en `specs/features/HU-22-create-edit-tickets/spec.md`; esta historia usa RF-113 a RF-118. Fuente: tarjeta Trello «HU-20 — Validación integral y despliegue del MVP».

- RF-113: EL SISTEMA permitirá recorrer el flujo principal completo con datos reales: inicio de sesión de cliente, alta de ticket, inicio de sesión de administrador, asignación a un técnico, inicio de sesión del técnico, cambio de prioridad y estado, registro de seguimiento, control de SLA y cierre del ticket; cada paso mostrará el resultado esperado y no dejará la aplicación en un estado inconsistente.
- RF-114: SI durante la validación se detecta un defecto que impide completar el flujo principal, ENTONCES se corregirá antes del despliegue y se añadirá o ajustará una prueba automatizada que lo cubra. Los defectos menores se registrarán con su impacto y no bloquearán la entrega si no afectan al flujo.
- RF-115: EL SISTEMA estará desplegado en un entorno accesible por URL para la demostración, con el frontend y el backend conectados, la base de datos PostgreSQL inicializada y las migraciones aplicadas; la URL y las instrucciones de acceso quedarán documentadas.
- RF-116: EL ENTORNO de demostración usará variables de entorno para la configuración sensible y no incluirá contraseñas, tokens ni secretos en el repositorio ni en el frontend. Las cuentas de desarrollo se documentarán sin exponer credenciales de producción.
- RF-117: EL SISTEMA contará con un conjunto de casos de prueba funcionales y una guía de ejecución que cubra instalación, migraciones, arranque del backend y del frontend, credenciales de desarrollo, flujo principal y limitaciones conocidas.
- RF-118: LA ENTREGA incluirá el resultado de la suite automatizada de backend y frontend, el build de producción del frontend y el smoke manual del flujo principal. No se declarará una prueba como superada sin evidencia de su ejecución.

## Requisitos no funcionales

- **Reproducibilidad**: los casos de prueba y el despliegue deben poder repetirse desde una copia limpia del repositorio.
- **Seguridad**: secretos fuera del repositorio, cookie de sesión correctamente configurada y CORS limitado al origen del frontend desplegado.
- **Disponibilidad**: el entorno de demostración debe responder durante el periodo de evaluación acordado.
- **Trazabilidad**: cada defecto crítico corregido debe quedar relacionado con el RF o la prueba que lo detectó.

## Casos límite

- Backend o base de datos no disponibles al arrancar: el despliegue falla de forma explícita y la guía indica cómo diagnosticarlo.
- Migraciones pendientes: el backend no arranca en un estado inconsistente.
- Origen del frontend distinto del configurado en CORS: el login falla con un error claro.
- Cookie `SameSite` incompatible con el dominio desplegado: se documenta la configuración necesaria.
- Cuenta de demostración sin datos: el flujo de alta funciona igualmente.
- Ticket cerrado durante la validación: no se permite modificarlo y se usa la reapertura solo si el flujo lo requiere.
- Defecto crítico detectado después del despliegue: se corrige, se vuelve a desplegar y se repite el smoke.

## Fuera de alcance

- Funcionalidades nuevas o cambios de alcance de HU-01 a HU-24.
- Migración a otro proveedor de nube, alta disponibilidad o escalado horizontal.
- Pruebas de carga, penetración o accesibilidad con auditoría externa.
- Internacionalización, aplicación móvil nativa o notificaciones push.
- Sustituir los datos mock de las vistas que aún no tienen endpoint; esas brechas se documentan.

## Criterios de finalización

- Flujo principal recorrido con las tres cuentas y evidencia de cada paso.
- Defectos críticos corregidos y cubiertos por pruebas.
- Frontend y backend desplegados y accesibles por URL, con migraciones aplicadas.
- Suites de backend y frontend en verde y build de producción correcto.
- Guía de ejecución y credenciales de desarrollo documentadas sin secretos.
- `MEMORY.md` actualizado con el estado del despliegue y las limitaciones conocidas.

## Dudas abiertas

- [NECESITA ACLARACIÓN] **Entorno de despliegue.** No está definido si la demostración será local (docker-compose), un servidor académico o un proveedor gratuito; la elección cambia los pasos de la guía y la configuración de CORS/cookies.
- [NECESITA ACLARACIÓN] **Alcance de la demo.** HU-13, HU-15 a HU-19 y las vistas de administración del frontend pueden no estar completas; hay que acordar qué se muestra y qué se declara como limitación.
