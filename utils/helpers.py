"""Utilidades generales de entorno."""

from __future__ import annotations

import os

from config.settings import AMBIENTE_ACTIVO


def obtener_env_requerida(nombre: str) -> str:
    """Obtiene una variable de entorno requerida o lanza un error descriptivo."""
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(
            f'❌ Variable de entorno requerida no encontrada: "{nombre}".\n'
            "Asegúrate de definirla en el archivo .env del ambiente activo.\n"
            f"Ambiente actual: {AMBIENTE_ACTIVO}"
        )
    return valor
