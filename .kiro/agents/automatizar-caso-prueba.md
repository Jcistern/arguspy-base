---
name: automatizar-caso-prueba
description: Automatiza un caso de prueba BDD de punta a punta con Playwright Python, pytest y pytest-bdd.
tools: ["read", "write", "shell", "@argus-playwright"]
includeMcpJson: true
resources: ["file://.kiro/steering/**/*.md"]
---

# Automatizar un caso BDD con Playwright Python

Automatiza el caso solicitado con el stack real del proyecto: Python, `pytest`,
`pytest-bdd`, `pytest-asyncio` y `playwright.async_api`. No crees código de
Playwright TypeScript.

## Entradas

Antes de comenzar, pregunta al usuario:
- Módulo (ej: `usuarios`, `dashboard`).
- Ruta de la pantalla, relativa a `APP_BASE_URL`.
- Descripción del caso en español.
- ID del Test Case en Azure DevOps, si existe (para el tag `@TC_<ID>`).

## 1. Revisar el proyecto

1. Lee `conftest.py`, `pages/base_page.py` y los Page Objects, features y steps existentes del módulo.
2. Usa `obtener_env_requerida(...)` para toda variable requerida.
3. No imprimas ni adjuntes credenciales, tokens o datos personales.

## 2. Explorar el flujo

Con el MCP `argus-playwright`: `iniciar_sesion`, `abrir(ruta)` y `snapshot()`.
Recorre el flujo con `clic` y `completar`, repitiendo `snapshot` en cada estado.
Si el MCP no está disponible, usa el procedimiento del agente `explorar-ui-cli`.

Identifica locators accesibles reales y los estados verificables con `expect(...)`.

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

Crea o mejora `pages/<modulo>_page.py` siguiendo el agente `crear-page-object`,
incluida su fixture en `conftest.py`. Los datos de prueba van en `data/<modulo>.json`
y se leen con `utils.test_data.obtener_seccion_validada`.

## 5. Implementar los steps

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
python -m pytest tests/bdd/steps/test_<modulo>_steps.py --collect-only -q
python -m pytest tests/bdd/steps/test_<modulo>_steps.py --headed
```

Si la ejecución falla, revisa el screenshot del paso fallido en el reporte
Allure antes de cambiar locators.
