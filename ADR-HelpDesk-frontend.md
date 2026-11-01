# ADRs del Front-end — HelpDesk (prototipo v1.1)

> Documento pensado para dárselo a una IA que construya el front. Cada ADR es autónomo, pero todos dependen del **ADR-000** (layout, tokens, stack). Léelo primero.
> Idioma de la UI: **español**. Los datos de ejemplo salen de las capturas del prototipo; son *mock data*.

## Índice
- ADR-000 — Fundamentos: stack, layout compartido, tokens y roles
- ADR-001 — Dashboard
- ADR-002 — Todos los tickets
- ADR-003 — Mis tickets
- ADR-004 — Crear ticket
- ADR-005 — Técnicos y asignaciones
- ADR-006 — Configuración de SLA
- ADR-007 — Usuarios y roles
- ADR-008 — Empresas y clientes
- ADR-009 — Notificaciones
- ADR-010 — Configuración de cuenta

---

# ADR-000 — Fundamentos del front-end

**Estado:** Aceptado
**Alcance:** Toda la aplicación

## Contexto
HelpDesk es una app web multi-empresa de gestión de tickets de soporte con SLA. Tiene tres roles (Administrador, Técnico, Cliente). El prototipo muestra 10 vistas con un layout común (sidebar + topbar + contenido). No hay backend definido: el front debe funcionar con datos mock detrás de una capa de servicios fácil de reemplazar.

## Decisiones

### 1. Stack (modificable si ya existe uno)
- **React 18 + TypeScript + Vite**
- **Tailwind CSS** para estilos (con tokens en `tailwind.config`)
- **React Router v6** para rutas
- **TanStack Query** para datos (con servicios mock locales o MSW)
- **lucide-react** para iconos
- **Recharts** (o SVG propio) para el gráfico de barras y el donut
- Fuente: **Inter** (Google Fonts)

### 2. Rutas
| Vista | Ruta |
|---|---|
| Dashboard | `/` |
| Todos los tickets | `/tickets` |
| Mis tickets | `/mis-tickets` |
| Crear ticket | `/tickets/nuevo` |
| Técnicos y asignaciones | `/tecnicos` |
| Configuración de SLA | `/sla` |
| Usuarios y roles | `/usuarios` |
| Empresas y clientes | `/empresas` |
| Notificaciones | `/notificaciones` |
| Configuración de cuenta | `/cuenta` (con subrutas `/cuenta/perfil`, `/cuenta/notificaciones`, `/cuenta/seguridad`) |

El ítem **"Estados del sistema"** del sidebar no tiene diseño en este prototipo: ruta `/estado` con una pantalla placeholder ("Próximamente").

### 3. Layout compartido (`AppShell`)
- **Sidebar** (~200 px, fondo blanco, borde derecho 1 px, fijo a la izquierda, altura completa):
  - Logo: cuadrado redondeado índigo con icono de barras + texto "HelpDesk" (el "Desk" en índigo).
  - Tarjeta de espacio de trabajo: avatar cuadrado negro con letra "A", nombre **Acme Solutions**, subtítulo "Plan Business".
  - Navegación principal (icono + texto): Dashboard, Todos los tickets, Mis tickets, Crear ticket, Técnicos y asignaciones (con **badge naranja** con contador, en el prototipo `7`), Configuración de SLA, Usuarios y roles, Empresas y clientes, Notificaciones.
  - Ítem activo: texto índigo + fondo lavanda claro + radio ~8 px.
  - Sección inferior con etiqueta en mayúsculas pequeñas **"ESPACIO DE TRABAJO"**: Estados del sistema, Configuración de cuenta.
  - Pie: "HelpDesk v1.1 · Prototipo" en texto muy pequeño y gris.
- **Topbar** (altura ~52 px, fondo blanco, borde inferior):
  - Buscador global a la izquierda: placeholder "Buscar tickets por ID o título...", icono lupa, badge de atajo **⌘K** a la derecha. El atajo `Cmd/Ctrl+K` enfoca el input.
  - A la derecha: campana con punto rojo si hay notificaciones sin leer, separador vertical, avatar con iniciales ("MG"), nombre y rol debajo ("María González / Administrador") y chevron (menú desplegable: Configuración de cuenta, Cerrar sesión).
- **Área de contenido:** fondo gris azulado muy claro, contenido centrado con ancho máximo según vista (ver cada ADR), padding ~32 px.
- **Botón flotante de ayuda:** círculo oscuro con "?" fijo abajo a la derecha.

