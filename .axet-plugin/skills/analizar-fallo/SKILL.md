---
name: analizar-fallo
description: Diagnostica por qué falló una prueba BDD (locator, sincronización, datos, ambiente, código de prueba o bug de la aplicación) y propone o aplica el arreglo correcto. Usar cuando una prueba falle en local o en el pipeline.
---

# Analizar el fallo de una prueba

Diagnostica la causa con evidencia antes de cambiar código. El objetivo es que la
prueba refleje la aplicación, no que "pase a cualquier precio".

## Entradas

Si el usuario no lo indicó, pregunta:
- Qué prueba falló (archivo de steps, nombre del escenario o `@TC_<ID>`), o si analizar la última ejecución.
- Dónde falló: en local o en el pipeline. Del pipeline, pide descargar el artefacto
  `allure-results` en la carpeta `allure-results/` o, si tienes el conector de
  Azure DevOps activo, lee el log del paso "Run BDD tests".

## 1. Reunir la evidencia

```bash
# macOS / Linux (Windows: .venv\Scripts\python)
.venv/bin/python tools/resumen_fallos.py
```

Muestra por cada prueba fallida: estado, tags, step fallido, mensaje, las líneas del
proyecto involucradas y las capturas. Si no hay resultados, reproduce solo esa prueba:

```bash
.venv/bin/python -m pytest <archivo_steps>::<test> --alluredir=allure-results --clean-alluredir --tb=short
```

Nunca agregues `--persistir-cambios`. Si puedes ver imágenes, revisa la captura del
step fallido; si no, apóyate en el árbol accesible (paso 3).

### 1.b Revisar cambios recientes (obligatorio)

Por cada archivo de `pages/`, `tests/`, `conftest.py` o `data/` que aparezca en
"código del proyecto involucrado", ejecuta **siempre**:

```bash
git diff HEAD -- <archivo>          # cambios sin commitear
git log -p -3 -- <archivo>          # últimos commits del archivo
```

Si las líneas que fallan cambiaron hace poco, la propuesta por defecto es
**restaurar la versión anterior** (o corregir ese cambio), citando el valor original.

## 2. Clasificar la causa

| Causa | Señales típicas | Estado Allure |
|---|---|---|
| **Locator roto** | `TimeoutError ... waiting for get_by_...`; `strict mode violation: resolved to N elements` | broken |
| **Sincronización** | Pasa al reintentar; `element is not attached`, `detached`; navegación a medio cargar | broken |
| **Datos** | `expect(...).to_have_text` con un valor distinto; el registro esperado no existe o ya existe | failed |
| **Ambiente** | `net::ERR_*`, título "Application Error", HTTP 5xx, falla el login en todas las pruebas, variable faltante en `obtener_env_requerida` | broken |
| **Código de prueba** | `StepDefinitionNotFound`, `fixture '...' not found`, `AttributeError`, `coroutine ... was never awaited` | broken |
| **Bug de la aplicación** | La UI muestra un error o un comportamiento distinto al resultado esperado del Test Case | failed |

Usa las líneas de "código del proyecto involucrado" para ubicar el Page Object,
step o fixture exacto. Si el paso 1.b mostró un cambio reciente en esas líneas,
esa es la primera hipótesis: la prueba se rompió por el cambio, no por la aplicación. Si el fallo ocurre en `_given_autenticado` (`conftest.py`),
el problema está en el login y afecta a todas las pruebas.

## 3. Confirmar contra la UI real

Para locators, sincronización y bugs, confirma la hipótesis con el skill
`explorar-ui` en el estado donde falló (usa `--clic` para llegar a modales o pasos
intermedios). Compara el locator del código con el rol y nombre accesible reales.

Para ambiente, comprueba si la aplicación responde:
`.venv/bin/python .kiro/mcp/explorar.py / --sin-sesion` (un título "Application Error"
o un error de red confirman que el problema no está en la prueba).

## 4. Actuar según la causa

| Causa | Acción |
|---|---|
| Locator roto | Corrige el locator **en el Page Object** según `AGENTS.md` (rol + nombre real, `re.compile`, acotado a un contenedor si se repite). Haz el cambio mínimo: si el patrón es genérico a propósito (ej: varias alternativas en `LoginPage`, la base del framework), amplíalo en vez de reemplazarlo por uno específico de esta app |
| Sincronización | Espera un estado concreto con `expect(...)` (visible, habilitado, URL, texto). **Nunca** `wait_for_timeout`, `time.sleep`, `force=True` ni subir timeouts como solución |
| Datos | Ajusta `data/<modulo>.json` o la precondición del escenario; no cambies la aserción para aceptar cualquier valor |
| Ambiente | No modifiques código. Informa qué falla (URL caída, credenciales vencidas) y qué debe revisar el usuario |
| Código de prueba | Corrige el step, la fixture o el feature (steps síncronos con `run_async`) |
| Bug de la aplicación | **No adaptes la prueba.** Redacta el reporte: pasos, resultado esperado vs. obtenido, `@TC_<ID>` y la captura |

Si la evidencia no alcanza para distinguir entre dos causas, dilo y propone cómo
confirmarlo en vez de adivinar.

Si el ambiente impidió llegar a una parte del flujo, no afirmes que esa parte es
correcta: indica explícitamente qué quedó **sin verificar** (por ejemplo, "el botón
de login no se pudo comprobar porque el formulario no cargó") y que debe
re-validarse cuando el ambiente responda.

## 5. Verificar

```bash
.venv/bin/python tools/validar_convenciones.py
.venv/bin/python -m pytest <archivo_steps>::<test> --alluredir=allure-results --clean-alluredir
```

Ejecuta la prueba **una vez**. Solo si la causa fue de **sincronización**,
ejecútala **dos veces**: un arreglo de ese tipo que pasa una sola vez no está confirmado.

## Formato del informe

```
Prueba:      <test> (@TC_<ID> si el escenario lo tiene; si no, "sin @TC")
Causa:       <categoría> — <una frase>
Evidencia:   <mensaje clave, archivo:línea, lo observado en el árbol accesible>
Cambios recientes: <resultado de git diff/log en las líneas que fallan, o "sin cambios recientes">
Acción:      <cambio aplicado (archivo:línea) | reporte de bug | acción para el usuario>
Verificación: validador OK, prueba ejecutada <1 vez | 2 veces si fue sincronización>: <resultado>
```
