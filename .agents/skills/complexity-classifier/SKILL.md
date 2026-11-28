---
name: complexity-classifier
description: Clasifica la complejidad (LOW/MEDIUM/HIGH) de una tarea o subtarea antes de delegarla, con riesgo, justificación y confianza. Úsala al repartir trabajo; no elige modelos, proveedores ni subagentes.
---

# Clasificador de complejidad

## 1. Propósito y límites

Devuelve una clasificación de complejidad técnica para una tarea o subtarea, antes de que se delegue.

- Decide **cuánta dificultad técnica** tiene la tarea y **cuánta incertidumbre** hay sobre sus requisitos.
- **No** decide qué modelo, proveedor, variante o agente la ejecuta. Esa decisión es de quien delega.
- **No** modifica artefactos, especificaciones, código ni el flujo de trabajo.
- **No** sustituye a la especificación: si falta una decisión de negocio, se reporta como aclaración pendiente.

## 2. Cuándo usar y cuándo omitir

**Usar** antes de delegar una tarea o subtarea, al replanificar, o cuando aparezcan dependencias nuevas.

**Omitir** si la tarea ya tiene una clasificación vigente sin cambios de alcance: reutiliza ese resultado en lugar de repetir el análisis.

**Vía rápida (0 consultas):** si la petición ya declara alcance acotado (un archivo o una capa), criterios de aceptación verificables y ninguna dependencia nueva, clasifica directamente con esa información. No abras el repositorio para confirmar lo que el texto ya dice.

## 3. Entradas

Mínimas:

- descripción de la tarea o subtarea;
- criterios de aceptación o requisitos funcionales;
- entradas y salidas esperadas;
- dependencias conocidas.

Opcionales: rutas de especificación, plan o tareas; clasificación previa; identificador de la tarea padre si es una subtarea.

Si falta alguna entrada mínima, no la inventes: marca `requiere_aclaracion: true` y formula como máximo tres preguntas concretas.

## 4. Procedimiento y presupuesto

1. Clasifica con lo entregado. No explores si la vía rápida aplica.
2. Si el alcance no está claro, haz **una** consulta de código con los nombres de módulo, símbolo o archivo implicados.
3. Si se dispara un override (sección 6), **detén la puntuación**. Se permite como máximo **una** verificación adicional de dependencia crítica para entender el alcance real: existencia de migración, consumidores de un contrato o cruce de módulos.
4. Esa verificación solo puede confirmar o ampliar el alcance; nunca rebaja el nivel fijado por el override.
5. Presupuesto total: **≤2 consultas de código y ≤3 lecturas dirigidas**. Nunca leas el repositorio completo ni releas documentos de convenciones que no se te hayan entregado.
6. Emite la salida una sola vez. No repitas la petición ni pegues contenido de archivos: cita rutas.

## 5. Dimensiones

Puntúa cada dimensión de 0 a 2.

| Dimensión | 0 | 1 | 2 |
|---|---|---|---|
| **Alcance** | 1 archivo o 1 capa, sin contratos | 2–3 archivos o 2 capas dentro de un módulo | ≥2 módulos, cambio de contrato entre módulos, o migración de esquema |
| **Complejidad técnica** | CRUD o renombrado, sin reglas nuevas | caso de uso nuevo con reglas, 1 integración | concurrencia, transacciones, máquina de estados, seguridad o dependencia nueva |
| **Riesgo** | aditivo, reversible, sin datos previos | altera comportamiento o pruebas existentes | autenticación/autorización, migración de datos, cálculo crítico, contrato público u operación destructiva |
| **Ambigüedad** | requisitos completos y verificables | huecos menores resolubles con la especificación | contradicciones o decisiones que exigen al usuario |
| **Validación** | pruebas existentes cubren el cambio | exige pruebas nuevas o flujos de API | difícil de validar: tiempo, concurrencia, servicios externos o interfaz sin runner |

## 6. Reglas de decisión

- Banda por puntuación total (0–10): **0–3 LOW**, **4–6 MEDIUM**, **7–10 HIGH**.
- Overrides que anulan la banda:
  - `riesgo = 2` ⇒ **HIGH**.
  - `riesgo = 1` ⇒ mínimo **MEDIUM**.
  - `validacion = 2` y `ambiguedad = 2` ⇒ **HIGH**.
  - **LOW** solo si todas las dimensiones son ≤1 y el total es ≤3. Si la banda es LOW pero no se cumple esa condición, el nivel es **MEDIUM**.
