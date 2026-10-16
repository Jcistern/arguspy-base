---
name: importar-plan
description: Convierte los casos de un plan de pruebas (.xlsx o .json) en archivos .feature de pytest-bdd, un feature por pantalla y un escenario por caso, enlazados con el tag @CP_<PANTALLA>_<NN>. Usar cuando el usuario quiera pasar el plan de pruebas a Gherkin.
---

# Importar el plan de pruebas a .feature

Genera **solo los `.feature`**. Los steps y Page Objects se crean después, caso a
caso, con el skill `automatizar-caso`.

## Entradas

Si el usuario no lo indicó, pregunta:
- Ruta del plan. Sugiere copiarlo a `data/planes/` (carpeta ignorada por git).
- Qué pantallas importar (prefijo del ID: `PRY`, `EMP`, `UGL`…) o todas.

## 1. Leer el plan

```bash
# macOS / Linux (Windows: .venv\Scripts\python)
.venv/bin/python tools/plan_pruebas.py leer <plan> --resumen
.venv/bin/python tools/plan_pruebas.py comparar <plan>
```

El resumen lista los casos por pantalla; `comparar` muestra cuáles ya tienen escenario.

**Trabaja un caso a la vez** (los casos son largos y la respuesta se corta si se
procesan juntos). Por cada caso de la pantalla:

```bash
.venv/bin/python tools/plan_pruebas.py leer <plan> --caso CP-PRD-01
```

1. Lee el caso y **escribe directamente** su escenario en el `.feature`: el primero
   crea el archivo (encabezado + `Background` + escenario); los siguientes se agregan
   al final. **No redactes borradores en el chat**: si algo no cuadra, corrígelo en el archivo.
2. Si el caso necesita datos que no caben en `Examples`, agrégalos a `data/<pantalla>.json`
   en ese mismo momento (archivo completo y válido, nunca vacío).
3. Revisa la **lista de control** (abajo) contra el texto del caso y corrige el archivo.
4. Pasa al siguiente caso.

Si el script avisa IDs duplicados, no adivines: importa el primero, marca el otro
con `@revision` y un comentario, e infórmalo al final.

### 1.b Revisar la calidad de los casos

```bash
.venv/bin/python tools/plan_pruebas.py revisar <plan> --pantalla PRD
```

- `[falta]`: el caso no alcanza para escribir el escenario sin suponer (sin
  precondición, resultado vago, datos sin definir). Escribe **solo lo que el plan
  dice**, márcalo `@revision` con el comentario `# Falta en el plan: <qué>` y
  redacta una **duda** para la hoja «Dudas» (ver Informe). Nunca completes con
  comportamiento inventado.
- `[nota]`: viñetas `*Validar …` en Detalle. No impiden importar el caso principal.

## 2. Escribir el feature de la pantalla

**Escritura:** cada caso se escribe en el archivo apenas se procesa (así, si la tarea
se corta, lo hecho queda guardado). Nunca crees un archivo vacío para llenarlo después.

Un archivo por pantalla: `tests/bdd/features/<pantalla>.feature`, con un nombre legible
(ej: `productos.feature`). Si ya existe, agrega solo los casos que falten.

```gherkin
# language: en
@test_regresion @perfil_admin
Feature: Productos
  Mantener el catálogo de productos.

  Background: Usuario autenticado
    Given que el usuario está autenticado

  @CP_PRD_01 @smoke @persistente
  Scenario Outline: Crear un producto con y sin descripción
    Given el administrador está en la pestaña "Productos"
    And no existe el producto "<nombre>"
    When crea un producto con nombre "<nombre>" y descripción "<descripcion>"
    Then el formulario solo pedía "Nombre" (obligatorio) y "Descripción"
    And el producto "<nombre>" queda vigente en el catálogo
    And el producto "<nombre>" sigue en el catálogo tras recargar
    And la descripción de "<nombre>" es "<descripcion>"
    And la cantidad de la pestaña "Productos" sube en uno

    Examples:
      | escenario | nombre           | descripcion                 |
      | A         | Taladro Demo 500 | Taladro inalámbrico de demo |
      | B         | Martillo Demo    |                             |

  # dato_A: valor exacto (con espacios dobles) en data/productos.json → "CP-PRD-02"
  @CP_PRD_02 @smoke
  Scenario: El nombre repetido se detecta sin importar mayúsculas ni espacios — A
    Given el administrador está en la pestaña "Productos"
    And existe el producto "Taladro Demo 500" vigente
    When crea un producto con nombre "dato_A"
    Then no se guarda y junto a "Nombre" aparece el aviso de nombre existente
    And sigue habiendo un solo producto "Taladro Demo 500"

  @CP_PRD_02 @smoke
  Scenario: El nombre repetido se detecta sin importar mayúsculas ni espacios — B
    Given el administrador está en la pestaña "Productos"
    When renombra el producto "Sierra Demo" como "TALADRO DEMO 500"
    Then no se guarda y junto a "Nombre" aparece el aviso de nombre existente
```

Reglas de mapeo:

