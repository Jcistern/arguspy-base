---
name: crear-page-object
description: Crea o mejora un Page Object de Playwright Python a partir de la UI real y registra su fixture en conftest.py. Usar cuando haya que modelar una pantalla nueva o ampliar una existente.
---

# Crear un Page Object con Playwright Python

## Entradas

Si el usuario no lo indicó, pregunta:
- Nombre del Page Object en PascalCase (ej: Dashboard, Usuarios).
- Ruta relativa a `APP_BASE_URL` (ej: `/dashboard`).
- Si requiere sesión y con qué perfil (por defecto `admin`).

## 1. Revisar el proyecto

Lee `pages/base_page.py`, `conftest.py` y los Page Objects existentes del módulo
para reutilizar métodos y no duplicar locators.

## 2. Explorar la interfaz real

Sigue el skill `explorar-ui`. Confirma:
- Rol y nombre accesible de enlaces, botones, diálogos y tablas.
- Etiquetas accesibles de los campos de formulario.
- Un elemento estable que indique que la página cargó.
- Contenedores accesibles para acotar controles repetidos.

## 3. Implementar el Page Object

Crea `pages/<nombre_en_snake_case>_page.py`, hereda de `BasePage` e inicializa los
locators en el constructor.

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

Las acciones van en el Page Object; los datos, en `data/*.json`; las
verificaciones de flujo, en los steps.

## 4. Registrar la fixture

En `conftest.py`, sección "Page Objects":

```python
@pytest.fixture
def ejemplo_page(app_page: Page) -> EjemploPage:
    """Expone el Page Object de la pantalla Ejemplo."""
    return EjemploPage(app_page)
```

## 5. Verificar

```bash
.venv/bin/python tools/validar_convenciones.py     # Windows: .venv\Scripts\python tools\validar_convenciones.py
```

Corrige todos los errores que informe (incluye `pytest --collect-only`).
