"""Servidor MCP de exploración de UI para ArgusPy (Playwright + Chromium).

Mantiene un navegador abierto entre llamadas y expone herramientas para
navegar, iniciar sesión y obtener el árbol accesible (``aria_snapshot``), que
es la base para definir locators con ``get_by_role`` / ``get_by_label``.

Usa la configuración del proyecto (``config/environments/<AMBIENTE>.env``):
``APP_BASE_URL``, ``APP_LOGIN_PATH`` y ``APP_<PERFIL>_USER`` / ``APP_<PERFIL>_PASSWORD``.

Requiere Python 3.10+ y ``fastmcp`` (ver ``requirements-dev.txt``).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROYECTO))
os.chdir(RAIZ_PROYECTO)

from config.settings import AMBIENTE_ACTIVO  # noqa: E402  (carga el .env del ambiente)
from pages.login_page import LoginPage  # noqa: E402
from utils.helpers import obtener_env_requerida  # noqa: E402

DIRECTORIO_CAPTURAS = RAIZ_PROYECTO / "test-results" / "mcp"

_pw: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_page: Optional[Page] = None


def _nombre(texto: str) -> re.Pattern[str]:
    """Convierte un nombre accesible en un patrón literal sin distinguir mayúsculas."""
    return re.compile(re.escape(texto), re.IGNORECASE)


async def _pagina() -> Page:
    """Retorna la página activa; abre el navegador si aún no existe."""
    global _pw, _browser, _context, _page
    if _page is not None and not _page.is_closed():
        return _page

    # start() en lugar de "async with": el navegador debe sobrevivir entre llamadas.
    if _pw is None:
        _pw = await async_playwright().start()
    if _browser is None or not _browser.is_connected():
        headless = os.getenv("MCP_HEADLESS", "false").lower() == "true"
        _browser = await _pw.chromium.launch(headless=headless)
    _context = await _browser.new_context(
        base_url=obtener_env_requerida("APP_BASE_URL"),
        locale="es-CL",
        timezone_id="America/Santiago",
    )
    _page = await _context.new_page()
    _page.set_default_timeout(15_000)
    return _page


async def abrir(ruta: str = "/") -> str:
    """Abre el navegador (si hace falta) y navega a una ruta relativa a APP_BASE_URL.

    Args:
        ruta: Ruta relativa (ej: /login, /dashboard) o URL completa.
    """
    page = await _pagina()
    await page.goto(ruta, wait_until="domcontentloaded")
    return f"Ambiente {AMBIENTE_ACTIVO}. URL: {page.url} | Título: {await page.title()}"


async def iniciar_sesion(perfil: str = "admin") -> str:
    """Inicia sesión con el LoginPage del proyecto usando las credenciales del perfil.

    Args:
        perfil: Perfil de credenciales; usa APP_<PERFIL>_USER y APP_<PERFIL>_PASSWORD.
    """
    page = await _pagina()
    prefijo = f"APP_{perfil.upper()}"
    usuario = obtener_env_requerida(f"{prefijo}_USER")
    password = obtener_env_requerida(f"{prefijo}_PASSWORD")
    login = LoginPage(page)
    await login.goto()
    await login.login(usuario, password)
    return f"Sesión iniciada como '{perfil}'. URL actual: {page.url}"


async def snapshot(rol_contenedor: str = "", nombre_contenedor: str = "") -> str:
    """Retorna el árbol accesible (roles y nombres) de la página o de un contenedor.

    Args:
        rol_contenedor: Rol del contenedor a acotar (ej: dialog, form, region). Vacío = página completa.
        nombre_contenedor: Nombre accesible del contenedor (opcional).
    """
    page = await _pagina()
    if rol_contenedor:
        if nombre_contenedor:
            objetivo = page.get_by_role(rol_contenedor, name=_nombre(nombre_contenedor))
        else:
            objetivo = page.get_by_role(rol_contenedor)
        objetivo = objetivo.first
    else:
        objetivo = page.locator("body")
    arbol = await objetivo.aria_snapshot()
    return f"URL: {page.url}\n\n{arbol}"


async def clic(rol: str, nombre: str) -> str:
    """Hace clic en un elemento por rol y nombre accesible (ej: button, "Guardar").

    Args:
        rol: Rol ARIA (button, link, tab, menuitem, checkbox...).
        nombre: Nombre accesible visible del elemento.
    """
    page = await _pagina()
    locator = page.get_by_role(rol, name=_nombre(nombre))
    cantidad = await locator.count()
    if cantidad != 1:
        return f"Se encontraron {cantidad} elementos {rol} '{nombre}'; acota con un contenedor."
    await locator.click()
    return f"Clic en {rol} '{nombre}'. URL actual: {page.url}"


async def completar(etiqueta: str, texto: str) -> str:
    """Completa un campo de formulario identificado por su etiqueta accesible.

    Args:
        etiqueta: Label accesible del campo (ej: "Correo electrónico").
        texto: Texto a ingresar.
    """
    page = await _pagina()
    locator = page.get_by_label(_nombre(etiqueta))
    cantidad = await locator.count()
    if cantidad != 1:
        return f"Se encontraron {cantidad} campos con etiqueta '{etiqueta}'."
    await locator.fill(texto)
    return f"Campo '{etiqueta}' completado."


async def captura(nombre: str = "captura") -> str:
    """Guarda un screenshot de la página completa en test-results/mcp/.

    Args:
        nombre: Nombre del archivo, sin extensión.
    """
    page = await _pagina()
    DIRECTORIO_CAPTURAS.mkdir(parents=True, exist_ok=True)
    ruta = DIRECTORIO_CAPTURAS / f"{nombre}.png"
    await page.screenshot(path=str(ruta), full_page=True)
    return f"Captura guardada en: {ruta}"


async def cerrar() -> str:
    """Cierra el navegador y libera Playwright."""
    global _pw, _browser, _context, _page
    if _browser is not None:
        await _browser.close()
    if _pw is not None:
        await _pw.stop()
    _pw = _browser = _context = _page = None
    return "Navegador cerrado."


HERRAMIENTAS = (abrir, iniciar_sesion, snapshot, clic, completar, captura, cerrar)


def main() -> None:
    """Registra las herramientas en FastMCP y arranca el servidor por stdio."""
    from fastmcp import FastMCP

    mcp = FastMCP("argus-playwright")
    for herramienta in HERRAMIENTAS:
        mcp.tool()(herramienta)
    mcp.run()


if __name__ == "__main__":
    main()