| Plan | Gherkin |
|---|---|
| `id` | Tag `@CP_<PANTALLA>_<NN>` (ej: `CP-PRD-02` → `@CP_PRD_02`). **Obligatorio**: es el enlace con el plan |
| `nombre` | Nombre del escenario (sin el ID) |
| `precondicion` | Pasos `Given`. Describe el estado; nunca escribas usuarios ni contraseñas |
| `pasos` | Pasos `When` / `And`, en tercera persona ("el administrador pulsa…") |
| `resultado_esperado` | Pasos `Then` / `And`, uno por cada verificación concreta |
| `datos_entrada` y "Escenario A / B" con **la misma acción** | `Scenario Outline`; en `Examples` van **solo datos** (nombres, valores), nunca frases de acción o de resultado |
| "Escenario A / B" con **acciones distintas** (ej: A crea, B edita) | Dos `Scenario` separados, con el **mismo** tag `@CP_` y el nombre terminado en "— A" / "— B" |
| `camino_critico` = sí | Tag `@smoke` |
| Crea, edita o elimina datos | Tag `@persistente` |
| `bloqueado_por` con valor | Tag `@revision` y comentario `# Bloqueado por <duda>` |

**Lista de control por caso (obligatoria, no se pierde nada del plan):**

- [ ] **Cada condición de la precondición tiene su `Given`**: qué debe existir y qué
  **no** debe existir (ej: `And no existe el producto "Martillo Demo"`,
  `And existe el producto "Sierra Demo" no vigente`).
- [ ] **Cada verificación del resultado esperado tiene su `Then`/`And`**: separa las
  frases unidas por "y", ";" o "," (ej: "queda vigente, sigue tras recargar y la
  cantidad sube" son tres `Then`). Incluye las negativas ("no pide confirmación",
  "conserva su nombre", "sigue habiendo uno solo").
- [ ] Lo que es **solo de un escenario** (ej: "en B la descripción queda vacía") va en
  ese escenario o como columna de `Examples`, no se omite.
- [ ] **Cada escenario es independiente**: si B necesita algo que crea A, B lleva un
  `Given` que lo deja preparado.
- [ ] **Toda clave de datos** usada en el feature (`dato_A`…) existe en `data/<pantalla>.json`;
  no inventes claves ni valores (para el resultado esperado usa el texto del plan).
- [ ] El tag de perfil corresponde a la cuenta de **este** caso (ver Perfiles).

**Perfiles:** la cuenta de administrador es `@perfil_admin`. Si el caso usa otra
cuenta (ej: `lector`, `supervisor`) y su perfil no existe en `_PERFILES` de `conftest.py`, márcalo `@revision`
con el comentario `# Requiere el perfil <cuenta>`, **sin** `@perfil_admin`. Pon el tag de
perfil a nivel de `Feature` **solo si todos** sus casos usan la misma cuenta; si uno
usa otra, el tag va en cada escenario (los tags del `Feature` se heredan y harían
login con la cuenta equivocada).

**Redacción:**
- Reutiliza **la misma frase** para la misma acción en todos los escenarios del feature
  (luego será un solo step). Las variaciones van como parámetros entre comillas.
- Un `Then` por verificación; no copies el resultado esperado como un párrafo.
- No inventes comportamiento: si el plan no lo dice, no va en el escenario.
- Los datos de prueba van en `Examples` o entre comillas en el step, nunca en los
  steps de Python ni en los Page Objects.
- **Gherkin recorta los espacios al inicio y al final de cada celda** y no admite
  tabuladores ni saltos de línea. Si el caso depende de ellos (como `CP-PRD-02`), usa
  una clave (`dato_A`) en `Examples` y deja el valor exacto en
  `data/<pantalla>.json` bajo el ID del caso, con un comentario en el escenario:
  `# dato_A: valor exacto en data/productos.json → "CP-PRD-02"`, con esta forma:
  `{"CP-PRD-02": {"dato_A": "  taladro   DEMO 500 "}}`.

**Columna `detalle`:** las viñetas `*Validar …` son validaciones aún no diseñadas.
No las conviertas salvo que el usuario lo pida. Si lo pide, escríbelas como escenarios
**sin tag `@CP_`**: el skill `actualizar-plan` las agregará luego al plan como casos nuevos.

## 3. Verificar

```bash
.venv/bin/python tools/validar_convenciones.py
.venv/bin/python tools/plan_pruebas.py comparar <plan>
.venv/bin/python tools/verificar_steps.py tests/bdd/features/<pantalla>.feature
```

- El validador no debe dar errores (tags registrados, `# language: en`).
- En `comparar`, los casos de las pantallas importadas ya no deben aparecer en
  "Casos del plan sin escenario".
- `verificar_steps.py` lista como `[pendiente]` los pasos que aún no tienen step:
  es el trabajo que queda para `automatizar-caso`. Revisa que la misma acción use
  siempre la misma frase (si hay dos frases para lo mismo, unifícalas).

## Informe

Compacto, una línea por pantalla:

```
PRD → tests/bdd/features/productos.feature: 4 escenarios (CP-PRD-01..04), 1 @revision (perfil lector), 9 pasos por implementar
Pendientes: CP-PRD-05 duplicado (filas 7 y 12); 3 viñetas «*Validar» sin convertir.
Dudas propuestas para la hoja «Dudas»:
- CP-PRD-05 (fila 12): el resultado esperado solo dice «se crea correctamente»; ¿qué debe verse?
```

Pregunta si quiere registrar las dudas en el plan: se agregan con el skill
`actualizar-plan` (sección «dudas» del JSON).
