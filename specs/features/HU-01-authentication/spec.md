# Spec HU-01 — Registro e inicio de sesión de usuarios

> Fuente: documento general, secciones 3.3 (módulo Identity) y 4 (HU-01). Sin decidir mecanismo ni contratos (diferidos por el equipo).

## Contexto y objetivo

Implementar la gestión y autenticación de usuarios para que clientes, técnicos y administradores accedan de forma segura a la plataforma según su rol.

## Usuarios / actores

- Clientes, técnicos y administradores o responsables de soporte.

## Historias de usuario

- H1: Como usuario, quiero registrarme e iniciar sesión en la plataforma para acceder de forma segura a las funcionalidades correspondientes a mi rol.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: CUANDO un usuario proporcione datos válidos (nombre, correo electrónico, contraseña y rol), EL SISTEMA registrará el usuario.
- RF-2: SI el correo electrónico ya se encuentra registrado, ENTONCES EL SISTEMA rechazará el registro.
- RF-3: CUANDO un usuario proporcione credenciales válidas, EL SISTEMA iniciará su sesión e identificará su rol.
- RF-4: SI las credenciales son incorrectas, ENTONCES EL SISTEMA rechazará el inicio de sesión.
- RF-5: CUANDO el usuario lo solicite, EL SISTEMA cerrará su sesión.
- RF-6: EL SISTEMA nunca almacenará contraseñas en texto plano.

## Requisitos no funcionales

Pendiente de confirmar (sin fuente en el documento general).

## Casos límite

- Registro con correo ya existente.
- Registro o inicio de sesión con datos vacíos o inválidos.
- Inicio de sesión con credenciales incorrectas.

## Fuera de alcance

- Gestión de tickets, asignación y SLA.
- Recuperación de contraseña, bloqueo u otros flujos no definidos en la fuente.

## Criterios de finalización

- Criterios RF-1 a RF-6 verificados con pruebas o comprobaciones apropiadas.
- Sin contraseñas en texto plano.
- Respeto a la arquitectura de módulos y capas.

## Dudas abiertas

- [NECESITA ACLARACIÓN] Mecanismo de autenticación y contratos: diferidos por el equipo, no decidir todavía.
- [NECESITA ACLARACIÓN] Política de contraseñas y mensajes de error detallados: no definidos en la fuente; no inventar.
