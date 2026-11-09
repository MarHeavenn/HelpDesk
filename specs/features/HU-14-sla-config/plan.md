# Plan HU-14 — Gestión de configuración de SLA

Spec: `specs/features/HU-14-sla-config/spec.md` (aprobada)
Estado: implementado

## 1. Alcance técnico

Backend únicamente, en memoria y sin dependencias nuevas. La historia añade **dos operaciones** sobre la configuración global de SLA (`GET` y `PUT /api/sla/policies`), sustituye la lectura de la constante de HU-05 por la configuración administrable del repositorio en memoria y conserva intactos los contratos de HU-02 a HU-10. No se toca PostgreSQL, el frontend ni la autenticación. La UI de configuración queda para HU-20.

La configuración se guarda en minutos enteros, pero se **expone y edita en horas** con decimales. La conversión y la validación de regla viven en el dominio; la validación de forma (cuerpo, claves y tipos) en el esquema HTTP; la autorización en la aplicación. El controlador solo traduce errores a códigos HTTP.

| RF | Dónde se cubre |
| --- | --- |
| RF-71 | `sla/domain/policy_config.py` (catálogo ordenado y semilla) + `sla/infrastructure/sla_policy_repository.py` |
| RF-72 | `sla/application/manage_sla_policies.py` (listado ordenado) + `sla/interface/schemas.py` + `sla/interface/router.py` |
| RF-73 | `sla/application/manage_sla_policies.py` (reemplazo total) + `sla/interface/router.py` (`PUT`) |
| RF-74 | `sla/domain/policy_config.py` (conversión y reglas) + `sla/interface/schemas.py` (forma) + `router.py` (422) |
| RF-75 | `sla/interface/dependencies.py` + `sla/application/manage_sla_policies.py` (guardia de rol) |
| RF-76 | `sla/application/policies.py` + `sla/domain/entities.py` + `tickets/application/*` (congelación y derivación en vivo) |
| RF-77 | `sla/infrastructure/sla_policy_repository.py` (semilla, último escritor gana, contrato preparado para `company_id`) |
| RF-78 | Router aditivo, sin códigos nuevos, y pruebas de no regresión de HU-02 a HU-10 |

## 2. Estructura de archivos

```
backend/app/modules/sla/
  domain/policy_config.py                 NUEVO  SLA_PRIORITIES, DEFAULT_SLA_TARGET_MINUTES,
                                                 SlaPolicyValidationError, hours_to_minutes(),
                                                 validate_policy_targets()
  domain/entities.py                      MOD    TicketSlaSnapshot + resolved_target_minutes;
                                                 calculate_sla usa el objetivo congelado
  application/policies.py                 MOD    reexporta la semilla; target_minutes_for()
                                                 consulta el repositorio (no la constante)
  application/calculate_ticket_sla.py     MOD    `policies` inyectable para pruebas
  application/manage_sla_policies.py      NUEVO  guardia de rol, consulta y reemplazo
  infrastructure/sla_policy_repository.py NUEVO  InMemorySlaPolicyRepository + singleton
  interface/schemas.py                    NUEVO  SlaPolicyResponse, UpdateSlaPoliciesRequest
  interface/dependencies.py               NUEVO  require_sla_admin (401/404 antes del cuerpo)
  interface/router.py                     NUEVO  GET/PUT /api/sla/policies
  interface/contract.py                   SIN CAMBIOS de firma (get_ticket_sla(snapshot, now=None))
  infrastructure/__init__.py              SIN CAMBIOS

backend/app/modules/tickets/
  domain/entities.py                      MOD    Ticket + resolved_target_minutes (interno)
  application/update_ticket_status.py     MOD    congela el objetivo al resolver; lo limpia al reabrir
  application/set_ticket_priority.py      MOD    re-congela con la configuración vigente si está resuelto
  application/list_attention_tickets.py  MOD    pasa el objetivo congelado al snapshot (defensivo)
  interface/router.py                     MOD    _sla_response pasa resolved_target_minutes

backend/app/main.py                       MOD    registra el router de sla
```

No se crean esquemas nuevos de ticket ni se expone `resolved_target_minutes` en `TicketResponse` o `TicketSummaryResponse`: la composición observable de HU-05 no cambia (RF-44, RF-78).

