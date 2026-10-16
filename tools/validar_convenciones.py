"""Valida las convenciones de AGENTS.md en Page Objects, steps, features y conftest.

Lo usan pre-commit, el pipeline y los hooks de aXet; solo requiere la biblioteca
estándar (la recolección de pytest usa el Python del ``.venv`` del proyecto).

Ejemplos:
    python tools/validar_convenciones.py
    python tools/validar_convenciones.py pages/login_page.py tests/bdd/features/productos.feature
    python tools/validar_convenciones.py --sin-recoleccion

Para aceptar un caso justificado, agregar ``# argus: permitido <motivo>`` en la línea.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import tokenize
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MARCA_PERMITIDO = "argus: permitido"
DECORADORES_STEP = {"given", "when", "then", "step"}
METODOS_LOCATOR = {"get_by_role", "get_by_label", "get_by_placeholder", "get_by_test_id", "get_by_text", "locator"}


@dataclass(frozen=True)
class Hallazgo:
    ruta: str
    linea: int
    severidad: str  # "error" o "aviso"
    mensaje: str

    def __str__(self) -> str:
        return f"{self.ruta}:{self.linea}: [{self.severidad}] {self.mensaje}"


def _relativa(ruta: Path) -> str:
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.as_posix()


def es_relevante(ruta: Path) -> bool:
    """Indica si el archivo está sujeto a las convenciones de pruebas."""
    rel = _relativa(ruta)
    if rel.endswith(".feature"):
        return rel.startswith("tests/")
    if rel.endswith(".json"):
        return rel.startswith("data/") and not rel.startswith("data/planes/")
    return rel.endswith(".py") and (rel.startswith(("pages/", "tests/")) or rel == "conftest.py")


def _es_steps(rel: str) -> bool:
    return rel.startswith("tests/bdd/steps/")


def _lineas_permitidas(codigo: str) -> set[int]:
    lineas: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(codigo).readline):
            if tok.type == tokenize.COMMENT and MARCA_PERMITIDO in tok.string:
                lineas.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        pass
    return lineas


def _nombre_llamada(nodo: ast.Call) -> str:
    if isinstance(nodo.func, ast.Attribute):
        return nodo.func.attr
    if isinstance(nodo.func, ast.Name):
        return nodo.func.id
    return ""


def _nombre_decorador(nodo: ast.expr) -> str:
    if isinstance(nodo, ast.Call):
        nodo = nodo.func
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    if isinstance(nodo, ast.Name):
        return nodo.id
    return ""


def _revisar_python(ruta: Path, rel: str) -> list[Hallazgo]:
    codigo = ruta.read_text(encoding="utf-8")
    try:
        arbol = ast.parse(codigo, filename=rel)
    except SyntaxError as exc:
        return [Hallazgo(rel, exc.lineno or 1, "error", f"Error de sintaxis: {exc.msg}")]

    permitidas = _lineas_permitidas(codigo)
    hallazgos: list[Hallazgo] = []
    steps = _es_steps(rel)
    # Alias de time.sleep importado como función suelta (from time import sleep).
    sleep_importado = any(
        isinstance(n, ast.ImportFrom) and n.module == "time" and any(a.name == "sleep" for a in n.names)
        for n in ast.walk(arbol)
    )

    def agregar(nodo: ast.AST, severidad: str, mensaje: str) -> None:
        linea = getattr(nodo, "lineno", 1)
        if linea not in permitidas:
            hallazgos.append(Hallazgo(rel, linea, severidad, mensaje))

    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call):
            nombre = _nombre_llamada(nodo)
            if nombre == "wait_for_timeout":
                agregar(nodo, "error", "No usar wait_for_timeout(); usar el auto-wait de Playwright o expect(...).")
            elif nombre == "sleep" and (
                (isinstance(nodo.func, ast.Attribute) and isinstance(nodo.func.value, ast.Name) and nodo.func.value.id == "time")
                or (isinstance(nodo.func, ast.Name) and sleep_importado)
            ):
                agregar(nodo, "error", "No usar time.sleep(); usar el auto-wait de Playwright o expect(...).")
            if any(k.arg == "force" and isinstance(k.value, ast.Constant) and k.value.value is True for k in nodo.keywords):
                agregar(nodo, "error", "No usar force=True; acotar el locator o esperar el estado correcto.")
            if nombre == "locator" and nodo.args and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str):
                selector = nodo.args[0].value.strip()
                if selector.startswith(("//", "(//", "xpath=", "./")):
                    agregar(nodo, "error", "No usar XPath; preferir get_by_role / get_by_label.")
            if nombre == "nth":
                agregar(nodo, "aviso", "Índice arbitrario (.nth); acotar con un contenedor accesible.")
            if steps and nombre in METODOS_LOCATOR:
                agregar(nodo, "aviso", "Locator dentro de un step; moverlo al Page Object.")
        elif isinstance(nodo, ast.Attribute) and nodo.attr in {"first", "last"} and isinstance(nodo.ctx, ast.Load):
            agregar(nodo, "aviso", f"Índice arbitrario (.{nodo.attr}); acotar con un contenedor accesible.")
        elif steps and isinstance(nodo, ast.AsyncFunctionDef):
            es_step = any(_nombre_decorador(d) in DECORADORES_STEP for d in nodo.decorator_list)
            detalle = "Los steps son síncronos (def)" if es_step else "Los archivos de steps no definen funciones async"
            agregar(nodo, "error", f"{detalle}; llamar al Page Object con run_async(...).")
    return sorted(hallazgos, key=lambda h: h.linea)


def markers_registrados() -> set[str]:
    """Markers declarados en pytest.ini (los @TC_<ID> se registran en conftest)."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(RAIZ / "pytest.ini", encoding="utf-8")
    texto = config.get("pytest", "markers", fallback="")
    return {linea.split(":", 1)[0].strip() for linea in texto.splitlines() if linea.strip()}


