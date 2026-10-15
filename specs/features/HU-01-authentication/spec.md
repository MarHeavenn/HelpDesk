# Spec HU-01 — Registro e inicio de sesión de usuarios
Estado: implementada

## Contexto y objetivo
Permitir que cualquier persona se registre como cliente e inicie sesión para acceder de forma segura a las funcionalidades correspondientes a su rol, garantizando que las credenciales se validan y protegen y que cada sesión identifica al usuario y su rol.

## Usuarios / actores
- Cliente: se registra por sí mismo y accede a sus funcionalidades.
- Tecnico: existe como rol del sistema, pero su creación no ocurre por autorregistro en esta historia.
- Administrador: existe como rol del sistema, pero su creación no ocurre por autorregistro en esta historia.

## Historias de usuario
- H1: Como visitante, quiero registrarme como cliente para acceder a la plataforma.
- H2: Como usuario registrado, quiero iniciar sesión con mi correo y contraseña para acceder según mi rol.
- H3: Como usuario con sesión iniciada, quiero cerrar sesión para que nadie más use mi sesión.

## Requisitos funcionales (criterios de aceptación en EARS)
- RF-1: CUANDO una persona solicite registrarse con nombre, correo, contraseña y rol que cumplan las reglas de validación (RF-3 y RF-4), EL SISTEMA creará el usuario con rol cliente y responderá 201 sin incluir en la respuesta la contraseña ni su hash.
- RF-2: SI una solicitud de autorregistro indica un rol distinto de cliente (tecnico, administrador o cualquier otro valor) u omite el campo de rol, ENTONCES EL SISTEMA la rechazará con 422 y no creará ningún usuario. El sistema no aplicará ningún valor por defecto al rol omitido ni aceptará el rol declarado como autorización; el rol efectivo lo determina el sistema.
- RF-3: EL SISTEMA aplicará estas reglas de validación y responderá 422 cuando alguna se incumpla, sin crear el usuario: nombre obligatorio con 2-100 caracteres tras eliminar espacios al inicio y al final; correo obligatorio con validación sintáctica verificable mediante una biblioteca adecuada, que rechaza valores vacíos, malformados o de más de 254 caracteres, eliminando espacios al inicio y al final antes de validar y almacenar; contraseña obligatoria de 8-128 caracteres sin recortar ni modificar su contenido; sin reglas adicionales de composición.
- RF-4: SI el correo indicado en el registro ya existe ignorando mayúsculas y minúsculas, ENTONCES EL SISTEMA rechazará el registro con 409. La unicidad del correo ignorando mayúsculas y minúsculas estará garantizada también en la persistencia.
- RF-5: CUANDO un usuario inicie sesión con correo y contraseña correctos, EL SISTEMA normalizará el correo con las mismas reglas que en el registro (eliminar espacios al inicio y al final, comparación sin distinguir mayúsculas y minúsculas) sin modificar ni normalizar la contraseña, y responderá 200 iniciando una sesión autenticada que permite identificar al usuario y su rol en peticiones posteriores.
- RF-6: SI una solicitud de inicio de sesión incumple la validación estructural (correo o contraseña ausentes; correo con formato inválido o que supera los límites acordados de formato/longitud; contraseña fuera de los límites acordados de 8-128 caracteres; o presencia de campos adicionales no documentados), ENTONCES EL SISTEMA la rechazará con 422 sin comprobar credenciales. SI la solicitud es estructuralmente válida pero el correo no está registrado o la contraseña es incorrecta, ENTONCES EL SISTEMA la rechazará con 401 y un mismo mensaje genérico idéntico en ambos casos, sin revelar si el correo existe.
- RF-7: CUANDO una petición a un recurso protegido llegue sin autenticación válida, EL SISTEMA la rechazará con 401. EL SISTEMA expondrá como recurso protegido GET /api/auth/me, que CUANDO recibe autenticación válida devuelve la identidad y el rol del usuario autenticado, y SI llega sin autenticación válida responde 401.
- RF-8: CUANDO un usuario con sesión activa solicite cerrar sesión mediante POST /api/auth/logout, EL SISTEMA invalidará efectivamente su sesión y responderá 204. SI no hay sesión activa, ENTONCES EL SISTEMA responderá igualmente 204 sin error (comportamiento idempotente). Esta es la única excepción declarada a la regla de RF-7: POST /api/auth/logout responde 204 incluso sin sesión activa, y no elimina la exigencia de autenticación del resto de recursos protegidos.
- RF-9: EL SISTEMA almacenará las contraseñas únicamente mediante una función diseñada para el almacenamiento de contraseñas (Argon2id o bcrypt) a través de una biblioteca con mantenimiento activo y documentación vigente, ambas verificables al implementar; la biblioteca y su versión quedarán documentadas. Nunca almacenará contraseñas en texto plano ni usará como sustituto funciones hash rápidas de propósito general. La API nunca expondrá contraseñas ni hashes en ninguna respuesta.
- RF-10: MIENTRAS exista una sesión autenticada válida, EL SISTEMA permitirá identificar al usuario y su rol a partir de ella. La elección del mecanismo concreto de sesión queda diferida a la planificación técnica: el plan documentará el mecanismo, cómo identifica al usuario y cómo se invalida, cumpliendo seguridad e invalidación efectiva (RF-8) sin complejidad innecesaria, y sin contradecir esta spec.

