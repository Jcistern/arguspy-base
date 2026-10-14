"""Carga y validación de datos de prueba almacenados en archivos JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
DIRECTORIO_DATOS = RAIZ_PROYECTO / "data"


def cargar_datos_json(nombre_archivo: str) -> Mapping[str, Any]:
    """Carga un archivo JSON desde ``data`` y valida que su raíz sea un objeto."""
    ruta = DIRECTORIO_DATOS / nombre_archivo
    try:
        with ruta.open(encoding="utf-8") as archivo:
            contenido = json.load(archivo)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"No existe el archivo de datos: {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en '{ruta}': {exc.msg}") from exc

    if not isinstance(contenido, dict):
        raise ValueError(f"El archivo '{ruta}' debe contener un objeto JSON en la raíz.")

    return contenido


def obtener_seccion_validada(
    nombre_archivo: str, clave_seccion: str, campos_requeridos: frozenset[str]
) -> dict[str, str]:
    """Carga una sección de un JSON de datos y valida campos requeridos y tipos texto.

    Ejemplo::

        obtener_seccion_validada("busqueda.json", "busqueda_valida", frozenset({"texto"}))
    """
    contenido = cargar_datos_json(nombre_archivo)
    datos = contenido.get(clave_seccion)

    if not isinstance(datos, dict):
        raise ValueError(
            f"La clave '{clave_seccion}' debe existir y contener un objeto JSON "
            f"en '{nombre_archivo}'."
        )

    campos_faltantes = campos_requeridos.difference(datos)
    if campos_faltantes:
        faltantes = ", ".join(sorted(campos_faltantes))
        raise ValueError(
            f"Faltan campos requeridos en '{nombre_archivo}' ({clave_seccion}): {faltantes}"
        )

    campos_no_texto = [
        campo for campo in campos_requeridos if not isinstance(datos[campo], str)
    ]
    if campos_no_texto:
        invalidos = ", ".join(sorted(campos_no_texto))
        raise ValueError(
            f"Los campos de '{clave_seccion}' deben ser texto en '{nombre_archivo}': {invalidos}"
        )

    return {campo: datos[campo] for campo in campos_requeridos}
