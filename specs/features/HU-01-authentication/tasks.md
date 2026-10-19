# Tareas HU-01 — Registro e inicio de sesión de usuarios

Orden de dependencia. 20-30 min por tarea. Verificación con pytest + TestClient (sin frontend).

- [x] **T1. Dominio y adaptadores base (entidades, normalización, hash Argon2id, validador de email).** RF-3, RF-9
  - Hecho cuando: `pytest backend/tests/test_auth_hash.py` verifica que lo almacenado no es la contraseña original, `verify` acepta la correcta y rechaza la incorrecta, con biblioteca y versión documentadas; la normalización de email (trim + case-insensitive) y los límites (nombre 2-100, email ≤254, contraseña 8-128 intacta) están probados en dominio; la entidad `Session` incluye `expires_at` (tiempo de vida máximo, base de la expiración que verifica T6).
- [x] **T2. POST /api/auth/register camino feliz (201 sin contraseña ni hash).** RF-1, RF-3
  - Hecho cuando: TestClient registra un cliente válido y obtiene 201 con `{id, name, email, role=cliente}` y ningún campo de contraseña/hash; entradas inválidas de RF-3 devuelven 422 sin crear usuario.
- [x] **T3. Rechazo de rol no-cliente u omitido en autorregistro (422).** RF-2
  - Hecho cuando: TestClient envía rol tecnico, administrador, otro valor y cuerpo sin rol, y cada caso devuelve 422 sin crear ningún usuario ni aplicar valor por defecto.
- [x] **T4. Unicidad de correo case-insensitive (409 + persistencia).** RF-4
  - Hecho cuando: TestClient registra un correo y el reintento con distintas mayúsculas devuelve 409; la persistencia rechaza el duplicado aunque se intente por debajo del caso de uso.
- [x] **T5. POST /api/auth/login (200/401/422, normalización y mensaje genérico).** RF-5, RF-6
  - Hecho cuando: TestClient inicia sesión con email con espacios/mayúsculas y contraseña correcta (200 + sesión); los casos estructuralmente inválidos y con campos extra devuelven 422 sin comprobar credenciales; email no registrado y contraseña incorrecta devuelven 401 con el mismo mensaje genérico idéntico.
- [x] **T6. Sesiones de servidor en cookie + GET /api/auth/me (200/401) + expiración y CORS.** RF-7, RF-10
  - Hecho cuando: TestClient obtiene 200 con identidad y rol en `GET /api/auth/me` con sesión válida, y 401 sin autenticación o con sesión inválida; un recurso protegido sin auth devuelve 401; una sesión con `expires_at` pasado devuelve 401 en `GET /api/auth/me` y en recurso protegido aunque la cookie exista y no esté revocada; la app expone el middleware CORS con `allow_credentials=True` (sin comodín `*` con credenciales) y la cookie de sesión sale con HttpOnly y la regla SameSite/Secure del despliegue (verificable vía pytest + TestClient inspeccionando la app y la cabecera `Set-Cookie`, sin runner de frontend).
- [x] **T7. POST /api/auth/logout idempotente con invalidación efectiva (204).** RF-8, RF-10
  - Hecho cuando: TestClient cierra sesión activa (204) y la sesión anterior deja de ser válida (`me` → 401); repetir logout sin sesión devuelve igualmente 204 sin error.
- [x] **T8. Barrido de seguridad y suite final RF-1 a RF-10.** RF-9, RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-8, RF-10
  - Hecho cuando: `pytest backend/tests/` pasa en verde, ninguna respuesta expone contraseñas ni hashes, y cada RF tiene su test asociado registrado en el informe de validación.
  - Validación T8 (2026-10-15): `pytest backend/tests/` → 69 passed (62 de T1-T7 + 7 nuevos en `test_auth_security_sweep.py`). Barrido RF-9: cuerpos 201/200 (/register, /login, /me) sin claves `password`/`hash` ni valor de la contraseña en texto crudo; errores 422/409/401 y 204 de logout igualmente limpios; lo almacenado es hash `$argon2` (verify ok). Mapa RF→test documentado en la cabecera de `test_auth_security_sweep.py`.
