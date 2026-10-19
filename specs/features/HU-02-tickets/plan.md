# Plan HU-02 — Crear y consultar tickets

Spec base: `specs/features/HU-02-tickets/spec.md` (Estado: borrador para revisión QA, veredicto QA APROBADO, 10 RF: RF-11 a RF-20).
Sin frontend hasta acordar runner. Verificación solo backend con pytest + TestClient de FastAPI.

## 1. Módulos y capas afectadas

Todo el cambio vive en el módulo `tickets` (`backend/app/modules/tickets/`), más el montaje del router en `backend/app/main.py` (`app.include_router(tickets_router)`). El módulo `identity` **no se modifica**: HU-02 solo consume su contrato de identidad autenticada. `assignment` y `sla` no se tocan.

| Capa | Contenido | RF que cubre |
|---|---|---|
| `domain/` | Entidad `Ticket` (`id`, `title`, `description`, `status`, `requester_id`, `created_at`) y constantes `TITLE_MIN_LENGTH = 1`, `TITLE_MAX_LENGTH = 200`, `DESCRIPTION_MIN_LENGTH = 1`, `DESCRIPTION_MAX_LENGTH = 5000`, `OPEN_STATUS = "Abierto"`. Reglas: `validate_title`/`validate_description` (valor de tipo cadena de texto, recorte con semántica `strip()` aplicado al validar y al almacenar, longitud 1-200 / 1-5000 contada en code points) y `is_valid_uuid_format`. | RF-12, RF-19 |
| `application/` | Casos de uso `create_ticket`, `list_my_tickets`, `get_my_ticket` y errores `TicketValidationError` (→ 422) y `TicketNotFoundError` (→ 404). Orquestan validación → generación de identificador, estado inicial y fecha/hora → persistencia, y el control de propiedad (un ticket ajeno se trata como inexistente). Ninguna regla de negocio fuera de aquí y del dominio. | RF-11, RF-13, RF-14, RF-15, RF-16, RF-17, RF-19, RF-20 |
| `infrastructure/` | `InMemoryTicketRepository` (mismo contrato y patrón que `InMemoryUserRepository` de `identity`): `add`, `find_by_id`, `list_by_requester` (orden descendente por `created_at`), `count`, `clear`, con singleton `get_ticket_repository()`. Sustituible por un adaptador PostgreSQL sin cambiar casos de uso ni interfaz. | RF-13, RF-15, RF-16, RF-17 |
| `interface/` | Router `POST /api/tickets`, `GET /api/tickets`, `GET /api/tickets/{ticket_id}`; esquemas Pydantic (`extra="forbid"`, `StrictStr` en título y descripción) y traducción de errores de aplicación a 422/404 (201/200 en los caminos válidos, 401 por la dependencia de identidad). Solo comunica: no decide ni valida reglas de negocio. | RF-11 a RF-20 (códigos y contrato HTTP) |

## 2. Contratos entre módulos y contrato HTTP

**Contrato reutilizado de `identity` (no se duplica):** la dependencia `get_current_user` de `app/modules/identity/interface/dependencies.py`, que devuelve `{"id", "email", "role"}` o eleva 401. El módulo `tickets` usa **solo `current["id"]`** como `requester_id`: no necesita nombre ni correo (RF-16 no expone datos personales) y nunca accede a las tablas internas de `identity` (regla de `AGENTS.md`). Como la dependencia se resuelve antes del cuerpo del handler, la autenticación se evalúa **antes** que la resolución del recurso: sin sesión válida la respuesta es 401 aunque el identificador sea inexistente o inválido (RF-18, D5).

**Contrato HTTP (cierra lo diferido en la spec sobre cuerpos y fecha/hora):**

