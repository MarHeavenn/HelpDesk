# Proyecto Help Desk SaaS

> Resumen inicial basado en el documento general del repositorio (`Sistema Help Desk — Especificación General, Requisitos y Arquitectura de Software.md`). No lo duplica; ver allí el detalle.

## Propósito

Aplicación web para gestionar solicitudes de soporte mediante tickets: ciclo de vida del ticket y control de acceso según el rol del usuario.

## Usuarios / actores

- Clientes: registran solicitudes y consultan sus tickets.
- Técnicos: gestionan tickets asignados, consultan detalle y actualizan prioridad y estado.
- Administradores o responsables de soporte: asignan tickets, configuran SLA y supervisan.

## Módulos funcionales

- `identity`: usuarios y autenticación (soporta HU-01).
- `tickets`: creación y consulta de tickets (HU-02), prioridad y estado (HU-03) y asignación de tickets a técnicos (HU-04); núcleo del sistema.
- `assignment`: políticas futuras de asignación (capacidad, turnos, colas); la asignación de tickets se implementa en `tickets` (D1 de HU-04).
- `sla`: tiempos de SLA por prioridad, control de cumplimiento y configuración administrable (soporta HU-05 y HU-14).

Detalle en las secciones 3.3 y 4 del documento general.

## Alcance general y MVP

- Backlog completo: HU-01 a HU-20 en la sección 2 del documento general.
- MVP: validar el flujo completo de gestión de tickets con una versión funcional y desplegada (HU-20).
- Walking skeleton (sección 7): registro e inicio de sesión + creación y consulta de tickets sobre React → FastAPI → PostgreSQL. Sin el resto de reglas al inicio.

## Restricciones principales

- Monolito modular (ADR-001); una única aplicación backend desplegable.
- Frontend: React. Backend: FastAPI con capas `domain`, `application`, `infrastructure`, `interface` por módulo. Base de datos: PostgreSQL.
- Frontend solo consume contratos HTTP; sin acceso directo a PostgreSQL ni reglas de negocio críticas.
- Sin acceso directo a las tablas internas de otros módulos; reglas de negocio fuera de los controladores HTTP.

## Historias de usuario

- HU-01 (registro e inicio de sesión): ver `specs/features/HU-01-authentication/spec.md`.
- HU-02 (crear y consultar tickets): ver `specs/features/HU-02-tickets/spec.md` (plan y tareas aprobados; T1-T8 en verde).
- HU-03 (prioridad y estado del ticket): ver `specs/features/HU-03-priority-status/` (implementada y validada en `develop`).
- HU-04 (asignar tickets a técnicos): ver `specs/features/HU-04-assignment/` (implementada y validada en `develop`).
- HU-05 (configurar y controlar SLA por prioridad): ver `specs/features/HU-05-sla/` (implementada y validada en `develop`).
- HU-06 (gestionar información y detalle del ticket): ver `specs/features/HU-06-ticket-detail/` (implementada y validada en `develop`).
- HU-07 (registrar seguimiento y comentarios del ticket): ver `specs/features/HU-07-ticket-comments/` (implementada y validada en `develop`).
- HU-08 (gestionar ciclo de vida del ticket): ver `specs/features/HU-08-ticket-lifecycle/` (implementada y validada en `develop`).
- HU-09 (registrar historial y trazabilidad del ticket): ver `specs/features/HU-09-ticket-history/` (implementada y validada en `develop`).
- HU-10 (alertas SLA): ver `specs/features/HU-10-sla-alerts/` (implementada y validada en `develop`).
- HU-14 (configuración de SLA): ver `specs/features/HU-14-sla-config/` (implementada y validada en `develop`).
- HU-11 (dashboard de tickets): ver `specs/features/HU-11-tickets-dashboard/` (spec, plan y tareas aprobadas; en implementación; RF-81 a RF-92).
- HU-12 (dashboard de cumplimiento de SLA): ver `specs/features/HU-12-sla-dashboard/` (spec, plan y tareas aprobadas; en implementación; RF-93 a RF-104).
- HU-20 (frontend del MVP): ver `specs/features/HU-20-frontend/` (spec, plan y tareas aprobadas; sin código).
- HU-21 (estructura visual y navegación): ver `specs/features/HU-21-frontend-shell/` (spec, plan y tareas aprobadas; RF-69 a RF-80).
- HU-13 y HU-15 a HU-19: definidas en el documento general (secciones 2 y 4); carpetas aún no creadas.
