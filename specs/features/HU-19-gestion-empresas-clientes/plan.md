# Plan HU-19 — Gestión de empresas clientes

Spec aprobada: `specs/features/HU-19-gestion-empresas-clientes/spec.md`, RF-125–RF-143 y RO-01/RO-02. HU-19 mantiene una única fuente de requisitos: este plan no añade RF, literales ni rutas distintas de las de RF-143. La entrega se ordena en dos bloques internos: **A** (backend, T1–T7) y **B** (interfaz y cierre operativo, T8–T10).

## 1. Orden y límites

| Orden | Bloque | Alcance | Dependencia |
|---|---|---|---|
| A | Backend de empresas | Migración y repositorio, dominio, contratos, casos de uso y rutas de datos, invitación/reenvío, asociación, bloqueo por empresa inactiva. | Ninguna. |
| B | Interfaz y cierre | Sección `/empresas`, semilla del administrador de plataforma, declaración del módulo `companies` en la documentación de arquitectura y regresión documentada. | A completo. |

Cada tarea empieza con pruebas focalizadas y termina con su comando de verificación. No se crean pantallas ni rutas de nivel superior distintas de `/empresas`; no se toca `backend/` ni `frontend/` en esta fase de planificación.

## 2. Módulos y capas afectadas

| Módulo/capa | Responsabilidad y RF cubiertos |
|---|---|
| `companies` (nuevo) — `domain` | Empresa como entidad propia: nombre y su forma normalizada, datos de contacto, estados `active`/`inactive`, reglas de rango y validación, mensajes de dominio. RF-126–RF-128, RF-131, RF-136, RF-139. |
| `companies` — `application` | Casos de uso: alta (con o sin administrador inicial), listado, ficha, actualización, cambio de estado, resolución de la rama de invitación/reenvío, asociación de cuentas y consulta de cuentas sin empresa. Orquesta los contratos ajenos; no conoce HTTP. RF-126–RF-137, RF-139–RF-143. |
| `companies` — `infrastructure` | Repositorio de empresas (PostgreSQL y fallback en memoria), normalización persistida, bloqueo transaccional de unicidad, migración `004_companies_management.sql`. RF-128, RF-129, RF-139. |
| `companies` — `interface` | Dependencias de alcance, esquemas Pydantic con campos extra rechazados, rutas de RF-143, contrato de estado de empresa hacia otros módulos y traducción de errores a los códigos y literales de RF-137. RF-125, RF-137, RF-143. |
| `identity` — `application`/`interface` | Invitaciones reutilizadas, creación del administrador inicial y de la cuenta invitada, asociación de una cuenta sin empresa, consulta de cuentas sin empresa, y bloqueo de altas y de aceptación en empresa inactiva. Contrato de cuentas hacia `companies`. RF-134–RF-136, RF-140, RF-141, RO-01, RO-02. |
| `tickets` — `application`/`interface` | Contrato de agregados por empresa (total y reparto por estado) y bloqueo de tickets nuevos en empresa inactiva antes de validar la entrada. RF-132, RF-136, RF-139. |
| Frontend existente | Sección `/empresas` sobre el armazón y las rutas actuales, cliente HTTP, hooks, textos y guards ya existentes. Solo refleja permisos. RF-125, RF-138, RF-142, RF-143. |
| Composición (`backend/app/main.py`) | Registro de las rutas nuevas y del contrato de estado en el arranque, manteniendo los límites modulares. RF-125, RF-143. |

**D-1 — Módulo nuevo `backend/app/modules/companies` con las cuatro capas (aprobado).**
La empresa es una entidad de negocio con ciclo de vida propio (datos de contacto, estado, unicidad, agregados) y con cuatro superficies HTTP que no son de cuenta. Ubicarla en `identity` mezclaría el catálogo de empresas con la gestión de cuentas, que HU-13 ya delimita, y haría crecer un módulo que hoy concentra autenticación, invitaciones, roles y directorio.

