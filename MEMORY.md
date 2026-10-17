# Memoria del proyecto

## Estado actual

- HU-01 completa en `feature/hu-01-authentication`: T1-T8 en verde.
- Suite final: `pytest backend/tests/` → 69 passed (8 archivos).
- Módulo `identity` cerrado: registro, login, sesiones en cookie, /me, logout.
- Hash Argon2id (`argon2-cffi==25.1.0`); email con `email-validator`.
- Spec HU-01: borrador con QA APROBADO; plan/tasks ejecutados al 100%.
- Rama actual: `feature/hu-01-authentication` (merge a `develop` pendiente).

## Decisiones tomadas

- Monolito modular: React + TypeScript, FastAPI, PostgreSQL.
- Módulos: identity, tickets, assignment, sla. Capas: domain/application/infrastructure/interface.
- Sesiones opacas de servidor en cookie HttpOnly (no JWT); huella SHA-256 en tabla `sessions`.
- Expiración por `expires_at` (401 igual que revocada); sin expiración deslizante.
- CORS con `allow_credentials=True`, orígenes explícitos; SameSite/Secure por env.
- `register_user`/`login_user`/`get_current_identity`/`logout_user` orquestan; interfaz solo comunica.
- Mapa RF→test en cabecera de `test_auth_security_sweep.py` (T8).

## Errores que se deben evitar

- No inventar reglas de negocio ambiguas; marcarlas como pendientes.
- No acceder a tablas internas de otros módulos.
- No poner lógica de negocio en controladores HTTP.
- No afirmar pruebas no ejecutadas.
- En PowerShell no existe `tail`; usar pytest sin tuberías.
- Barrido RF-9: verificar cuerpo crudo (`response.text`), no solo claves del JSON.
- Logout 204 devuelve cuerpo vacío (`b""`), no JSON: no llamar `.json()`.

## Próximos pasos

- Revisar HU-01 (reviewer) y mergear `feature/hu-01-authentication` → `develop`.
- Iniciar siguiente HU (tickets u otra según prioridad del equipo).
- Frontend pendiente de runner acordado; backend verificado con TestClient.