## 3. Contrato HTTP

```
GET /api/sla/policies      (solo administrador)
PUT /api/sla/policies      (solo administrador; reemplazo total)
```

| Caso | Respuesta |
| --- | --- |
| `GET` administrador | 200 con `[{priority, hours}]` en orden `Crítica`→`Alta`→`Media`→`Baja`; solo lectura; parámetros desconocidos ignorados |
| `PUT` administrador con cuerpo válido | 200 con el array resultante; misma forma; reemplazo íntegro |
| Sin sesión válida | 401 (antes que cualquier otra resolución) |
| `cliente` o `tecnico` | 404 uniforme `{"detail": "not found"}`, también con cuerpo inválido |
| Cuerpo inválido | 422: lista de Pydantic para errores de forma; cadena para errores de regla |

Cuerpo del reemplazo (mapa de exactamente cuatro claves):

```json
{"Crítica": 2, "Alta": 4, "Media": 12, "Baja": 24}
```

Respuesta (semilla):

```json
[
  {"priority": "Crítica", "hours": 2},
  {"priority": "Alta", "hours": 4},
  {"priority": "Media", "hours": 12},
  {"priority": "Baja", "hours": 24}
]
```

- `hours` es `target_minutes / 60` (número, no cadena): `150` minutos → `2.5`; `30` → `0.5`.
- No se declaran parámetros de consulta ni paginación; los desconocidos se ignoran en silencio (RF-72, misma regla que RF-15/RF-66).
- No hay 403 ni códigos nuevos: 200, 401, 404 y 422 (RF-75, RF-78).
- **Precedencia**: `get_current_user` (401) → `require_sla_admin` (404) → validación del cuerpo (422). La guardia es una dependencia, así que un `cliente`/`tecnico` con cuerpo inválido recibe 404 y no 422, igual que la precedencia de HU-03/HU-06.

### Reparto de la validación (RF-74)

| Comprobación | Capa | Resultado |
| --- | --- | --- |
| El cuerpo no es un objeto, `{}`, falta una prioridad, clave extra, valor no numérico (cadena, booleano, `null`, lista, objeto), `NaN`/`Infinity` | `interface/schemas.py` (Pydantic) | 422 con `detail` lista |
| Valor numérico `<= 0` | `domain/policy_config.py` | 422 con `detail` cadena |
| Tras convertir, menos de 1 minuto (`0.001` h) | `domain/policy_config.py` | 422 con `detail` cadena |
| Conjunto de claves distinto del catálogo (defensivo) | `domain/policy_config.py` | 422 con `detail` cadena |

## 4. Reglas y capas

### 4.1 Dominio (`sla/domain/policy_config.py`)

- `SLA_PRIORITIES = ("Crítica", "Alta", "Media", "Baja")`: catálogo ordenado, coincidencia exacta con RF-21. `sla` no importa `tickets`; una prueba comprueba que ambas tuplas coinciden para evitar deriva.
- `DEFAULT_SLA_TARGET_MINUTES = {"Crítica": 120, "Alta": 240, "Media": 720, "Baja": 1440}`: **solo semilla** del repositorio (RF-71). Se traslada aquí desde `application/policies.py`, que lo reexporta para no romper los imports de HU-05.
- `class SlaPolicyValidationError(ValueError)`: error de regla de la configuración.
- `hours_to_minutes(hours: Decimal) -> int`:
  - exige `hours > 0` (si no, `SlaPolicyValidationError`);
  - `minutos = int((hours * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))`;
  - exige `minutos >= 1` (si no, `SlaPolicyValidationError`).
- `validate_policy_targets(values: Mapping[str, Decimal]) -> dict[str, int]`:
  - exige que el conjunto de claves sea exactamente `set(SLA_PRIORITIES)`;
  - convierte cada valor con `hours_to_minutes`;
  - devuelve el mapa **en orden de catálogo**.

`calculate_sla` y `TicketSla` no cambian de forma salvo lo indicado en el apartado 5 (objetivo congelado).

### 4.2 Repositorio en memoria (`sla/infrastructure/sla_policy_repository.py`, RF-77)

