# Tareas HU-02 — Crear y consultar tickets

Orden de dependencia. 20-30 min por tarea. Verificación con pytest + TestClient (sin frontend).
Estado inicial: todas pendientes (`[ ]`). Tests primero (en rojo), luego el código mínimo hasta verde.

- [x] **T1. Dominio y repositorio en memoria de tickets (entidad, constantes, validación, estado inicial y orden del listado).** RF-12, RF-13, RF-19
  - Hecho cuando: los tests de dominio pasan: título y descripción con 1, 200 y 5000 code points tras el recorte se aceptan, 201 y 5001 se rechazan, valores de otro tipo JSON se rechazan sin coerción, el valor almacenado es el recortado (semántica `strip()`), todo ticket nuevo tiene estado `Abierto` y `list_by_requester` devuelve solo los tickets del solicitante ordenados por `created_at` descendente; el repositorio es en memoria, con `get_ticket_repository()` singleton y `clear()` para pruebas, siguiendo el patrón de HU-01 y sin dependencias nuevas.
- [x] **T2. POST /api/tickets, camino feliz (201).** RF-11, RF-13, RF-14
  - Hecho cuando: con sesión válida, TestClient crea un ticket y obtiene 201 con `id` UUID, `title` y `description` recortados, `status="Abierto"`, `created_at` con zona UTC y `requester_id` igual al `id` de la sesión (nunca al valor enviado en el cuerpo); dos creaciones devuelven identificadores distintos.
- [x] **T3. Validación de la creación (422) y duplicados permitidos.** RF-12
  - Hecho cuando: ausente, vacío o solo espacios tras el recorte, fuera de las fronteras 1-200/1-5000, tipo JSON no textual (número, booleano, objeto, lista, nulo) y cualquier campo extra (`status`, `priority`, `assignee`, `requester_id`, `id`, `created_at` o inventado) devuelven 422 sin crear ticket; dos tickets con el mismo título y descripción se crean con 201 e identificadores distintos.
- [x] **T4. GET /api/tickets (listado).** RF-15, RF-18, RF-20
  - Hecho cuando: la lista devuelve 200 solo con los tickets del usuario autenticado, ordenados por `created_at` descendente, con resumen `{id, title, status, created_at}` sin `description`; sin tickets devuelve `[]`; `?status=Abierto&page=2` se ignora (mismo resultado y sin error); sin sesión válida devuelve 401.
- [x] **T5. GET /api/tickets/{ticket_id} (detalle).** RF-16
  - Hecho cuando: el detalle de un ticket propio devuelve 200 con `{id, title, description, status, created_at, requester_id}` y sin nombre, correo ni hash, con `status` igual al valor almacenado (`Abierto`) y `created_at` en ISO 8601 con offset UTC.
- [x] **T6. 404 unificado y precedencia 401 sobre 404.** RF-17, RF-18
  - Hecho cuando: ticket inexistente, identificador con formato inválido (`"no-es-uuid"`, `"123"`) y ticket de otro usuario devuelven los tres 404 con el mismo cuerpo de error, y sin sesión válida esos mismos casos devuelven 401 (nunca 404 ni 422).
- [x] **T7. Aislamiento entre usuarios e inmutabilidad del estado.** RF-14, RF-19, RF-20
  - Hecho cuando: con dos usuarios y dos sesiones simultáneas, el listado y el detalle de cada uno solo alcanzan sus propios tickets y ninguno aparece en los del otro; enviar `requester_id` en el cuerpo da 422 sin crear ticket; tras crear, listar y consultar repetidamente, el `status` de un ticket existente sigue siendo `Abierto`.
- [x] **T8. Barrido final RF-11 a RF-20 y suite completa.** RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19, RF-20
  - Hecho cuando: `pytest backend/tests/` pasa en verde (los 69 de HU-01 más los nuevos), `test_tickets_sweep.py` documenta el mapa RF→test en su cabecera y verifica la composición de las respuestas (resumen sin `description`; detalle con los seis campos y sin datos personales), los duplicados permitidos, los empates de fecha sin afirmar orden y que ningún rechazo usa 400.
