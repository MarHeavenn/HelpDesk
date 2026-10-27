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
- `sla`: tiempos de SLA por prioridad y control de cumplimiento (soporta HU-05).

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
- HU-03 (prioridad y estado del ticket): ver `specs/features/HU-03-priority-status/` (implementada y validada; PR a `develop` pendiente).
- HU-04 (asignar tickets a técnicos): ver `specs/features/HU-04-assignment/` (implementada y validada localmente; PR a `develop` pendiente).
- HU-05 a HU-20: definidas en el documento general (secciones 2 y 4); carpetas aún no creadas.
