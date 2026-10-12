# Constitución del proyecto Help Desk SaaS

1. Mantener el stack y la arquitectura acordados (React + TypeScript, FastAPI, PostgreSQL, monolito modular), salvo aprobación del equipo.
2. Respetar la separación de responsabilidades entre módulos (`identity`, `tickets`, `assignment`, `sla`) y entre capas (`domain`, `application`, `infrastructure`, `interface`).
3. Mantener las reglas de negocio fuera de los controladores HTTP y de la interfaz; la interfaz solo comunica, no decide.
4. Definir requisitos y criterios de aceptación antes de implementar funcionalidades.
5. Verificar los cambios mediante pruebas o comprobaciones apropiadas; no afirmar verificaciones no realizadas.
6. Proteger secretos y datos sensibles: sin contraseñas en texto plano, sin credenciales en el repositorio.
7. Evitar dependencias, abstracciones y funcionalidades innecesarias.

Cualquier modificación de estos principios debe revisarse y aprobarse por el equipo.