```python
class InMemorySlaPolicyRepository:
    def get_target_minutes(self, priority, company_id=None) -> int | None
    def get_all(self, company_id=None) -> dict[str, int]      # copia en orden de catálogo
    def replace(self, targets: Mapping[str, int], company_id=None) -> None
    def reset(self, company_id=None) -> None                  # vuelve a la semilla
```

- Semilla inicial = `DEFAULT_SLA_TARGET_MINUTES`; al arrancar el proceso vuelve a ella.
- `replace` construye un mapa nuevo y lo asigna de una vez: la configuración siempre se ve íntegra (sin mezclas parciales) y el **último escritor gana**.
- `get_target_minutes` es una lectura O(1) por prioridad; `None` para prioridad vacía o desconocida.
- El almacenamiento interno se clavea por ámbito (`dict[str | None, dict[str, int]]`), con un único ámbito global (`None`) en esta historia. `company_id` es un **kwarg opcional** que hoy no se usa: la integración multitenant podrá pasarlo sin romper a los consumidores, sin adelantar `company_id` ni PostgreSQL.
- `get_sla_policy_repository()` devuelve el singleton compartido, mismo patrón que `get_user_repository()`.

### 4.3 Aplicación

- `sla/application/policies.py`:
  - mantiene `DEFAULT_SLA_TARGET_MINUTES` como reexportación de dominio;
  - `target_minutes_for(priority, policies=None)` deja de leer la constante: resuelve contra `get_sla_policy_repository()` (o el repositorio inyectado) en cada llamada. `None`/prioridad desconocida → `None`.
- `sla/application/calculate_ticket_sla.py`: misma firma pública, con un `policies` opcional para inyectar el repositorio en pruebas. El contrato `get_ticket_sla(snapshot, now=None)` no cambia.
- `sla/application/manage_sla_policies.py`:
  - `SLA_POLICIES_NOT_FOUND_MESSAGE = "not found"`;
  - `class SlaPolicyAccessDeniedError(ValueError)`;
  - `ensure_sla_admin(actor_role)`: si el rol no es `administrador`, lanza `SlaPolicyAccessDeniedError("not found")` **antes** de leer o escribir;
  - `list_sla_policies(actor_role, policies) -> list[SlaPolicy]`: guardia y devuelve `SlaPolicy(priority, target_minutes)` en orden de catálogo;
  - `replace_sla_policies(actor_role, values, policies) -> list[SlaPolicy]`: guardia → `validate_policy_targets` → `policies.replace(...)` → lista resultante. Si la validación falla, no se escribe nada.
- La regla de autorización vive aquí, no en el controlador (constitución). La interfaz reutiliza `ensure_sla_admin` desde la dependencia.

### 4.4 Interfaz

- `sla/interface/schemas.py`:
  - `SlaPolicyResponse(BaseModel)`: `priority: str`, `hours: float`.
  - `UpdateSlaPoliciesRequest(BaseModel)` con `model_config = ConfigDict(extra="forbid")` y campos `Crítica`, `Alta`, `Media`, `Baja` de tipo `Decimal`. Un `field_validator("*", mode="before")` exige que cada valor sea un **número JSON** (`int`/`float`/`Decimal`, excluyendo `bool`) y finito; cadenas, booleanos, `null`, listas y objetos se rechazan con 422 de forma. La positividad y el mínimo de 1 minuto no se validan aquí.
- `sla/interface/dependencies.py`:
  - `require_sla_admin(current=Depends(get_current_user)) -> dict`: llama a `ensure_sla_admin(current["role"])` y traduce `SlaPolicyAccessDeniedError` a `HTTPException(404, detail="not found")`. Al ser dependencia, se resuelve antes del cuerpo → 401/404 > 422.
- `sla/interface/router.py`:
  - `router = APIRouter(prefix="/api/sla", tags=["sla"])`;
  - `GET /policies` y `PUT /policies`, ambos con `Depends(require_sla_admin)`;
  - `_policy_response(policy)` construye `SlaPolicyResponse(priority=..., hours=target_minutes / 60)`;
  - `PUT` captura `SlaPolicyValidationError` → 422 con `detail` cadena;
  - no hay lógica de negocio en el handler.
