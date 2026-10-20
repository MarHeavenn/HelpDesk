# Help Desk SaaS — Guía para agentes

## Descripción

Sistema Help Desk SaaS para registrar, asignar y dar seguimiento a tickets de soporte, con control de identidad y cumplimiento de SLA.

## Stack y estructura

- Frontend: React con TypeScript en `frontend/` (`src/`, `public/`, `tests/`).
- Backend: FastAPI con Python en `backend/` (`app/`, `migrations/`, `tests/`).
- Base de datos: PostgreSQL (ver `infra/docker-compose.yml`).
- Arquitectura: monolito modular. Módulos en `backend/app/modules/`: `identity`, `tickets`, `assignment`, `sla`.
- Documentación: `docs/constitution.md`, `README.md`, `MEMORY.md`.
- Especificaciones: `specs/project.md` y `specs/features/<HU>/` (`spec.md`, `plan.md`, `tasks.md`).

## Convenciones

- Código e identificadores técnicos en inglés.
- Documentación, especificaciones y textos de interfaz en español.
- Mantener la separación de responsabilidades entre módulos y capas.
- No añadir complejidad innecesaria.

## Arquitectura

Capas de cada módulo del backend (`domain`, `application`, `infrastructure`, `interface`):

- `domain/`: reglas y conceptos del negocio.
- `application/`: casos de uso y coordinación.
- `infrastructure/`: persistencia e integraciones técnicas.
- `interface/`: comunicación con el exterior (p. ej. rutas HTTP).

Reglas:

- El frontend no debe acceder directamente a PostgreSQL.
- Un módulo no debe acceder directamente a las tablas internas de otro módulo.
- Las reglas de negocio no deben implementarse en los controladores HTTP.

## Forma de trabajar

1. Leer `MEMORY.md` al comenzar.
2. Consultar `docs/constitution.md` y la especificación correspondiente en `specs/`.
3. Revisar los criterios de aceptación antes de implementar.
4. Seguir el flujo: especificación → plan → tareas → implementación → verificación.
5. Hacer cambios pequeños y enfocados.
6. No inventar reglas de negocio cuando un requisito sea ambiguo; registrarlo en dudas abiertas.
7. Al terminar, resumir los cambios y las verificaciones ejecutadas.

## Límites

Siempre:

- Respetar la arquitectura acordada.
- Abrir los PR contra `develop`; `main` solo recibe versiones estables (nunca abrir un PR contra `main`).
- Actualizar `MEMORY.md` al terminar cada tarea.
- Usar CodeGraph (`codegraph_explore` o `codegraph explore`) para entender y explorar el código antes de rastrear archivos con grep/Read.
- Sincronizar el índice con `codegraph sync` después de cada cambio en el código.
- Usar el MCP Context7 cuando se necesite información sobre una librería (sintaxis, configuración, versiones).

Preguntar antes de:

- Cambiar la arquitectura.
- Añadir dependencias.
- Realizar cambios incompatibles en contratos o estructuras de datos.

Nunca:

- Guardar contraseñas en texto plano.
- Exponer secretos.
- Acceder directamente a las tablas internas de otros módulos.
- Afirmar que se ejecutaron pruebas si no se ejecutaron.

## Memoria

- Leer `MEMORY.md` al comenzar cada tarea.
- Actualizarlo al terminar con el estado actual, decisiones importantes y errores que se deben evitar.
- Mantenerlo breve, con un máximo aproximado de 50 líneas.
- Si una regla se vuelve permanente, proponer incorporarla a `AGENTS.md` o a la constitución.
- No guardar claves, tokens ni datos sensibles.