### 4. Tokens de diseño
- Color primario: **índigo** (`#4F46E5` aprox.), hover más oscuro.
- Fondo app: `#F5F6FA` aprox.; tarjetas blancas con borde `#E5E7EB` y radio 12 px, sombra muy sutil.
- Texto: título casi negro (`#111827`), secundario gris (`#6B7280`).
- Títulos de página: ~28 px, peso 700; subtítulo ~14 px gris.
- Encabezados de tabla: MAYÚSCULAS, 11 px, peso 600, gris, fondo gris muy claro.
- Botón primario: fondo índigo, texto blanco, radio 8 px. Botón secundario: blanco con borde gris.
- **Badges de prioridad** (punto + texto, píldora):
  - Crítica → rojo (fondo rosado)
  - Alta → naranja
  - Media → amarillo
  - Baja → verde
- **Badges de estado:**
  - Abierto → azul
  - En progreso → índigo/lavanda
  - Resuelto → verde
  - Cerrado → gris
- **Indicadores de SLA** (punto + texto, sin píldora): En tiempo → índigo; En riesgo → naranja; Cumplido → verde; Incumplido → rojo.
- **Avatares:** círculo con iniciales sobre fondo lavanda (técnicos) o verde claro (según contexto); si no hay técnico, círculo gris con "?".

### 5. Roles y visibilidad (supuesto, ajustable)
El selector "Rol para demostración" (ADR-010) cambia el rol activo en un contexto global (`useAuth`) para previsualizar permisos y navegación.

| Ítem / acción | Administrador | Técnico | Cliente |
|---|---|---|---|
| Dashboard | ✅ completo | ✅ solo sus métricas | ❌ (redirige a Mis tickets) |
| Todos los tickets | ✅ | ✅ | ❌ |
| Mis tickets | ✅ | ✅ (asignados a él) | ✅ (creados por él) |
| Crear ticket | ✅ | ✅ | ✅ |
| Técnicos y asignaciones | ✅ | ❌ | ❌ |
| Configuración de SLA | ✅ | ❌ | ❌ |
| Usuarios y roles | ✅ | ❌ | ❌ |
| Empresas y clientes | ✅ | ❌ | ❌ |
| Notificaciones | ✅ | ✅ | ✅ |
| Configuración de cuenta | ✅ | ✅ | ✅ |

### 6. Modelo de datos compartido (TypeScript)
```ts
type Prioridad = 'critica' | 'alta' | 'media' | 'baja';
type EstadoTicket = 'abierto' | 'en_progreso' | 'resuelto' | 'cerrado';
type EstadoSLA = 'en_tiempo' | 'en_riesgo' | 'cumplido' | 'incumplido';
type Rol = 'administrador' | 'tecnico' | 'cliente';

interface Ticket {
  id: string;               // "TCK-000128"
  titulo: string;
  descripcion: string;
  prioridad: Prioridad;
  estado: EstadoTicket;
  tecnicoId: string | null; // null => "Sin asignar"
  solicitanteId: string;
  empresaId: string;
  creadoEn: string;         // ISO
  sla: EstadoSLA;
  slaVenceEn?: string;      // ISO
}
interface Tecnico { id: string; nombre: string; iniciales: string; especialidad: string; ticketsActivos: number; }
interface Usuario { id: string; nombre: string; email: string; rol: Rol; empresaId: string; activo: boolean; }
interface Empresa { id: string; nombre: string; plan: 'Starter' | 'Business'; activa: boolean; usuarios: number; tickets: number; }
interface SlaConfig { prioridad: Prioridad; descripcion: string; valor: number; unidad: 'minutos' | 'horas' | 'dias'; }
interface Notificacion { id: string; tipo: 'sla_riesgo' | 'sla_incumplido' | 'asignacion' | 'resuelto'; titulo: string; detalle: string; etiqueta?: 'Atención' | 'Incumplido'; leida: boolean; creadaEn: string; }
```

### 7. Estados transversales (todas las vistas)
Cada vista debe contemplar: **cargando** (skeletons), **vacío** (ilustración/icono + texto), **error** (mensaje + botón "Reintentar") y **sin permiso** (redirección o aviso).

### 8. Formato de fechas
- Relativas en tablas: "Hoy, 09:42", "Ayer, 16:32", "18 jun, 15:20".
- Relativas en notificaciones: "Hace 8 min", "Hace 1 h", "Ayer".
- Usar `Intl.DateTimeFormat('es-CO')` y zona horaria del usuario.

