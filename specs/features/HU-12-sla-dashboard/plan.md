# Plan HU-12 — Dashboard de cumplimiento de SLA

Spec base: `specs/features/HU-12-sla-dashboard/spec.md` (aprobada; RF-93 a RF-104).
Alcance: cálculo real de SLA sobre los tickets, contrato HTTP y panel en `/`. Sin configuración de SLA (HU-14), sin alertas (HU-10/HU-16) y sin datos mock.

## 1. Módulos y capas afectadas

| Capa | Módulo | Cambio |
|---|---|---|
| `domain` | `tickets` | `Ticket.resolved_at` (campo aditivo, `None` por defecto). |
| `application` | `tickets` | `update_ticket_status` fija o limpia `resolved_at` según el estado. |
| `domain` | `sla` | `sla.py`: política por defecto, umbral y evaluación de estados. |
| `application` | `sla` | `dashboard.py`: agrega el cumplimiento por rol y periodo. |
| `interface` | `tickets` | `sla_contract.py`: vista mínima de tickets para el módulo de SLA. |
| `interface` | `sla` | `dashboard_router.py` y esquemas de respuesta. |
| `main` | — | Registra el router del dashboard de SLA. |
| `frontend` | — | Servicio, hook, donut, leyenda y selector de periodo en `/`. |

El cálculo vive en `sla`; `tickets` solo expone una vista de lectura a través de su contrato. No se accede a las tablas internas de otro módulo.

## 2. Fecha de resolución (RF-97)

- `Ticket` añade `resolved_at: datetime | None = None` al final de la dataclass (compatible con las construcciones posicionales existentes).
- `update_ticket_status` usa el mismo `now` para `changed_at` y `resolved_at`:
  - Al pasar a `Resuelto` o `Cerrado`, si `resolved_at` es `None`, se fija con `now`.
  - Al volver a `Abierto` o `En progreso`, se limpia a `None`.
  - Un cambio no efectivo (mismo estado) no altera `resolved_at`.
- No se añade el campo a las respuestas HTTP de HU-02..HU-04 en esta historia; es interno para SLA. Si más adelante se expone, será un cambio aditivo y con su propia spec.

## 3. Evaluación de SLA (RF-95 a RF-97)

`evaluate_sla(priority, status, created_at, resolved_at, now)`:

1. `target = DEFAULT_SLA_TARGETS.get(priority)`; si no hay prioridad, devuelve `None` (ticket `sin_sla`).
2. Normaliza fechas sin zona a UTC; las compara como instantes.
3. `due_at = created_at + timedelta(minutes=target)`.
4. Si el estado es `Resuelto` o `Cerrado`:
   - `cumplido` si `resolved_at is None` o `resolved_at <= due_at` (el caso `None` se informa aparte);
   - `incumplido` si `resolved_at > due_at`.
5. Si el estado es `Abierto` o `En progreso`:
   - `incumplido` si `now > due_at`;
   - `en_riesgo` si `now <= due_at` y `due_at - now <= 20 % de target`;
   - `en_tiempo` en el resto.
6. Cualquier otro estado se trata como abierto, sin romper la consulta.

Política por defecto: `Crítica` 120, `Alta` 240, `Media` 720, `Baja` 1440 minutos (TSK-025). Los valores se aíslan en `sla/domain/sla.py` para que HU-14 los sustituya sin cambiar el contrato.

## 4. Contrato HTTP (RF-93 a RF-101)

`GET /api/dashboard/sla?days=7|30|90`

- `days` opcional, por defecto 30; `Literal[7, 30, 90]` produce 422 para otros valores.
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
- Para el mismo rol e instante, `total_evaluated + sin_sla` coincide con el total de HU-11 (RF-100).

## 5. Agregación (RF-94, RF-98 a RF-101)

`get_sla_dashboard(actor_id, actor_role, tickets, now, days=30)`:

1. Valida el rol (`administrador` o `tecnico`); otro rol lanza `DashboardAccessDeniedError`.
2. Obtiene la instantánea del contrato de tickets y filtra por rol y por periodo.
3. Para cada ticket, evalúa SLA; acumula totales y `by_priority`.
4. Cuenta `sin_sla` y `closed_without_resolved_at`.
5. Calcula porcentajes con protección de denominador cero.
6. Devuelve el DTO con `generated_at`, `period_days` y `threshold_percent`.

Una sola pasada; sin persistencia y sin escritura.

## 6. Interfaz (RF-102 a RF-104)