def _revisar_feature(ruta: Path, rel: str) -> list[Hallazgo]:
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    hallazgos: list[Hallazgo] = []
    primera = next((l.strip() for l in lineas if l.strip()), "")
    if primera != "# language: en":
        hallazgos.append(Hallazgo(rel, 1, "aviso", "El feature debe comenzar con '# language: en'."))
    registrados = markers_registrados()
    for numero, linea in enumerate(lineas, start=1):
        if not linea.strip().startswith("@"):
            continue
        for tag in re.findall(r"@([^\s@]+)", linea):
            if not re.fullmatch(r"TC_\d+|CP_[A-Z]+_N?\d+", tag) and tag not in registrados:
                hallazgos.append(Hallazgo(rel, numero, "error", f"Tag @{tag} no registrado como marker en pytest.ini."))
    return hallazgos


def _revisar_json(ruta: Path, rel: str) -> list[Hallazgo]:
    """Los datos de prueba deben ser un objeto JSON no vacío (cargar_datos_json lo exige)."""
    import json

    texto = ruta.read_text(encoding="utf-8").strip()
    if not texto:
        return [Hallazgo(rel, 1, "error", "Archivo de datos vacío (¿escritura interrumpida?); completarlo o borrarlo.")]
    try:
        contenido = json.loads(texto)
    except json.JSONDecodeError as exc:
        return [Hallazgo(rel, exc.lineno, "error", f"JSON inválido: {exc.msg}.")]
    if not isinstance(contenido, dict):
        return [Hallazgo(rel, 1, "error", "La raíz debe ser un objeto JSON ({...}).")]
    return []


def revisar_archivo(ruta: Path) -> list[Hallazgo]:
    """Revisa un archivo; devuelve [] si no aplica o no existe."""
    if not ruta.is_file() or not es_relevante(ruta):
        return []
    rel = _relativa(ruta)
    if rel.endswith(".feature"):
        return _revisar_feature(ruta, rel)
    if rel.endswith(".json"):
        return _revisar_json(ruta, rel)
    return _revisar_python(ruta, rel)


def python_del_proyecto() -> str | None:
    """Python del .venv del proyecto, o el actual si tiene pytest-bdd instalado."""
    for candidato in (RAIZ / ".venv" / "bin" / "python", RAIZ / ".venv" / "Scripts" / "python.exe"):
        if candidato.exists():
            return str(candidato)
    if importlib.util.find_spec("pytest_bdd") is not None:
        return sys.executable
    return None


def recolectar(objetivo: str = "tests") -> tuple[bool | None, str]:
    """Ejecuta ``pytest --collect-only``; devuelve (ok, salida) u (None, motivo) si no hay entorno."""
    python = python_del_proyecto()
    if python is None:
        return None, "No se encontró el .venv del proyecto; se omite la recolección de pytest."
    with tempfile.TemporaryDirectory() as tmp:
        # --html apunta a un temporal para no sobrescribir el reporte real (addopts lo agrega).
        comando = [python, "-m", "pytest", objetivo, "--collect-only", "-q", "-p", "no:cacheprovider",
                   f"--html={Path(tmp) / 'collect.html'}"]
        resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    salida = (resultado.stdout + resultado.stderr).strip()
    # 5 = "no tests collected": válido mientras ningún escenario tenga steps todavía.
    return resultado.returncode in (0, 5), salida


def steps_faltantes() -> list[str]:
    """Pasos de escenarios enlazados con @scenario que no tienen step visible."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from verificar_steps import DIR_FEATURES, verificar

    resultado = verificar(sorted(DIR_FEATURES.rglob("*.feature")))
    lineas = []
    for escenario, paso, enlazado in resultado.faltantes:
        if enlazado:
            nota = resultado.fuera_de_alcance.get((str(escenario.archivo), paso.linea), "sin step definido")
            lineas.append(f"{_relativa(escenario.archivo)}:{paso.linea}: [error] '{paso.texto}' ({nota}).")
    return lineas


def archivos_por_defecto() -> list[Path]:
    rutas = [RAIZ / "conftest.py"]
    for carpeta, patron in (("pages", "*.py"), ("tests", "*.py"), ("tests", "*.feature"), ("data", "*.json")):
        rutas.extend(sorted((RAIZ / carpeta).rglob(patron)))
    return [r for r in rutas if "__pycache__" not in r.parts]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida las convenciones de AGENTS.md.")
    parser.add_argument("archivos", nargs="*", type=Path, help="Archivos a revisar (por defecto, todo el proyecto).")
    parser.add_argument("--sin-recoleccion", action="store_true", help="No ejecuta pytest --collect-only.")
    args = parser.parse_args(argv)

    archivos = [a for a in args.archivos if es_relevante(a)] if args.archivos else archivos_por_defecto()
    hallazgos = [h for archivo in archivos for h in revisar_archivo(archivo)]
    for hallazgo in hallazgos:
        print(hallazgo)
    errores = sum(h.severidad == "error" for h in hallazgos)

    if archivos:
        faltantes = steps_faltantes()
        errores += len(faltantes)
        for linea in faltantes:
            print(linea)

    if archivos and not args.sin_recoleccion:
        ok, salida = recolectar()
        if ok is None:
            print(f"[aviso] {salida}")
        elif not ok:
            errores += 1
            print("[error] pytest --collect-only falló:")
            print(salida)

    if errores:
        print(f"\n{errores} error(es). Ver convenciones en AGENTS.md.")
        return 1
    print(f"Convenciones OK ({len(archivos)} archivo(s) revisado(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