Como añadir un quinto módulo modifica la arquitectura acordada, la entrega incluye declararlo en la documentación de proyecto, dentro de T10: `docs/constitution.md` (punto 2, lista de módulos y su separación de responsabilidades) y `AGENTS.md` (sección «Stack y estructura», lista de `backend/app/modules/`, y sección «Arquitectura», responsabilidad de `companies` y sus límites con `identity` y `tickets`). No se cambia ningún otro principio ni regla.

Alternativas descartadas:

- **Dentro de `identity`**: obligaría a exponer desde `identity` rutas y reglas de empresa, y la frontera «`identity` gestiona cuentas, no empresas» se perdería. Además el contrato de cuentas que `companies` necesita quedaría dentro del mismo módulo, sin verificación posible de que no se accede a tablas internas.
- **Subpaquete `identity/companies/`**: mantiene el acoplamiento de despliegue y de autorización, y no deja claro qué módulo posee la tabla `companies` frente a las claves foráneas de `users`, `tickets` y `sla_policies`.
- **Renombrar `identity` a `companies`**: rompe rutas, imports, pruebas y la trazabilidad de HU-01/HU-13 sin aportar nada.

## 3. Contratos entre módulos

Regla única: **ningún módulo lee ni escribe las tablas de otro**. Toda relación pasa por un contrato en `interface/` que devuelve solo DTOs, igual que `sla/interface/contract.py` y `identity/interface/technicians_contract.py`. Un contrato **nunca importa el contrato de otro módulo**; la composición entre módulos ocurre en `companies/interface/router.py` y en `main.py`. Esa regla es la que evita ciclos de importación y se verifica con una prueba dedicada (T3).

| Dirección | Contrato | Contenido |
|---|---|---|
| `companies` → `identity` | `identity/interface/company_account_contract.py` | `get_company_account_stats(company_id)` → `{users_total, has_administrator, administrator_invitation_pending}`; `list_company_administrators(company_id)` → `[{id, created_at, status, invitation_status}]` en el orden determinista de RF-141; `invite_company_administrator(company_id, name, email, conn=None)`; `resend_company_administrator_invitation(company_id, conn=None)`; `associate_account(company_id, account_id, conn=None)`; `list_unassigned_accounts()` → `[{id, name, email, role, status}]`. RF-132, RF-134, RF-140, RF-141. |
| `companies` → `tickets` | `tickets/interface/company_ticket_contract.py` | `get_company_ticket_stats(company_id)` → `{tickets_total, by_status}` con las cuatro claves siempre presentes y exclusión de tickets sin empresa. RF-132, RF-143. |
| `identity` → `companies` | `companies/interface/company_status_contract.py` | `get_company_status(company_id)` → `active`, `inactive` o `None`; `company_exists(company_id)`. Solo lectura, sin entidades ni agregados. RF-134, RF-136, RF-141. |
| `tickets` → `companies` | `companies/interface/company_status_contract.py` | Igual que la fila anterior, usado al crear tickets. RF-136. |

Notas de implementación de los contratos:

- Los contratos `companies → identity` y `companies → tickets` viven en el módulo proveedor (patrón `technicians_contract.py`) y exportan funciones, no repositorios: `companies` no puede llamar a `get_user_repository()` ni a `get_ticket_repository()`.
- `invite_company_administrator`, `resend_company_administrator_invitation` y `associate_account` aceptan un `conn` opcional para participar en la misma transacción que el alta de empresa (T1/T5), reutilizando el parámetro `conn` que ya existe en `identity/application/invitations.py`.
- El contrato de estado no revela datos de la empresa: devuelve solo el estado o `None`, y quien lo consume traduce a su propio 404/409.
- DTOs inmutables (dataclasses `frozen`) para que ningún consumidor mute el agregado ajeno.

## 4. Persistencia

