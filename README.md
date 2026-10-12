# Help Desk SaaS

Sistema Help Desk SaaS para registrar, asignar y dar seguimiento a tickets de soporte. Repositorio en estructura inicial, sin funcionalidades implementadas.

## Estructura inicial

- `AGENTS.md`: guía breve para agentes y colaboradores.
- `MEMORY.md`: memoria viva del proyecto (máx. ~50 líneas).
- `docs/constitution.md`: principios del proyecto.
- `specs/project.md`: resumen del proyecto.
- `specs/features/HU-01-authentication/`: ejemplo inicial (`spec.md`, `plan.md`, `tasks.md`).
- `frontend/`: React con TypeScript (`public/`, `src/`, `tests/`).
- `backend/`: FastAPI (`app/`, `migrations/`, `tests/`). Módulos: `identity`, `tickets`, `assignment`, `sla`, cada uno con `domain`, `application`, `infrastructure`, `interface`.
- `infra/docker-compose.yml`: esqueleto de infraestructura (PostgreSQL).

## Forma de trabajo

Flujo Spec-Driven Development: especificación → plan → tareas → implementación → verificación. Ver `AGENTS.md`.