- Nivel final: `max(banda_total, banda_riesgo, overrides)`.
- Regla de desempate: ante duda entre dos niveles, elige el mayor **solo** si la duda afecta a riesgo o validación. Si afecta a un detalle de implementación, mantén el nivel y anótalo en `supuestos`.
- La puntuación ordena; los overrides mandan. Informa ambos para que la decisión sea auditable.

## 7. Confianza y aclaración

Son dimensiones distintas y no se mezclan:

- `clasificacion` mide dificultad técnica. **No** cambia por falta de datos.
- `confianza` mide la calidad de la evidencia:
  - **alta**: entradas completas y dependencias declaradas o verificadas.
  - **media**: alcance claro, dependencias inferidas o sin verificar.
  - **baja**: faltan entradas mínimas o hay contradicción entre requisitos.
- `requiere_aclaracion` indica si se puede delegar:
  - `true` si faltan entradas mínimas, si `ambiguedad = 2` o si `confianza` es baja;
  - mientras sea `true`, **no se delega** la tarea: se resuelven las preguntas y se vuelve a clasificar;
  - cuando sea `true`, incluye como máximo tres `preguntas` concretas.
- Si el hueco es solo técnico (dependencias sin verificar) pero los requisitos y el alcance están claros, usa `confianza: media` y `requiere_aclaracion: false`.

## 8. Formato de salida

Devuelve un bloque YAML y una línea de resumen. No añadas texto fuera de ese bloque salvo la línea final.

```yaml
tarea: T3
clasificacion: HIGH
riesgo: alto
confianza: media
requiere_aclaracion: false
puntuacion: {alcance: 2, complejidad: 1, riesgo: 2, ambiguedad: 0, validacion: 1, total: 6}
nivel_por_puntuacion: MEDIUM
override: "riesgo=2 ⇒ HIGH"
justificacion:
  - "Cruza el contrato entre dos módulos y exige migración de datos"
evidencia:
  - "<ruta del contrato>"
  - "<ruta de la migración>"
supuestos:
  - "Sin consumidores externos del contrato"
reclasificacion: {requiere: false, motivo: null}
resumen: "HIGH (riesgo alto, confianza media) — override por migración y contrato"
```

Reglas del formato:

- `justificacion`: de 1 a 3 líneas, cada una ligada a una dimensión u override.
- `evidencia`: de 0 a 3 rutas; nunca contenido de archivos.
- Si `requiere_aclaracion` es `true`, añade `preguntas` con 1–3 elementos y deja `clasificacion` como la mejor estimación disponible.
- Prohibido incluir identificadores de modelo, proveedor, variante o subagente, y cualquier recomendación de enrutamiento.

## 9. Reclasificación

Reclasifica una subtarea cuando ocurra alguno de estos disparadores:

- aparece una dependencia con otro módulo o contrato;
- el alcance real supera lo estimado;
- dos intentos de validación fallan sin causa clara;
- cambia un criterio de aceptación;
- se descubre una migración, requisito de seguridad u operación destructiva.

Emite **solo el delta**, sin repetir el informe completo:

```yaml
reclasificacion: {tarea: T3, de: MEDIUM, a: HIGH, disparador: "requiere migración y cambio de contrato", evidencia: ["<ruta>"]}
```

Si solo cambia la incertidumbre, no cambies `clasificacion`: emite `{de_confianza: alta, a_confianza: baja, requiere_aclaracion: true}`.

## 10. Ejemplos

**LOW** — renombrar un campo visible en una sola capa, con pruebas existentes:

```yaml
tarea: "Renombrar etiqueta de un campo"
clasificacion: LOW
riesgo: bajo
confianza: alta
requiere_aclaracion: false
puntuacion: {alcance: 0, complejidad: 0, riesgo: 0, ambiguedad: 0, validacion: 1, total: 1}
nivel_por_puntuacion: LOW
override: null
justificacion:
  - "Un solo archivo, sin reglas nuevas ni datos persistidos"
evidencia:
  - "<ruta del componente>"
supuestos:
  - "La etiqueta no se expone en la API ni se guarda"
reclasificacion: {requiere: false, motivo: null}
resumen: "LOW (riesgo bajo, confianza alta) — 1 archivo, prueba existente"
```

**HIGH** — cambio de contrato con migración, como el bloque de la sección 8.

## 11. Anti-patrones

- Clasificar por sensación sin recorrer las cinco dimensiones.
- Sumar la puntuación e ignorar un override.
- Subir el nivel porque faltan datos: eso es incertidumbre, no complejidad.
- Delegar con `requiere_aclaracion: true` pendiente.
- Explorar el repositorio completo o repetir consultas ya hechas.
- Incluir modelos, proveedores o subagentes en la salida.
- Reclasificar reescribiendo el informe entero en lugar de emitir el delta.