- **Migración nueva `backend/migrations/004_companies_management.sql`** (no se reescribe `001`, `002` ni `003`; el runner `migrations/run.py` la aplica después por nombre).
  - `ALTER TABLE companies ADD COLUMN IF NOT EXISTS email text, phone text, contact_name text, status text NOT NULL DEFAULT 'active', name_normalized text;`
  - Backfill de `status` a `active` (RF-139) y de `name_normalized` con la misma forma que el dominio: `lower(normalize(btrim(name), NFC))` de PostgreSQL (`CREATE EXTENSION IF NOT EXISTS ...` no es necesario: `normalize()` es función de cadena).
  - Restricciones: `status IN ('active','inactive')`; longitud de nombre no se impone por CHECK porque las empresas heredadas pueden quedar fuera de 2–100 (RF-139); `contact_name` y `phone` sin reglas nuevas.
  - Índice **no único** `companies_name_normalized_idx` sobre `name_normalized`, usado solo para localizar candidatos a duplicado.
- **D-2 — Unicidad del nombre en la capa de aplicación (aprobado).** El índice de `name_normalized` es no único por diseño: RF-139 tolera empresas preexistentes con nombres duplicados y prohíbe migrarlas o renombrarlas, de modo que la unicidad no puede depender de una restricción de esquema. Se garantiza en la capa de aplicación con `pg_advisory_xact_lock(hashtextextended(name_normalized, 0))` dentro de la transacción del alta o del cambio de nombre, igual que HU-13 resolvió la invariancia del administrador activo; sin PostgreSQL, el repositorio en memoria usa el mismo punto de serialización para unitarios. El bloqueo se adquiere con la forma normalizada de RF-128, nunca con el nombre en bruto.
- **Repositorio `companies/infrastructure/company_repository.py`** con el mismo patrón que `InMemoryUserRepository`: `add`, `find_by_id`, `list_all`, `update`, `remove` (solo para compensar un alta fallida), `count`, `clear`, singleton `get_company_repository()` y sincronización a PostgreSQL (`sync_persistent`, `load_persistent_for_update`) con el seam `HELPDESK_ALLOW_IN_MEMORY=1` para unitarios. Sin PostgreSQL configurado y sin ese seam, la operación falla: no hay fallback silencioso.
- **Alta atómica con administrador inicial (RF-135).** Una sola transacción: `INSERT` de empresa con `conn`, luego `invite_company_administrator(..., conn=conn)`. Si el correo está tomado, se hace rollback completo y no queda empresa; en el repositorio en memoria se compensa con `remove` en el `except`. La verificación cubre ambos modos.
- **SLA por defecto (RF-139).** El trigger `companies_seed_sla_policies` de `001` crea las cuatro políticas al insertar la empresa: el alta cumple RF-139 sin código adicional y no toca la configuración de otras empresas.

## 5. Autorización

- `companies/interface/dependencies.py` define dos dependencias sobre `get_current_user` (que ya eleva 401 antes de todo):
  - `require_platform_admin`: `role == "administrador"` y `company_id is None`; en caso contrario 404 `"company not found"`.
  - `require_company_admin`: `role == "administrador"` y `company_id` no nulo; en caso contrario 404 `"company not found"`.
- El alcance se deriva solo de la sesión: no existe rol nuevo ni parámetro de empresa enviado por el cliente. Supervisores, técnicos y clientes reciben el mismo 404 uniforme con cuerpo idéntico.
- `/api/companies/me` usa la empresa de la sesión sin aceptar identificador; se registra **antes** de `/api/companies/{company_id}` para que `me` nunca se interprete como identificador. `GET /api/users/unassigned` se registra antes de `/api/users/{user_id}` por la misma razón.
- La precedencia se materializa en el orden de dependencias y de validaciones, no en el controlador: dependencia de sesión/alcance (401/404) → esquema Pydantic (422 estructural) → caso de uso (409 → 422 de dominio). RF-137.
- Para el bloqueo por empresa inactiva en la creación de **tickets**, la comprobación va en una dependencia de ruta: FastAPI resuelve subdependencias antes de validar el cuerpo, por lo que el 409 precede al 422 de entrada, como exige RF-137. Se verifica con una prueba explícita.

