"""Page Object del login por usuario y contraseña de la aplicación."""

from __future__ import annotations

import os
import re

from playwright.async_api import Page, expect

from pages.base_page import BasePage
from utils.logger import logger


class LoginPage(BasePage):
    """Page Object del formulario de login.

    TODO: ajustar los locators a la aplicación real. Los patrones actuales
    cubren las etiquetas más comunes en español e inglés.
    """

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._campo_usuario = page.get_by_label(
            re.compile(r"usuario|username|correo|e-?mail", re.I)
        )
        self._campo_password = page.get_by_label(re.compile(r"contrase[ñn]a|password", re.I))
        self._btn_ingresar = page.get_by_role(
            "button", name=re.compile(r"ingresar|iniciar sesi[oó]n|entrar|log ?in|sign ?in", re.I)
        )

    async def goto(self) -> None:
        """Navega a la página de login (``APP_LOGIN_PATH``, por defecto ``/``)."""
        ruta = os.getenv("APP_LOGIN_PATH", "/")
        logger.info(f"Navegando al login: {ruta}")
        await self.page.goto(ruta, wait_until="domcontentloaded")
        await expect(self._campo_usuario).to_be_visible()

    async def login(self, usuario: str, password: str) -> None:
        """Completa el formulario y espera a que la sesión quede iniciada."""
        await self.fill_field(self._campo_usuario, usuario)
        await self.fill_field(self._campo_password, password)
        await self.click_element(self._btn_ingresar)
        await self.verificar_sesion_iniciada()

    async def verificar_sesion_iniciada(self) -> None:
        """Verifica que el formulario de login ya no esté visible."""
        await expect(self._campo_password).to_be_hidden()
