# Plan HU-12 — Dashboard de cumplimiento de SLA

Spec base: `specs/features/HU-12-sla-dashboard/spec.md` (aprobada; RF-93 a RF-104).
Alcance: agregación real de SLA sobre los tickets, contrato HTTP y panel en `/`. Sin configuración de SLA (HU-14), sin alertas (HU-10/HU-16) y sin datos mock.

## 1. Módulos y capas afectadas

| Capa | Módulo | Cambio |
|---|---|---|
| `interface` | `tickets` | `sla_contract.py`: vista mínima de lectura (id, prioridad, estado, `created_at`, `resolved_at`, `resolved_target_minutes`, técnico). |
| `application` | `sla` | `dashboard.py`: agrega el cumplimiento por rol y periodo reutilizando `calculate_ticket_sla`. |
| `interface` | `sla` | `dashboard_router.py` y esquemas de respuesta; inyecta la vista de tickets en la agregación. |
| `main` | — | Registra el router del dashboard de SLA. |
| `frontend` | — | Servicio, hook, donut, leyenda y selector de periodo en `/`. |

No se modifican `tickets/domain`, `tickets/application/update_ticket_status` ni `sla/domain`: HU-05 y HU-14 ya aportan `Ticket.resolved_at`, `Ticket.resolved_target_minutes`, `calculate_ticket_sla`, `target_minutes_for`, `RISK_THRESHOLD_RATIO`, `TicketSlaSnapshot` y los estados `en_tiempo`, `en_riesgo`, `cumplido` e `incumplido`.

El cálculo vive en `sla`; `tickets` solo expone una vista de lectura a través de su contrato. `sla` no importa el repositorio ni el dominio de `tickets`: la capa `interface` de `sla` conecta ambos contratos.

## 2. Reutilización del cálculo existente (RF-95 a RF-97)

- `calculate_ticket_sla(snapshot, now)` resuelve el objetivo vigente con `target_minutes_for(priority)` (configuración de HU-14) y delega en `calculate_sla`.
- `TicketSlaSnapshot` aporta `priority`, `created_at`, `resolved_at` y `resolved_target_minutes`.
- `calculate_sla` decide el estado con las reglas de HU-05:
  - resuelto: `cumplido` si `resolved_at <= due_at`; `incumplido` si es posterior;
  - activo: `incumplido` si `now >= due_at`; `en_riesgo` si queda un 20 % o menos del objetivo; `en_tiempo` en el resto.
- El objetivo de un ticket resuelto se congela con `resolved_target_minutes`; un cambio posterior de la configuración no lo mueve. Si se cambia la prioridad de un resuelto, `set_ticket_priority` lo re-congela con la configuración vigente para la nueva prioridad (HU-14).
- No se crea un `evaluate_sla` paralelo ni se duplica la política. El umbral `threshold_percent` se deriva de `RISK_THRESHOLD_RATIO` (20).

## 3. Contrato de lectura de tickets (RF-100)

`tickets/interface/sla_contract.py` expone:

```python
@dataclass(frozen=True)
class SlaTicketView:
    id: str
    priority: str | None
    status: str
    is_resolved: bool
    created_at: datetime
    resolved_at: datetime | None
    resolved_target_minutes: int | None
    assignee_id: str | None


def list_sla_tickets() -> list[SlaTicketView]: ...
```

- Solo lectura; no expone título, descripción, solicitante, correo ni credenciales.
- `is_resolved` lo deriva el contrato del estado del ticket; la agregación de `sla` no compara nombres de estado.
- Toma una instantánea del repositorio de tickets; no muta nada.
- El router de SLA mapea cada `SlaTicketView` a la estructura de la agregación; la capa `application` de `sla` no importa `tickets`.

## 4. Contrato HTTP (RF-93 a RF-101)

`GET /api/dashboard/sla?days=7|30|90`

- `days` opcional, por defecto 30; se valida como entero con `Annotated[int, AfterValidator]` y produce 422 para valores fuera de 7/30/90.
- Sesión válida obligatoria (401).
- Rol `administrador`: todos los tickets del periodo.
- Rol `tecnico`: solo los asignados a él.
- Rol `cliente`: 404 uniforme.
- Periodo: `created_at` entre `generated_at - days` y `generated_at`, incluido el límite inferior; se excluyen fechas futuras.

Respuesta 200:

