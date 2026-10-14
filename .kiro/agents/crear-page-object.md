---
name: crear-page-object
description: Crea o mejora un Page Object Python para Playwright tras explorar la UI real, y registra su fixture.
tools: ["read", "write", "shell", "@argus-playwright"]
includeMcpJson: true
resources: ["file://.kiro/steering/**/*.md"]
---

# Crear un Page Object con Playwright Python

Crea o mejora un Page Object en Python para la pantalla indicada. El repositorio
usa `pytest`, `pytest-bdd` y `playwright.async_api`; no generes código TypeScript.

## Entradas

Antes de comenzar, pregunta al usuario:
- Nombre del Page Object en PascalCase (ej: Dashboard, Usuarios).
- Ruta relativa a `APP_BASE_URL` (ej: `/dashboard`).
- Si la pantalla requiere sesión y con qué perfil (por defecto `admin`).

## 1. Revisar el proyecto

Lee `pages/base_page.py`, `conftest.py` y los Page Objects existentes del módulo,
si los hay, para reutilizar métodos y no duplicar locators.

## 2. Explorar la interfaz real

Con el MCP `argus-playwright`: `iniciar_sesion(perfil)` si corresponde, `abrir(ruta)`
y `snapshot()`. Abre modales o menús con `clic(rol, nombre)` y repite `snapshot`.
Si el MCP no está disponible, usa el procedimiento del agente `explorar-ui-cli`.

Confirma:
- `role` y nombre accesible de enlaces, botones, diálogos y tablas.
- Etiquetas accesibles de los campos de formulario.
- Un elemento estable que indique que la página cargó.
- Contenedores accesibles para acotar controles repetidos.

## 3. Implementar el Page Object

Crea `pages/<nombre_en_snake_case>_page.py`, hereda de `BasePage` e inicializa los locators en el constructor.

```python
from __future__ import annotations

import re

from playwright.async_api import Page, expect

from pages.base_page import BasePage


class EjemploPage(BasePage):
    """Page Object de la pantalla Ejemplo."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._titulo = page.get_by_role(
            "heading", name=re.compile(r"Ejemplo", re.IGNORECASE)
        )
        self._boton_guardar = page.get_by_role(
            "button", name=re.compile(r"^Guardar$", re.IGNORECASE)
        )

    async def goto(self) -> None:
        """Navega a la pantalla y espera su título."""
        await self.page.goto("/ruta", wait_until="domcontentloaded")
        await expect(self._titulo).to_be_visible()

    async def guardar(self) -> None:
        """Hace clic en Guardar."""
        await self.click_element(self._boton_guardar)
```

## 4. Registrar la fixture

Agrega la fixture en `conftest.py`, en la sección "Page Objects":

```python
@pytest.fixture
def ejemplo_page(app_page: Page) -> EjemploPage:
    """Expone el Page Object de la pantalla Ejemplo."""
    return EjemploPage(app_page)
```

## Reglas

- Usa `get_by_role`, `get_by_label`, `get_by_placeholder` o `get_by_test_id`; CSS solo como último recurso documentado.
- Usa expresiones regulares con `re.IGNORECASE` para texto no exacto.
- No uses `page.wait_for_timeout()`, `time.sleep()` ni `force=True`.
- Las acciones van en el Page Object; los datos, en `data/*.json`; las verificaciones de flujo, en los steps.
- Verifica con `python -m pytest --collect-only -q` que el proyecto sigue recolectando sin errores.