## Requisitos no funcionales
- Los mensajes de error seguirán una estructura consistente en todos los rechazos de esta historia; el fallo de autenticación usará siempre el mismo mensaje genérico idéntico para correo inexistente y contraseña incorrecta.
- Los detalles exactos de los cuerpos de respuesta y la estructura exacta del cuerpo de error se definirán en el contrato de la API durante la planificación, sin contradecir los códigos, mensajes genéricos y comportamientos exigidos en estos RF (201/409/422 en registro; 200/401/422 en login; 401 en protegidos; 204 en logout).

## Casos límite
- Registro con nombre de 1 carácter o de más de 100 caracteres tras trim → RF-3 (422, sin crear usuario).
- Registro con nombre vacío o solo espacios → RF-3 (422).
- Registro con correo vacío, malformado o de más de 254 caracteres → RF-3 (422).
- Registro con contraseña de menos de 8 o más de 128 caracteres, o con espacios al inicio/final que deben respetarse tal cual → RF-3 (422).
- Registro con correo ya existente con distintas mayúsculas/minúsculas → RF-4 (409).
- Registro indicando rol tecnico, administrador u otro valor, o sin campo de rol → RF-2 (422, sin crear usuario, sin valor por defecto).
- Inicio de sesión con correo con espacios o mayúsculas que normalizado coincide con el registrado y contraseña correcta → RF-5 (200).
- Inicio de sesión con contraseña modificada (recortada o con mayúsculas alteradas) respecto a la registrada → RF-6 (401 genérico, no 200).
- Inicio de sesión con correo o contraseña ausentes, correo malformado o fuera de límites, contraseña fuera de 8-128, o campos adicionales no documentados → RF-6 (422).
- Inicio de sesión con correo no registrado → RF-6 (401 con mensaje genérico).
- Inicio de sesión con contraseña incorrecta → RF-6 (401 con el mismo mensaje genérico idéntico).
- GET /api/auth/me con sesión válida → RF-7 (200 con identidad y rol); sin autenticación o con sesión inválida → RF-7 (401).
- Acceso a recurso protegido sin autenticación o con sesión inválida → RF-7 (401).
- Cierre de sesión con sesión activa → RF-8 (204 e invalidación efectiva; la sesión deja de ser válida).
- Cierre de sesión sin sesión activa (POST /api/auth/logout) → RF-8 (204 idempotente, sin error; excepción explícita frente al 401 de RF-7).

## Fuera de alcance
- Aprovisionamiento o creación de usuarios con rol tecnico o administrador (vía inicialización o proceso controlado, fuera de HU-01).
- Gestión administrativa de usuarios y roles (corresponde a HU-13).
- Reglas adicionales de composición de contraseñas.
- Verificación de propiedad del correo (fuera de HU-01).
- Recuperación de contraseña, bloqueo de cuentas y otros flujos no pedidos.
- Gestión, asignación y seguimiento de tickets y SLA.

## Criterios de finalización
- RF-1 a RF-10 verificados con pruebas automatizadas con datos de prueba: registro, unicidad de correo, validación de entradas de registro y de login (incluidos rol omitido, campos extra en login y normalización de correo en login con contraseña intacta), autenticación correcta e incorrecta con mensaje genérico idéntico, GET /api/auth/me con y sin autenticación, rechazo de recursos protegidos sin autenticación, cierre de sesión e invalidación efectiva incluido logout sin sesión (204), y almacenamiento seguro.
- Comprobado que lo almacenado no es la contraseña original y que la verificación criptográfica acepta la contraseña correcta y rechaza la incorrecta, con biblioteca y versión documentadas.
- Comprobado que ninguna respuesta de la API expone contraseñas ni hashes.

## Dudas abiertas
- [NECESITA ACLARACIÓN] Mecanismo concreto de sesión (cómo identifica al usuario, cómo se invalida) y estructura exacta de los cuerpos de respuesta/error: diferidos a la planificación técnica y al contrato de la API, con la condición de cumplir los códigos, mensajes genéricos y propiedades exigidos en estos RF.