- `POST /api/tickets` — cuerpo `{title, description}` con `extra="forbid"` y tipos `StrictStr` → **201** con `{id, title, description, status, created_at, requester_id}` (RF-11, RF-13, RF-14); **422** si se incumple cualquier regla de RF-12 (incluidos campos extra y valores de otro tipo JSON); **401** sin sesión válida (RF-18).
- `GET /api/tickets` — **200** con `[{id, title, status, created_at}]` (resumen, **sin** `description`), únicamente los tickets del usuario autenticado, ordenados por `created_at` descendente, sin paginación y sin filtros; los parámetros de consulta desconocidos se ignoran porque la operación no declara ninguno (RF-15); **401** sin sesión válida (RF-18).
- `GET /api/tickets/{ticket_id}` — **200** con `{id, title, description, status, created_at, requester_id}` (RF-16); **404** si el ticket no existe, si pertenece a otro usuario o si el identificador no tiene formato UUID válido (RF-17, D5); **401** sin sesión válida (RF-18).
- Cuerpo de error consistente `{"detail": <mensaje>}` en todos los rechazos, como en HU-01. Códigos de la historia: 201/200 en los caminos válidos y 401/404/422 en los rechazos (sin 400, RF y NFR de la spec).
- **`created_at`**: instante con zona UTC (`datetime.now(timezone.utc)`, D6), serializado en ISO 8601/RFC 3339 con offset y microsegundos, p. ej. `2026-10-17T12:34:56.123456+00:00`.
- **Detalle de implementación que hace cumplir el 404 de RF-17:** `ticket_id` se declara como `str`, **no** como `uuid.UUID`. Si se declarara `uuid.UUID`, FastAPI devolvería 422 al recibir un identificador mal formado, contradiciendo RF-17; el formato se valida en la aplicación y se traduce a `TicketNotFoundError`.

## 3. Modelo de datos y migración

**Modelo lógico del ticket** (contrato de persistencia; en memoria en HU-02 por decisión del usuario, ver D4): `id` (UUID, generado en la aplicación), `title` (texto, 1-200 code points tras el recorte), `description` (texto, 1-5000 code points tras el recorte), `status` (texto, siempre `Abierto` en HU-02), `requester_id` (identificador UUID del usuario, **valor opaco** del contrato de `identity`, sin datos personales), `created_at` (instante con zona UTC, generado por el sistema).

**Esquema destino PostgreSQL (orientativo y diferido: documenta el contrato al que deberá migrar el adaptador, no es un entregable de HU-02; alineado con `infra/docker-compose.yml`, PostgreSQL 16):**

| Columna | Tipo | Restricción |
|---|---|---|
| `id` | `uuid` | `PRIMARY KEY` |
| `title` | `varchar(200)` | `NOT NULL`, `CHECK (char_length(title) BETWEEN 1 AND 200)` |
| `description` | `text` | `NOT NULL`, `CHECK (char_length(description) BETWEEN 1 AND 5000)` |
| `status` | `text` | `NOT NULL DEFAULT 'Abierto'` (sin `CHECK` de catálogo: lo amplía HU-03) |
| `requester_id` | `uuid` | `NOT NULL`, valor del contrato de `identity` **sin clave foránea** hacia sus tablas |
| `created_at` | `timestamptz` | `NOT NULL DEFAULT now()` |

Índices y restricciones: `CREATE INDEX ix_tickets_requester_created_at ON tickets (requester_id, created_at DESC)` sirve el listado de RF-15 (acceso por solicitante con orden descendente por fecha de creación). No se crea índice único ni restricción de unicidad sobre título/descripción: los duplicados son válidos (RF-12.5). `char_length` en PostgreSQL cuenta caracteres (no bytes), coherente con RF-12.2.

**Estrategia de migración: decidida por el usuario (2026-10-17) — HU-02 mantiene la persistencia en memoria y no añade migraciones ni capa de persistencia real.** Comprobado en el código y la configuración actuales: no existe `backend/migrations/` ni carpeta equivalente en la raíz, `backend/requirements.txt` no incluye SQLAlchemy, Alembic ni driver de PostgreSQL, y HU-01 persiste usuarios y sesiones **en memoria** con repositorios singleton (`InMemoryUserRepository`, `InMemorySessionStore`) documentados como "sustituibles por un adaptador PostgreSQL sin cambiar el contrato". HU-02 replica exactamente ese patrón para tickets (`InMemoryTicketRepository` + `get_ticket_repository()`), de modo que el contrato del repositorio y el esquema destino de arriba quedan fijados y la migración futura sea un cambio de adaptador. La alternativa de introducir ahora la capa de persistencia (SQLAlchemy + Alembic + driver, migrando también `identity`) fue descartada por el usuario: añadiría dependencias nuevas no autorizadas por `AGENTS.md` y ampliaría el alcance de la historia (ver D4). Por tanto **el esquema destino de arriba es orientativo y diferido**: no se crean tablas, migraciones ni scripts, y no es un entregable de HU-02.

