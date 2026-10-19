# Memoria del proyecto

## Estado actual

- HU-01 completa y mergeada a `develop` (PR #1, commit 42356dc).
- HU-02 completa (commit `a25380c`, rama publicada); PR a `develop` pendiente de abrir a mano (no hay `gh`).
- HU-03 (prioridad y estado): completa y validada por el reviewer (R1 aplicada: precedencia con JSON
  sintácticamente inválido; 520 passed); rama `feature/hu-03-priority-status` publicada en `origin`
  (commit `2c6e7b6`). PR a `develop` pendiente de abrir a mano (no hay `gh`).
- Suite actual: `pytest backend/tests/` -> **520 passed** (HU-01 + HU-02 revisada + HU-03; 11 del barrido T10).
- HU-03: catalogos exactos (`PRIORITIES`/`STATUSES`), `Ticket.priority` (`None`), `TicketModification`,
  log append-only, `provision_user`, `set_ticket_priority`/`update_ticket_status`, `get_modifiable_ticket`,
  `PUT /api/tickets/{id}/priority|status`, `priority` en listado/detalle/creacion y barrido RF-21..RF-30.
- Modulos: `identity` (registro/login/sesion/provision interna, sin endpoint), `tickets` (HU-02 + HU-03),
  `assignment` y `sla` aun sin implementar. Persistencia en memoria.

## Decisiones tomadas (HU-03)

- Prioridades `Crítica/Alta/Media/Baja`; estados `Abierto/En progreso/Resuelto/Cerrado`; coincidencia exacta.
- Prioridad no fijada = `null` (D3); creacion sigue naciendo `Abierto`, sin prioridad y rechaza `priority` con 422.
- Registro de cambios efectivos aparte (`InMemoryTicketModificationLog`), nunca expuesto ni en respuestas.
- Repetir el valor vigente -> 200 sin cambio ni registro. `Cerrado` inmutable en HU-03 (409).
- Precedencia 401 > 404 (permiso uniforme/resolucion) > 409 (cerrado) > 422 (cuerpo/catalogo), resuelta con
  dependencias antes del cuerpo. Sin 400 ni 403.
- El cuerpo de `PUT .../priority|status` se lee y valida en una dependencia declarada al final (no como
  parámetro): con JSON sintácticamente inválido también 401/404/409 preceden al 422 de decodificación.
- `provision_user` solo roles `tecnico`/`administrador`, reutiliza validaciones/hash/unicidad, sin operacion publica.
- Sin dependencias nuevas ni control de concurrencia; empates de `changed_at` no fijan orden.

## Errores que se deben evitar

- No inventar reglas ambiguas; marcarlas como pendientes.
- No acceder a estructuras/tablas internas de otros modulos ni poner logica de negocio en los HTTP.
- No afirmar pruebas no ejecutadas. En PowerShell no existe `tail`: pytest sin tuberias.
- Barridos: verificar cuerpo crudo (`response.text`/`json.loads`), no solo claves del JSON.
- Logout 204 devuelve cuerpo vacio (`b""`), no JSON.
- `Ticket` (dataclass): campos con default (`priority`, `status`) al final.
- 422 de Pydantic devuelven `detail` lista; los del dominio, string (aceptado desde HU-01).
- Un `TestClient` tiene una sola cookie: al iniciar sesion con otro usuario se reemplaza la anterior;
  para dos sesiones reales usar clientes distintos o iniciar sesion antes de las peticiones de cada rol.

## Proximos pasos

- HU-03: abrir el PR de `feature/hu-03-priority-status` -> `develop` a mano.
- HU-02: abrir tambien su PR pendiente a `develop`.
- Pendiente opcional (no bloqueante): bytes UTF-8 invalidos en el cuerpo de `PUT .../priority|status`
  devuelven 500 en vez de 422; el usuario decidio dejarlo pendiente.
- El usuario indico que ya no necesita HU-04 (asignacion) ni HU-05 (SLA).
