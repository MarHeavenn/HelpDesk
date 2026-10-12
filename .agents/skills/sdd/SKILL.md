---
name: sdd
description: Úsala siempre que trabajes con Spec-Driven Development en este proyecto (docs/constitution.md o cualquier archivo dentro de specs/) — redactar, revisar o cambiar specs, planes y tareas, o implementar y validar tareas de una spec.
---

# Spec-Driven Development (SDD)

## Flujo

Constitución → Spec → Clarificación → Plan → Tareas → Implementación → Validación → Cambio.

- Nunca pases a la siguiente fase sin la aprobación explícita del usuario.
- La spec manda: si algo no está en la spec, no se implementa. Si falta una decisión, para y pregunta.
- Un cambio de requisitos se hace primero en la spec, luego en el plan y las tareas, y por último en el código.
- Cada spec vive en su carpeta: `specs/features/HU-XX-nombre/` con `spec.md`, `plan.md` y `tasks.md` (HU-01 es el ejemplo inicial).
- Al terminar cada fase, actualiza `MEMORY.md`.
- Explora el código con CodeGraph antes que con grep/Read, y ejecuta `codegraph sync` después de cada cambio en el código.
- Usa Context7 cuando necesites información sobre una librería.

## Plantilla de spec (spec.md)

```
# Spec HU-XX — <Nombre>
Estado: borrador | aprobada | implementada

## Contexto y objetivo
<Qué problema resuelve y por qué merece la pena. Un párrafo.>

## Usuarios / actores
<Quiénes la utilizan.>

## Historias de usuario
- H1: Como <rol>, quiero <acción> para <beneficio>.

## Requisitos funcionales (criterios de aceptación en EARS)
- RF-1: ...

## Requisitos no funcionales
<Solo los que apliquen.>

## Casos límite
<Vacíos, duplicados, datos inválidos, límites, concurrencia, etc.>

## Fuera de alcance
<Qué no se implementará en esta iteración.>

## Criterios de finalización
<Cómo se comprobará que la funcionalidad está terminada.>

## Dudas abiertas
- [NECESITA ACLARACIÓN] <Duda pendiente.>
```

La spec describe el QUÉ y el POR QUÉ. Nada de stack, arquitectura ni nombres de archivos.

## Requisitos en EARS (en español)

- RF-x: CUANDO \<evento\>, EL SISTEMA \<respuesta\>.
- RF-x: SI \<condición no deseada\>, ENTONCES EL SISTEMA \<respuesta\>.
- RF-x: MIENTRAS \<estado\>, EL SISTEMA \<respuesta\>.
- RF-x: EL SISTEMA \<comportamiento permanente\>.

Cada RF debe ser verificable: nada de "rápido" o "bonito" sin un criterio medible.

## Plan (plan.md)

Módulos y capas afectadas (`domain`, `application`, `infrastructure`, `interface`) · Contratos entre módulos · Decisiones justificadas con su alternativa descartada · Estrategia de pruebas con pytest (+ TestClient de FastAPI para la API). Indica qué RF cubre cada parte. Sin pruebas de frontend hasta que se acuerde el runner.

## Tareas (tasks.md)

```
- [ ] **Tn. <Descripción>.** RF-x, RF-y
- Hecho cuando: <comprobación verificable>.
```

Máximo 20-30 min por tarea, en orden de dependencia. Si salen más de 10, propón dividir la spec.

## Implementación

Una sola tarea cada vez: tests primero con pytest (en rojo), luego el código hasta que pasen. Ejecuta pytest y muestra el resultado. Marca la tarea en `tasks.md`, ejecuta `codegraph sync`, actualiza `MEMORY.md` y PÁRATE.

## Validación

Recorre la spec RF por RF: qué test lo cubre y su resultado con pytest. Los RF de API/HTTP se verifican con TestClient de FastAPI. Si algún RF no está cubierto o falla, dilo claramente. Comprueba los criterios de finalización y da un veredicto: ¿la spec está cumplida?
