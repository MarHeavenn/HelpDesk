# Sistema Help Desk — Especificación General, Requisitos y Arquitectura de Software

---

## 1. Contexto General y Visión del Sistema

### 1.1. Introducción
La arquitectura del sistema Help Desk se define a partir de las responsabilidades, límites y relaciones entre las diferentes partes del sistema. De acuerdo con los principios de arquitectura, una buena arquitectura no depende de utilizar muchas tecnologías, sino de establecer límites claros, responsabilidades claras, contratos claros y decisiones explícitas.

Para el sistema Help Desk se propone una arquitectura de **monolito modular**, organizada alrededor de los principales conceptos que reconoce el negocio: identidad y autenticación, gestión de tickets, asignación de tickets y gestión de SLA. Esta decisión permite mantener una separación clara de responsabilidades sin introducir la complejidad operativa de una arquitectura distribuida que no es necesaria para el alcance actual del proyecto.

El sistema Help Desk es una aplicación web destinada a gestionar solicitudes de soporte mediante tickets. La responsabilidad central del sistema es gestionar el ciclo de vida de los tickets y controlar el acceso a las diferentes operaciones según el rol del usuario.

### 1.2. Roles del Sistema y Actores
En el sistema participan principalmente tres tipos de usuarios:
* **Clientes:** Registran solicitudes de soporte y consultan sus tickets.
* **Técnicos:** Gestionan los tickets que tienen asignados, consultan detalles y actualizan su prioridad y estado.
* **Administradores o responsables de soporte:** Realizan acciones de gestión como la asignación de tickets a técnicos, configuración de SLA y supervisión general.

### 1.3. Flujo Principal del Sistema
1. El usuario se autentica en la plataforma.
2. Un cliente crea un ticket proporcionando título y descripción.
3. El sistema genera un identificador único, registra automáticamente la fecha y hora de creación y asocia el ticket con el usuario que lo creó.
4. Posteriormente, los usuarios autorizados pueden modificar la prioridad y el estado, asignar el ticket a un técnico y realizar el seguimiento del SLA correspondiente.

---

## 2. Inventario General de Historias de Usuario (Backlog)

A continuación se presenta el listado completo de historias de usuario del sistema Help Desk:

| ID | Tarea | Historia de Usuario |
| :--- | :--- | :--- |
| **HU-01** | Registro e inicio de sesión de usuarios | **Como usuario**, quiero registrarme e iniciar sesión en la plataforma, **para** acceder de forma segura a las funcionalidades correspondientes a mi rol. |
| **HU-02** | Crear y consultar tickets | **Como cliente**, quiero crear y consultar tickets de soporte, **para** reportar mis solicitudes y conocer el estado de su atención. |
| **HU-03** | Gestionar prioridad y estado del ticket | **Como técnico**, quiero establecer la prioridad y actualizar el estado de los tickets, **para** organizar y controlar la atención de las solicitudes. |
| **HU-04** | Asignar tickets a técnicos | **Como administrador**, quiero asignar tickets a técnicos, **para** garantizar que cada solicitud tenga un responsable de atención. |
| **HU-05** | Configurar y controlar SLA por prioridad | **Como administrador**, quiero establecer tiempos de SLA según la prioridad de los tickets, **para** controlar automáticamente el cumplimiento de los tiempos de atención. |
| **HU-06** | Gestionar información y detalle del ticket | **Como técnico**, quiero consultar el detalle completo de un ticket, **para** conocer toda la información necesaria para atender la solicitud. |
| **HU-07** | Registrar seguimiento y comentarios del ticket | **Como técnico**, quiero registrar comentarios y avances en los tickets, **para** mantener actualizado el seguimiento de las solicitudes atendidas. |
| **HU-08** | Gestionar ciclo de vida del ticket | **Como técnico**, quiero actualizar el estado de los tickets durante su atención, **para** reflejar correctamente el progreso de cada solicitud hasta su cierre. |
| **HU-09** | Registrar historial y trazabilidad del ticket | **Como administrador**, quiero consultar el historial de cambios de un ticket, **para** conocer las acciones realizadas y mantener la trazabilidad de cada solicitud. |
| **HU-10** | Implementar alertas de SLA | **Como técnico**, quiero recibir alertas cuando un ticket esté próximo a incumplir su SLA, **para** priorizar su atención antes de superar el tiempo establecido. |
| **HU-11** | Dashboard de tickets | **Como administrador**, quiero visualizar un dashboard con el estado y distribución de los tickets, **para** supervisar de forma general la operación del servicio de soporte. |
| **HU-12** | Dashboard de cumplimiento de SLA | **Como administrador**, quiero visualizar indicadores de cumplimiento de SLA, **para** identificar el comportamiento de los tiempos de atención del equipo de soporte. |
| **HU-13** | Gestión de usuarios y roles | **Como administrador**, quiero gestionar los usuarios y sus roles, **para** controlar el acceso a las funcionalidades de la plataforma. |
| **HU-14** | Gestión de configuración de SLA | **Como administrador**, quiero modificar los tiempos de SLA asociados a cada prioridad, **para** adaptar los acuerdos de atención a las necesidades de la empresa. |
| **HU-15** | Notificaciones de tickets | **Como cliente**, quiero recibir notificaciones sobre cambios importantes en mis tickets, **para** mantenerme informado sobre el progreso de mis solicitudes. |
| **HU-16** | Notificaciones de incumplimiento de SLA | **Como administrador**, quiero recibir notificaciones cuando un ticket incumpla su SLA, **para** identificar oportunamente los casos que requieren seguimiento. |
| **HU-17** | Búsqueda y filtrado de tickets | **Como técnico**, quiero buscar y filtrar tickets por diferentes criterios, **para** localizar rápidamente las solicitudes que necesito gestionar. |
| **HU-18** | Métricas de gestión de soporte | **Como administrador**, quiero consultar métricas de gestión de soporte, **para** analizar el desempeño del servicio y los tiempos de atención. |
| **HU-19** | Gestión de empresas/clientes | **Como administrador**, quiero gestionar las empresas y sus usuarios dentro de la plataforma, **para** organizar los clientes y asociar correctamente sus solicitudes de soporte. |
| **HU-20** | Validación integral y despliegue del MVP | **Como administrador**, quiero disponer de una versión funcional y desplegada del sistema, **para** validar el flujo completo de gestión de tickets y demostrar el funcionamiento del MVP. |

---

## 3. Arquitectura del Sistema

### 3.1. Contenedores Principales

La arquitectura se divide en dos contenedores principales de aplicación:

#### 3.1.1. Cliente Web (Frontend)
Será la interfaz utilizada por clientes, técnicos y administradores. Se propone implementar este contenedor utilizando **React**.
* **Responsabilidades:**
  * Mostrar las interfaces de registro e inicio de sesión.
  * Permitir la creación y consulta de tickets.
  * Mostrar información de los tickets.
  * Mostrar prioridad, estado, técnico asignado y estado del SLA.
  * Permitir las operaciones disponibles según el rol del usuario.
  * Consumir los contratos expuestos por la API de aplicación.
  * No contener reglas de negocio críticas ni realizar acceso directo a la base de datos.

#### 3.1.2. API de Aplicación / Backend
Será el núcleo del sistema y contendrá los módulos de negocio del Help Desk. Se propone implementar este contenedor utilizando **FastAPI**.
* **Responsabilidades:**
  * Autenticar usuarios.
  * Gestionar roles y permisos.
  * Crear y consultar tickets.
  * Gestionar prioridades y estados.
  * Gestionar asignaciones.
  * Configurar y controlar los SLA.
  * Validar las reglas de negocio.
  * Exponer contratos HTTP para que el Cliente Web pueda consumir las funcionalidades.
  * Gestionar la persistencia mediante una capa de infraestructura.

