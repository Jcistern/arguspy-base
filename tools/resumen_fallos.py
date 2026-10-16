"""Resume las pruebas fallidas de una ejecución a partir de ``allure-results/``.

Por cada prueba no exitosa muestra estado, tags (incluido @TC_<ID>), el step
donde falló, el mensaje de error y las capturas adjuntas. Solo biblioteca estándar.

Ejemplos:
    python tools/resumen_fallos.py
    python tools/resumen_fallos.py --resultados ruta/a/allure-results
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
# broken = excepción (timeout, locator, código); failed = falló un assert/expect.
ESTADOS_FALLIDOS = {"failed", "broken"}
FRAME_PROYECTO = re.compile(r"^(pages/|tests/|utils/|config/|conftest\.py)\S*:\d+")


def _step_fallido(steps: list[dict], ruta: tuple[str, ...] = ()) -> tuple[str, ...]:
    for step in steps:
        if step.get("status") in ESTADOS_FALLIDOS:
            return _step_fallido(step.get("steps", []), ruta + (step.get("name", "?"),)) or ruta + (step.get("name", "?"),)
    return ()


def _frames_proyecto(traza: list[str]) -> list[str]:
    """Líneas de la traza que pertenecen al código del proyecto (archivo:línea: función)."""
    return [l.strip() for l in traza if FRAME_PROYECTO.match(l.strip().replace("\\", "/"))]


def _capturas(nodo: dict, carpeta: Path) -> list[str]:
    capturas = [carpeta / a["source"] for a in nodo.get("attachments", []) if a.get("type") == "image/png"]
    for step in nodo.get("steps", []):
        capturas += [Path(c) for c in _capturas(step, carpeta)]
    return [str(c) for c in capturas]


def _relativa(ruta: Path) -> str:
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return str(ruta)


def resumir(carpeta: Path) -> list[str]:
    bloques = []
    for archivo in sorted(carpeta.glob("*-result.json")):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        if datos.get("status") not in ESTADOS_FALLIDOS:
            continue
        tags = [l["value"] for l in datos.get("labels", []) if l.get("name") == "tag"]
        detalle = datos.get("statusDetails", {})
        mensaje = (detalle.get("message") or "").strip()
        traza = (detalle.get("trace") or "").strip().splitlines()
        lineas = [
            f"PRUEBA: {datos.get('fullName') or datos.get('name')}",
            f"  estado: {datos['status']}",
            f"  tags: {', '.join('@' + t for t in tags) or '-'}",
            f"  step fallido: {' > '.join(_step_fallido(datos.get('steps', []))) or '(fuera de un step)'}",
            "  mensaje:",
            *[f"    {l}" for l in mensaje.splitlines()[:12]],
            "  código del proyecto involucrado (de afuera hacia adentro):",
            *[f"    {l}" for l in _frames_proyecto(traza) or ["(ninguno: revisar la traza completa en el reporte)"]],
            f"  capturas: {', '.join(_relativa(Path(c)) for c in _capturas(datos, carpeta)) or '-'}",
        ]
        bloques.append("\n".join(lineas))
    return bloques


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume las pruebas fallidas desde allure-results.")
    parser.add_argument("--resultados", type=Path, default=RAIZ / "allure-results", help="Carpeta de resultados Allure.")
    args = parser.parse_args()

    if not args.resultados.is_dir() or not any(args.resultados.glob("*-result.json")):
        print(f"No hay resultados en {args.resultados}. Ejecuta pytest con --alluredir=allure-results.")
        return 2
    bloques = resumir(args.resultados)
    if not bloques:
        print("No hay pruebas fallidas en la última ejecución.")
        return 0
    print(f"{len(bloques)} prueba(s) fallida(s):\n")
    print("\n\n".join(bloques))
    return 1


if __name__ == "__main__":
    sys.exit(main())
