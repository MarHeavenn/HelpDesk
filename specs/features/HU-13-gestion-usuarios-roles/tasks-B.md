# Lote B — RBAC y aislamiento de tickets/dashboards

Dependencia: lote A completo. Completar B antes de C. Estimación por tarea: 20–30 minutos. Tests backend con `pytest` + `TestClient`; frontend con Vitest/Testing Library.

- [x] **T1. Autorización de lectura y modificación de tickets.** RF-105–RF-106, RF-113–RF-117
  - Hecho cuando: pruebas con dos empresas y relaciones requester/assignee cruzadas verifican que manda `ticket.company_id`; admin/supervisor/técnico/cliente tienen exactamente su alcance y una cuenta sin empresa recibe 404 uniforme. Rechazos por actor/recurso no visible no filtran datos ni mutan el estado; se respetan las precedencias de RF-117.
- [x] **T2. Creación, comentarios e historial bajo RBAC.** RF-105–RF-106, RF-113–RF-117, RF-121
  - Hecho cuando: `TestClient` verifica creación solo admin/cliente con empresa y requester fijados desde sesión, denegación de técnico/supervisor antes de validar cuerpo, `company_id` enviado con 422 sin crear, y lectura/escritura permitida de comentarios e historial según rol/tenant. Flujos y autoría preexistentes se conservan; errores mantienen forma y precedencia aprobadas.
- [x] **T3. Dashboards, controles existentes y regresión B.** RF-105–RF-106, RF-113–RF-117, RF-121, RF-124
  - Hecho cuando: ambos dashboards conservan exactamente esquemas/métricas HU-11/HU-12 y cálculo/configuración HU-14; TestClient verifica alcance por rol/tenant, periodos 7/30/90 y `by_assignee` sin técnicos ajenos, incluyendo técnicos propios con cero para admin/supervisor. Vitest verifica dashboard, navegación y alta por rol. `pytest` + TestClient y Vitest/build cubren B antes de habilitar C.