## 4. Decisiones justificadas (con alternativa descartada)

**D1. Identificador UUID generado en la aplicación (`uuid.uuid4()`), igual que en `identity` (RF-13).** *Alternativa descartada: esquema legible con prefijo y secuencia (`TCK-000001`)*, el del ejemplo del documento general: exige una secuencia coordinada (estado compartido y coordinación de concurrencia) para un valor que ningún RF necesita legible, y rompe la coherencia con los identificadores de usuario ya implementados; el usuario ya lo descartó en la spec.

**D2. Validación semántica en `domain`/`application`; el esquema HTTP solo exige presencia, tipo cadena (`StrictStr`) y `extra="forbid"` (RF-12).** El recorte (semántica `strip()`), los límites 1-200/1-5000 en code points y el valor recortado que se almacena viven en el dominio y el caso de uso, como exige la constitución 3 y como ya hace HU-01 (longitudes y trim en `domain/entities.py`). `StrictStr` hace explícita la ausencia de coerción desde otros tipos JSON. *Alternativa descartada: `min_length`/`max_length` de Pydantic sobre el valor crudo.* Rechazaría entradas válidas como `"  x  "` (5 caracteres antes del recorte, 1 después), pondría una regla de negocio en la capa de comunicación y duplicaría la verdad de RF-12 en dos sitios.

**D3. Estado inicial como constante de dominio `OPEN_STATUS = "Abierto"` asignada por el caso de uso (RF-11, RF-19).** *Alternativa descartada: aceptar `status` en el cuerpo con valor por defecto.* Permitiría fijar el estado desde fuera (prohibido por RF-12.4), haría indivisible el 422 de campos extra y adelantaría el catálogo de estados que pertenece a HU-03.

**D4. Persistencia en memoria con `InMemoryTicketRepository` (singleton + `clear()` para pruebas), mismo patrón y contrato que `InMemoryUserRepository`. Decisión del usuario (2026-10-17), no una recomendación del plan.** *Alternativa descartada: introducir ahora SQLAlchemy + Alembic + driver PostgreSQL y migrar también `identity`.* Añade tres dependencias no aprobadas (constitución 7; `AGENTS.md` exige preguntar antes de añadir dependencias), obliga a reescribir la persistencia de HU-01 dentro de una historia que no lo pide y ningún RF lo exige. Planteado como duda abierta 1 de este plan y resuelto por el usuario a favor de la persistencia en memoria, sin dependencias nuevas y sin tocar `identity`; el esquema PostgreSQL de la sección 3 queda como referencia orientativa para el futuro adaptador.

**D5. Ticket ajeno, inexistente o con identificador mal formado → un único `TicketNotFoundError` → 404, con `ticket_id` declarado como `str` (RF-17).** El formato se valida en la aplicación (`is_valid_uuid_format`), no en la firma de la ruta. *Alternativas descartadas: (a) declarar el parámetro como `uuid.UUID`,* que devolvería 422 ante un identificador mal formado, contradiciendo RF-17; *(b) devolver 403 cuando el ticket existe pero es ajeno,* que revelaría la existencia de tickets de otros usuarios.

**D6. `created_at` con `datetime.now(timezone.utc)`, almacenado con zona y serializado en ISO 8601/RFC 3339 con offset UTC y precisión de microsegundos** (cierra lo que la spec difirió al plan). *Alternativas descartadas: hora local sin zona,* ambigua e incomparable entre despliegues; *segundos sin microsegundos,* que introduce empates artificiales y hace el orden del listado menos fiel a RF-15 (aunque, por spec, un empate exacto no fija orden).

**D7. Reutilizar la dependencia `get_current_user` de `identity` como único punto de contacto, en lugar de resolver la cookie o la sesión dentro de `tickets`.** *Alternativa descartada: leer la cookie de sesión o los almacenes de `identity` desde `tickets`:* duplicaría la regla de "sesión válida" (expiración y revocación) en dos módulos y accedería a estructuras internas de otro módulo, prohibido por `AGENTS.md`.

