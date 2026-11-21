# Remediación HU-13 — Concurrencia e infraestructura

Dependencia: A completado y aprobación explícita de esta propuesta.
Estimación por tarea: 20–30 minutos. Tests primero; backend con `pytest` y
`TestClient`. No cambiar la spec ni llamar a implementer sin aprobación.

- [x] **R-T1. Pruebas concurrentes deterministas de invitaciones.** RF-111, RF-118, RF-120
  - Archivos previstos: `backend/tests/` (suite focalizada de invitaciones/
    concurrencia) y, solo si los tests lo exigen,
    `backend/app/modules/identity/application/invitations.py` o el repositorio
    persistente.
  - Hecho cuando: dos workers operan realmente con conexiones/repositorios
    independientes; `Barrier`/eventos controlan el punto de contención sin
    sleeps; se cubren ambos órdenes de aceptación↔desactivación y
    aceptación↔rotación/reenvío; las aserciones prueban serialización válida,
    como máximo una aceptación exitosa, token viejo inválido y estado final
    leído desde una tercera conexión. El test es reproducible y no pasa por
    ser secuencial.

- [x] **R-T2. Fallos de infraestructura y regresión completa.** RF-111, RF-118, RF-120
  - Archivos previstos:
    `backend/app/modules/identity/application/invitations.py`,
    `backend/tests/` (fallo de lock/conexión/esquema), y `frontend/` únicamente
    para la regresión Vitest/build.
  - Hecho cuando: con PostgreSQL configurado, un fallo de conexión, lock o
    esquema se propaga, revierte la transacción y no muta el agregado en
    memoria; la configuración ausente conserva únicamente el fallback
    intencionado de unitarios. `TestClient` verifica que no hay éxito parcial
    ni se consume/rota el token. Después pasan pytest focalizado, suite
    backend, Vitest y build frontend; se documentan resultados reales y se
  mantienen las respuestas de dominio de RF-111/RF-118/RF-120.

- [x] **R-T2-C. Corrección de rollback y seam explícito de configuración.** RF-111, RF-118, RF-120
  - Hecho cuando: las mutaciones de invitación y estado restauran el agregado
    ante cualquier fallo de persistencia; producción exige PostgreSQL y los
    tests unitarios activan explícitamente el fallback sin base de datos.
