"""Sistema de logging con formato uniforme para ArgusPy."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any


class LoggerArgus:
    """Logger del framework con niveles y mensajes orientados a pruebas."""

    _ICONOS = {
        "INFO": "📋",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "DEBUG": "🔍",
        "PASO": "✅",
    }

    def _emitir(self, nivel: str, mensaje: str, detalle: Any = None) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        icono = self._ICONOS[nivel]
        encoding = sys.stdout.encoding or "utf-8"

        try:
            icono.encode(encoding)
        except UnicodeEncodeError:
            icono = ""

        print(f"[{timestamp}] {icono} [{nivel}] {mensaje}".replace("  [", " ["))
        if detalle is not None:
            print(f"   Detalle: {json.dumps(detalle, ensure_ascii=False, indent=2, default=str)}")

    def info(self, mensaje: str, detalle: Any = None) -> None:
        self._emitir("INFO", mensaje, detalle)

    def warn(self, mensaje: str, detalle: Any = None) -> None:
        self._emitir("WARNING", mensaje, detalle)

    def error(self, mensaje: str, detalle: Any = None) -> None:
        self._emitir("ERROR", mensaje, detalle)

    def debug(self, mensaje: str, detalle: Any = None) -> None:
        if os.getenv("DEBUG", "").lower() == "true":
            self._emitir("DEBUG", mensaje, detalle)

    def paso(self, mensaje: str) -> None:
        self._emitir("PASO", mensaje)


logger = LoggerArgus()