- `backend/app/main.py`: `app.include_router(sla_router)`.

## 5. Integración con `tickets` y congelación (RF-76)

- **Tickets activos** (`Abierto`/`En progreso`): `_sla_response` sigue llamando a `get_ticket_sla` con el `TicketSlaSnapshot`; `target_minutes_for` lee la configuración vigente en cada llamada. Un cambio de configuración se refleja en la siguiente consulta sin recalcular ni persistir nada: `due_at`, `remaining_minutes`, `status`, `near_due` y `breached` se derivan de nuevo.
- **Tickets `Resuelto`/`Cerrado` (congelados)**: con la configuración mutable, recalcular `due_at` con el objetivo vigente haría que un ticket ya resuelto cambiara de `cumplido` a `incumplido` al acortar el SLA, lo que rompe RF-46/RF-76. Para conservar la congelación sin persistir el SLA calculado:
  - `Ticket` gana un campo interno `resolved_target_minutes: int | None = None` (al final, con valor por defecto; no se expone en las respuestas);
  - al pasar a `Resuelto`/`Cerrado`, `update_ticket_status` calcula una vez el SLA con el instante de resolución (`changed_at`) y guarda su `target_minutes`; al reabrir borra `resolved_at` y `resolved_target_minutes`;
  - `TicketSlaSnapshot` gana `resolved_target_minutes: int | None = None`; `calculate_sla`, si hay `resolved_at` y ese objetivo congelado, lo usa para `due_at` y para el `target_minutes` devuelto (el SLA del ticket resuelto queda estable);
  - `_sla_response` pasa `ticket.resolved_target_minutes`; `list_attention_tickets` lo pasa también (solo procesa activos, así que es defensivo);
  - si a un `Resuelto` se le cambia la prioridad (HU-03 lo permite), `set_ticket_priority` recalcula el objetivo con la **configuración vigente en ese momento** para la nueva prioridad y actualiza `resolved_target_minutes`: el ticket queda re-congelado con el nuevo acuerdo, como pide RF-76;
  - un ticket sin prioridad sigue con `sla: null`; la configuración no le aplica.
- **Listado de atención (HU-10)**: no cambia; sigue usando `get_ticket_sla`, de modo que un cambio de configuración puede hacer entrar o salir tickets del listado sin recalcular historial.
- **Composición**: `TicketResponse` y `TicketSummaryResponse` no cambian; el nuevo campo es interno y no altera los conjuntos exactos de claves de los tests de HU-02 a HU-10.

## 6. Contratos y dependencias

- Dirección: `sla.interface → sla.application → sla.infrastructure/domain`; `tickets.interface/application → sla.interface → sla.application → sla.domain`. `sla` **no** importa `tickets`; `tickets` no lee la configuración directamente.
- `sla.interface` importa `identity.interface.dependencies` para la sesión, igual que `tickets`; `identity` no importa `sla` (sin ciclo).
- `get_ticket_sla(snapshot, now=None)` conserva su firma. `TicketSlaSnapshot` gana un campo opcional al final, retrocompatible con las construcciones posicionales existentes.
- `resolved_target_minutes` es un dato interno del ticket (como `resolved_at`), no un cambio del contrato HTTP.
- Sin acceso a repositorios o tablas de otros módulos; sin dependencias nuevas.

## 7. Decisiones técnicas