```json
{
  "total_evaluated": 10,
  "en_tiempo": 6,
  "en_riesgo": 1,
  "cumplido": 2,
  "incumplido": 1,
  "sin_sla": 3,
  "compliance_percentage": 80.0,
  "closed_without_resolved_at": 0,
  "threshold_percent": 20,
  "period_days": 30,
  "by_priority": [
    {"priority": "Crítica", "en_tiempo": 1, "en_riesgo": 0, "cumplido": 1, "incumplido": 0, "compliance_percentage": 100.0},
    {"priority": "Alta", "en_tiempo": 2, "en_riesgo": 1, "cumplido": 0, "incumplido": 1, "compliance_percentage": 50.0},
    {"priority": "Media", "en_tiempo": 3, "en_riesgo": 0, "cumplido": 1, "incumplido": 0, "compliance_percentage": 100.0},
    {"priority": "Baja", "en_tiempo": 0, "en_riesgo": 0, "cumplido": 0, "incumplido": 0, "compliance_percentage": 0.0}
  ],
  "generated_at": "2026-11-02T12:00:00+00:00"
}
```

Reglas:

- `total_evaluated = en_tiempo + en_riesgo + cumplido + incumplido` (RF-98).
- `compliance_percentage = round((en_tiempo + cumplido) / total_evaluated * 100, 2)` o `0.0` si el denominador es cero (RF-98).
- `by_priority` contiene las cuatro prioridades siempre; la suma de sus estados es `total_evaluated` (RF-99).
- `sin_sla` cuenta los tickets sin prioridad; no entra en `total_evaluated` (RF-95).
- `closed_without_resolved_at` informa los cerrados sin fecha (RF-97).
- `total_evaluated + sin_sla` coincide con los tickets del alcance creados en el periodo; es un subconjunto del total de HU-11, que no filtra por periodo (RF-100).

## 5. Agregación (RF-94, RF-98 a RF-101)

`get_sla_dashboard(actor_id, actor_role, tickets, now, days=30)`:

1. Valida el rol (`administrador` o `tecnico`); otro rol lanza `SlaDashboardAccessDeniedError`.
2. Fija `generated_at = now or datetime.now(timezone.utc)` y el inicio del periodo.
3. Filtra por rol y por periodo (`created_at` entre el inicio y `generated_at`, incluido el inicio).
4. Para cada ticket:
   - sin prioridad: incrementa `sin_sla`;
   - `Resuelto`/`Cerrado` sin `resolved_at`: incrementa `cumplido` y `closed_without_resolved_at`;
   - resto: construye `TicketSlaSnapshot` y llama a `calculate_ticket_sla(..., now=generated_at)`; acumula el estado devuelto.
5. Acumula totales y `by_priority` en la misma pasada.
6. Calcula porcentajes con protección de denominador cero.
7. Devuelve el DTO con `generated_at`, `period_days` y `threshold_percent`.

Una sola pasada; sin persistencia y sin escritura.

## 6. Interfaz (RF-102 a RF-104)

- `SlaCompliancePanel` dentro de `/`, después de las distribuciones de HU-11 y antes de los recientes.
- Donut SVG (sin librería de gráficos) con el porcentaje al centro; segmentos por estado y leyenda con texto y conteos (no solo color).
- Selector 7/30/90 días con 30 por defecto; al cambiar, TanStack Query recarga el panel con esqueleto usando `useSlaDashboard(days)`.
- Nota «{n} tickets sin SLA (sin prioridad) excluidos del cálculo» y, si aplica, «{n} cerrados sin fecha de resolución».
- Estados: `Skeleton`, vacío «No hay tickets evaluables en este periodo», `ErrorState` con «Reintentar»; 401 → logout.
- Responsive: donut y leyenda apilados en móvil; el panel ocupa una tarjeta en escritorio.
- Sin `DemoBadge`: datos reales.

## 7. Estrategia de pruebas

Backend (`pytest` + `TestClient`):

- Reutilización: el dashboard usa la configuración vigente de HU-14 en tickets activos y conserva `resolved_target_minutes` en resueltos; no se repiten las pruebas de `resolved_at` ni del dominio SLA, ya cubiertas por HU-05/HU-14.
- Agregación: porcentajes, `by_priority` con ceros, `sin_sla`, `closed_without_resolved_at`, periodo 7/30/90, límites del periodo y dataset vacío.
- API: 401, 404 para cliente, 200 admin/técnico, 422 para `days` inválido, invariantes y `generated_at`.
- Contrato: la vista no expone descripción, solicitante ni datos personales.
- Consistencia con HU-11: `total_evaluated + sin_sla` coincide con los tickets del alcance creados en el periodo.

