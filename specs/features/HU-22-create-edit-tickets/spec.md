# Spec HU-22 — Formularios e interfaz de creación y edición de tickets
Estado: aprobada (creación y detalle implementados; smoke manual ejecutado el 2026-11-13)

## Contexto y objetivo

El backend ya expone el alta de tickets (HU-02), el detalle (HU-06), los cambios de prioridad y estado (HU-03 y HU-08), la asignación (HU-04) y el seguimiento por comentarios (HU-07). El frontend ya tiene el armazón y la sesión real (HU-21), pero solo `/tickets/nuevo` usa la API: las demás vistas de tickets siguen siendo marcadores.

Esta historia construye los formularios e interfaces con los que un cliente o un técnico crea un ticket y consulta o modifica los datos que el backend permite. La creación y el detalle ya están implementados y verificados con pruebas; el detalle se presenta como un modal accesible abierto desde la tabla (decisión del 2026-11-13). El smoke manual con las tres cuentas se ejecutó el 2026-11-13, con la API y la interfaz reales, en verde. No se modifica el backend ni se inventan campos editables: el título y la descripción son inmutables después del alta porque no existe un endpoint para cambiarlos y HU-06 es de solo lectura.

## Usuarios / actores

- **Cliente**: crea tickets y consulta los suyos. No puede cambiar prioridad, estado ni técnico, y HU-07 no le permite registrar comentarios.
- **Técnico**: crea tickets y, sobre los tickets que puede ver, cambia prioridad y estado, y registra comentarios.
- **Administrador**: además asigna o reasigna el técnico responsable.
- **Visitante sin sesión**: no accede; cualquier ruta protegida lo devuelve a `/login`.

## Historias de usuario

- H1: Como cliente o técnico, quiero crear un ticket con un formulario claro para registrar una solicitud de soporte sin dificultad.
- H2: Como técnico o administrador, quiero consultar el detalle de un ticket y modificar sus datos permitidos para mantenerlo actualizado.
- H3: Como usuario, quiero ver validaciones, errores y confirmaciones para saber si la operación se guardó.

## Requisitos funcionales (criterios de aceptación en EARS)

> Numeración: la secuencia global llega a RF-104 en `specs/features/HU-12-sla-dashboard/spec.md`; esta historia usa RF-105 a RF-112. Fuente: tarjeta Trello «HU-22 — Implementar formularios e interfaz de creación y edición de tickets» y contratos de HU-02, HU-03, HU-04, HU-06, HU-07 y HU-08.

- RF-105: CUANDO un usuario autenticado abra `/tickets/nuevo`, EL SISTEMA mostrará un formulario con campos etiquetados de título y descripción y, solo para administrador y técnico, un selector de prioridad con «Media» por defecto. El cliente no verá el selector de prioridad y verá una nota de que un administrador o técnico la definirá.
- RF-106: EL SISTEMA validará el alta con el contrato de HU-02: título de 1 a 200 code points y descripción de 1 a 5000 code points, contados después de recortar; un valor vacío o compuesto solo por espacios será inválido. SI hay errores, ENTONCES mostrará el mensaje junto al campo, asociado con `aria-describedby`, enfocará el primer campo inválido y no enviará la petición.
- RF-107: CUANDO se envíe un formulario válido, EL SISTEMA creará el ticket con `POST /api/tickets` (estado `Abierto`, sin técnico y solicitante de la sesión), mostrará «Creando...», evitará envíos duplicados y, si el rol es administrador o técnico, fijará la prioridad con `PUT /api/tickets/{id}/priority`. Después redirigirá a `/mis-tickets` con un aviso que incluye el identificador del ticket. SI el alta funciona y la prioridad falla, ENTONCES conservará el ticket creado y avisará del fallo sin deshacer el alta.
- RF-108: MIENTRAS el rol sea administrador, EL SISTEMA mostrará el tiempo objetivo de SLA de la prioridad seleccionada, leído de `GET /api/sla/policies`; el técnico no consultará esa política y el cliente no verá prioridad ni tiempo objetivo. SI la consulta de SLA falla, ENTONCES el formulario seguirá siendo utilizable y no bloqueará el alta.
- RF-109: CUANDO un usuario abra el detalle de un ticket visible, EL SISTEMA mostrará los campos de `TicketResponse` (identificador, título, descripción, prioridad, estado, técnico, solicitante, SLA, fecha de creación y fecha de resolución) y el seguimiento de comentarios. El título y la descripción serán de solo lectura y la interfaz indicará que no se editan porque el backend no expone esa operación.
- RF-110: SI el usuario es administrador o técnico y el ticket no está cerrado, ENTONCES podrá cambiar la prioridad con `PUT /api/tickets/{id}/priority` y el estado con `PUT /api/tickets/{id}/status`; el administrador podrá además asignar o reasignar al técnico con `PUT /api/tickets/{id}/assignee`. El cliente verá el detalle sin acciones de edición. SI el backend responde 409 (ticket cerrado o transición inválida) o 422 (valor fuera del catálogo), ENTONCES el error se mostrará sin perder la vista y sin dejar la interfaz en un estado inconsistente. Un ticket cerrado deshabilitará las acciones de prioridad, estado y asignación.
- RF-111: EL SISTEMA mostrará el seguimiento de HU-07 en el detalle: `GET /api/tickets/{id}/comments` para administrador, técnico y para el cliente en un ticket propio; solo administrador y técnico verán el formulario de alta de comentario y podrán enviarlo con `POST /api/tickets/{id}/comments`. El contenido se validará de 1 a 2000 code points tras recortar y el error del backend se mostrará sin perder el texto escrito.
- RF-112: La interfaz será accesible (WCAG 2.1 AA), estará en español, usará los estados de carga, vacío y error de la aplicación y se verificará con Vitest + Testing Library y `npm run build`. No se almacenarán contraseñas ni secretos y no se modificará el backend.

