# Memoria del proyecto

## Estado actual

- HU-01 completa y mergeada a `develop` (PR #1, commit 42356dc): T1-T8 en verde.
- HU-02 (crear y consultar tickets): **T1-T8 en verde** (spec/plan/tasks aprobados). Falta PR/merge a `develop`.
- Suite actual: `pytest backend/tests/` → 183 passed (69 de HU-01 + 114 de HU-02: 19 T1 + 7 T2 + 32 T3 + 5 T4
  + 4 T5 + 14 T6 + 10 T7 + 23 T8). Modulo `tickets` cerrado para esta historia.
- Modulo `tickets` (`backend/app/modules/tickets/`, capas domain/application/infrastructure/interface): T1
  `domain/entities.py` + `infrastructure/ticket_repository.py`; T2 `create_ticket.py` + `interface/` (POST 201,
  montado en `app/main.py`); T3 solo tests; T4 `GET /api/tickets` con resumen `{id,title,status,created_at}`;
  T5 `get_ticket.py` + `GET /api/tickets/{ticket_id}` (`ticket_id: str`, no UUID); T6 `TicketNotFoundError` ->
  404 (mismo cuerpo para inexistente/formato invalido/ajeno, sin 422); T7 solo tests (aislamiento 2 sesiones +
  inmutabilidad de `status`); T8 `test_tickets_sweep.py` (mapa RF->test en la cabecera, composicion sobre
  `response.text`, duplicados, empates de fecha sin orden, rechazos solo 401/404/422). Codigos: 201/422/404.
  Precedencia 401 > 404 y 401 > 422: `get_current_user` se resuelve antes que el handler y que el cuerpo.
- Modulo `identity` cerrado: registro, login, sesiones en cookie, /me, logout.
- Hash Argon2id (`argon2-cffi==25.1.0`); email con `email-validator`.
- Rama actual: `feature/hu-02-tickets` (creada desde `develop` 42356dc).

## Decisiones tomadas (HU-02)

- Identificador: UUID opaco (`uuid.uuid4()`), coherente con HU-01.
- Estado inicial: constante de dominio `OPEN_STATUS = "Abierto"`; sin catalogo ni transiciones (HU-03/HU-08).
- Visibilidad: solo los tickets propios (RF-20). Listado: solo los del solicitante, `created_at` descendente,
  sin paginacion ni filtros; empate de fecha no fija orden.
- Resumen del listado `{id,title,status,created_at}` sin `description`; detalle con `{id,title,description,
  status,created_at,requester_id}` y sin datos personales.
- Validacion: titulo 1-200 y descripcion 1-5000 code points contados tras el recorte; recorte = `strip()` sin
  argumentos (no elimina U+200B) aplicado al validar y antes de almacenar. Tipo estricto (StrictStr) sin coercion.
- Duplicados permitidos (sin deduplicacion). Errores: 401/404/422, sin 400. 404 unificado (inexistente/ajeno/mal UUID).
- API: `identity` solo por `get_current_user` (tickets usa `current["id"]`); `identity` no se modifica.
- Persistencia **en memoria** (patron HU-01): sin SQLAlchemy/Alembic/driver, sin migraciones, sin dependencias nuevas.
- `created_at` con `datetime.now(timezone.utc)`, serializado con `datetime.isoformat()` en la interfaz (offset `+00:00` y microsegundos; no el formato por defecto de Pydantic).

## Errores que se deben evitar

- No inventar reglas de negocio ambiguas; marcarlas como pendientes.
- No acceder a tablas internas de otros modulos ni poner logica de negocio en los controladores HTTP.
- No afirmar pruebas no ejecutadas.
- En PowerShell no existe `tail`; usar pytest sin tuberias.
- Barridos: verificar el cuerpo crudo (`response.text`), no solo las claves del JSON.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON: no llamar `.json()`.
- `Ticket` (dataclass) tiene `status: str = OPEN_STATUS` al final (los campos con default van ultimos).
- Nota aceptada: los 422 de Pydantic devuelven `detail` como lista y los del dominio como string (como HU-01).

## Proximos pasos

- HU-02 cerrada: abrir PR de `feature/hu-02-tickets` -> `develop` y mergear.
- Siguiente HU del backlog (asignacion/SLA) con su propio spec -> plan -> tasks.
- Frontend pendiente de runner acordado; backend verificado con TestClient.
- `origin/feature/hu-01-authentication` sigue en remoto (solo se borro la rama local).
