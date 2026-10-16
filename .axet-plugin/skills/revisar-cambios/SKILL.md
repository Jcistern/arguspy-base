---
name: revisar-cambios
description: Revisa los cambios pendientes o de una rama contra las convenciones de AGENTS.md (lo que el validador automático no detecta) y entrega hallazgos priorizados sin modificar archivos. Usar antes de hacer commit o abrir un PR.
---

# Revisar cambios antes del commit o PR

Revisión de solo lectura: **no modifiques archivos** salvo que el usuario lo pida
después de ver los hallazgos.

## 1. Delimitar el alcance

Si el usuario no lo indicó, revisa los cambios sin commitear. Comandos:

```bash
git status --short              # archivos nuevos, modificados y eliminados
git diff HEAD                   # cambios sin commitear (staged y no staged)
git diff main...HEAD            # cambios de la rama actual frente a main
```

Los archivos nuevos (`??`) no aparecen en `git diff`: léelos completos.
No leas ni muestres `config/environments/*.env` aunque aparezcan en la lista.

## 2. Ejecutar la validación automática

```bash
# macOS / Linux (Windows: .venv\Scripts\python)
.venv/bin/python tools/validar_convenciones.py
```

Sus errores son hallazgos **bloqueantes**. No los repitas en el resto de la revisión.

## 3. Revisar lo que requiere criterio

Lee cada archivo cambiado completo (no solo el diff) cuando haga falta contexto.

**Page Objects (`pages/`)**
- Hereda de `BasePage`, locators en el constructor, métodos `async`.
- Sin datos de prueba ni reglas de negocio; sin aserciones de flujo (van en los steps).
- Locators: prioridad de `AGENTS.md`, sin CSS sin justificar, sin duplicar locators de otro Page Object.
- Tiene su fixture en `conftest.py`.
- `goto()` usa `navigate_to()` con ruta relativa y confirma la carga con `expect(...)` sobre un elemento estable.

**Steps (`tests/bdd/steps/`)**
- Delgados: solo llaman al Page Object con `run_async(...)`; sin locators ni lógica.
- Cada `@scenario` con `allure.epic`, `feature`, `story` y `severity`.
- No redefinen `que el usuario está autenticado`.

**Features (`tests/bdd/features/`)**
- Escenarios independientes: no mezclan consulta, creación y eliminación.
- `@TC_<ID>` presente cuando el caso existe en Azure DevOps.
- Si guardan datos reales: `@persistente` y el clic final condicionado a `permitir_cambios_persistentes`.
- Texto en español claro, con `Given/When/Then` en inglés.
- Datos de prueba en la tabla `Examples` o entre comillas en el step (o en `data/<modulo>.json` si dependen de espacios); nunca escritos en los steps de Python ni en los Page Objects.
- Escenarios del plan con su tag `@CP_<PANTALLA>_<NN>`; los nuevos sin `@CP_` se agregan al plan con `%actualizar-plan`.

**Datos y seguridad**
- Sin URLs, usuarios, contraseñas ni tokens hardcodeados; variables con `obtener_env_requerida`.
- Sin credenciales ni datos personales en `logger`, `print` ni adjuntos de Allure.
- Datos de prueba en `data/*.json`, leídos con `obtener_seccion_validada`.

**Otros archivos**
- `pytest.ini`: cada tag nuevo registrado como marker.
- `requirements*.txt` cambiado: su `.lock` regenerado con `uv pip compile`.
- Scripts y comandos multiplataforma (sin depender solo de bash).
- `README.md` actualizado si cambió la estructura o el uso.

## 4. Informe

El informe debe ser **compacto**: las respuestas largas se cortan. Reglas:

- **Una línea por hallazgo**, de máximo ~25 palabras: `archivo:línea — problema → corrección`.
- Sin párrafos de explicación ni citas de `AGENTS.md`; basta con nombrar la regla.
- Varios hallazgos iguales en el mismo archivo van en una sola línea con todas las líneas citadas.
- Antes de citar una línea, confírmala con `git grep -n --untracked "<texto>" -- <archivo>`
  (funciona igual en Windows, macOS y Linux).

```
## Bloqueantes
- tests/bdd/steps/test_x_steps.py:27 — credenciales en el log → eliminar la línea.
- pages/x_page.py:19 — URL hardcodeada → usar ruta relativa a APP_BASE_URL.

## Sugerencias
- tests/bdd/steps/test_x_steps.py:19 — @scenario sin metadata Allure → agregar epic/feature/story/severity.

## Sin observaciones
- <archivos revisados sin hallazgos, en una línea>

Total: <N> bloqueantes, <M> sugerencias.
```

Si hay más de 12 hallazgos, escribe el informe completo en `test-results/revision-cambios.md`
(carpeta ignorada por git; es la única escritura permitida en este skill) y en el
chat muestra solo los bloqueantes y el total.

Si no hay hallazgos, dilo explícitamente e indica qué revisaste. No inventes
problemas para llenar el informe. Al final pregunta si el usuario quiere que
apliques las correcciones.