**D8. Pruebas con el patrón ya existente en `backend/tests/`: inserción de `sys.path`, `TestClient(app)` desde `app.main` y fixture `autouse` por archivo que limpia repositorios, almacén de sesiones y cookies; sin `conftest.py` compartido.** *Alternativa descartada: crear `backend/tests/conftest.py` con fixtures centralizadas.* Obligaría a refactorizar los 8 archivos de HU-01 (fuera del alcance) y mezclaría una mejora de infraestructura de tests con esta historia; queda anotada como mejora futura, no como parte de HU-02.

## 5. Estrategia de pruebas (pytest + TestClient, sin frontend)

- Nuevos archivos en `backend/tests/`: `test_tickets_domain.py` (dominio: entidad, constantes, validación con recorte y fronteras, estado inicial `Abierto` y orden del listado, sobre el repositorio en memoria; RF-12, RF-13, RF-19), `test_tickets_create.py` (RF-11, RF-13, RF-14), `test_tickets_validation.py` (RF-12), `test_tickets_list.py` (RF-15, RF-18, RF-20), `test_tickets_detail.py` (RF-16, con los parámetros de consulta desconocidos ignorados), `test_tickets_not_found.py` (RF-17 y RF-18: 404 unificado, precedencia 401 > 404 y sesión expirada), `test_tickets_isolation.py` (RF-14, RF-19, RF-20) y `test_tickets_sweep.py` (barrido RF-11 a RF-20, con el mapa RF→test en la cabecera al estilo de `test_auth_security_sweep.py`).
- Preparación de sesión: registrar e iniciar sesión **por la API de HU-01** (reutilizando `POST /api/auth/register` y `POST /api/auth/login`) para obtener la cookie de sesión real; para el aislamiento se usan dos clientes con cookies propias y sesiones simultáneas.
- Limpieza: fixture `autouse` que limpia `get_user_repository()`, `get_session_store()`, `get_ticket_repository()` y las cookies de los clientes, antes y después de cada test (patrón de `test_auth_me.py`).
- Cobertura RF por RF: creación 201 con `id` UUID, `status="Abierto"`, `created_at` con zona UTC y `requester_id` tomado de la sesión y no del cuerpo (RF-11, RF-13, RF-14); matriz de RF-12: fronteras 1/200 y 1/5000 code points, 201/5001 fuera de rango, vacío o solo espacios tras el recorte, valores no textuales (número, booleano, objeto, lista, nulo) sin coerción, campos extra prohibidos, sin coerción de `requester_id`/`status`/`id`/`created_at` en el cuerpo y duplicados permitidos (RF-12); listado 200 con solo los propios, orden descendente por `created_at`, resumen sin `description`, lista vacía y parámetros de consulta desconocidos ignorados (RF-15); detalle 200 con los seis campos y sin nombre ni correo (RF-16); 404 en inexistente, con formato inválido y ajeno (RF-17); 401 en las tres operaciones sin sesión válida y precedencia 401 > 404 (RF-18); estado inmutable tras operaciones posteriores (RF-19); aislamiento con dos usuarios (RF-20).
- TDD por tarea: test en rojo primero y código mínimo hasta verde; no afirmar pruebas no ejecutadas. En PowerShell, ejecutar `pytest backend/tests/` sin tuberías (no existe `tail`).
- **Sin dependencias nuevas:** `pytest`, `httpx` (TestClient) y Pydantic (vía FastAPI) ya están en `backend/requirements.txt`.

## 6. Dudas abiertas

Sin dudas abiertas pendientes. La duda abierta 1 (capa de persistencia) quedó resuelta por el usuario el 2026-10-17: HU-02 mantiene la persistencia en memoria replicando el patrón de HU-01 (repositorio sustituible con `get_ticket_repository()` singleton y `clear()` para pruebas), sin dependencias nuevas (nada de SQLAlchemy, Alembic ni driver de PostgreSQL), sin tocar el módulo `identity` y sin migraciones; el esquema PostgreSQL de la sección 3 es solo referencia orientativa para el futuro adaptador. Ver D4.
