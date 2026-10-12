# Memoria del proyecto

## Estado actual

- Estructura inicial creada. Implementación pendiente.
- Push inicial hecho: `main` y `develop` publicadas en origin (idénticas). Rama actual: `develop`.
- Documento general incorporado como fuente (en la raíz del repo).
- `specs/project.md` y spec de HU-01 actualizados desde el documento general; plan/tasks siguen como esqueletos.
- Mecanismo de autenticación y contratos mínimos: diferidos por el equipo.
- CodeGraph instalado (npm global v1.6.2), conectado a opencode y proyecto indexado (24 archivos).
- Uso de CodeGraph obligatorio (en `AGENTS.md`): explorar con él antes que grep/Read y `codegraph sync` tras cada cambio.
- Context7 configurado como MCP remoto global (verificado con consulta de prueba); su uso para docs de librerías es obligatorio (en `AGENTS.md`).
- Automatización SDD lista: skill `.agents/skills/sdd/`, 10 comandos en `.opencode/commands/` (9 sdd-* + feature) y 4 agentes en `.opencode/agents/` (coordinator, planner, implementer, reviewer).
- Validación SDD: pytest + TestClient (sin Chrome DevTools); frontend sin runner acordado.

## Decisiones tomadas

- Monolito modular: React + TypeScript, FastAPI, PostgreSQL.
- Módulos: identity, tickets, assignment, sla.
- Capas por módulo: domain, application, infrastructure, interface.
- Flujo SSD: spec.md → plan.md → tasks.md → implementación → verificación.

## Errores que se deben evitar

- No inventar reglas de negocio ambiguas; marcarlas como pendientes.
- No acceder a tablas internas de otros módulos.
- No poner lógica de negocio en controladores HTTP.
- No afirmar pruebas no ejecutadas.

## Próximos pasos

- Revisar y aprobar spec de HU-01.
- Completar plan/tasks de HU-01 cuando el equipo lo indique.
- No implementar ni decidir mecanismo/contratos hasta entonces.
