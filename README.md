# ArgusPy 🐍🎭

Framework de automatización web construido con **Python**, **pytest**, **pytest-bdd** y **Playwright**.

---

## Características

- **Python 3.10+** con type hints.
- **Playwright** con API asíncrona (`playwright.async_api`) sobre Chromium.
- **pytest-bdd** para escenarios Gherkin que reutilizan los Page Objects y fixtures.
- **Page Object Model (POM)** con `BasePage` reutilizable.
- Login por usuario y contraseña, centralizado en el Background y con perfiles por tag (`@perfil_admin`).
- Locators **ARIA-first** (`get_by_role`, `get_by_label`, `get_by_placeholder`).
- Configuración por ambiente en `config/environments/<ambiente>.env`.
- Evidencias automáticas: screenshot del último paso de cada escenario y screenshot al fallar, adjuntos a Allure.
- Reporte HTML propio con historial, sin depender de Java ni del CLI de Allure.
- Integración opcional con Azure DevOps (pipeline y publicación en Test Plans).

## Inicio rápido

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Crea tu archivo de ambiente a partir del ejemplo y complétalo:

```bash
cp config/environments/dev.env.example config/environments/dev.env
```

```dotenv
AMBIENTE=dev
HEADLESS=true
APP_BASE_URL=https://mi-app.example.com/
APP_LOGIN_PATH=/
APP_ADMIN_USER=usuario
APP_ADMIN_PASSWORD=secreto
```

`dev.env` no se versiona. El ambiente activo se elige con la variable `AMBIENTE` (por defecto `dev`).

Ejecutar las pruebas:

```bash
pytest                    # todas
pytest --headed           # con navegador visible
pytest --slowmo=500       # pausa entre acciones
pytest -m smoke           # por marker
pytest --alluredir=allure-results --clean-alluredir
```

## Estructura

```text
ArgusPy/
├── config/
│   ├── environments/dev.env.example
│   └── settings.py              # carga del .env según AMBIENTE
├── data/                        # datos de prueba en JSON
├── pages/
│   ├── base_page.py             # acciones, esperas y verificaciones comunes
│   └── login_page.py            # login por usuario y contraseña
├── tests/bdd/
│   ├── features/login.feature
│   └── steps/test_login_steps.py
├── reporting/                   # generador del reporte HTML
├── tools/
│   ├── publish_testplan_result.py
│   └── run_report.ps1
├── utils/
│   ├── helpers.py               # obtener_env_requerida
│   ├── logger.py
│   └── test_data.py             # cargar_datos_json / obtener_seccion_validada
├── conftest.py                  # fixtures, hooks de evidencia y login del Background
├── azure-pipelines.yml          # plantilla de pipeline
└── pytest.ini
```

## Login y perfiles

`pages/login_page.py` trae locators genéricos (etiquetas "Usuario/Correo", "Contraseña" y botón "Ingresar/Iniciar sesión", en español e inglés). **Ajústalos a la aplicación real.**

Los escenarios inician sesión con el step global definido en `conftest.py`:

```gherkin
Given que el usuario está autenticado
```

Las credenciales salen del perfil indicado por tag (`@perfil_admin` → `APP_ADMIN_USER` / `APP_ADMIN_PASSWORD`). Para sumar un perfil, agrégalo a `_PERFILES` en `conftest.py` y registra su marker en `pytest.ini`.

## Agregar un módulo

1. Crea `pages/mi_pagina.py` heredando de `BasePage`.
2. Registra su fixture en `conftest.py` a partir de `app_page`:
   ```python
   @pytest.fixture
   def mi_pagina(app_page: Page) -> MiPagina:
       return MiPagina(app_page)
   ```
3. Crea `tests/bdd/features/mi_modulo.feature` y `tests/bdd/steps/test_mi_modulo_steps.py`, cargando cada escenario con `@scenario(...)`.
4. En los steps (síncronos) ejecuta los métodos async de los Page Objects con la fixture `run_async`.
5. Si el módulo usa datos, guárdalos en `data/*.json` y léelos con `obtener_seccion_validada`.

Para pasos que guardan datos reales, condiciona el clic final a la fixture `permitir_cambios_persistentes` (se activa con `--persistir-cambios`) y marca el escenario con `@persistente`.

## Convenciones

- Hereda siempre de `BasePage` y consume los Page Objects mediante fixtures.
- Usa locators accesibles; evita CSS o XPath frágiles.
- No hardcodees URLs, usuarios ni contraseñas: usa `obtener_env_requerida`.
- Usa `allure.step` para separar acciones y verificaciones.
- Evita esperas fijas: Playwright gestiona el auto-waiting.

## Reporte HTML propio

El generador consume `allure-results/` y conserva epic, feature, story, severity, tags, pasos, duración y screenshots.

El reporte carga sus datos con `fetch()`, así que **hay que abrirlo por HTTP**, no con doble clic (`file://`):

```bash
python -m pytest --alluredir=allure-results --clean-alluredir
python -m reporting.generate_report --results allure-results --output reporte-html
python -m http.server 8000 -d reporte-html
# abrir http://localhost:8000/
```

En Windows, `.\tools\run_report.ps1` ejecuta las pruebas, genera el reporte y lo abre en un solo paso.

## Azure DevOps (opcional)

- **Pipeline:** `azure-pipelines.yml` es una plantilla. Regístrala como pipeline nuevo en el proyecto de la aplicación, define las variables `APP_BASE_URL`, `APP_LOGIN_PATH`, `APP_ADMIN_USER` y `APP_ADMIN_PASSWORD` (las contraseñas como secretas) y ajusta `agentPool` y `pytestMarker`.
- **Test Plans:** etiqueta cada escenario con `@TC_<ID>` (ID del Test Case en Azure). El ID queda en el JUnit y la evidencia se guarda como `test-results/evidencia/TC_<ID>.png`. Con la variable `testPlanId` definida, el pipeline publica cada resultado en su Test Point con `tools/publish_testplan_result.py`.