## Consecuencias
- Un solo `AppShell` evita duplicar layout; las vistas solo renderizan su contenido.
- La capa de servicios mock permite cambiar a API real sin tocar componentes.
- Los componentes de tabla, badge y filtros se reutilizan en ADR-001, 002, 003 y 005.

---

# ADR-001 — Dashboard

**Estado:** Aceptado · **Ruta:** `/` · **Roles:** Administrador, Técnico

## Contexto
Pantalla de entrada. Da un panorama del soporte: volumen, desempeño frente al SLA y tickets recientes.

## Decisión
Construir un dashboard con encabezado de bienvenida, 4 KPIs, gráfico semanal, donut de SLA, 3 métricas secundarias y tabla de recientes.

## Detalle

**Encabezado**
- Sobretítulo en mayúsculas pequeñas con la fecha actual (ej. "MIÉRCOLES, 19 DE JUNIO").
- Título: "Buenos días, {nombre}" (el saludo cambia según la hora: Buenos días / Buenas tardes / Buenas noches).
- Subtítulo: "Aquí tienes el panorama general de soporte y desempeño del equipo."
- Botón primario a la derecha: **"+ Crear ticket"** → `/tickets/nuevo`.

**Fila 1: 4 tarjetas KPI** (grid de 4 columnas iguales). Cada una: título, icono en cuadro de color en la esquina, número grande y línea inferior con micro-tendencia.
| Título | Valor ejemplo | Línea inferior | Color del icono |
|---|---|---|---|
| Total de tickets | 128 | ↗ "+12 este mes" (índigo) | lavanda |
| Tickets abiertos | 24 | ⓘ "3 requieren atención" (naranja) | naranja claro |
| En atención | 18 | ↗ "14 dentro del SLA" (índigo) | azul claro |
| Tickets resueltos | 86 | ↗ "+18% vs. mes anterior" (verde) | verde claro |

**Fila 2 (2/3 + 1/3)**
- **Actividad de tickets** (tarjeta ancha): título, subtítulo "Tickets creados y resueltos esta semana", select de rango (**7 días** por defecto; opciones sugeridas: 7 días, 30 días, 90 días), leyenda "Creados" (índigo oscuro) / "Resueltos" (lavanda). Gráfico de barras agrupadas, eje X Lun–Dom, con líneas de cuadrícula horizontales suaves y tooltip al hover.
- **Cumplimiento de SLA** (tarjeta estrecha): título, subtítulo "Últimos 30 días", menú "⋯" arriba a la derecha. Donut con **94%** y "cumplido" al centro. Leyenda a la derecha con punto de color y conteo: En tiempo **121** (índigo), En riesgo **5** (naranja), Incumplidos **2** (rojo). El porcentaje = en tiempo / total.

**Fila 3: 3 tarjetas de métricas compactas**
- Tiempo medio de resolución: **3 h 24 min** · "−18 min frente al mes anterior" (verde)
- Primera respuesta: **28 min** · "Objetivo general: 45 min"
- Tickets por técnico: **5.0** · "Promedio de carga activa"

**Fila 4: Tickets recientes**
- Título + subtítulo "Últimas solicitudes registradas en tu organización"; botón secundario **"Ver todos →"** a `/tickets`.
- Tabla con columnas: TICKET (ID en índigo + título en negrita debajo), PRIORIDAD, ESTADO, TÉCNICO ASIGNADO (avatar + nombre), CREADO, SLA, menú "⋯".
- Mostrar los últimos 5 tickets. Clic en la fila o en el ID abre el detalle (`/tickets/:id`, fuera de alcance de este prototipo).

## Estados y comportamiento
- Cambiar el rango del select recarga el gráfico (con skeleton).
- KPIs con tendencia negativa usan color rojo y flecha hacia abajo.
- En móvil: KPIs en 2 columnas, luego 1 columna; tabla con scroll horizontal.

## Criterios de aceptación
- [ ] Se ven las 4 KPIs, el gráfico, el donut, 3 métricas y la tabla de recientes.
- [ ] El gráfico responde al cambio de rango.
- [ ] El donut suma 100% y su leyenda coincide con los conteos.
- [ ] "Crear ticket" y "Ver todos" navegan correctamente.

---

# ADR-002 — Todos los tickets

**Estado:** Aceptado · **Ruta:** `/tickets` · **Roles:** Administrador, Técnico

