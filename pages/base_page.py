"""Clase base reutilizable para los Page Objects de ArgusPy."""

from __future__ import annotations

from pathlib import Path
from time import time
from typing import Pattern

from playwright.async_api import Locator, Page, expect

# Timeout global de las verificaciones expect(...) (Playwright usa 5 s por
# defecto). Se fija aquí para que aplique a los tests y al MCP de exploración.
TIMEOUT_EXPECT_MS = 15_000
expect.set_options(timeout=TIMEOUT_EXPECT_MS)


class BasePage:
    """Clase base que encapsula navegación, acciones y verificaciones comunes."""

    def __init__(self, page: Page) -> None:
        self.page = page

    # ─── Navegación ────────────────────────────────────────────────────────

    async def navigate_to(self, ruta: str) -> None:
        """Navega a una ruta relativa a BASE_URL.

        Solo espera el DOM: cada Page Object debe verificar después con
        ``expect`` un elemento que confirme que la pantalla cargó.
        """
        await self.page.goto(ruta, wait_until="domcontentloaded")

    async def wait_for_page_load(self) -> None:
        """Espera el evento ``load`` de la página.

        No usa ``networkidle``: en SPAs con polling o websockets puede no
        cumplirse nunca. Para sincronizar, preferir ``expect`` sobre un elemento.
        """
        await self.page.wait_for_load_state("load")

    # ─── Esperas ───────────────────────────────────────────────────────────

    async def wait_for_element(self, locator: Locator, timeout: int = 10_000) -> None:
        """Espera que un elemento sea visible."""
        await locator.wait_for(state="visible", timeout=timeout)

    async def wait_for_element_to_disappear(
        self, locator: Locator, timeout: int = 10_000
    ) -> None:
        """Espera que un elemento deje de estar visible."""
        await locator.wait_for(state="hidden", timeout=timeout)

    # ─── Acciones ──────────────────────────────────────────────────────────

    async def click_element(self, locator: Locator) -> None:
        """Hace clic con espera automática de visibilidad."""
        await self.wait_for_element(locator)
        await locator.click()

    async def fill_field(self, locator: Locator, valor: str) -> None:
        """Limpia y completa un campo de texto."""
        await self.wait_for_element(locator)
        await locator.fill(valor)

    async def select_option(self, locator: Locator, opcion: str) -> None:
        """Selecciona una opción por texto visible."""
        await self.wait_for_element(locator)
        await locator.select_option(label=opcion)

    async def upload_file(self, locator: Locator, ruta_archivo: str) -> None:
        """Carga un archivo en un input de tipo file."""
        await locator.set_input_files(ruta_archivo)

    # ─── Verificaciones ────────────────────────────────────────────────────

    async def verify_visible(self, locator: Locator) -> None:
        """Verifica que el elemento sea visible."""
        await expect(locator).to_be_visible()

    async def verify_text(self, locator: Locator, texto: str | Pattern[str]) -> None:
        """Verifica que el elemento contenga el texto esperado."""
        await expect(locator).to_contain_text(texto)

    async def verify_url(self, patron: str | Pattern[str]) -> None:
        """Verifica que la URL actual coincida con el patrón."""
        await expect(self.page).to_have_url(patron)

    async def verify_title(self, titulo: str | Pattern[str]) -> None:
        """Verifica el título de la página."""
        await expect(self.page).to_have_title(titulo)

    # ─── Utilidades ────────────────────────────────────────────────────────

    async def take_screenshot(self, nombre: str) -> Path:
        """Captura un screenshot completo y retorna su ruta."""
        directorio = Path("test-results") / "screenshots"
        directorio.mkdir(parents=True, exist_ok=True)
        ruta = directorio / f"{nombre}-{int(time() * 1000)}.png"
        await self.page.screenshot(path=str(ruta), full_page=True)
        return ruta

    async def get_text(self, locator: Locator) -> str:
        """Retorna el texto de un elemento visible."""
        await self.wait_for_element(locator)
        return await locator.text_content() or ""

    async def is_visible(self, locator: Locator) -> bool:
        """Indica si el elemento está visible sin fallar el test."""
        return await locator.is_visible()

    async def reload_page(self) -> None:
        """Recarga la página actual."""
        await self.page.reload()
        await self.wait_for_page_load()

    async def go_back(self) -> None:
        """Regresa a la página anterior del historial."""
        await self.page.go_back()
        await self.wait_for_page_load()

    async def get_attribute(self, locator: Locator, atributo: str) -> str | None:
        """Retorna el valor de un atributo HTML."""
        return await locator.get_attribute(atributo)

    async def press_key(self, tecla: str) -> None:
        """Presiona una tecla."""
        await self.page.keyboard.press(tecla)

    async def scroll_to_element(self, locator: Locator) -> None:
        """Desplaza hasta el elemento."""
        await locator.scroll_into_view_if_needed()
