# ArgusPy - Proyecto de Pruebas Automatizadas

Fuente única de convenciones para personas y asistentes de IA (aXet, Claude Code
u otros). Las reglas de "Locators", "Esperas" y "BDD" las verifica
`tools/validar_convenciones.py` en pre-commit, en el pipeline y en los hooks de aXet.

## Descripción
Framework de automatización E2E de aplicaciones web con Python, pytest-bdd y Playwright.

Este repositorio **no usa Playwright con TypeScript**. No generar archivos `.ts`,
imports de `@playwright/test` ni comandos `npm`/`npx`.

## Stack
- **Python 3.10+**
- **pytest** + **pytest-bdd** (escenarios Gherkin) + **pytest-asyncio**
- **Playwright** con API asíncrona (`playwright.async_api`) sobre Chromium
- **Allure** (resultados) + reporte HTML propio (`reporting/`)
- Configuración: `pytest.ini` (markers y opciones) y `config/environments/<AMBIENTE>.env`

## Estructura
- `config/` - carga del `.env` del ambiente (`AMBIENTE`, por defecto `dev`)
- `pages/` - Page Objects; todos heredan de `pages/base_page.py`
- `tests/bdd/features/` - archivos `.feature`
- `tests/bdd/steps/` - steps (`test_<modulo>_steps.py`) con `@scenario(...)`
- `data/` - datos de prueba JSON, leídos con `utils/test_data.py`; `data/planes/` (ignorada por git) guarda los planes de pruebas `.xlsx`
- `utils/` - `obtener_env_requerida`, logger, carga de datos
- `reporting/` - generador del reporte HTML a partir de `allure-results/`
- `tools/` - publicación en Azure Test Plans, script de reporte y `validar_convenciones.py`
- `conftest.py` - fixtures (`app_page`, `login_page`, `run_async`), login del Background y hooks de evidencia
- `.kiro/mcp/playwright_server.py` - servidor MCP `argus-playwright` para explorar la UI
- `.kiro/mcp/explorar.py` - la misma exploración desde la terminal, sin cliente MCP
- `.axet-plugin/skills/` - procedimientos paso a paso (explorar UI, crear Page Object, automatizar caso, analizar fallos, revisar cambios)

## Comandos
Ejecuta siempre con el Python del entorno virtual: `.venv/bin/python -m pytest ...` en
macOS/Linux y `.venv\Scripts\python -m pytest ...` en Windows (o con el `.venv` activado).
El proyecto es multiplataforma: no uses comandos exclusivos de bash (heredocs, `cp`)
en instrucciones o scripts compartidos; prefiere scripts Python.
Dependencias: se declaran en `requirements*.txt` y se instalan desde `requirements*.lock`
(versiones exactas); si cambias un `.txt`, regenera su `.lock` con `uv pip compile` (ver README).
Nunca edites un `.lock` a mano.

- `pytest` - todas las pruebas
- `pytest -m smoke` - por marker
- `pytest --headed --slowmo=500` - navegador visible y lento
- `pytest <archivo_steps> --collect-only` - validar recolección
- `python tools/validar_convenciones.py` - validar convenciones (+ recolección)
- `python tools/resumen_fallos.py` - resumen de las pruebas fallidas desde `allure-results/`
- `python tools/plan_pruebas.py leer|revisar|comparar|agregar <plan.xlsx>` - sincroniza el plan de pruebas con los `.feature`
- `python tools/verificar_steps.py [feature] --sugerir` - pasos de los `.feature` sin step definido (sin ejecutar)
- `pytest --alluredir=allure-results --clean-alluredir` - resultados Allure
- `python -m reporting.generate_report --results allure-results --output reporte-html` - reporte HTML

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
contenedor accesible (`dialog`, `form`, `region`, `group`). Si un caso está
justificado, marcar la línea con `# argus: permitido <motivo>`.

Si el nombre accesible incluye un ícono (ej: `" Login"`), no anclar el inicio:
`re.compile(r"Login\s*$", re.IGNORECASE)`.

Antes de proponer locators nuevos, revisar los Page Objects existentes en `pages/`
y reutilizar lo que ya exista. Validar los locators contra la UI real (ver
"Exploración de la UI").

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
  `@TC_<ID>` (enlace al Test Case de Azure DevOps) y `@CP_<PANTALLA>_<NN>` (enlace al
  caso del plan de pruebas `.xlsx`), que se registran solos.
- Cada escenario que viene del plan lleva su `@CP_…`. Un escenario sin `@CP_` es un caso
  que falta en el plan (`%actualizar-plan` lo agrega), salvo que tenga `@sin_plan`.
- Los datos de cada escenario van en la tabla `Examples` o entre comillas en el step.

## Datos persistentes

Si un escenario guarda datos reales, condicionar el clic final a la fixture
`permitir_cambios_persistentes` (se activa con `--persistir-cambios`) y marcar el
escenario con `@persistente`. Nunca ejecutar con `--persistir-cambios` sin que
el usuario lo pida explícitamente.

## Datos, configuración y autenticación

- Datos de prueba no sensibles en `data/*.json`, leídos con
  `utils.test_data.obtener_seccion_validada`; no leer archivos desde los steps.
- Variables requeridas siempre vía `obtener_env_requerida("NOMBRE")`. Nunca
  hardcodear URLs, usuarios, contraseñas ni secretos.
- No exponer credenciales, tokens ni datos personales en logs o adjuntos de Allure.

## Exploración de la UI

Para descubrir locators se usa el **árbol accesible**, no capturas de pantalla:

1. MCP `argus-playwright` (herramientas `iniciar_sesion`, `abrir`, `snapshot`,
   `clic`, `completar`, `captura`, `cerrar`), si el asistente lo tiene configurado.
2. Si no, `.kiro/mcp/explorar.py` desde la terminal:

   ```bash
   .venv/bin/python .kiro/mcp/explorar.py /login --sin-sesion          # Windows: .venv\Scripts\python .kiro\mcp\explorar.py ...
   .venv/bin/python .kiro/mcp/explorar.py /dashboard --perfil admin --clic "button:Nuevo" --contenedor "dialog:Nuevo"
   ```

Ambos inician sesión con `LoginPage` y las credenciales del `.env`, sin mostrarlas.
No usar navegadores integrados del asistente para definir locators.

## Uso de asistentes de IA

- **Nunca leer, mostrar ni editar `config/environments/*.env`**: contienen
  credenciales y el contenido que lee un asistente se envía a su proveedor.
  Para saber qué variables existen, usar `*.env.example`.
- Acotar los snapshots al contenedor necesario (`--contenedor`) y no copiar
  tablas con datos personales de la aplicación al chat.
- Antes de dar por terminado un cambio, ejecutar `python tools/validar_convenciones.py`
  (con el Python del `.venv`) y corregir los errores.
- No hacer `git push` ni commits sin que el usuario lo pida.
