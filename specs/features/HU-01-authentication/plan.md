# Plan HU-01 — Registro e inicio de sesión de usuarios

Spec base: `specs/features/HU-01-authentication/spec.md` (Estado: borrador, veredicto QA APROBADO, 10 RF).
Sin frontend hasta acordar runner. Verificación solo backend con pytest + TestClient de FastAPI.

## 1. Módulos y capas afectadas

Todo el cambio vive en el módulo `identity` (`backend/app/modules/identity/`). Ningún otro módulo se toca; `tickets`, `assignment` y `sla` solo consumirán el contrato de la sección 2 cuando lo necesiten.

| Capa | Contenido | RF que cubre |
|---|---|---|
| `domain/` | Entidades `User` (id, name, email normalizado, password_hash, role) y `Session` (id, user_id, token_hash, created_at, revoked_at, expires_at con tiempo de vida máximo). Reglas de normalización: email con trim + comparación case-insensitive; contraseña intacta sin trim. Constantes de longitud (nombre 2-100 tras trim, email ≤254, contraseña 8-128). Sesión expirada (`now >= expires_at`) se trata como inválida igual que revocada (401); `expires_at` permite además purga futura de la tabla. | RF-3, RF-4, RF-5, RF-9, RF-10 |
| `application/` | Casos de uso `register`, `login`, `get_current_identity`, `logout`. Orquestan validación → unicidad → hash/verificación → creación/invalidación de sesión. Ninguna regla de negocio fuera de aquí y del dominio. | RF-1, RF-2, RF-4, RF-5, RF-6, RF-8, RF-10 |
| `infrastructure/` | `UserRepository` (persistencia con unicidad de email case-insensitive también a nivel de persistencia), `SessionStore` (tabla `sessions`), adaptador de hash Argon2id, adaptador de validación sintáctica de email. | RF-4, RF-9, RF-10 |
| `interface/` | Router `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`. Esquemas Pydantic estrictos, dependencia `get_current_user`, traducción de errores de aplicación a códigos HTTP. Solo comunica, no decide. | RF-1, RF-2, RF-3, RF-5, RF-6, RF-7, RF-8 |

## 2. Contratos entre módulos y contrato HTTP

**Contrato hacia otros módulos (único punto de contacto):** dependencia `get_current_user` de `identity` que devuelve `{id, email, role}` o eleva 401. Los demás módulos nunca acceden a las tablas internas de `identity` (regla de `AGENTS.md`). Cubre RF-7 y RF-10.

**Contrato HTTP (definido aquí, cierra la duda abierta de la spec sobre cuerpos exactos):**

- `POST /api/auth/register` → 201 `{id, name, email, role}` (sin contraseña ni hash, RF-1, RF-9); 409 email duplicado case-insensitive (RF-4); 422 validación o rol ≠ cliente / rol omitido (RF-2, RF-3). Cuerpo de error consistente `{"detail": <mensaje>}` en todos los rechazos.
- `POST /api/auth/login` `{email, password}` con `extra="forbid"` → 200 `{id, name, email, role}` + cookie de sesión (RF-5); 422 solicitud estructuralmente inválida o con campos extra, sin comprobar credenciales (RF-6); 401 mismo mensaje genérico idéntico para email no registrado y contraseña incorrecta (RF-6).
- `GET /api/auth/me` → 200 `{id, email, role}` con sesión válida; 401 sin autenticación válida (RF-7).
- `POST /api/auth/logout` → siempre 204, con o sin sesión (idempotente, RF-8; única excepción al 401 de RF-7).

## 3. Decisiones justificadas (con alternativa descartada)

**D1. Sesiones opacas de servidor en cookie HttpOnly (cierra la duda RF-10).** Token aleatorio (`secrets.token_urlsafe`, ≥32 bytes) cuya huella SHA-256 se guarda en la tabla `sessions`; la cookie (`HttpOnly`, `Secure`, `SameSite=Lax`) solo transporta el token. Identifica usuario y rol por búsqueda de sesión → usuario (RF-10, RF-7). `logout` elimina o marca `revoked_at` la sesión: invalidación efectiva trivialmente verificable (RF-8). Cada sesión lleva además `expires_at` (tiempo de vida máximo): pasada esa marca se rechaza con 401 igual que una sesión revocada, de modo que la sesión no vive para siempre si el usuario olvida hacer logout, y la tabla admite purga futura por `expires_at`. Sin expiración deslizante complicada ni infraestructura extra: cumple seguridad e invalidación sin complejidad innecesaria (constitución 7). *Alternativa descartada: JWT stateless tipo Bearer.* Requiere denylist o rotación con TTL corto para invalidar, lo que añade complejidad y deja ventana donde la sesión "cerrada" seguiría válida, contradiciendo la invalidación efectiva simple de RF-8; además en localStorage aumenta exposición a XSS. *Alternativa descartada para expiración: sesiones sin `expires_at` (solo `revoked_at`).* Dejaría sesiones huérfanas válidas indefinidamente si no hay logout, sin criterio de purga.

