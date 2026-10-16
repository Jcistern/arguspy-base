"""Fixtures compartidos y configuración global de pytest para ArgusPy."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import allure
import nest_asyncio
import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright
from pytest_bdd import given

from config.settings import AMBIENTE_ACTIVO
from pages.login_page import LoginPage
from utils.helpers import obtener_env_requerida
from utils.logger import logger

nest_asyncio.apply()

_bdd_loop: asyncio.AbstractEventLoop | None = None

# Referencia a la config activa de pytest, usada para registrar dinamicamente
# los markers @TC_<ID> de Azure DevOps sin listarlos todos en pytest.ini.
_pytest_config: pytest.Config | None = None
_tc_markers_registrados: set[str] = set()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Registra las opciones de línea de comandos propias de ArgusPy."""
    try:
        parser.addoption(
            "--headed",
            action="store_true",
            default=False,
            help="Ejecuta los tests con el navegador visible.",
        )
        parser.addoption(
            "--persistir-cambios",
            action="store_true",
            default=False,
            help=(
                "Habilita operaciones que persisten datos en la aplicación. "
                "Sin esta opción, los escenarios se detienen antes de guardar."
            ),
        )
        parser.addoption(
            "--slowmo",
            action="store",
            default=0,
            type=int,
            help="Milisegundos de pausa entre cada acción de Playwright (ej: --slowmo=500).",
        )
    except ValueError:
        pass


def pytest_configure(config: pytest.Config) -> None:
    """Prepara directorios de artefactos y muestra el ambiente de ejecución."""
    for directorio in ("allure-results", "playwright-report", "test-results"):
        Path(directorio).mkdir(parents=True, exist_ok=True)

    global _pytest_config
    _pytest_config = config
    logger.info(f"Iniciando tests en ambiente: {AMBIENTE_ACTIVO}")


def pytest_bdd_apply_tag(tag: str, function):
    """Mapea los tags Gherkin ``@TC_<ID>`` y ``@perfil_*`` a markers de pytest.

    Cada escenario enlazado a un Test Case de Azure DevOps lleva un tag
    ``@TC_<ID>`` (ej: ``@TC_1234``). El marker se registra en tiempo de
    colección para no romper ``--strict-markers``. Para el resto de tags se
    devuelve ``None`` y pytest-bdd aplica su comportamiento por defecto.
    """
    # @CP_<PANTALLA>_<NN> enlaza el escenario con su caso del plan de pruebas (.xlsx).
    if tag.startswith(("TC_", "CP_")):
        if _pytest_config is not None and tag not in _tc_markers_registrados:
            descripcion = f"Test Case Azure DevOps ID {tag[3:]}" if tag.startswith("TC_") else f"Caso del plan {tag}"
            _pytest_config.addinivalue_line("markers", f"{tag}: {descripcion}")
            _tc_markers_registrados.add(tag)
        getattr(pytest.mark, tag)(function)
        return True
    # Tags de perfil de login: se aplican como markers para que el step de
    # Background pueda leerlos con request.node.iter_markers().
    if tag in _PERFILES:
        getattr(pytest.mark, tag)(function)
        return True
    return None


# ---------------------------------------------------------------------------
# Fixture de navegador
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_page(request: pytest.FixtureRequest, pytestconfig: pytest.Config) -> Page:
    """Abre Chromium con un contexto aislado apuntando a ``APP_BASE_URL``.

    Las capturas de evidencia las toman los hooks de pytest-bdd (ver más abajo).
    """
    global _bdd_loop
    _bdd_loop = asyncio.get_running_loop()

    headed = pytestconfig.getoption("--headed", default=False)
    headless_env = os.getenv("HEADLESS", "true").lower() != "false"
    headless = False if headed else headless_env
    slowmo = int(pytestconfig.getoption("--slowmo", default=0))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            slow_mo=slowmo if slowmo > 0 else None,
        )
        context = await browser.new_context(
            locale="es-CL",
            timezone_id="America/Santiago",
            # base_url permite que los Page Objects naveguen con rutas relativas.
            base_url=obtener_env_requerida("APP_BASE_URL"),
        )
        pg = await context.new_page()
        pg.set_default_timeout(60_000)
        pg.set_default_navigation_timeout(60_000)

        request.node._argus_page = pg

        yield pg

        try:
            await context.close()
            await browser.close()
        except Exception as exc:
            logger.warn("No se pudo cerrar el navegador", str(exc))


@pytest.fixture(autouse=True)
def _registrar_test_case_id(request: pytest.FixtureRequest, record_property) -> None:
    """Vuelca los tags @TC_<ID> del test como propiedad en el JUnit XML.

    Permite que 'tools/publish_testplan_result.py' descubra a qué Test Case
    de Azure DevOps corresponde cada test ejecutado.
    """
    for marcador in request.node.iter_markers():
        if marcador.name.startswith("TC_"):
            record_property("test_case_id", marcador.name[len("TC_"):])


@pytest.fixture
def permitir_cambios_persistentes(pytestconfig: pytest.Config) -> bool:
    """Indica si la ejecución autorizó explícitamente cambios persistentes.

    Los escenarios deben completar sus validaciones previas al envío siempre.
    Solo el último clic que persiste información puede depender de esta opción.
    """
    return bool(pytestconfig.getoption("--persistir-cambios", default=False))