- `SlaCompliancePanel` dentro de `/`, después de las distribuciones de HU-11 y antes de los recientes.
- Donut SVG (sin librería de gráficos) con el porcentaje al centro; segmentos por estado y leyenda con texto y conteos (no solo color).
- Selector 7/30/90 días con 30 por defecto; al cambiar, TanStack Query recarga el panel con esqueleto.
- Nota «{n} tickets sin SLA (sin prioridad) excluidos del cálculo» y, si aplica, «{n} cerrados sin fecha de resolución».
- Estados: `Skeleton`, vacío «No hay tickets evaluables en este periodo», `ErrorState` con «Reintentar»; 401 → logout.
- Responsive: donut y leyenda apilados en móvil; el panel ocupa una tarjeta en escritorio.
- Sin `DemoBadge`: datos reales.

## 7. Estrategia de pruebas

Backend (`pytest` + `TestClient`):

- `resolved_at`: se fija al resolver/cerrar, se limpia al reabrir y no cambia en un estado repetido.
- Dominio SLA: en tiempo, en riesgo en el umbral, incumplido abierto, cumplido, incumplido cerrado, sin prioridad, cerrado sin fecha y cambio de prioridad.
- Agregación: porcentajes, `by_priority` con ceros, `sin_sla`, periodo 7/30/90, límites del periodo y dataset vacío.
- API: 401, 404 para cliente, 200 admin/técnico, 422 para `days` inválido, invariantes y `generated_at`.
- Consistencia con HU-11: `total_evaluated + sin_sla` igual al total del dashboard de tickets para el mismo alcance.

Frontend (Vitest + Testing Library):

- `dashboard.api` y `useSlaDashboard` con `FakeApiClient`: éxito, cambio de periodo, 401, 404 y error.
- `SlaCompliancePanel`: porcentaje, leyenda, nota de `sin_sla`, estados de carga/vacío/error y accesibilidad.
- Integración en `/`: panel junto al dashboard de HU-11 sin romper sus pruebas.
- `npm run test` y `npm run build`.

## 8. Cobertura RF por parte

| Parte | RF |
|---|---|
| `resolved_at` en tickets | RF-97 |
| Dominio SLA | RF-95, RF-96, RF-97 |
| Contrato de tickets | RF-100 |
| Agregación y porcentajes | RF-94, RF-98, RF-99, RF-101 |
| Router y autorización | RF-93, RF-94 |
| Panel y selector | RF-102 |
| Estados, accesibilidad y datos reales | RF-103, RF-104 |

## 9. Decisiones justificadas

- **D1. El cálculo vive en `sla`.** Es la responsabilidad del módulo y evita duplicar la política. *Alternativa descartada: calcular en el frontend*, rompe la separación y expone reglas de negocio.
- **D2. `resolved_at` aditivo en el ticket.** Es la única forma de distinguir cumplido de incumplido en cerrados sin inventar datos. *Alternativa descartada: asumir que todo cerrado cumplió*, oculta incumplimientos.
- **D3. Política por defecto en código hasta HU-14.** La base ya tiene los valores, pero los casos de uso no leen PostgreSQL. *Alternativa descartada: consultar `sla_policies` ahora*, mezcla la integración de BD con esta historia y devolvería datos no usados por los tickets en memoria.
- **D4. Umbral de riesgo del 20 % devuelto en el contrato.** La UI no duplica la regla y el valor queda auditable. *Alternativa descartada: hardcodear 20 % en el frontend*, dos fuentes de verdad.
- **D5. Donut SVG sin Recharts.** Un solo gráfico no justifica la dependencia; el SVG es accesible y ligero. *Alternativa descartada: Recharts*, añade peso y configuración para un elemento simple.
- **D6. Panel dentro de `/`.** Coherente con ADR-001 y evita una ruta nueva. *Alternativa descartada: `/sla/cumplimiento`*, duplica el dashboard y confunde con la configuración de HU-14.
- **D7. Datos reales desde la fuente en memoria.** Mismo criterio que HU-11; la integración con PostgreSQL es una tarea aparte. *Alternativa descartada: leer `ticket_sla` directamente*, hoy no está sincronizado con los tickets.

## 10. Riesgos y supuestos

- **`resolved_at` en tickets antiguos**: si faltara, se cuenta como cumplido y se informa en `closed_without_resolved_at`.
- **Cambio de prioridad**: la fecha límite se recalcula con la prioridad vigente; no se conserva la política original.
- **Zonas horarias**: todas las fechas se normalizan a UTC; la UI presenta en la zona del usuario.
- **Periodo**: el panel usa 30 días por defecto; un ticket de hace 31 días no aparece aunque siga abierto. Es el comportamiento acordado.
- **Dependencia de HU-11/HU-21**: el panel se integra en la misma página y reutiliza sus componentes y su cliente HTTP.
- **HU-14**: cuando exista configuración editable, el dominio de SLA deberá leerla sin cambiar el contrato del panel.

## 11. Dudas abiertas

- Ninguna. Si el equipo decide una ruta propia para el detalle de SLA, se actualiza la spec y este plan antes de implementar.
