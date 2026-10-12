---
description: SDD · Genera el plan técnico de una spec aprobada
agent: plan
---

Lee docs/constitution.md, AGENTS.md y specs/features/$1/spec.md. Usa la skill sdd. NO escribas código. Genera specs/features/$1/plan.md con: módulos y capas que se crean o modifican (domain, application, infrastructure, interface) y la responsabilidad de cada parte, contratos entre módulos, decisiones técnicas justificadas (con su alternativa descartada) y estrategia de pruebas con pytest (+ TestClient de FastAPI para la API). Todo debe respetar la constitución y cubrir todos los RF. Marca qué RF cubre cada parte. Si la spec no está aprobada o tiene dudas abiertas, para y avísame.
