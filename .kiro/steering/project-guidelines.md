# ArgusPy - Proyecto de Pruebas Automatizadas

## Descripción
Framework de automatización E2E de aplicaciones web con Python, pytest-bdd y Playwright.

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
- `data/` - datos de prueba JSON, leídos con `utils/test_data.py`
- `utils/` - `obtener_env_requerida`, logger, carga de datos
- `reporting/` - generador del reporte HTML a partir de `allure-results/`
- `tools/` - publicación en Azure Test Plans y script de reporte
- `conftest.py` - fixtures (`app_page`, `login_page`, `run_async`), login del Background y hooks de evidencia
- `.kiro/mcp/playwright_server.py` - servidor MCP `argus-playwright` para explorar la UI

## Comandos
- `pytest` - todas las pruebas
- `pytest -m smoke` - por marker
- `pytest --headed --slowmo=500` - navegador visible y lento
- `pytest <archivo_steps> --collect-only` - validar recolección
- `pytest --alluredir=allure-results --clean-alluredir` - resultados Allure
- `python -m reporting.generate_report --results allure-results --output reporte-html` - reporte HTML
