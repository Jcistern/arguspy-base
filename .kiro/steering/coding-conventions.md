---
inclusion: fileMatch
fileMatchPattern: ["tests/**/*.py", "tests/**/*.feature", "pages/**/*.py", "conftest.py"]
---

# Convenciones de código — Playwright Python + pytest-bdd

Este repositorio **no usa Playwright con TypeScript**. No generar archivos `.ts`,
imports de `@playwright/test` ni comandos `npm`/`npx`.

## Locators: prioridad y reglas

Inicializar los locators en el constructor del Page Object:

```python
import re

self._boton_guardar = page.get_by_role(
    "button", name=re.compile(r"^Guardar$", re.IGNORECASE)
)
self._correo = page.get_by_label(re.compile(r"Correo electrónico", re.IGNORECASE))
self._buscador = page.get_by_placeholder(re.compile(r"Buscar", re.IGNORECASE))
```

Orden de preferencia:
1. `get_by_role()` con `name` exacto o expresión regular anclada.
2. `get_by_label()` para controles de formulario.
3. `get_by_placeholder()` cuando no exista etiqueta accesible.
4. `get_by_test_id()` si la aplicación entrega atributos de prueba estables.
5. CSS específico solo como último recurso, con un comentario que explique la
   limitación de accesibilidad (ej: botón sin nombre accesible).

No usar XPath, clases de estilo, índices arbitrarios (`.first`, `.nth`) ni
`force=True`. Si hay controles con nombres repetidos, acotar el locator con un
contenedor accesible (`dialog`, `form`, `region`, `group`).

Validar los locators contra la UI real antes de consolidarlos, usando el MCP
`argus-playwright` (herramientas `abrir`, `iniciar_sesion` y `snapshot`).

## Esperas y sincronización

- No usar `page.wait_for_timeout()` ni `time.sleep()`.
- Confiar en el auto-wait de Playwright y en `expect(...)`.
- Tras navegar, verificar un elemento estable de la página con `expect(...).to_be_visible()`.

## Page Objects

Encapsulan locators y acciones de UI; no contienen datos de prueba ni reglas de
negocio. Heredan de `BasePage` y sus métodos son `async`.

```python
from __future__ import annotations

import re

from playwright.async_api import Page, expect

from pages.base_page import BasePage


class EjemploPage(BasePage):
    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._titulo = page.get_by_role(
            "heading", name=re.compile(r"Ejemplo", re.IGNORECASE)
        )

    async def goto(self) -> None:
        await self.page.goto("/ruta", wait_until="domcontentloaded")
        await expect(self._titulo).to_be_visible()
```

Cada Page Object nuevo necesita su fixture en `conftest.py`, creada a partir de `app_page`:

```python
@pytest.fixture
def ejemplo_page(app_page: Page) -> EjemploPage:
    return EjemploPage(app_page)
```

## BDD con pytest-bdd

- Los features usan `# language: en` (palabras clave `Feature`, `Background`,
  `Scenario`, `Given/When/Then`) con el texto en español.
- **Los steps son funciones síncronas** (`def`, nunca `async def`). Para llamar
  a métodos del Page Object usar la fixture `run_async`:

  ```python
  @when("el usuario guarda el formulario")
  def guardar(ejemplo_page: EjemploPage, run_async: Callable) -> None:
      with allure.step("Guardar el formulario"):
          run_async(ejemplo_page.guardar())
  ```

- El login ya está centralizado en `conftest.py`. En el `Background` usar
  `Given que el usuario está autenticado` y **no redefinir ese step**. El perfil
  de credenciales se elige por tag (`@perfil_admin`).
- Declarar cada escenario con `@scenario(...)` y metadata Allure (`epic`,
  `feature`, `story`, `severity`).
- Escenarios pequeños e independientes: no mezclar consulta, creación y eliminación.
- Steps delgados: toda interacción va en el Page Object.
- Todo tag Gherkin debe estar registrado como marker en `pytest.ini`, excepto
  `@TC_<ID>` (enlace al Test Case de Azure DevOps), que se registra solo.

## Datos persistentes

Si un escenario guarda datos reales, condicionar el clic final a la fixture
`permitir_cambios_persistentes` (se activa con `--persistir-cambios`) y marcar el
escenario con `@persistente`.

## Datos, configuración y autenticación

- Datos de prueba no sensibles en `data/*.json`, leídos con
  `utils.test_data.obtener_seccion_validada`; no leer archivos desde los steps.
- Variables requeridas siempre vía `obtener_env_requerida("NOMBRE")`. Nunca
  hardcodear URLs, usuarios, contraseñas ni secretos.
- No exponer credenciales, tokens ni datos personales en logs o adjuntos de Allure.