## Contexto
Listado completo de tickets de la organización con búsqueda, filtros y orden.

## Decisión
Una tarjeta única con barra de herramientas + tabla paginada.

## Detalle

**Encabezado:** título "Todos los tickets", subtítulo "Consulta, filtra y administra todas las solicitudes de soporte."

**Barra de herramientas** (dentro de la tarjeta, fila superior):
- Buscador local con placeholder "Buscar por ID o título..." y badge ⌘K.
- Tres selects: **Prioridad** (valor por defecto mostrado como "Todas"), **Estado** (por defecto "Todos"), **Técnico** (por defecto "Todos los técnicos").
- Botón de orden con icono de ordenar: **"Más recientes"** (opciones: Más recientes, Más antiguos, Prioridad, SLA más próximo).
- *Supuesto:* en el prototipo los dos primeros selects solo muestran "Todas"/"Todos"; deben tener `aria-label` y etiqueta clara ("Prioridad", "Estado").

**Contador:** "7 tickets encontrados" (se actualiza con los filtros).

**Tabla**
- Columnas: TICKET (ID índigo + título), PRIORIDAD, ESTADO, TÉCNICO ASIGNADO, CREADO, SLA, acciones (⋯).
- Técnico: avatar con iniciales + nombre; si no hay, avatar gris "?" + "Sin asignar".
- Menú ⋯ por fila: Ver detalle, Asignar técnico (solo admin), Cambiar estado, Cambiar prioridad.

**Datos de ejemplo (7 filas)**
| ID | Título | Prioridad | Estado | Técnico | Creado | SLA |
|---|---|---|---|---|---|---|
| TCK-000128 | Servidor principal sin conexión | Crítica | En progreso | Diego Ruiz | Hoy, 09:42 | En riesgo |
| TCK-000127 | Error al sincronizar correo corporativo | Alta | Abierto | Sin asignar | Hoy, 08:16 | En tiempo |
| TCK-000126 | Instalación de licencia de diseño | Media | En progreso | Ana Torres | Ayer, 16:32 | En tiempo |
| TCK-000125 | Cambio de contraseña de acceso | Baja | Resuelto | Luis Vega | Ayer, 11:08 | Cumplido |
| TCK-000124 | Impresora de recepción no responde | Media | Abierto | Sin asignar | 18 jun, 15:20 | En tiempo |
| TCK-000123 | Acceso VPN intermitente | Alta | En progreso | Diego Ruiz | 18 jun, 10:45 | En riesgo |
| TCK-000122 | Configuración de acceso a carpeta | Baja | Cerrado | Ana Torres | 17 jun, 14:10 | Cumplido |

**Pie:** "Mostrando 1–7 de 7" a la izquierda; botones "Anterior" y "Siguiente" a la derecha (deshabilitados según corresponda). Tamaño de página por defecto: 10.

## Estados y comportamiento
- Búsqueda con *debounce* (300 ms) por ID o título; filtros combinables; guardar filtros en la query string.
- Sin resultados: mensaje "No encontramos tickets con esos filtros" + botón "Limpiar filtros".
- Filas con hover gris muy claro.

## Criterios de aceptación
- [ ] Filtros, búsqueda y orden funcionan combinados.
- [ ] El contador y el pie reflejan el resultado filtrado.
- [ ] Badges de prioridad, estado y SLA usan los colores del ADR-000.

---

# ADR-003 — Mis tickets

**Estado:** Aceptado · **Ruta:** `/mis-tickets` · **Roles:** todos

## Contexto
Misma estructura que "Todos los tickets", pero limitada a los tickets del usuario actual.

## Decisión
**Reutilizar** el componente de tabla/filtros del ADR-002 pasando un parámetro de alcance:
- Técnico/Administrador → tickets **asignados** a él.
- Cliente → tickets **creados** por él.

## Detalle
- Título "Mis tickets", subtítulo "Consulta y da seguimiento a las solicitudes asignadas a ti."
- Mismos filtros, contador ("7 tickets encontrados"), columnas, menú ⋯ y paginación.
- **Nota del prototipo:** la captura muestra los mismos 7 tickets que "Todos los tickets"; es solo mock data. La implementación real debe filtrar por usuario.
- Para el rol Cliente, ocultar el filtro de "Técnico" y el menú de asignar.

## Criterios de aceptación
- [ ] Solo muestra tickets del usuario según su rol.
- [ ] Comparte componentes con ADR-002 (sin duplicar código).
- [ ] El ítem "Mis tickets" aparece activo en el sidebar.