## 6. Invitaciones y entrega de correo

- No se duplica lógica: `companies` llama a `identity`, que usa `issue_invitation` (token de un solo uso, hash, 168 h) y `send_invitation` (SMTP opcional) ya existentes. El token solo existe en memoria durante el envío y nunca entra en la respuesta HTTP.
- La resolución de la rama de RF-141 vive en `companies/application/manage_administrator_invitation.py` y usa `list_company_administrators` ordenado por `created_at` ascendente e `id` ascendente: aceptada + `active` → 409 `"la empresa ya tiene administrador"` sin leer el cuerpo; pendiente + `active` → reenvío (200); ninguna activa → invitación (201). El cuerpo de cada rama se valida después de resolverla.
- `email_status` proviene de `send_invitation`: `sent`, `failed` o `not-attempted` (RO-02). Se propaga tal cual; no cambia el código de éxito ni habilita el acceso. Las pruebas usan un doble del envío (`monkeypatch` de `send_invitation` o de `smtplib.SMTP`) y la ausencia de `SMTP_HOST`, sin servidor real.

## 7. Interfaces HTTP y frontend

| Método y ruta | Alcance | Respuesta | RF |
|---|---|---|---|
| `GET /api/companies` | plataforma | 200 array ordenado o `[]` | RF-129, RF-143 |
| `GET /api/companies/me` | administrador con empresa | 200 ficha | RF-142, RF-143 |
| `PATCH /api/companies/me` | administrador con empresa | 200 ficha | RF-131, RF-142 |
| `GET /api/companies/{company_id}` | plataforma | 200 ficha | RF-130, RF-143 |
| `POST /api/companies` | plataforma | 201 `{company}` o `{company, email_status}` | RF-126, RF-135, RF-143 |
| `PATCH /api/companies/{company_id}` | plataforma | 200 ficha | RF-131, RF-143 |
| `PUT /api/companies/{company_id}/status` | plataforma | 200 ficha, idempotente, sin 409 | RF-136, RF-143 |
| `POST /api/companies/{company_id}/administrator/invitation` | plataforma | 200 o 201 `{company, email_status}` | RF-141, RF-143 |
| `PUT /api/companies/{company_id}/accounts/{user_id}` | plataforma | 200 `{company}` | RF-134, RF-143 |
| `GET /api/users/unassigned` | plataforma | 200 array o `[]` | RF-140, RF-143 |

Errores: los códigos, literales y precedencias de RF-137, sin añadir ninguno. Las dos secuencias quedan separadas: rutas de datos de empresa (401 → 404 → 422 estructural → 409 de unicidad → 422 de dominio), RF-141 con su propia secuencia, y las superficies de usuarios replicando HU-13. `PUT …/status` no produce 409.

Frontend (RF-138), sin rutas nuevas de nivel superior:

- `frontend/src/pages/CompaniesPage.tsx` sustituye el `PlaceholderPage` de `/empresas` y contiene catálogo, ficha y formularios en la misma sección.
- `frontend/src/api/companies.api.ts` sobre `request` de `httpClient.ts`; `frontend/src/hooks/useCompanies.ts` con `@tanstack/react-query`, siguiendo `useTechnicians.ts`.
- `frontend/src/lib/strings.ts`: bloque `companies` (títulos, vacío, error, carga, acciones como «Invitar administrador», «Reenviar invitación» y los avisos de `email_status` de HU-13, reutilizados).
- `frontend/src/routes.tsx`: `/empresas` pasa a un `RequireRole allow={['administrador']}` propio, separándolo del grupo de supervisor y técnico. `permissions.ts` ya tiene `/empresas` solo para `administrador`; las redirecciones de supervisor/técnico a `/` y de cliente a `/mis-tickets` se mantienen con el mecanismo `firstAllowedRoute` existente.
- El administrador de empresa no ve el catálogo: la vista pide `GET/PATCH /api/companies/me`. La interfaz no decide la empresa de ningún recurso.

