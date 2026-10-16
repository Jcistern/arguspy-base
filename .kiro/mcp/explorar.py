"""Exploración de UI desde la terminal, sin cliente MCP (Windows, macOS y Linux).

Reutiliza las herramientas de ``playwright_server.py`` como funciones Python e
imprime el árbol accesible de la ruta indicada. No requiere ``fastmcp``.

Ejemplos:
    python .kiro/mcp/explorar.py /login --sin-sesion
    python .kiro/mcp/explorar.py /dashboard --perfil admin
    python .kiro/mcp/explorar.py /usuarios --clic "button:Nuevo usuario" --contenedor "dialog:Nuevo usuario"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import Error as PlaywrightError


def _par_rol_nombre(valor: str) -> tuple[str, str]:
    """Separa 'rol:nombre' en (rol, nombre); el nombre es opcional."""
    rol, _, nombre = valor.partition(":")
    if not rol:
        raise argparse.ArgumentTypeError(f"Formato inválido '{valor}'; usa rol:nombre.")
    return rol.strip(), nombre.strip()


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explora una pantalla y muestra su árbol accesible.")
    parser.add_argument("ruta", help="Ruta relativa a APP_BASE_URL (ej: /dashboard).")
    sesion = parser.add_mutually_exclusive_group()
    sesion.add_argument("--perfil", default="admin", help="Perfil de credenciales APP_<PERFIL>_* (por defecto: admin).")
    sesion.add_argument("--sin-sesion", action="store_true", help="No inicia sesión antes de abrir la ruta.")
    parser.add_argument(
        "--clic", action="append", default=[], type=_par_rol_nombre, metavar="ROL:NOMBRE",
        help="Clic previo al snapshot (repetible, en orden). Ej: button:Nuevo.",
    )
    parser.add_argument(
        "--contenedor", type=_par_rol_nombre, metavar="ROL[:NOMBRE]",
        help="Acota el snapshot a un contenedor. Ej: dialog:Confirmar.",
    )
    parser.add_argument("--captura", metavar="NOMBRE", help="Guarda un screenshot en test-results/mcp/.")
    parser.add_argument("--headed", action="store_true", help="Muestra el navegador.")
    return parser.parse_args()


async def _explorar(args: argparse.Namespace) -> None:
    # Importación diferida: MCP_HEADLESS debe estar definido antes de abrir el navegador.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import playwright_server as srv

    try:
        if not args.sin_sesion:
            print(await srv.iniciar_sesion(args.perfil))
        print(await srv.abrir(args.ruta))
        for rol, nombre in args.clic:
            print(await srv.clic(rol, nombre))
        rol_contenedor, nombre_contenedor = args.contenedor or ("", "")
        print(await srv.snapshot(rol_contenedor, nombre_contenedor))
        if args.captura:
            print(await srv.captura(args.captura))
    except PlaywrightError as error:
        primera_linea = str(error).splitlines()[0]
        sys.stdout.flush()
        print(f"Error de Playwright: {primera_linea}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        print(await srv.cerrar())


def main() -> None:
    args = _argumentos()
    os.environ["MCP_HEADLESS"] = "false" if args.headed else "true"
    # Evita UnicodeEncodeError en consolas Windows sin UTF-8 (emojis y tildes del árbol).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(_explorar(args))


if __name__ == "__main__":
    main()