#### 3.1.3. Base de Datos
La persistencia se realizará mediante **PostgreSQL**, utilizado por el backend como mecanismo de almacenamiento. El acceso a PostgreSQL estará encapsulado por la infraestructura del backend y no será responsabilidad directa del Cliente Web.

```
+-----------------------------------------------------------------------+
|                         CLIENTE WEB (React)                           |
+-----------------------------------------------------------------------+
                                    |
                             Contratos HTTP
                                    v
+-----------------------------------------------------------------------+
|                     API DE APLICACIÓN (FastAPI)                       |
|                                                                       |
|   +-------------------+  +-------------------+  +-----------------+   |
|   |  Identity Module  |  |  Tickets Module   |  |Assignment Module|   |
|   +-------------------+  +-------------------+  +-----------------+   |
|                                                                       |
|                          +-----------------+                          |
|                          |   SLA Module    |                          |
|                          +-----------------+                          |
+-----------------------------------------------------------------------+
                                    |
                           Capa Infraestructura
                                    v
+-----------------------------------------------------------------------+
|                       BASE DE DATOS (PostgreSQL)                      |
+-----------------------------------------------------------------------+
```

---

### 3.2. Estructura de Módulos del Backend

Dentro del backend se propone organizar el sistema mediante cuatro módulos principales:

```shell
backend/
│
├── identity/
├── tickets/
├── assignment/
└── sla/
```

Esta organización sigue un enfoque modular, donde los módulos representan conceptos reconocibles por el negocio. Cada módulo se organiza internamente en cuatro responsabilidades clave:

```shell
modulo/
├── application/
├── domain/
├── infrastructure/
└── interface/
```

> **Nota:** No se propone crear más capas o componentes de los estrictamente necesarios, ya que la abstracción tiene un costo y separar excesivamente las responsabilidades puede generar archivos y componentes sin aportar una separación real.

---

### 3.3. Responsabilidad de cada Módulo

#### 4.1. Módulo Identity
Es responsable de la gestión de usuarios y autenticación (soporta principalmente la **HU-01**).
* **Responsabilidades:**
  * Registrar usuarios.
  * Validar que el correo electrónico sea único.
  * Gestionar credenciales.
  * Iniciar sesión.
  * Cerrar sesión.
  * Identificar el rol del usuario.
  * Evitar el almacenamiento de contraseñas en texto plano.
  * Proporcionar la información necesaria para que otros módulos puedan validar la identidad y autorización del usuario.

#### 4.2. Módulo Tickets
Es responsable del ciclo básico de creación y consulta de tickets (soporta principalmente la **HU-02**). Es el núcleo sobre el cual se relacionan los módulos de asignación y SLA.
* **Responsabilidades:**
  * Crear tickets.
  * Validar que tengan título y descripción.
  * Generar un identificador único.
  * Registrar automáticamente la fecha y hora de creación.
  * Asociar el ticket con el usuario solicitante.
  * Consultar los tickets pertenecientes al usuario.
  * Consultar la información completa de un ticket.
  * Mantener el estado inicial del ticket.

#### 4.3. Módulo Assignment
Es responsable de administrar la asignación de tickets a técnicos (soporta principalmente la **HU-04**).
* **Responsabilidades:**
  * Consultar los técnicos disponibles.
  * Asignar un ticket a un técnico autorizado.
  * Cambiar el técnico asignado.
  * Permitir que un ticket permanezca sin asignar.
  * Mostrar el técnico responsable del ticket.
  * Registrar quién realizó la asignación.
  * Permitir que un técnico consulte los tickets que tiene a su cargo.
  * Impedir que un cliente realice directamente una asignación.