- **Lectura de la configuración en el cálculo**: `target_minutes_for` delega en el repositorio en memoria; así `calculate_ticket_sla` y `get_ticket_sla` no cambian y la configuración se resuelve en cada llamada (O(1)). *Alternativa descartada: que `contract.py` leyera el repositorio y pasara los minutos a la aplicación, lo que cambiaría la firma probada de `calculate_ticket_sla` o duplicaría en la interfaz la regla de prioridad ausente/desconocida.*
- **Congelación de resueltos**: guardar el objetivo aplicado al resolver (`resolved_target_minutes`) y re-congelarlo al cambiar la prioridad de un `Resuelto`. *Alternativa descartada: seguir calculando `due_at` con el objetivo vigente, que haría cambiar de estado a tickets resueltos al editar la configuración (incumple RF-46/RF-76); y un historial de versiones de política, que es auditoría (fuera de alcance) y no resuelve el «configuración vigente» al cambiar la prioridad.* Se guarda el objetivo (entrada), no el SLA calculado; los tickets activos siguen sin estado y se derivan en vivo.
- **Guardia de rol como dependencia**: 401 → 404 → 422, sin revelar el recurso a `cliente`/`tecnico` ni siquiera con cuerpo inválido. *Alternativa descartada: comprobar el rol dentro del handler, donde el 422 del cuerpo se produciría antes y filtraría la existencia de la operación.*
- **Reparto de la validación**: Pydantic para forma y tipos; dominio para positividad y mínimo de 1 minuto. *Alternativa descartada: validar todo en el controlador (prohibido por la constitución) o toda la regla en Pydantic (regla de negocio en la interfaz).*
- **`hours` como número `float`**: `target_minutes / 60`, con `150 → 2.5`. *Alternativa descartada: `Decimal` en la respuesta, que Pydantic serializa como cadena y rompería el contrato `hours: número`; o redondear a horas enteras, que perdería los minutos configurados.*
- **Reemplazo total**: `PUT` con las cuatro prioridades y `extra="forbid"`. *Alternativa descartada: actualización parcial, ya descartada en la spec.*
- **Alcance global y contrato preparado para `company_id`**: kwarg opcional e implementación por ámbitos con un solo ámbito `None`. *Alternativa descartada: introducir `company_id` ahora o cerrar la firma del repositorio sin margen para multitenant.*

## 8. Estrategia de pruebas

Sin pruebas de frontend (no hay runner acordado). Todo con pytest; las rutas con `TestClient` y sesiones reales (`provision_user` + login), con **un `TestClient` por rol** (una sola cookie por cliente). Cada tarea es TDD: test en rojo, implementación, `pytest` y `codegraph sync`.

| Archivo | Tipo | Cobertura |
| --- | --- | --- |
| `tests/test_sla_policy_domain.py` | unitario | RF-71, RF-74: catálogo ordenado e igual a `PRIORITIES` de `tickets`; semilla; `2→120`, `0.5→30`, `0.25→15`, `0.02→1`; `0.001→error`; `0`/negativo→error; `{}`, prioridad ausente, clave extra → error; `ROUND_HALF_UP` en el límite; no finitos |
| `tests/test_sla_policy_repository.py` | unitario | RF-71, RF-77: semilla de una instancia nueva; `get_target_minutes` por prioridad y `None`; orden de `get_all`; reemplazo total; último escritor gana; `reset`; instancia aislada; kwarg `company_id=None` aceptado |
| `tests/test_sla_calculation.py` (ampliar) | aplicación | RF-76: `target_minutes_for` y `get_ticket_sla` usan la configuración del repositorio; un cambio de configuración mueve `target_minutes`/`due_at`; prioridad ausente/desconocida sigue `None`; firma del contrato intacta |
| `tests/test_sla_policies_use_case.py` | aplicación | RF-72, RF-73, RF-74, RF-75: listado ordenado; reemplazo válido y persistido; idempotencia; errores de validación sin escritura; `cliente`/`tecnico` → `SlaPolicyAccessDeniedError("not found")` antes de tocar el repositorio |
| `tests/test_sla_policies_api.py` | API + `TestClient` | RF-72, RF-73, RF-74, RF-75, RF-78: semilla, orden, `hours` exactos, recarga, parámetros desconocidos ignorados, solo lectura, 401/404, 422 de forma y de regla, sin mutación, último escritor gana, sin 403 |
| `tests/test_sla_live_config.py` | API + aplicación | RF-76, RF-78: activo recalculado en vivo; resuelto/cerrado congelado; reapertura; cambio de prioridad de un `Resuelto` con configuración vigente; listado de atención; sin estado persistido en tickets activos |
| Regresión | suite existente | RF-76, RF-78: `test_sla_api.py` (se sustituye la prueba que exigía 404 en `/api/sla/policies`), `test_attention_api.py` (ajuste de la prueba de rutas inexistentes), `test_sla_domain.py`, `test_tickets_update_status.py`, `test_tickets_set_priority.py` |

Aislamiento y determinismo:

