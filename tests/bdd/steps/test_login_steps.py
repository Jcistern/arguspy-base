"""Definiciones de pasos BDD para el login de la aplicación."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import allure
from pytest_bdd import scenario, then

from pages.login_page import LoginPage
from utils.logger import logger


FEATURE = Path(__file__).resolve().parents[1] / "features" / "login.feature"


@allure.epic("App")
@allure.feature("Login")
@allure.story("Inicio de sesión exitoso")
@allure.severity(allure.severity_level.CRITICAL)
@scenario(str(FEATURE), "Inicio de sesión exitoso")
def test_inicio_de_sesion_exitoso() -> None:
    """Escenario BDD: inicio de sesión exitoso."""


# NOTA: step "que el usuario está autenticado" centralizado en conftest.py.


@then("la sesión queda iniciada")
def verificar_sesion_iniciada(login_page: LoginPage, run_async: Callable) -> None:
    """Verifica que el usuario quedó autenticado."""
    with allure.step("Verificar que la sesión quedó iniciada"):
        run_async(login_page.verificar_sesion_iniciada())
        logger.paso("Sesión iniciada correctamente")