#### 4.4. Módulo SLA
Es responsable de calcular y controlar el tiempo disponible para la atención de cada ticket según su prioridad (soporta principalmente la **HU-05**).
* **Responsabilidades:**
  * Configurar el tiempo de SLA para cada prioridad.
  * Determinar el SLA correspondiente a un ticket.
  * Calcular el tiempo transcurrido.
  * Calcular el tiempo restante.
  * Identificar cuando un ticket está próximo a vencer.
  * Identificar automáticamente cuando el SLA ha sido incumplido.
  * Actualizar el estado del SLA sin intervención manual.
  * Actualizar el tiempo correspondiente cuando cambia la prioridad del ticket.

* **Tiempos iniciales configurados de SLA:**
  | Prioridad | Tiempo de SLA |
  | :--- | :--- |
  | **Crítica** | 2 horas |
  | **Alta** | 4 horas |
  | **Media** | 12 horas |
  | **Baja** | 24 horas |

> **Nota de diseño:** El requisito indica que el sistema debe identificar cuándo un ticket está próximo a vencer, pero no establece un porcentaje o cantidad exacta de tiempo para determinar dicho estado. Por lo tanto, ese umbral deberá definirse posteriormente como una decisión de negocio.

---

### 3.4. Reglas de Dependencias Permitidas

La arquitectura debe evitar que los módulos conozcan directamente las estructuras internas de otros módulos para evitar el acoplamiento fuerte.

#### Reglas Principales:
1. El Cliente Web solamente se comunica con el backend mediante los contratos de la API.
2. El Cliente Web no accede directamente a PostgreSQL.
3. Los módulos de negocio no deben acceder directamente a las tablas internas de otro módulo.
4. La persistencia debe estar encapsulada en la infraestructura correspondiente.
5. `Identity` proporciona la información necesaria para autenticación y autorización.
6. `Tickets` constituye el núcleo de la gestión de tickets.
7. `Assignment` utiliza la información del ticket mediante un contrato definido.
8. `SLA` utiliza la información de ticket y prioridad mediante contratos definidos.
9. Las reglas de negocio deben permanecer en los módulos correspondientes y no en los controladores HTTP.

---

## 4. Especificación Detallada de las Historias de Usuario Principales (HU-01 a HU-05)

### HU-01 — Registro e inicio de sesión de usuarios
* **Objetivo:** Implementar el mecanismo de gestión y autenticación de usuarios del sistema, permitiendo que los clientes, técnicos y administradores accedan de forma segura a la plataforma según su rol.
* **Descripción:** Se desarrollará el módulo encargado de registrar usuarios y autenticar sus credenciales. El sistema deberá identificar el rol del usuario para controlar posteriormente el acceso a las funcionalidades correspondientes.
* **Estimación:** 5 horas.
* **Prioridad:** Alta.
* **Dependencias:** Ninguna.
* **Entradas:**
  * Nombre del usuario.
  * Correo electrónico.
  * Contraseña.
  * Rol del usuario.
* **Salidas:**
  * Usuario registrado.
  * Usuario autenticado.
  * Sesión iniciada.
  * Rol del usuario identificado.
* **Criterios de aceptación:**
  * El sistema permite registrar un usuario con datos válidos.
  * El sistema valida que el correo electrónico no se encuentre registrado previamente.
  * El sistema permite iniciar sesión utilizando credenciales válidas.
  * El sistema rechaza credenciales incorrectas.
  * El sistema identifica correctamente el rol del usuario.
  * El usuario puede cerrar su sesión.
  * Las contraseñas no se almacenan en texto plano.

---

### HU-02 — Crear y consultar tickets
* **Objetivo:** Implementar la funcionalidad de gestión básica de tickets, permitiendo a los clientes registrar solicitudes de soporte y consultar su información y estado.
* **Descripción:** Se desarrollará el módulo encargado de crear y consultar tickets de soporte. Cada ticket deberá almacenar la información necesaria para realizar su seguimiento durante el proceso de atención.
* **Estimación:** 6 horas.
* **Prioridad:** Alta.
* **Dependencias:** HU-01.
* **Entradas:**
  * Usuario solicitante.
  * Título del ticket.
  * Descripción del problema o solicitud.
  * Fecha y hora de creación.
