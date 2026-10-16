"""Hooks de aXet (``.axetrules/hooks/``): protege archivos sensibles y valida convenciones.

aXet envía el evento como JSON por stdin y espera por stdout un JSON con
``cancel``, ``errorMessage`` y ``contextModification``.

    PreToolUse  -> bloquea leer/editar ``*.env`` y editar ``*.lock`` a mano.
    PostToolUse -> tras editar pages/, tests/ o conftest.py, informa las
                   infracciones a AGENTS.md para que el asistente las corrija.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validar_convenciones import RAIZ, recolectar, revisar_archivo, steps_faltantes  # noqa: E402

HERRAMIENTAS_LECTURA = {"read_file", "search_files", "list_code_definition_names"}
HERRAMIENTAS_ESCRITURA = {"write_to_file", "replace_in_file", "apply_patch"}
# Archivos .env reales; las plantillas *.env.example quedan permitidas.
PATRON_ENV = re.compile(r"(^|[\\/\s\"'])[\w.-]*\.env(?![\w.])")


def _es_env(texto: str) -> bool:
    return bool(PATRON_ENV.search(texto))


def _rutas(parametros: dict) -> list[str]:
    rutas = [parametros["path"]] if parametros.get("path") else []
    # apply_patch indica los archivos dentro del parche: "*** Update File: ruta".
    rutas += re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", parametros.get("input", ""), re.MULTILINE)
    return [r.strip() for r in rutas]


def pre_tool_use(evento: dict) -> dict:
    datos = evento.get("preToolUse") or {}
    herramienta = datos.get("toolName", "")
    parametros = datos.get("parameters") or {}

    if herramienta == "execute_command" and _es_env(parametros.get("command", "")):
        return _cancelar("El comando referencia un archivo .env con credenciales; no se permite leerlo ni modificarlo.")
    if herramienta in HERRAMIENTAS_LECTURA | HERRAMIENTAS_ESCRITURA:
        for ruta in _rutas(parametros):
            if _es_env(ruta):
                return _cancelar(f"'{ruta}' contiene credenciales y no se comparte con la IA. Usa obtener_env_requerida(...) en el código.")
            if herramienta in HERRAMIENTAS_ESCRITURA and ruta.endswith(".lock"):
                return _cancelar(f"'{ruta}' no se edita a mano: modifica el requirements*.txt y regenera el .lock con 'uv pip compile' (ver README).")
    return {"cancel": False}


def post_tool_use(evento: dict) -> dict:
    datos = evento.get("postToolUse") or {}
    if datos.get("toolName") not in HERRAMIENTAS_ESCRITURA:
        return {"cancel": False}

    rutas = [RAIZ / r for r in _rutas(datos.get("parameters") or {})]
    hallazgos = [str(h) for ruta in rutas for h in revisar_archivo(ruta)]
    toca_bdd = any(r.resolve().is_relative_to(RAIZ / "tests") or r.name == "conftest.py" for r in rutas)
    if toca_bdd:
        hallazgos += steps_faltantes()
        ok, salida = recolectar()
        if ok is False:
            hallazgos.append("pytest --collect-only falló:\n" + "\n".join(salida.splitlines()[-15:]))

    if not hallazgos:
        return {"cancel": False}
    mensaje = "Validación de convenciones (AGENTS.md). Corrige antes de continuar:\n" + "\n".join(hallazgos)
    return {"cancel": False, "contextModification": mensaje}


def _cancelar(mensaje: str) -> dict:
    return {"cancel": True, "errorMessage": mensaje}


def main() -> None:
    nombre = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        evento = json.loads(sys.stdin.read() or "{}")
        manejadores = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use}
        respuesta = manejadores[nombre](evento) if nombre in manejadores else {"cancel": False}
    except Exception as exc:  # Un error del hook nunca debe bloquear al asistente.
        respuesta = {"cancel": False, "contextModification": f"[hook_axet] error interno: {exc}"}
    print(json.dumps(respuesta, ensure_ascii=False))


if __name__ == "__main__":
    main()
