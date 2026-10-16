---
name: actualizar-plan
description: Ingeniería inversa del plan de pruebas. Detecta los escenarios .feature que no están en el plan (.xlsx), los redacta como casos con el formato del plan y los agrega en una copia del Excel con ID provisional; además marca como automáticos los casos ya automatizados. Usar después de automatizar o al agregar casos de borde.
---

# Actualizar el plan de pruebas desde los .feature

El plan original **nunca se modifica**: se genera una copia `<plan>_actualizado.xlsx`.
En las filas existentes solo puede cambiar la columna `Ejecución` (a `automática`).

## Entradas

Si el usuario no lo indicó, pregunta la ruta del plan `.xlsx` (sugiere `data/planes/`).

## 1. Comparar

```bash
# macOS / Linux (Windows: .venv\Scripts\python)
.venv/bin/python tools/plan_pruebas.py comparar <plan> --plantilla test-results/plan_nuevos.json
```

Informa:
- **Escenarios que faltan en el plan**: escenarios sin tag `@CP_`. Son los casos a agregar.
- **Casos automatizados a marcar**: casos con `@scenario` en los steps cuya `Ejecución` no es `automática`.
- **Tags `@CP_` que no existen en el plan**: inconsistencias; infórmalas y no las corrijas solo.

Si no hay escenarios faltantes ni casos por marcar, dilo y termina.

Si un escenario faltante es propio del framework y no del cliente (ej: el login base),
propón al usuario marcarlo `@sin_plan` en vez de agregarlo.

## 2. Redactar los casos nuevos

`test-results/plan_nuevos.json` trae, por cada escenario faltante, su `feature`,
`escenario`, `gherkin` (pasos) y `ejemplos` (tabla Examples), con el resto de campos
vacíos. Antes de completarlos, lee 2 o 3 casos de la misma pantalla para imitar su estilo:

```bash
.venv/bin/python tools/plan_pruebas.py leer <plan> --pantalla <PANTALLA>
```

Completa cada caso:

| Campo | Cómo llenarlo |
|---|---|
| `pantalla` | Prefijo de la pantalla (`PRD`, `USR`…), según el feature |
| `nombre` | Una frase que dice qué se comprueba, como los casos existentes |
| `precondicion` | Cuenta (`admin.sistema (Administrador funcional)`…) y estado previo, a partir de los `Given` |
| `pasos` | Lista de pasos en segunda persona ("Pulsa…", "Escribe…"), a partir de los `When`. Con `Examples`, un paso "Escenario A: …" por fila |
| `datos_entrada` | Desde la tabla `Examples`: "A: …; B: …" |
| `resultado_esperado` | A partir de los `Then`, en una o dos frases |
| `tecnica` | `caso de uso`, `particiones de equivalencia`, `valores límite`, `Negativos y permisos` o `Basados en la experiencia` |
| `prioridad` | `alta`, `media` o `baja` |
| `riesgo`, `ambito` | Los mismos de los otros casos de la pantalla |
| `requisito` | El "Texto del requisito" de un caso existente que cubra la misma regla; si ninguno aplica, `Pendiente: asociar requisito` |
| `camino_critico` | `no`, salvo que el usuario diga otra cosa |
| `ejecucion` | Deja el valor que trae la plantilla |

No inventes reglas de negocio: lo que no esté en el escenario no va en el caso.

**Dudas.** Si al importar o automatizar quedó algo sin definir en el plan (resultado
vago, texto exacto de un mensaje, permisos no especificados), agrégalo en la lista
`dudas` del mismo JSON, una por tema:

```json
{"pantalla": "PRD", "tarea": "REQ-12", "que_no_esta_claro": "…qué falta y en qué caso…",
 "supuesto": "…con qué se automatizó mientras tanto…", "casos": ["CP-PRD-05 (fila 12)"], "bloquea": "no"}
```

Se registran en la hoja «Dudas» con ID provisional `D-<PANTALLA>-N01`.

## 3. Confirmar con el usuario

Muestra una línea por caso nuevo y los casos a marcar, y pide confirmación:

```
Nuevos (ID provisional al guardar):
- PRD · El nombre del producto acepta 100 caracteres y rechaza 101 · valores límite · media
Marcar como automática: CP-PRD-02
Dudas: 1 (PRD · resultado esperado vago en CP-PRD-05 fila 12)
```

## 4. Escribir la copia del plan

```bash
.venv/bin/python tools/plan_pruebas.py agregar <plan> --casos test-results/plan_nuevos.json \
    --salida <carpeta del plan>/<nombre>_actualizado.xlsx --marcar-automaticos --etiquetar-features
```

- Asigna IDs provisionales `CP-<PANTALLA>-N01`, `N02`… (no chocan con el plan completo).
- Agrega cada caso al final de «Casos» con el formato de su ámbito, y su iteración 1 en «Ejecuciones».
- Con `--etiquetar-features`, agrega el tag `@CP_<PANTALLA>_N<NN>` a cada escenario.

## 5. Verificar

```bash
.venv/bin/python tools/plan_pruebas.py comparar <carpeta del plan>/<nombre>_actualizado.xlsx
.venv/bin/python tools/validar_convenciones.py
```

"Escenarios que faltan en el plan" y "Casos automatizados a marcar" deben quedar en 0.
Si solo había dudas, `agregar` acepta un JSON con `"casos": []`.

## Informe

```
Plan actualizado: data/planes/<nombre>_actualizado.xlsx (original sin cambios)
Agregados: CP-PRD-N01 (fila 38) · <nombre>
Marcados como automática: CP-PRD-02
Features etiquetados: tests/bdd/features/productos.feature
Pendiente para QA: revisar y renumerar los IDs provisionales; asociar requisitos «Pendiente».
```