* **Salidas:**
  * Ticket creado.
  * Identificador único del ticket.
  * Listado de tickets.
  * Información y estado del ticket.
* **Criterios de aceptación:**
  * Un usuario autenticado puede crear un ticket.
  * El sistema genera un identificador único para cada ticket.
  * El sistema registra automáticamente la fecha y hora de creación.
  * El ticket queda asociado al usuario que lo creó.
  * El sistema permite consultar los tickets creados por el usuario.
  * El sistema permite visualizar la información completa de un ticket.
  * Todo ticket nuevo se crea con un estado inicial definido.
  * No se permite crear un ticket sin título o descripción.

---

### HU-03 — Gestionar prioridad y estado del ticket
* **Objetivo:** Implementar la gestión de prioridad y estado de los tickets para permitir que el equipo de soporte organice y controle el proceso de atención.
* **Descripción:** Se desarrollará la funcionalidad que permita a los técnicos gestionar la prioridad y actualizar el estado de los tickets durante su ciclo de vida. La prioridad permitirá determinar posteriormente el tiempo de SLA correspondiente.
* **Estimación:** 5 horas.
* **Prioridad:** Alta.
* **Dependencias:** HU-02.
* **Entradas:**
  * Ticket.
  * Prioridad.
  * Estado.
  * Usuario responsable de la modificación.
* **Salidas:**
  * Ticket actualizado.
  * Prioridad asignada.
  * Estado actualizado.
  * Registro de modificación.
* **Criterios de aceptación:**
  * El sistema permite establecer una prioridad para cada ticket.
  * Las prioridades disponibles son: Crítica, Alta, Media y Baja.
  * El sistema permite actualizar el estado del ticket.
  * Los estados disponibles son: Abierto, En progreso, Resuelto y Cerrado.
  * Solo los usuarios con permisos de gestión pueden modificar prioridad y estado.
  * El sistema conserva la información actualizada del ticket.
  * El cambio de prioridad queda registrado.
  * Un ticket cerrado no puede volver a modificarse sin una acción autorizada.

---

### HU-04 — Asignar tickets a técnicos
* **Objetivo:** Implementar la asignación de tickets a técnicos para establecer un responsable directo de la atención de cada solicitud.
* **Descripción:** Se desarrollará la funcionalidad que permita a los administradores o responsables de soporte asignar tickets a técnicos disponibles. La asignación permitirá identificar quién es responsable de gestionar cada solicitud.
* **Estimación:** 4 horas.
* **Prioridad:** Alta.
* **Dependencias:** HU-01, HU-02.
* **Entradas:**
  * Ticket.
  * Técnico.
  * Usuario que realiza la asignación.
* **Salidas:**
  * Ticket asignado.
  * Técnico responsable.
  * Registro de asignación.
* **Criterios de aceptación:**
  * El sistema permite visualizar los técnicos registrados.
  * Un usuario autorizado puede asignar un ticket a un técnico.
  * El sistema muestra el técnico responsable dentro del ticket.
  * El sistema permite cambiar el técnico asignado.
  * Un ticket puede permanecer sin asignar inicialmente.
  * El sistema registra quién realizó la asignación.
  * El técnico asignado puede visualizar los tickets que tiene a su cargo.
  * Un cliente no puede asignar directamente un ticket a un técnico.

---

### HU-05 — Configurar y controlar SLA por prioridad
* **Objetivo:** Implementar el mecanismo de gestión y seguimiento de SLA para controlar automáticamente el tiempo disponible para la atención de cada ticket según su prioridad.
* **Descripción:** Se desarrollará la funcionalidad que permita definir tiempos de SLA para cada nivel de prioridad y controlar automáticamente el tiempo transcurrido desde la creación del ticket. El sistema deberá identificar visualmente cuando un ticket se encuentre próximo a incumplir el SLA o cuando este ya haya sido superado.
* **Estimación:** 8 horas.
* **Prioridad:** Alta.
* **Dependencias:** HU-02, HU-03.
* **Entradas:**
  * Ticket.
  * Prioridad.
  * Tiempo de SLA configurado.
  * Fecha y hora de creación.