Frontend (Vitest + Testing Library):

- `dashboard.api` y `useSlaDashboard` con `FakeApiClient`: éxito, cambio de periodo, 401, 404 y error.
- `SlaCompliancePanel`: porcentaje, leyenda, nota de `sin_sla`, estados de carga/vacío/error y accesibilidad.
- Integración en `/`: panel junto al dashboard de HU-11 sin romper sus pruebas.
- `npm run test` y `npm run build`.

## 8. Cobertura RF por parte

| Parte | RF |
|---|---|
| Reutilización del SLA de HU-05/HU-14 | RF-95, RF-96, RF-97 |
| Contrato de tickets | RF-100 |
| Agregación y porcentajes | RF-94, RF-98, RF-99, RF-101 |
| Router y autorización | RF-93, RF-94 |
| Panel y selector | RF-102 |
| Estados, accesibilidad y datos reales | RF-103, RF-104 |

## 9. Decisiones justificadas

- **D1. El cálculo vive en `sla` y se reutiliza.** Es la responsabilidad del módulo y evita duplicar la política. *Alternativa descartada: crear un `evaluate_sla` nuevo*, duplica reglas ya probadas en HU-05/HU-14.
- **D2. `resolved_at` ya existe.** HU-05 lo registra y lo limpia; HU-12 solo lo consume. *Alternativa descartada: añadirlo otra vez*, sería redundante y rompería la historia ya mergeada.
- **D3. La política vigente la administra HU-14.** HU-12 lee la configuración en cada consulta mediante `target_minutes_for`; no la cachea ni la duplica. *Alternativa descartada: fijar 2/4/12/24 h en el dashboard*, dos fuentes de verdad.
- **D4. Umbral del 20 % desde `RISK_THRESHOLD_RATIO`.** La UI no duplica la regla y el valor queda auditable. *Alternativa descartada: hardcodear 20 % en el frontend*, dos fuentes de verdad.
- **D5. Contrato de lectura de tickets.** `tickets/interface/sla_contract.py` mantiene el desacoplamiento y evita que `sla` acceda al repositorio de tickets. *Alternativa descartada: importar `InMemoryTicketRepository` desde `sla`*, rompe la separación de módulos.
- **D6. Donut SVG sin Recharts.** Un solo gráfico no justifica la dependencia; el SVG es accesible y ligero. *Alternativa descartada: Recharts*, añade peso y configuración para un elemento simple.
- **D7. Panel dentro de `/`.** Coherente con ADR-001 y evita una ruta nueva. *Alternativa descartada: `/sla/cumplimiento`*, duplica el dashboard y confunde con la configuración de HU-14.
- **D8. Datos reales desde la fuente en memoria.** Mismo criterio que HU-11; la integración con PostgreSQL es una tarea aparte. *Alternativa descartada: leer `ticket_sla` directamente*, hoy no está sincronizado con los tickets.
- **D9. `closed_without_resolved_at` como salvaguarda.** Los tickets antiguos sin fecha no se ocultan ni se inventan. *Alternativa descartada: asumir que todos cumplieron*, oculta incumplimientos.

## 10. Riesgos y supuestos

- **`resolved_at` en tickets antiguos**: si faltara, se cuenta como cumplido y se informa en `closed_without_resolved_at`.
- **Cambio de política**: los tickets activos se recalculan con la configuración vigente; los resueltos conservan `resolved_target_minutes`. Un cambio de prioridad en un resuelto lo re-congela con la configuración vigente.
- **Zonas horarias**: todas las fechas se normalizan a UTC; la UI presenta en la zona del usuario.
- **Periodo**: el panel usa 30 días por defecto; un ticket de hace 31 días no aparece aunque siga abierto. Es el comportamiento acordado.
- **Dependencia de HU-11/HU-21**: el panel se integra en la misma página y reutiliza sus componentes y su cliente HTTP.
- **Contrato de tickets**: la vista debe mantenerse mínima; cualquier campo nuevo requiere revisar la separación de módulos.

## 11. Dudas abiertas

- Ninguna. Si el equipo decide una ruta propia para el detalle de SLA, se actualiza la spec y este plan antes de implementar.