---

# ADR-004 — Crear ticket

**Estado:** Aceptado · **Ruta:** `/tickets/nuevo` · **Roles:** todos

## Contexto
Formulario simple para registrar una solicitud de soporte. El SLA depende de la prioridad elegida.

## Decisión
Una tarjeta centrada (ancho máx. ~630 px) con formulario controlado y validación en cliente.

## Detalle

**Encabezado:** "Crear nuevo ticket" / "Describe el problema y nuestro equipo de soporte se encargará del resto."

**Tarjeta "Información de la solicitud"** (subtítulo: "Incluye todos los detalles necesarios para que podamos ayudarte más rápido.", separador debajo):
1. **Título del ticket** — input de texto. Placeholder: "Ej. No puedo acceder al servidor de archivos". Ayuda: "Resume el problema en una frase clara." Obligatorio, 5–120 caracteres.
2. **Descripción del problema** — textarea (~8 filas, redimensionable). Placeholder: "Describe qué sucede, cuándo comenzó y qué acciones intentaste..." Ayuda: "No incluyas contraseñas ni información confidencial." Obligatorio, mínimo 20 caracteres.
3. **Prioridad** — select con Crítica, Alta, Media, Baja. Valor por defecto: **Media**. Debajo, con icono de reloj: "Tiempo objetivo para prioridad media: 12 horas" → el texto y el valor **se leen de la configuración de SLA** (ADR-006) y cambian al cambiar la prioridad.
4. **Aviso informativo "Asignación automática"** (caja lavanda con icono de escudo): "La fecha, hora y solicitante se registrarán automáticamente. Un administrador asignará el técnico responsable."
5. **Acciones** (alineadas a la derecha, separador arriba): **Cancelar** (secundario, vuelve atrás) y **Crear ticket →** (primario).

## Estados y comportamiento
- Errores inline bajo cada campo en rojo; el foco va al primer campo inválido.
- Al enviar: botón en estado "Creando..." (deshabilitado + spinner); al éxito, toast "Ticket TCK-000129 creado" y redirección a `/mis-tickets` (o al detalle).
- Si hay cambios sin guardar y se pulsa Cancelar → confirmar descarte.
- Estado inicial del ticket: **Abierto**, sin técnico.

## Criterios de aceptación
- [ ] No se puede enviar con campos obligatorios vacíos.
- [ ] El tiempo objetivo cambia dinámicamente con la prioridad.
- [ ] El ticket nuevo aparece en las listas con estado Abierto y "Sin asignar".

---

# ADR-005 — Técnicos y asignaciones

**Estado:** Aceptado · **Ruta:** `/tecnicos` · **Roles:** Administrador

## Contexto
El administrador necesita ver la carga del equipo y asignar o reasignar técnicos a los tickets.

## Decisión
Resumen superior (pendientes + disponibilidad) y debajo una tabla de asignación con selector inline por fila.

## Detalle

**Encabezado:** "Técnicos y asignaciones" / "Distribuye la carga de trabajo y mantén cada solicitud en buenas manos." Botón primario **"+ Registrar técnico"** (abre modal: nombre, correo, especialidad).

**Fila superior (1/3 + 2/3)**
- **Pendientes de asignación:** icono naranja, número grande (**7**) y píldora naranja "2 de prioridad alta". Este mismo contador alimenta el badge del sidebar.
- **Disponibilidad del equipo:** título, subtítulo "Carga activa por técnico", enlace **"Administrar equipo"** arriba a la derecha. Tres mini-tarjetas en fila:
  - Diego Ruiz — Infraestructura — **6** tickets
  - Ana Torres — Aplicaciones — **4** tickets
  - Luis Vega — Soporte general — **5** tickets
  (avatar con iniciales + nombre + especialidad + número y etiqueta "tickets").

**Tarjeta "Asignación de tickets"** (subtítulo "Asigna o cambia al técnico responsable"):
- Botón **Filtros** (con icono) y buscador "Buscar ticket..." con ⌘K.
- Tabla: TICKET, PRIORIDAD, ESTADO, TÉCNICO ASIGNADO (lectura), CREADO, SLA, **ACCIÓN** (select con la lista de técnicos + "Sin asignar"), menú ⋯.
- Filas de ejemplo: TCK-000128 (Diego Ruiz), TCK-000127 (Sin asignar), TCK-000126 (Ana Torres), TCK-000125 (Luis Vega), TCK-000124 (Sin asignar).