* **Salidas:**
  * Tiempo de SLA asignado.
  * Tiempo transcurrido.
  * Tiempo restante.
  * Estado del SLA.
  * Indicador de SLA próximo a vencer.
  * Indicador de SLA incumplido.
* **Criterios de aceptación:**
  * El sistema permite configurar un tiempo de SLA para cada prioridad.
  * Los valores iniciales son:
    * Crítica: 2 horas.
    * Alta: 4 horas.
    * Media: 12 horas.
    * Baja: 24 horas.
  * El contador de SLA inicia automáticamente al crear el ticket.
  * El sistema determina el SLA correspondiente según la prioridad del ticket.
  * El sistema muestra el tiempo transcurrido.
  * El sistema muestra el tiempo restante mientras el SLA se encuentre vigente.
  * El sistema identifica cuando el ticket está próximo a vencer.
  * El sistema identifica automáticamente cuando el SLA ha sido incumplido.
  * El estado del SLA se actualiza sin intervención manual.
  * El cambio de prioridad actualiza el tiempo de SLA correspondiente.

---

## 5. Contrato de API de Ejemplo (Creación de Ticket)

### POST /api/tickets

#### Objetivo
Crear un nuevo ticket de soporte para un usuario autenticado. Especifica la operación, entradas, salidas, errores, autenticación e invariantes importantes.

#### Autenticación
La operación requiere un usuario autenticado. El usuario solicitante se obtiene de la identidad autenticada y no debe ser enviado libremente por el cliente como un dato que pueda ser manipulado.

#### Entrada (Request Body)
```json
{
  "title": "No puedo acceder al sistema",
  "description": "El sistema rechaza mis credenciales."
}
```

#### Salida Exitosa (Response 201 Created)
```json
{
  "id": "TCK-000001",
  "title": "No puedo acceder al sistema",
  "description": "El sistema rechaza mis credenciales.",
  "status": "Abierto",
  "created_at": "2026-09-27T10:30:00",
  "requester_id": "USR-000001"
}
```

#### Respuestas HTTP
| Código | Situación |
| :--- | :--- |
| **201** | Ticket creado correctamente |
| **400** | Datos inválidos |
| **401** | Usuario no autenticado |
| **422** | Datos de entrada que no cumplen las validaciones |

#### Invariantes
Al crear un ticket deben cumplirse las siguientes condiciones:
* El usuario debe estar autenticado.
* El ticket debe tener un identificador único.
* El título es obligatorio.
* La descripción es obligatoria.
* La fecha y hora de creación son generadas por el sistema.
* El ticket queda asociado al usuario autenticado.
* El ticket debe comenzar con un estado inicial definido.
* El usuario no puede asignar directamente un técnico durante la creación.

---

## 6. Registro de Decisiones de Arquitectura (ADR)

### ADR-001: Uso de un monolito modular para el sistema Help Desk

#### Estado
Aceptado.

#### Contexto / Problema
El sistema Help Desk necesita implementar diferentes funcionalidades relacionadas entre sí: autenticación de usuarios, gestión de tickets, asignación de tickets y control de SLA.

El sistema será desarrollado por un equipo pequeño y cuenta con un alcance y un periodo de desarrollo limitado. Por lo tanto, se necesita una arquitectura que permita separar claramente las responsabilidades del negocio sin introducir complejidad innecesaria en la infraestructura.

Pensar en servicios significa establecer límites y contratos, pero no implica necesariamente utilizar contenedores, Kubernetes, microservicios o repositorios independientes.

#### Decisión
Se decide implementar el sistema como un **monolito modular**.