**D2. Hash con `argon2-cffi` (Argon2id, `PasswordHasher` por defecto `Type.ID`), versión a fijar al implementar (referencia verificada vía Context7: `argon2-cffi`, p. ej. línea 23.1.x; el implementador pinnea la versión exacta vigente en requirements y la documenta).** Función diseñada para contraseñas, mantenimiento activo y documentación vigente (RF-9). *Alternativa descartada: bcrypt vía `passlib`/`bcrypt`.* Trunca a 72 bytes (riesgo con el límite de 128 de RF-3) e historial de mantenimiento más irregular; *y descartados los hashes rápidos* (SHA-256/bcrypt no: SHA-256/MD5) como sustitutos, prohibidos por RF-9.

**D3. Validación sintáctica de correo con biblioteca `email-validator` (versión exacta a pinnear al implementar), con trim previo y límite 254.** Verificable y mantenida frente a regex propia (RF-3). *Alternativa descartada: regex propia.* Frágil, no verificable como "biblioteca adecuada" y propensa a falsos positivos/negativos.

**D4. CORS con credenciales para la cookie de sesión (restricción ligada a D1).** El middleware CORS de FastAPI se configura con `allow_credentials=True` y orígenes explícitos (sin `allow_origins=["*"]` combinado con credenciales), porque la sesión viaja en cookie HttpOnly y el navegador solo la envía/recibe cross-site si el CORS la permite. Regla de despliegue: si frontend y backend quedan en dominios distintos (p. ej. `app.tu-dominio.com` y `api.tu-dominio.com`), la cookie llevará explícitamente `SameSite=None` y `Secure=True`; en mismo sitio se mantiene `SameSite=Lax` de D1. *Alternativa descartada: `allow_origins=["*"]` con `allow_credentials=True` o no activar credenciales.* El comodín con credenciales lo rechazan los navegadores (la cookie no viajaría) y, sin credenciales, el login parecería funcionar en TestClient pero fallaría en navegador real.

## 4. Estrategia de pruebas (pytest + TestClient, sin frontend)

- `backend/tests/test_auth_*.py` con `TestClient` de FastAPI sobre la app real y persistencia de prueba (SQLite en memoria o PostgreSQL efímero; la unicidad case-insensitive se prueba también a nivel de persistencia).
- TDD por tarea: test en rojo primero, luego código mínimo hasta verde; no afirmar pruebas no ejecutadas.
- Cobertura RF por RF: registro 201 sin hash en respuesta (RF-1); rol no-cliente u omitido → 422 sin crear usuario (RF-2); matriz de validación nombre/email/contraseña → 422 (RF-3); duplicado con mayúsculas → 409 (RF-4); login con email con espacios/mayúsculas → 200 y cookie, contraseña intacta (RF-5); login inválido estructural → 422 sin tocar credenciales, login válido con fallo → 401 con mensaje genérico idéntico en ambos casos (RF-6); `me` con/sin sesión y recurso protegido sin auth → 200/401 (RF-7); logout con sesión → 204 y sesión inutilizable después, logout sin sesión → 204 (RF-8); inspección de lo almacenado (no es la contraseña, `verify` acepta correcta y rechaza incorrecta) y barrido de respuestas sin `password`/`hash` (RF-9); identidad y rol derivados de la sesión en peticiones posteriores (RF-10).
- Casos añadidos por los ajustes (solo backend, pytest + TestClient, sin runner de frontend): sesión expirada (`now >= expires_at`) → 401 en `GET /api/auth/me` y en recurso protegido aunque la cookie exista y no esté revocada; configuración CORS verificada por inspección de la app (middleware con `allow_credentials=True`, sin comodín `*` con credenciales) más prueba de `Set-Cookie` con atributos HttpOnly y regla SameSite/Secure según despliegue (mismo sitio `Lax`; dominios distintos `SameSite=None; Secure`).