## 8. Estrategia de pruebas

- **Dominio (`pytest`)**: normalización del nombre (recorte, NFC, minúsculas, code points), rango 2–100, excepción de nombres heredados, correo 254 y minúsculas, teléfono 32, persona de contacto 2–100, `null` frente a cadena vacía y los ocho literales de dominio. RF-126–RF-128, RF-131, RF-137, RF-139.
- **Migración (`pytest`, se omite sin `DATABASE_URL`)**: `001`+`002`+`003`+`004` e instalación limpia; preexistentes en `active`; `name_normalized` coherente con el dominio; duplicados heredados siguen presentes; índice creado; fallo de migración deja el esquema intacto. RF-128, RF-139.
- **Contratos entre módulos**: forma exacta de los DTOs, exclusión de entidades, exclusión de tickets sin empresa y de cuentas con empresa en la consulta de sin empresa, orden determinista de administradoras, y prueba de que ningún contrato importa el contrato de otro módulo ni repositorios ajenos. RF-132, RF-134, RF-140, RF-141.
- **API (`pytest` + `TestClient`)**: un cliente por rol y por alcance (plataforma, administrador con empresa, supervisor, técnico, cliente, sin sesión), dos empresas con relaciones cruzadas, y comprobación de códigos, cuerpos exactos, `detail` lista frente a cadena y precedencias. RF-125–RF-143.
- **Concurrencia**: dos altas simultáneas con el mismo nombre y con el mismo correo de administrador inicial, con conexiones o repositorios independientes cuando haya PostgreSQL; como máximo un éxito y el resto 409, sin empresa huérfana. RF-128, RF-135.
- **Invitaciones**: tres ramas, orden determinista, rotación y 168 h, y `email_status` con doble de envío y sin configuración. RF-141, RO-02.
- **Interfaz (Vitest + Testing Library, sin dependencias nuevas)**: `/empresas` para ambos alcances de administrador, guardas de supervisor/técnico/cliente, estado vacío y de error reutilizados, ausencia de token o enlace en el DOM, y que no se añaden rutas de nivel superior. RF-125, RF-138, RF-142.
- Comandos de referencia: `cd backend` y `..\.venv\Scripts\python.exe -m pytest tests/test_companies_*.py -q`; `cd frontend` y `npm test`, `npm run build`, `npm run lint`. Ninguna prueba se declara ejecutada en esta fase.

## 9. Cobertura por bloque

| Bloque/parte | RF |
|---|---|
| A — esquema, repositorio y compatibilidad | RF-126, RF-128, RF-139 |
| A — dominio y errores de dominio | RF-126–RF-128, RF-131, RF-136, RF-137, RF-139 |
| A — contratos entre módulos | RF-132, RF-134, RF-136, RF-140, RF-141 |
| A — datos de empresa por HTTP | RF-125–RF-131, RF-135, RF-137, RF-142, RF-143 |
| A — invitación y reenvío | RF-135, RF-141, RO-02 |
| A — asociación y cuentas sin empresa | RF-133, RF-134, RF-140, RF-143 |
| A — estado y bloqueo por inactividad | RF-136, RF-141, RF-139 |
| B — interfaz | RF-125, RF-138, RF-142, RF-143 |
| B — operación y cierre | RO-01, RO-02, criterios de finalización |
| B — documentación de arquitectura | D-1: quinto módulo `companies` en `docs/constitution.md` y `AGENTS.md` |

## 10. Decisiones y alternativas descartadas

