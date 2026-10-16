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
python -m venv .venv          # Windows: py -3.12 -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.lock  # pruebas + herramientas (pre-commit, plan .xlsx, MCP); solo pruebas: requirements.lock
python -m playwright install chromium
```

Los `.lock` fijan versiones exactas para que todas las máquinas (Windows, macOS, Linux y el pipeline) instalen lo mismo. Las dependencias directas se declaran en `requirements.txt` / `requirements-dev.txt`; tras modificarlas, regenera los lock con [uv](https://docs.astral.sh/uv/):

```bash
uv pip compile requirements.txt --universal --python-version 3.10 -o requirements.lock
uv pip compile requirements-dev.txt --universal --python-version 3.10 -o requirements-dev.lock
```

Crea tu archivo de ambiente a partir del ejemplo y complétalo:

```bash
cp config/environments/dev.env.example config/environments/dev.env
# Windows: copy config\environments\dev.env.example config\environments\dev.env
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
│   ├── features/                # .feature (uno por pantalla, enlazados al plan con @CP_)
│   └── steps/                   # test_<pantalla>_steps.py con @scenario(...)
├── reporting/                   # generador del reporte HTML
├── tools/
│   ├── publish_testplan_result.py
│   ├── run_report.ps1
│   ├── validar_convenciones.py  # convenciones de AGENTS.md (pre-commit, CI, hooks)
│   ├── resumen_fallos.py        # resumen de pruebas fallidas (allure-results)
│   ├── plan_pruebas.py          # plan de pruebas .xlsx ⇄ .feature (casos y dudas)
│   ├── verificar_steps.py       # pasos de los .feature sin step definido
│   └── hook_axet.py             # hooks de aXet
├── utils/
│   ├── helpers.py               # obtener_env_requerida
│   ├── logger.py
│   └── test_data.py             # cargar_datos_json / obtener_seccion_validada
├── conftest.py                  # fixtures, hooks de evidencia y login del Background
├── azure-pipelines.yml          # plantilla de pipeline
├── pytest.ini
├── AGENTS.md                    # convenciones para personas y asistentes de IA
├── .axetrules/                  # reglas y hooks de aXet
├── .axet-plugin/skills/         # procedimientos (skills) de aXet
└── .kiro/mcp/                   # exploración de UI: explorar.py y servidor MCP argus-playwright
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

El `index.html` es autocontenido (los datos van incrustados), así que se abre directamente con doble clic:

```bash
python -m pytest --alluredir=allure-results --clean-alluredir
python -m reporting.generate_report --results allure-results --output reporte-html
# abrir reporte-html/index.html
```

En Windows, `.\tools\run_report.ps1` ejecuta las pruebas, genera el reporte y lo abre en un solo paso.

## Asistentes de IA y validaciones

Las convenciones viven en un solo lugar, **`AGENTS.md`**, y los procedimientos en **`.axet-plugin/skills/`**. Cada herramienta solo apunta a ellos:

| Herramienta | Qué lee |
|---|---|
| **aXet** | `AGENTS.md`, `.axetrules/reglas.md`, skills con `%explorar-ui`, `%crear-page-object`, `%automatizar-caso`, `%analizar-fallo`, `%revisar-cambios`, `%importar-plan`, `%actualizar-plan`; `.clineignore` le oculta los `.env` |
| **Claude Code** | `CLAUDE.md` (importa `AGENTS.md`) |

### Validaciones (para todo el equipo, con o sin IA)

`tools/validar_convenciones.py` revisa `pages/`, `tests/` y `conftest.py` (sin `wait_for_timeout`, `time.sleep`, `force=True`, XPath ni steps `async`; tags registrados en `pytest.ini`) y ejecuta `pytest --collect-only`. Se aplica en tres lugares:

- **pre-commit**, en cada commit. Activarlo una vez por clon: `.venv/bin/python -m pre_commit install` (Windows: `.venv\Scripts\python -m pre_commit install`).
- **Azure Pipelines**, paso `Validar convenciones` antes de ejecutar las pruebas.
- **Hooks de aXet** (`.axetrules/hooks/`, solo macOS/Linux): activar *Settings → Feature Settings → Enable Hooks*. Bloquean leer `.env` y editar `.lock`, y avisan al asistente de las infracciones apenas edita un archivo.

Para aceptar un caso justificado, agregar `# argus: permitido <motivo>` en la línea.

### Plan de pruebas ⇄ .feature

Los planes `.xlsx` se dejan en `data/planes/` (ignorada por git). Cada escenario se enlaza con su caso por el tag `@CP_<PANTALLA>_<NN>` (ej: `CP-PRD-02` → `@CP_PRD_02`).

- `%importar-plan`: convierte los casos del plan en `.feature` (un feature por pantalla).
- `%actualizar-plan`: agrega al plan los escenarios sin `@CP_` con ID provisional (`CP-PRD-N01`) y marca como `automática` los casos automatizados. Escribe una copia `<plan>_actualizado.xlsx`; el original no se toca.
- Los escenarios propios del framework llevan `@sin_plan` y no se sincronizan.

```bash
.venv/bin/python tools/plan_pruebas.py revisar data/planes/<plan>.xlsx    # casos incompletos o vagos
.venv/bin/python tools/plan_pruebas.py comparar data/planes/<plan>.xlsx   # plan vs .feature
.venv/bin/python tools/verificar_steps.py --sugerir                       # pasos sin step definido
```

Lo que el plan no define se registra como duda en la hoja «Dudas» (ID provisional `D-<PANTALLA>-N01`) en vez de suponerlo.

### Configuración recomendada de aXet

Modelo **Claude Sonnet 5** (o equivalente), *Auto Compact* y *Checkpoints* activos, **YOLO Mode desactivado**. Se recomienda marcar *Browser Settings → Disable browser tool usage*: los locators se obtienen del árbol accesible, no de capturas.

### Exploración de la UI

`argus-playwright` (`.kiro/mcp/playwright_server.py`) abre Chromium con la config del `.env`, inicia sesión con `LoginPage` y entrega el árbol accesible (`snapshot`) para definir locators. aXet no admite conectores MCP propios, así que usa la versión de terminal:

```bash
.venv/bin/python .kiro/mcp/explorar.py /login --sin-sesion
.venv/bin/python .kiro/mcp/explorar.py /dashboard --perfil admin --clic "button:Nuevo" --contenedor "dialog:Nuevo"
```

En Windows, `.venv\Scripts\python .kiro\mcp\explorar.py ...`.

En un cliente que sí admita MCP propios (ej: Claude Code), se registra con `command` = Python del `.venv` y `args` = ruta a `.kiro/mcp/playwright_server.py` (requiere `requirements-dev.lock`).

## Azure DevOps (opcional)

- **Pipeline:** `azure-pipelines.yml` es una plantilla. Regístrala como pipeline nuevo en el proyecto de la aplicación, define las variables `APP_BASE_URL`, `APP_LOGIN_PATH`, `APP_ADMIN_USER` y `APP_ADMIN_PASSWORD` (las contraseñas como secretas) y ajusta `agentPool` y `pytestMarker`.
- **Test Plans:** etiqueta cada escenario con `@TC_<ID>` (ID del Test Case en Azure). El ID queda en el JUnit y la evidencia se guarda como `test-results/evidencia/TC_<ID>.png`. Con la variable `testPlanId` definida, el pipeline publica cada resultado en su Test Point con `tools/publish_testplan_result.py`.
