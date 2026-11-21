# Tareas HU-13 — Índice de paquetes

La spec aprobada se ejecuta en orden A → B → C. Las listas subordinadas
sumaron 10 tareas originales; la remediación propuesta añade 2 tareas
temporales, cada una de 20–30 minutos y con pruebas focalizadas primero. No
se crean historias ni RF nuevos. **Estado de la remediación: pendiente de
aprobación explícita; no llamar a implementer todavía.**

| Orden | Lote | Archivo | Tareas | Dependencia |
|---|---|---|---:|---|
| 1 | A — Cuentas, invitaciones y roles | [`tasks-A.md`](tasks-A.md) | 5 | Ninguna; terminar A antes de B. |
| 2 | B — RBAC/tenant de tickets y dashboards | [`tasks-B.md`](tasks-B.md) | 3 | Lote A completo. |
| 3 | C — Directorio y asignaciones | [`tasks-C.md`](tasks-C.md) | 2 | Lotes A y B completos. |
| 4 | Remediación — concurrencia e infraestructura | [`tasks-remediation.md`](tasks-remediation.md) | 2 | HU-13 A completado; aprobación explícita de esta propuesta. |

**Total original: 10 tareas; propuesta de remediación: 2 tareas adicionales.**
Las referencias locales se identifican como A-Tn, B-Tn, C-Tn y R-Tn. Las
verificaciones indicadas son criterios futuros; no se afirma que se hayan
ejecutado pruebas en esta fase.
