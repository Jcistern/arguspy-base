---
name: automatizar-caso
description: Automatiza un caso de prueba BDD de punta a punta (feature, Page Object, steps y verificación) con Playwright Python y pytest-bdd. Usar cuando el usuario pida automatizar un caso o un Test Case de Azure DevOps.
---

# Automatizar un caso BDD con Playwright Python

## Entradas

Si el usuario no lo indicó, pregunta:
- Módulo (ej: `usuarios`, `dashboard`).
- Ruta de la pantalla, relativa a `APP_BASE_URL`.
- Descripción del caso en español, o el ID del Test Case de Azure DevOps.

Si te dan un ID de Test Case y tienes el conector de Azure DevOps activo, lee sus
pasos y resultado esperado desde ahí. El ID se usa en el tag `@TC_<ID>`.

## 1. Revisar el proyecto

Lee `conftest.py`, `pages/base_page.py` y los Page Objects, features y steps
existentes del módulo. Usa `obtener_env_requerida(...)` para toda variable
requerida y no muestres credenciales, tokens ni datos personales.

## 2. Explorar el flujo

Sigue el skill `explorar-ui` para cada estado del flujo (pantalla inicial,
modales, resultado). Identifica los locators accesibles reales y los estados
verificables con `expect(...)`.

## 3. Modelar el escenario BDD

Agrega o actualiza `tests/bdd/features/<modulo>.feature`:

```gherkin
# language: en
@test_regresion @perfil_admin
Feature: <Módulo>
  Como <rol>
  Quiero <acción>
  Para <beneficio>

  Background: Usuario autenticado
    Given que el usuario está autenticado

  @smoke @TC_<ID>
  Scenario: <Descripción del caso>
    When el usuario ...
    Then se visualiza ...
```

- El step `que el usuario está autenticado` ya existe en `conftest.py`; no lo redefinas.
- Escenarios independientes: no mezcles consulta, creación y eliminación.
- Todo tag debe estar registrado en `pytest.ini`, salvo `@TC_<ID>`.
- Si el caso guarda datos reales, márcalo `@persistente` y condiciona el clic
  final a `permitir_cambios_persistentes`.

## 4. Implementar el Page Object

Sigue el skill `crear-page-object`, incluida su fixture en `conftest.py`. Los datos
de prueba van en `data/<modulo>.json` y se leen con `utils.test_data.obtener_seccion_validada`.

## 5. Implementar los steps

Lista los pasos que faltan y su esqueleto antes de escribir:

```bash
.venv/bin/python tools/verificar_steps.py tests/bdd/features/<modulo>.feature --sugerir
```

Si al explorar la UI encuentras algo que el caso del plan no define (texto exacto de
un mensaje, nombre de un botón, un permiso), no lo supongas en silencio: anótalo como
duda para registrarla con el skill `actualizar-plan`.

Crea o actualiza `tests/bdd/steps/test_<modulo>_steps.py`:

```python
"""Definiciones de pasos BDD para <módulo>."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import allure
from pytest_bdd import scenario, then, when

from pages.modulo_page import ModuloPage
from utils.logger import logger


FEATURE = Path(__file__).resolve().parents[1] / "features" / "modulo.feature"


@allure.epic("App")
@allure.feature("<Módulo>")
@allure.story("<Historia>")
@allure.severity(allure.severity_level.NORMAL)
@scenario(str(FEATURE), "<Descripción del caso>")
def test_descripcion_del_caso() -> None:
    """Escenario BDD: <descripción>."""


@when("el usuario ...")
def accion(modulo_page: ModuloPage, run_async: Callable) -> None:
    """..."""
    with allure.step("..."):
        run_async(modulo_page.goto())
        logger.paso("...")
```

- **Los steps son síncronos (`def`)** y llaman a los métodos async con `run_async(...)`.
- Steps delgados: toda la interacción va en el Page Object.

## 6. Verificar

```bash
# macOS / Linux (Windows: .venv\Scripts\python)
.venv/bin/python tools/validar_convenciones.py      # incluye pasos sin step en escenarios enlazados
.venv/bin/python tools/verificar_steps.py tests/bdd/features/<modulo>.feature
.venv/bin/python -m pytest tests/bdd/steps/test_<modulo>_steps.py --headed
```

- Corrige todos los errores del validador antes de ejecutar la prueba.
- No agregues `--persistir-cambios` salvo que el usuario lo pida.
- Si la ejecución falla, revisa el screenshot del paso fallido en el reporte
  Allure antes de cambiar locators.
