"""Carga centralizada de la configuración por ambiente."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIRECTORIO_AMBIENTES = RAIZ_PROYECTO / "config" / "environments"


def cargar_ambiente() -> str:
    """Carga el archivo .env del ambiente indicado por AMBIENTE o dev."""
    ambiente = os.getenv("AMBIENTE", "dev")
    archivo_ambiente = DIRECTORIO_AMBIENTES / f"{ambiente}.env"

    if not archivo_ambiente.is_file():
        raise FileNotFoundError(
            f"No se encontró la configuración del ambiente '{ambiente}': "
            f"{archivo_ambiente}"
        )

    load_dotenv(archivo_ambiente, override=False)
    return ambiente


AMBIENTE_ACTIVO = cargar_ambiente()