## Estados y comportamiento
- Cambiar el select asigna al instante (optimista), muestra toast "Ticket asignado a {nombre}" y actualiza: columna "Técnico asignado", cargas del equipo, contador de pendientes y badge del sidebar.
- Ordenar por defecto: sin asignar y prioridad alta primero.
- **Nota del prototipo:** el contador dice 7 pero solo hay 2 filas "Sin asignar" en la tabla de ejemplo; en la implementación el contador debe calcularse de los datos reales.

## Criterios de aceptación
- [ ] Asignar/reasignar actualiza tabla, tarjetas de carga y badge del sidebar.
- [ ] Solo accesible para Administrador.
- [ ] "Registrar técnico" abre un modal con validación.

---

# ADR-006 — Configuración de SLA

**Estado:** Aceptado · **Ruta:** `/sla` · **Roles:** Administrador

## Contexto
Define el tiempo objetivo de atención por nivel de prioridad. Alimenta el cálculo de SLA de los tickets y el texto del formulario de creación.

## Decisión
Página angosta (ancho máx. ~750 px) con un banner informativo y una tarjeta-formulario de 4 filas.

## Detalle

**Encabezado:** "Configuración de SLA" / "Define los tiempos objetivo de atención para cada nivel de prioridad."

**Banner informativo** (fondo lavanda, icono ⓘ): título "¿Cómo funcionan los SLA?" y texto "El tiempo comienza al crear el ticket y se calcula según la prioridad seleccionada. Los cambios aplican a nuevos tickets."

**Tarjeta de formulario**
- Cabecera de columnas: NIVEL DE PRIORIDAD · TIEMPO OBJETIVO.
- Cuatro filas, cada una con icono ⓘ en cuadro de color, badge de prioridad, descripción pequeña, input numérico y select de unidad (por defecto **Horas**; opciones: Minutos, Horas, Días):
  | Prioridad | Descripción | Valor por defecto |
  |---|---|---|
  | Crítica | Incidentes que detienen la operación | 2 Horas |
  | Alta | Impacto importante en el trabajo | 4 Horas |
  | Media | Afectación parcial con alternativa | 12 Horas |
  | Baja | Consultas y solicitudes generales | 24 Horas |
- Pie: **Cancelar** (descarta cambios, restaura valores guardados) y **Guardar cambios** (primario).

## Estados y comportamiento
- Validación: número entero > 0; recomendado que Crítica ≤ Alta ≤ Media ≤ Baja (advertir, no bloquear).
- "Guardar cambios" deshabilitado hasta que haya cambios; al guardar → toast "SLA actualizado" (los cambios solo afectan tickets nuevos).
- Los valores guardados se exponen globalmente (`useSlaConfig`) para el ADR-004.

## Criterios de aceptación
- [ ] Editar y guardar persiste los valores y se refleja en "Crear ticket".
- [ ] Cancelar revierte los inputs.
- [ ] Inputs aceptan solo números positivos.

---

# ADR-007 — Usuarios y roles

**Estado:** Aceptado · **Ruta:** `/usuarios` · **Roles:** Administrador

## Contexto
Gestión de usuarios del espacio: crear, editar, activar/desactivar y asignar rol y empresa.

## Decisión
Directorio en tabla dentro de una tarjeta, con filtros por rol y estado y acciones por fila.

## Detalle

**Encabezado:** "Usuarios y roles" / "Crea usuarios, administra permisos y controla el acceso al espacio." Botón primario **"+ Nuevo usuario"** (modal: nombre, correo, rol, empresa).

**Tarjeta "Directorio de usuarios"**
- Subtítulo dinámico: "4 usuarios registrados".
- Filtros a la derecha: select de rol (**"Todos los roles"**: Administrador, Técnico, Cliente) y select de estado (**"Todos"**: Activo, Desactivado).
- Tabla: USUARIO (avatar con iniciales + nombre en negrita + correo pequeño debajo), ROL (píldora), EMPRESA, ESTADO (píldora), ACCIONES.
- Píldoras de rol: Administrador → lavanda con punto índigo; Técnico → blanca con borde y punto negro; Cliente → verde claro.
- Píldoras de estado: Activo → verde; Desactivado → gris.
- Acciones: botón **Editar** (secundario pequeño) + enlace **Desactivar** (o **Activar** si está desactivado).