## Requisitos no funcionales

- **Accesibilidad**: etiquetas asociadas, errores anunciados (`role="alert"`), foco en el primer error, navegación por teclado y confirmaciones con `role="status"`.
- **Responsive**: formularios y detalle utilizables de 360 a 1440 px, sin tablas que desborden la pantalla.
- **Mantenibilidad**: cliente HTTP tipado, validaciones compartidas y textos centralizados en `lib/strings.ts`.
- **Pruebas**: Vitest + Testing Library con un cliente API falso; no se depende del backend real en las pruebas.
- **Seguridad**: la sesión viaja por cookie (`credentials: include`); no se guardan credenciales en el navegador.

## Casos límite

- Título vacío, solo espacios, de 200 code points o de 201; descripción vacía, solo espacios, de 5000 o de 5001.
- Diferencias entre longitud en code points y en unidades UTF-16 (emoji y caracteres fuera del plano básico).
- Doble clic en «Crear ticket»: una sola petición.
- Alta correcta con prioridad fallida: el ticket existe y el aviso lo explica.
- Backend caído o error de red: mensaje con opción de reintentar sin perder los datos escritos.
- 401 durante una operación: cierre de sesión global y vuelta a `/login`.
- Ticket cerrado: acciones de edición deshabilitadas y error 409 si se intenta igualmente.
- Transición de estado no permitida: 409 con el mensaje del backend.
- Prioridad o estado fuera del catálogo: 422 con el mensaje del backend.
- Técnico inexistente o identificador inválido en la asignación: error sin cambiar la vista.
- Ticket sin prioridad: el SLA se muestra como no disponible.
- Ticket sin comentarios: estado vacío con texto, sin error.
- Cliente en un ticket ajeno: 404 uniforme; la interfaz no revela su existencia.
- Cliente que intenta comentar: no ve el formulario y el backend responde 404 si se fuerza la petición.

## Fuera de alcance

- Editar título o descripción después del alta: no existe endpoint y HU-06 es de solo lectura.
- Crear tickets en nombre de otro usuario o elegir el solicitante.
- Adjuntos, menciones, notificaciones por correo y edición o borrado de comentarios (HU-07 los excluye).
- Reapertura de tickets cerrados e historial de cambios como interfaz propia (HU-08 y HU-09); se integrarán cuando se aborde su vista.
- Datos mock o etiqueta «Demo» en estas pantallas: toda la información viene del backend.
- Pruebas E2E con navegador; la verificación es Vitest + Testing Library y smoke manual.

## Criterios de finalización

- RF-105 a RF-108 verificados con las 10 pruebas existentes de `/tickets/nuevo` y las que se añadan para los casos límite.
- RF-109 a RF-111 verificados con pruebas del detalle, las acciones por rol, los errores 409/422 y los comentarios.
- `npm run test`, `npm run lint` y `npm run build` en verde.
- Smoke manual con las tres cuentas: cliente crea y consulta su ticket; técnico cambia prioridad, estado y comenta; administrador asigna y reasigna. Ejecutado el 2026-11-13 contra la API real (90 comprobaciones) y la interfaz real en Chrome headless (27), en verde.
- `tasks.md` y `MEMORY.md` actualizados; ninguna prueba se declara ejecutada sin serlo.

## Decisiones de alcance adoptadas

- **D1 — El cliente no elige prioridad ni guarda metadatos locales.** El backend solo permite fijarla a administrador y técnico; el formulario del cliente no simula una prioridad que el ticket no tiene. *Alternativa descartada: guardar la prioridad en `localStorage`*, que mostraría un dato que el backend no reconoce.
- **D2 — El título y la descripción son inmutables tras el alta.** Se muestran en modo lectura; no se ofrece un formulario de edición que el backend rechazaría. *Alternativa descartada: habilitar campos y descartar los cambios en silencio*, que confunde al usuario.
- **D3 — La edición se limita a los datos que el backend acepta.** Prioridad y estado para administrador y técnico; asignación solo para administrador; comentarios para administrador y técnico. *Alternativa descartada: edición genérica de cualquier campo*, que obligaría a cambiar el backend y saldría del alcance.
- **D4 — Sin datos mock.** Las pantallas de esta historia usan la API real; el seed «Demo» se reserva para las vistas que aún no tienen endpoint. *Alternativa descartada: mantener tickets de ejemplo en el detalle*, que mezclaría orígenes.
- **D5 — Verificación con Vitest + Testing Library y un cliente API falso.** Permite probar permisos, errores y estados sin depender del backend. *Alternativa descartada: pruebas E2E*, fuera del runner acordado.

## Dudas abiertas

- **Presentación del detalle (resuelta el 2026-11-13).** Se usa un modal accesible abierto desde la tabla, coherente con RF-53 y aprobado por el usuario. No se añade la ruta `/tickets/:id`.
- [NECESITA ACLARACIÓN] **Alcance de la reapertura.** El backend ya permite reabrir un ticket cerrado (`POST /api/tickets/{id}/reopen`, solo administrador), pero la tarjeta HU-22 no la incluye entre sus dependencias. Se deja fuera hasta confirmar si forma parte de esta interfaz o de HU-23/HU-24.