@pytest.fixture
def run_async():
    """Ejecuta una coroutine en el event loop activo de pytest-asyncio.

    Uso exclusivo en pasos BDD sincronos para awaitear metodos async de
    los Page Objects sin cambiar pytest-bdd por un framework async.

    Ejemplo::

        @given("que el usuario abre la aplicación")
        def abrir_login(login_page, run_async):
            run_async(login_page.goto())
    """
    def _run(coro):
        if _bdd_loop is None:
            raise RuntimeError(
                "run_async: no hay event loop disponible (fixture 'app_page' no fue inicializado)"
            )
        return _bdd_loop.run_until_complete(coro)

    return _run


# ---------------------------------------------------------------------------
# Page Objects
# ---------------------------------------------------------------------------


@pytest.fixture
def login_page(app_page: Page) -> LoginPage:
    """Expone el Page Object de login de la aplicación."""
    return LoginPage(app_page)


# ---------------------------------------------------------------------------
# Hooks pytest-bdd: screenshots de evidencia
# ---------------------------------------------------------------------------

_last_step_screenshot: dict = {}
# Tests cuyo screenshot final ya se adjuntó como captura del step fallido.
_captura_error_adjuntada: set[str] = set()


def pytest_bdd_after_step(request, feature, scenario, step, step_func):
    """Guarda en memoria el screenshot del step actual (se sobreescribe en cada step)."""
    page = getattr(request.node, "_argus_page", None)
    if page is None or page.is_closed():
        return

    try:
        if _bdd_loop is not None:
            captura = _bdd_loop.run_until_complete(page.screenshot(full_page=True))
            _last_step_screenshot[request.node.nodeid] = captura
    except Exception:
        pass


def pytest_bdd_step_error(request, feature, scenario, step, step_func, step_func_args, exception):
    """Captura un screenshot cuando un step BDD falla y lo adjunta inmediatamente."""
    page = getattr(request.node, "_argus_page", None)
    if page is None or page.is_closed():
        return

    step_keyword = step.keyword.strip()
    step_label = f"ERROR_{step_keyword}_{step.name[:50]}"
    step_label = step_label.replace(" ", "_").replace("/", "_").replace("\\", "_")

    try:
        if _bdd_loop is not None:
            captura = _bdd_loop.run_until_complete(page.screenshot(full_page=True))
            allure.attach(
                captura,
                name=f"step_{step_label}",
                attachment_type=allure.attachment_type.PNG,
            )
            _last_step_screenshot[request.node.nodeid] = captura
            _captura_error_adjuntada.add(request.node.nodeid)
    except Exception as exc:
        logger.warn(f"No se pudo capturar screenshot del step fallido: {exc}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    """Al terminar cada test, adjunta el screenshot del ULTIMO step a Allure y
    lo guarda como evidencia ``TC_<id>.png`` (pase o falle el caso).

    Si el test falló en un step, esa captura ya se adjuntó en
    ``pytest_bdd_step_error`` y no se repite."""
    yield
    nodeid = item.nodeid
    captura = _last_step_screenshot.pop(nodeid, None)
    ya_adjuntada = nodeid in _captura_error_adjuntada
    _captura_error_adjuntada.discard(nodeid)
    if captura is None:
        return

    if not ya_adjuntada:
        allure.attach(
            captura,
            name="resultado_final",
            attachment_type=allure.attachment_type.PNG,
        )

    try:
        tc_id = None
        for marcador in item.iter_markers():
            if marcador.name.startswith("TC_"):
                tc_id = marcador.name[len("TC_"):]
                break
        if tc_id:
            evidencia_dir = Path("test-results") / "evidencia"
            evidencia_dir.mkdir(parents=True, exist_ok=True)
            (evidencia_dir / f"TC_{tc_id}.png").write_bytes(captura)
    except Exception as exc:
        logger.warn(f"No se pudo guardar la evidencia TC del ultimo paso: {exc}")


# ---------------------------------------------------------------------------
# Autenticación centralizada del Background (selección de perfil por tag)
# ---------------------------------------------------------------------------
# Los escenarios arrancan su Background con "que el usuario está autenticado".
# El perfil de credenciales lo decide un tag del escenario/feature
# (ej: @perfil_admin). Para agregar un perfil, sumar una entrada aquí y el
# marker correspondiente en pytest.ini.

# Perfiles soportados: tag Gherkin -> (env_usuario, env_password, etiqueta).
_PERFILES = {
    "perfil_admin": ("APP_ADMIN_USER", "APP_ADMIN_PASSWORD", "admin"),
}
_PERFIL_POR_DEFECTO = "perfil_admin"


def _resolver_perfil(request) -> tuple[str, str, str]:
    """Resuelve el perfil de login según el tag del escenario/feature."""
    for marcador in request.node.iter_markers():
        if marcador.name in _PERFILES:
            return _PERFILES[marcador.name]
    return _PERFILES[_PERFIL_POR_DEFECTO]


@given("que el usuario está autenticado")
def _given_autenticado(login_page: LoginPage, run_async, request) -> None:
    """Login centralizado; el perfil lo define el tag del escenario."""
    env_usuario, env_password, etiqueta = _resolver_perfil(request)
    usuario = obtener_env_requerida(env_usuario)
    password = obtener_env_requerida(env_password)
    with allure.step(f"Autenticar como {etiqueta}"):
        run_async(login_page.goto())
        run_async(login_page.login(usuario, password))