**Datos de ejemplo**
| Usuario | Correo | Rol | Empresa | Estado |
|---|---|---|---|---|
| María González | maria@acme.com | Administrador | Acme Solutions | Activo |
| Diego Ruiz | diego@acme.com | Técnico | Acme Solutions | Activo |
| Carlos Mendoza | carlos@norte.com | Cliente | Grupo Norte | Activo |
| Elena Castro | elena@orbita.com | Cliente | Órbita Studio | Desactivado |

## Estados y comportamiento
- Desactivar pide confirmación; un usuario desactivado no puede iniciar sesión pero conserva su historial.
- No permitir que el último administrador se desactive a sí mismo ni cambie su propio rol.
- Editar abre el mismo modal que "Nuevo usuario" precargado.

## Criterios de aceptación
- [ ] Filtros por rol y estado funcionan y actualizan el subtítulo.
- [ ] Activar/Desactivar cambia la píldora y el texto de la acción.
- [ ] Modal de crear/editar valida correo único y campos obligatorios.

---

# ADR-008 — Empresas y clientes

**Estado:** Aceptado · **Ruta:** `/empresas` · **Roles:** Administrador

## Contexto
Administración de las organizaciones que reciben soporte, con su plan y volumen de uso.

## Decisión
Grid de tarjetas (3 columnas en desktop) en lugar de tabla, para destacar identidad y métricas por empresa.

## Detalle

**Encabezado:** "Empresas y clientes" / "Administra las organizaciones que reciben soporte en HelpDesk." Botón primario **"+ Nueva empresa"** (modal: nombre, plan, estado).

**Tarjeta de empresa**
- Avatar cuadrado oscuro con la inicial (A, G, Ó) arriba a la izquierda.
- Nombre en negrita + píldora verde **"Activa"** a la derecha (gris "Inactiva" si está desactivada).
- Plan en texto pequeño (Plan Business / Plan Starter).
- Separador y dos métricas: número grande + etiqueta ("usuarios", "tickets").
- Acciones: **Editar** (botón secundario pequeño) y **Desactivar** (enlace; **Activar** si está inactiva).

**Datos de ejemplo**
| Empresa | Plan | Estado | Usuarios | Tickets |
|---|---|---|---|---|
| Acme Solutions | Business | Activa | 18 | 42 |
| Grupo Norte | Starter | Activa | 7 | 16 |
| Órbita Studio | Business | Activa | 11 | 21 |

## Estados y comportamiento
- Desactivar una empresa pide confirmación e informa del impacto ("sus usuarios no podrán iniciar sesión").
- Grid responsivo: 3 → 2 → 1 columnas.
- Estado vacío: "Aún no hay empresas" + CTA "Nueva empresa".

## Criterios de aceptación
- [ ] Tarjetas muestran plan, estado y métricas correctas.
- [ ] Editar y desactivar funcionan con confirmación.
- [ ] "Nueva empresa" crea una tarjeta nueva en la lista.

---

# ADR-009 — Notificaciones

**Estado:** Aceptado · **Ruta:** `/notificaciones` · **Roles:** todos

## Contexto
Centro de alertas operativas: SLA, asignaciones y eventos relevantes de los tickets del usuario.

## Decisión
Lista vertical dentro de una tarjeta, con pestañas de filtro y orden, y acciones de lectura.

## Detalle

**Encabezado:** "Centro de notificaciones" / "Alertas operativas, asignaciones y eventos relevantes de tus tickets." Botón secundario **"✓ Marcar todas como leídas"** a la derecha.

**Barra de la tarjeta**
- Pestañas tipo pill: **Todas** (activa: fondo lavanda, texto índigo), **No leídas**, **SLA**.
- Select de orden a la derecha ocupando el resto del ancho: **"Más recientes"** (también "Más antiguas").

**Ítem de notificación**: icono en cuadro de color a la izquierda, título en negrita (+ etiqueta opcional), detalle en una línea, tiempo relativo pequeño y gris debajo; a la derecha el enlace **"Marcar como leída"** (solo en no leídas). Las **no leídas** tienen fondo gris muy claro.