1. **Módulo nuevo `companies` (D-1, aprobado).** Alternativas descartadas en la sección 2; la aprobación arrastra la actualización de `docs/constitution.md` y `AGENTS.md` declarando el quinto módulo, incluida en T10.
2. **Contratos en el módulo proveedor, con DTOs y sin entidades.** Alternativa descartada: acceder a `users`/`tickets` desde `companies`, que rompe el aislamiento modular y hace imposible probar que no hay acceso cruzado. También se descarta inyectar puertos `Protocol` desde un módulo de composición: añade indirección sin resolver nada que los contratos actuales no resuelvan ya (constitución, punto 7).
3. **Unicidad en aplicación con bloqueo transaccional y persistencia de la forma normalizada (D-2, aprobado).** El índice de `name_normalized` es no único; la serialización por nombre normalizado se hace con `pg_advisory_xact_lock` y, en memoria, en el mismo punto de la aplicación, para que dos altas con el mismo nombre nunca coexistan ni se procesen fuera de orden.
4. **Reutilizar `identity/application/invitations.py`.** Alternativa descartada: reimplementar token, hash, expiración y envío en `companies`, que duplicaría reglas de HU-13 y abriría dos caminos para el mismo secreto.
5. **Alcance derivado de la sesión con dos dependencias (`require_platform_admin` y `require_company_admin`).** Alternativa descartada: un rol nuevo o un parámetro `company_id` de cliente, prohibidos por RF-125 y D1.
6. **`/empresas` con la sección existente y una guarda propia de administrador.** Alternativa descartada: rutas nuevas (`/empresas/{id}`) o confiar en el cliente para ocultar el catálogo.
7. **`pytest` + `TestClient` y Vitest/Testing Library ya instalados.** Alternativa descartada: añadir dependencias de prueba o usar pruebas manuales como evidencia.
8. **Verificación de correo con doble de envío y ausencia de configuración.** Alternativa descartada: exigir un servidor SMTP real para cerrar la historia (RO-02).

## 11. Riesgos y decisiones abiertas

- **Decisiones cerradas.** D-1 (módulo `companies`) y D-2 (índice no único sobre `name_normalized` más bloqueo transaccional por nombre normalizado) están aprobadas; T1 y T10 las implementan y documentan. No queda ninguna decisión de arquitectura pendiente de aprobación para empezar.
- **Dirección de dependencias.** `companies` importa contratos de `identity` y `tickets`, y esos módulos importan el contrato de estado de `companies`. No hay ciclo a nivel de archivo porque ningún contrato importa otro contrato; la prueba de T3 lo fija y cualquier import nuevo fuera de `interface/*_contract.py` debe rechazarse en revisión.
- **Persistencia dual.** Como el resto de módulos, la fuente de verdad en desarrollo es el repositorio en memoria; PostgreSQL valida el esquema y los invariantes de unicidad. La suite sin `DATABASE_URL` no prueba el advisory lock: esas pruebas se marcan como omitidas, nunca como aprobadas.
- **Atomicidad del alta con administrador** entre dos repositorios: en memoria se resuelve con compensación, en PostgreSQL con una única transacción. Cualquier camino nuevo debe cubrir el rollback con una prueba.
- **Precedencia en creación de tickets.** El 409 por empresa inactiva depende del orden de resolución de dependencias de FastAPI; si una versión cambiara ese orden, la prueba de precedencia falla y obliga a resolverlo en la dependencia, no en el cuerpo.
- **`companies` pasa a ser el dueño de la tabla `companies`**, ya referenciada por `users`, `tickets` y `sla_policies` desde `001`. No se renombran tablas ni claves foráneas; cualquier cambio de esquema futuro debe coordinarse con esos módulos.
- **Forma normalizada en dos lenguajes.** `name_normalized` se calcula en PostgreSQL y en Python. `normalize(…, NFC)` es equivalente, pero `lower()` depende de la configuración regional de la base; la prueba de T1 debe fijar la colación del entorno de pruebas y comparar una muestra de nombres (mayúsculas, acentos y `İ`) entre dominio y base. Si divergen, la forma autoritativa es la del dominio y el backfill debe calcularse desde la aplicación, no con `lower()` en SQL.
- **RO-01** introduce un script operativo nuevo (`backend/scripts/`), no una ruta: si el equipo prefiere ejecutarlo desde el arranque, debe decidirse antes de T9 porque cambia el modo de aprovisionamiento.
