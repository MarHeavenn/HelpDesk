# Lote C — Directorio de técnicos y asignaciones

Dependencia: lotes A y B completos. Estimación por tarea: 20–30 minutos. Backend con `pytest` + `TestClient`; Vitest/Testing Library para las vistas existentes.

- [x] **T1. Directorio tenant-aware y resultado vacío.** RF-105–RF-106, RF-114, RF-121, RF-124
  - Hecho cuando: `TestClient` verifica admin/supervisor autorizados, array exacto `{id,name}` de técnicos activos propios, exclusión de inactivos/ajenos y respuesta válida vacía exactamente `[]`; el rol no autorizado conserva 404. Vitest verifica que la UI detecta `[]` y muestra el mensaje de que aún no hay técnicos, sin indicador extra en el payload.
- [x] **T2. Asignación existente y aceptación final HU-13.** RF-105–RF-124
  - Hecho cuando: las pruebas verifican RF-122 mediante la misma operación HTTP de HU-04, sin cambiar ruta ni método; técnico asignable activo y del tenant del actor/ticket; UUID malformado 422, inexistente/cruzado 404 uniforme e inactivo/no técnico propio 422 después de autorizar actor/ticket. Los rechazos no mutan ticket/registro y desactivar no elimina asignaciones vigentes. `pytest` + TestClient y Vitest/build cubren secuencia A→B→C; cada RF queda con prueba/resultado o brecha identificada.
  - Verificado: 7 pruebas focalizadas, suite backend 1248 passed/18 skipped, Vitest 125 passed y build frontend correcto.
