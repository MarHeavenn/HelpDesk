---
description: SDD · Valida la spec RF por RF (pytest + TestClient)
agent: build
---

Recorre specs/features/$1/spec.md requisito por requisito. Para cada RF indica qué test lo cubre y el resultado de ejecutarlo con pytest. Los RF de API/HTTP, verifícalos con TestClient de FastAPI. Si algún RF no está cubierto o falla, dilo claramente. NO arregles nada todavía. Después comprueba los criterios de finalización y dame un veredicto: ¿la spec está cumplida?