- La configuración es un singleton global: toda prueba que la mute usa un fixture `autouse` que llama a `get_sla_policy_repository().reset()` al inicio y al final. Se añade el mismo reset a los fixtures de `test_sla_api.py`, `test_attention_api.py` y `test_sla_calculation.py`.
- Los estados dependientes del reloj se fuerzan **envejeciendo** `created_at` del ticket en el repositorio (nunca durmiendo) y con márgenes amplios de horas; los límites exactos de conversión y del 20 % quedan en los tests de dominio.
- Los tests de API usan sesiones reales: un `TestClient` para cliente, otro para técnico, otro para administrador y otro para un segundo cliente.
- La congelación se prueba resolviendo por el caso de uso/API (para poblar `resolved_target_minutes`) y después cambiando la configuración por API.

## 9. Riesgos y mitigaciones

- **Cambio de estado de tickets resueltos al editar la configuración**: es el riesgo principal. Mitigación: objetivo congelado por ticket (apartado 5) y pruebas explícitas de `Resuelto`/`Cerrado`, reapertura y cambio de prioridad.
- **Pruebas existentes que asumen que `/api/sla/policies` no existe**: `test_sla_api.py` espera 404 para administrador y fallará en cuanto se registre el router. Mitigación: la tarea del `GET` sustituye esa prueba por el contrato nuevo; `test_attention_api.py` se ajusta porque un técnico sigue recibiendo 404, pero ya no por ausencia de ruta.
- **Fuga del estado del singleton entre pruebas**: mitigación con `reset()` en fixtures `autouse` de todos los archivos que mutan la configuración.
- **Precedencia 404/422**: mitigación con la guardia como dependencia y pruebas de las tres combinaciones (sin sesión, técnico con cuerpo inválido, administrador con cuerpo inválido).
- **Coerción de tipos en Pydantic**: en modo JSON, `Decimal` puede aceptar cadenas; mitigación con un validador `mode="before"` que exige número JSON y rechaza `bool`/no finitos.
- **Deriva del catálogo**: `sla` no puede importar `tickets`; mitigación con una prueba que compara `SLA_PRIORITIES` con `PRIORITIES`.
- **Reloj real en pruebas de API**: márgenes de horas y tickets envejecidos mediante mutación de `created_at`, como en HU-05/HU-10.
- **Cambio de contrato accidental**: no se añaden campos a `TicketResponse`/`TicketSummaryResponse`; los conjuntos exactos de claves de HU-02 a HU-10 deben seguir en verde.

## 10. Orden de implementación

1. Dominio de la configuración: catálogo, semilla, conversión y validación (RF-71, RF-74).
2. Repositorio en memoria con semilla y último escritor gana (RF-71, RF-77).
3. Cálculo con la configuración vigente, sin cambiar `get_ticket_sla` (RF-76).
4. Casos de uso de consulta y reemplazo con guardia de rol (RF-72, RF-73, RF-75).
5. Esquemas HTTP, `GET`, dependencia de rol y registro del router (RF-72, RF-75, RF-78).
6. `PUT` de reemplazo total y respuesta (RF-73, RF-74).
7. Pruebas de API de validación 422 y precedencias (RF-74, RF-75).
8. Congelación de `Resuelto`/`Cerrado` y re-congelación al cambiar prioridad (RF-76).
9. Efecto en vivo, listado de atención y ajuste de pruebas de regresión (RF-76, RF-78).
10. Verificación final, documentación, índice y cierre.

El detalle verificable de cada paso está en `tasks.md`.

## 11. Estimación

6–7 horas, repartidas en las 10 tareas de 20–40 minutos del orden anterior. La mayor parte del tiempo está en la congelación de resueltos y en las pruebas de precedencia y de recalculación en vivo.

## Notas para el coordinador

- La spec pide a la vez «sin estado persistido» y que un ticket resuelto no cambie al editar la configuración. Para cumplir lo segundo se guarda en el ticket el **objetivo aplicado al resolver** (un dato de entrada, como `resolved_at`), no el SLA calculado; los tickets activos siguen derivándose en vivo. Es una decisión no bloqueante, pero conviene que el equipo la conozca antes de implementar.
- El resto de decisiones de negocio ya están fijadas en la spec; no hay dudas nuevas que impidan empezar.