**Datos de ejemplo**
| Título | Etiqueta | Detalle | Tiempo | Icono | Leída |
|---|---|---|---|---|---|
| SLA próximo a vencer | Atención (naranja) | TCK-000128 tiene 1 h 16 min restantes. | Hace 8 min | ⓘ naranja | No |
| SLA incumplido | Incumplido (rojo) | TCK-000119 superó el tiempo objetivo de prioridad alta. | Hace 32 min | ⓘ rojo | No |
| Nuevo ticket asignado | — | TCK-000123 fue asignado a tu bandeja. | Hace 1 h | persona azul | Sí |
| Ticket resuelto | — | TCK-000125 fue marcado como resuelto por Luis Vega. | Ayer | check verde | Sí |

## Estados y comportamiento
- La pestaña **SLA** muestra solo `sla_riesgo` y `sla_incumplido`; **No leídas**, solo las no leídas.
- Marcar como leída quita el fondo, oculta el enlace y actualiza el punto rojo de la campana del topbar.
- Clic en el ID del ticket dentro del detalle navega al ticket.
- Vacío por pestaña: "No tienes notificaciones aquí".

## Criterios de aceptación
- [ ] Pestañas y orden filtran correctamente.
- [ ] "Marcar todas como leídas" y la acción individual actualizan la campana.
- [ ] Colores/etiquetas de SLA coinciden con ADR-000.

---

# ADR-010 — Configuración de cuenta

**Estado:** Aceptado · **Ruta:** `/cuenta/perfil` · **Roles:** todos

## Contexto
Cada usuario edita su perfil y preferencias. El prototipo incluye además un selector de **rol para demostración** que permite previsualizar la navegación y permisos de cada rol.

## Decisión
Layout de dos columnas: sub-navegación vertical a la izquierda y tarjeta de contenido a la derecha (ancho total ~750 px, centrado).

## Detalle

**Encabezado:** "Configuración de cuenta" / "Administra tu información personal y preferencias del espacio."

**Sub-navegación** (tarjeta pequeña): **Perfil** (activo, fondo lavanda), **Notificaciones**, **Seguridad**, cada una con icono.

**Tarjeta "Perfil"**
- Cabecera: avatar "MG" grande, nombre "María González", rol "Administrador del espacio" y botón secundario **"Cambiar foto"** a la derecha. Separador debajo.
- Dos campos en fila: **Nombre completo** (valor "María González") y **Correo electrónico** (valor "maria@empresa.com").
- **Rol para demostración:** select con Administrador, Técnico, Cliente. Texto de ayuda: "Cambia el rol para previsualizar los permisos y la navegación." Al cambiar, el sidebar y las rutas permitidas se actualizan en vivo (ver matriz del ADR-000). Este control es solo del prototipo y debe quedar detrás de un flag (`VITE_DEMO_ROLES=true`).
- Pie (separador arriba): botón **"Cerrar sesión"** (rojo suave con icono de salida) a la izquierda y **"Guardar perfil"** (primario) a la derecha.

**Pestañas sin diseño en el prototipo (propuesta mínima)**
- *Notificaciones:* switches para recibir alertas por correo de: SLA próximo a vencer, SLA incumplido, nueva asignación, ticket resuelto.
- *Seguridad:* cambiar contraseña (actual, nueva, confirmar) y listado de sesiones activas.

## Estados y comportamiento
- "Guardar perfil" deshabilitado sin cambios; toast "Perfil actualizado".
- Validar formato de correo y nombre no vacío.
- "Cerrar sesión" limpia el estado de auth y redirige a `/login` (pantalla fuera de alcance).
- Cambiar el rol de demostración **no** persiste en el perfil real; vive en el contexto global/localStorage.

## Criterios de aceptación
- [ ] Editar nombre/correo y guardar actualiza el topbar.
- [ ] Cambiar el rol de demostración modifica la navegación del sidebar al instante.
- [ ] Las tres pestañas son navegables (Notificaciones y Seguridad con la propuesta mínima).

---

# Notas finales para la IA que construya el front

1. Empieza por **ADR-000** (AppShell, tokens, componentes `Badge`, `Avatar`, `DataTable`, `Card`, `Select`, `Button`) y luego implementa las vistas en el orden 002 → 003 → 001 → 004 → 005 → 006 → 007 → 008 → 009 → 010.
2. Los datos de ejemplo no son consistentes entre vistas (ej. 7 pendientes vs. 2 sin asignar; 128 tickets totales vs. 79 sumando empresas). Genera un único *seed* coherente y deriva los contadores de ahí.
3. Todo texto de la UI debe estar en español; deja las cadenas en un archivo central para facilitar i18n futuro.
4. Accesibilidad: foco visible, `aria-label` en selects/íconos, contraste AA, navegación por teclado en tablas y modales.