El backend será una única aplicación desplegable, pero estará dividido internamente en módulos de negocio independientes:
* Identity
* Tickets
* Assignment
* SLA

Cada módulo tendrá responsabilidades claramente definidas y podrá organizar internamente sus componentes en aplicación, dominio, infraestructura e interfaz. La comunicación entre módulos se realizará mediante contratos definidos y se evitará el acceso directo a las estructuras internas de otros módulos.

#### Alternativas Consideradas
1. **Monolito tradicional sin modularización:** Permite desarrollar todo dentro de una única estructura, pero podría provocar que las responsabilidades de autenticación, tickets, asignaciones y SLA se mezclen, aumentando el acoplamiento. Descartado.
2. **Microservicios:** Proporciona un mayor aislamiento físico y despliegue independiente, pero introduce complejidad adicional en comunicación entre servicios, despliegues, consistencia de datos y operación. Para el alcance actual no existe una necesidad que lo justifique. Descartado.
3. **Monolito modular:** Permite mantener una única aplicación desplegable y, al mismo tiempo, establecer límites claros entre las responsabilidades del negocio. **Seleccionado.**

#### Consecuencias Aceptadas
* El sistema tendrá un único backend desplegable.
* Los módulos compartirán la misma aplicación.
* La separación entre módulos será principalmente lógica.
* Se deberá respetar estrictamente la dirección de las dependencias.
* Un error grave en el backend puede afectar potencialmente a toda la aplicación.
* Los módulos no podrán escalar independientemente.
* En caso de que en el futuro aparezca una necesidad real de separación física, los límites modulares establecidos facilitarán una posible evolución.

---

## 7. Walking Skeleton (Demostración de Arquitectura)

El **Walking Skeleton** es la implementación mínima que permite demostrar que las piezas fundamentales de la arquitectura pueden trabajar juntas de extremo a extremo (de la interfaz a la base de datos y de regreso).

### Flujo Mínimo
1. El usuario accede al Cliente Web.
2. El usuario registra una cuenta.
3. El sistema almacena el usuario de forma segura.
4. El usuario inicia sesión.
5. Identity autentica las credenciales.
6. El backend identifica el rol del usuario.
7. El usuario autenticado accede a la creación de tickets.
8. El usuario introduce título y descripción.
9. El módulo Tickets valida la información.
10. Tickets genera el identificador y fecha de creación.
11. El ticket se almacena en PostgreSQL.
12. El backend devuelve la información del ticket.
13. El Cliente Web muestra el ticket creado.

### Qué Demuestra el Walking Skeleton
* Comunicación entre React y FastAPI.
* Funcionamiento de la autenticación.
* Comunicación entre Identity y Tickets.
* Acceso a la persistencia en PostgreSQL.
* Creación de un ticket.
* Generación de identificadores.
* Registro de fecha de creación.
* Asociación entre usuario y ticket.

> **Nota:** No es necesario implementar inicialmente todas las reglas de prioridad, asignación y SLA para considerar válido el Walking Skeleton. Estas funcionalidades podrán incorporarse posteriormente sobre la misma estructura arquitectónica.

---

## 8. Conclusión

La arquitectura propuesta para el sistema Help Desk se basa en un **monolito modular**, con una separación clara entre interfaz, backend, módulos de negocio y persistencia.

Los módulos principales son **Identity, Tickets, Assignment y SLA**, cada uno con una responsabilidad concreta derivada de las historias de usuario. Las dependencias se controlan mediante contratos y se evita que los módulos accedan directamente a las estructuras internas de otros módulos.

La decisión arquitectónica busca evitar dos extremos: un monolito sin límites claros y una arquitectura distribuida innecesariamente compleja. De esta manera, el sistema mantiene una estructura que puede ser desarrollada y mantenida por el equipo actual, pero que también establece límites suficientemente claros para permitir una evolución futura.

La propuesta sigue estrictamente los principios planteados: **límites claros, responsabilidades claras, contratos claros y decisiones arquitectónicas explícitas**.