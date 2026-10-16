"""Verifica que cada paso de los .feature tenga su step definido, sin ejecutar pruebas.

Cruza los pasos Given/When/Then (incluido el Background y cada fila de Examples)
con los ``@given/@when/@then/@step`` de ``conftest.py`` y ``tests/``, entendiendo
textos exactos, ``parsers.parse``, ``parsers.cfparse`` y ``parsers.re``.

    - Escenario enlazado (@scenario) con pasos sin definir -> error: fallará al ejecutar.
    - Escenario sin enlazar -> solo informa (aún no se automatiza).

Ejemplos:
    python tools/verificar_steps.py
    python tools/verificar_steps.py tests/bdd/features/productos.feature --sugerir
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_FEATURES = RAIZ / "tests" / "bdd" / "features"
TIPOS = {"Given": "given", "When": "when", "Then": "then"}
CONTINUACION = {"And", "But", "*"}


@dataclass
class Paso:
    tipo: str  # given | when | then
    texto: str
    linea: int


@dataclass
class Escenario:
    archivo: Path
    linea: int
    nombre: str
    pasos: list[Paso] = field(default_factory=list)
    encabezados: list[str] = field(default_factory=list)
    filas: list[list[str]] = field(default_factory=list)

    def variantes(self, paso: Paso) -> list[str]:
        """El texto del paso con los <marcadores> reemplazados por cada fila de Examples."""
        if "<" not in paso.texto or not self.filas:
            return [paso.texto]
        variantes = []
        for fila in self.filas:
            texto = paso.texto
            for encabezado, valor in zip(self.encabezados, fila):
                texto = texto.replace(f"<{encabezado}>", valor)
            variantes.append(texto)
        return variantes


@dataclass
class Definicion:
    tipo: str  # given | when | then | step
    clase: str  # exacto | parse | cfparse | re
    patron: str
    origen: str  # archivo:línea

    @property
    def archivo(self) -> str:
        return self.origen.rsplit(":", 1)[0]

    def visible_desde(self, modulo: str) -> bool:
        """pytest-bdd solo ve los steps del propio módulo de test y de los conftest.py."""
        return self.archivo == modulo or self.archivo.endswith("conftest.py")

    def coincide(self, texto: str) -> bool:
        if self.clase == "exacto":
            return texto == self.patron
        if self.clase == "re":
            return re.fullmatch(self.patron, texto) is not None
        if self.clase == "cfparse":
            try:
                from parse_type import cfparse
                return cfparse.Parser(self.patron).parse(texto) is not None
            except ImportError:
                pass
        import parse
        return parse.compile(self.patron).parse(texto) is not None


def leer_feature(archivo: Path) -> list[Escenario]:
    escenarios: list[Escenario] = []
    fondo: list[Paso] = []
    actual: Escenario | None = None
    destino: list[Paso] | None = None
    ultimo_tipo = "given"
    en_ejemplos = False
    for numero, bruta in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
        linea = bruta.strip()
        if not linea or linea.startswith(("#", "@")):
            continue
        clave = linea.split(":", 1)[0].strip()
        if clave in ("Background", "Antecedentes"):
            destino, actual, en_ejemplos = fondo, None, False
        elif clave in ("Scenario", "Scenario Outline", "Escenario", "Esquema del escenario"):
            actual = Escenario(archivo, numero, linea.split(":", 1)[1].strip(), list(fondo))
            escenarios.append(actual)
            destino, en_ejemplos = actual.pasos, False
        elif clave in ("Examples", "Ejemplos"):
            en_ejemplos = True
        elif en_ejemplos and actual is not None and linea.startswith("|"):
            celdas = [c.strip() for c in linea.strip("|").split("|")]
            if actual.encabezados:
                actual.filas.append(celdas)
            else:
                actual.encabezados = celdas
        elif destino is not None:
            palabra, _, texto = linea.partition(" ")
            if palabra in TIPOS:
                ultimo_tipo = TIPOS[palabra]
            elif palabra not in CONTINUACION:
                continue
            destino.append(Paso(ultimo_tipo, texto.strip(), numero))
    return escenarios


def _patron(argumento: ast.expr) -> tuple[str, str] | None:
    if isinstance(argumento, ast.Constant) and isinstance(argumento.value, str):
        return "exacto", argumento.value
    if isinstance(argumento, ast.Call) and argumento.args and isinstance(argumento.args[0], ast.Constant):
        nombre = getattr(argumento.func, "attr", getattr(argumento.func, "id", ""))
        if nombre in ("parse", "cfparse", "re"):
            return nombre, str(argumento.args[0].value)
    return None


def leer_definiciones() -> tuple[list[Definicion], dict[str, str]]:
    """Steps definidos y escenarios enlazados con @scenario(...) -> módulo que los enlaza."""
    definiciones: list[Definicion] = []
    enlazados: dict[str, str] = {}
    archivos = [RAIZ / "conftest.py", *sorted((RAIZ / "tests").rglob("*.py"))]
    for archivo in archivos:
        if not archivo.is_file():
            continue
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = archivo.relative_to(RAIZ).as_posix()
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            nombre = getattr(nodo.func, "id", getattr(nodo.func, "attr", ""))
            if nombre in ("given", "when", "then", "step") and nodo.args:
                patron = _patron(nodo.args[0])
                if patron:
                    definiciones.append(Definicion(nombre, patron[0], patron[1], f"{rel}:{nodo.lineno}"))
            elif nombre == "scenario" and len(nodo.args) >= 2 and isinstance(nodo.args[1], ast.Constant):
                enlazados[str(nodo.args[1].value)] = rel
    return definiciones, enlazados


def buscar(paso: Paso, texto: str, definiciones: list[Definicion]) -> list[Definicion]:
    return [d for d in definiciones if d.tipo in (paso.tipo, "step") and d.coincide(texto)]


def sugerencia(paso: Paso) -> str:
    """Esqueleto del step: los textos entre comillas y los <marcadores> pasan a parámetros."""
    nombres: list[str] = []

    def reemplazar(coincidencia: re.Match) -> str:
        if coincidencia.group(1):  # <marcador> de Scenario Outline
            nombres.append(re.sub(r"\W+", "_", coincidencia.group(1)).strip("_").lower())
            return f"{{{nombres[-1]}}}"
        nombres.append(f"valor{len(nombres) + 1}")
        return f'"{{{nombres[-1]}}}"'

    patron = re.sub(r'<([^>]+)>|"[^"]*"', reemplazar, paso.texto)
    funcion = re.sub(r"\W+", "_", re.split(r'["<]', paso.texto)[0]).strip("_").lower()[:40] or "paso"
    decorador = f"parsers.parse('{patron}')" if nombres else f'"{paso.texto}"'
    parametros = "".join(f", {n}: str" for n in nombres)
    return f"@{paso.tipo}({decorador})\ndef {funcion}(run_async: Callable{parametros}) -> None:\n    ..."


@dataclass
class Resultado:
    faltantes: list[tuple[Escenario, Paso, bool]] = field(default_factory=list)  # (escenario, paso, enlazado)
    ambiguos: list[tuple[Escenario, Paso, list[Definicion]]] = field(default_factory=list)
    # Pasos definidos en otro módulo de test, invisibles para el escenario enlazado.
    fuera_de_alcance: dict[tuple[str, int], str] = field(default_factory=dict)
    escenarios: int = 0
    enlazados: int = 0


def verificar(features: list[Path]) -> Resultado:
    definiciones, enlazados = leer_definiciones()
    resultado = Resultado()
    for archivo in features:
        for escenario in leer_feature(archivo):
            resultado.escenarios += 1
            modulo = enlazados.get(escenario.nombre)
            enlazado = modulo is not None
            resultado.enlazados += enlazado
            visibles = [d for d in definiciones if d.visible_desde(modulo)] if enlazado else definiciones
            for paso in escenario.pasos:
                coincidencias = [buscar(paso, texto, visibles) for texto in escenario.variantes(paso)]
                if enlazado and any(not c for c in coincidencias):
                    otros = {d.archivo for t in escenario.variantes(paso) for d in buscar(paso, t, definiciones)}
                    if otros:
                        resultado.fuera_de_alcance[(str(escenario.archivo), paso.linea)] = (
                            f"definido en {', '.join(sorted(otros))}, no visible desde {modulo}: muévelo a conftest.py")
                if any(not c for c in coincidencias):
                    resultado.faltantes.append((escenario, paso, enlazado))
                elif any(len(c) > 1 for c in coincidencias):
                    resultado.ambiguos.append((escenario, paso, next(c for c in coincidencias if len(c) > 1)))
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica que los pasos de los .feature tengan step definido.")
    parser.add_argument("features", nargs="*", type=Path, help="Archivos o carpetas .feature (por defecto, todos).")
    parser.add_argument("--sugerir", action="store_true", help="Muestra el esqueleto de cada step faltante.")
    parser.add_argument("--estricto", action="store_true", help="También falla por escenarios aún sin enlazar.")
    args = parser.parse_args(argv)

    rutas = args.features or [DIR_FEATURES]
    archivos = sorted({f.resolve() for r in rutas for f in ([r] if r.is_file() else r.rglob("*.feature"))})
    r = verificar(archivos)

    def ubicacion(escenario: Escenario, paso: Paso) -> str:
        return f"{escenario.archivo.relative_to(RAIZ).as_posix()}:{paso.linea}"

    errores = [f for f in r.faltantes if f[2] or args.estricto]
    pendientes = [f for f in r.faltantes if not (f[2] or args.estricto)]
    print(f"{r.escenarios} escenarios ({r.enlazados} enlazados con @scenario) en {len(archivos)} feature(s).")
    if errores:
        print(f"\n[error] Pasos sin step en escenarios enlazados: {len(errores)} (fallarán al ejecutar)")
        for escenario, paso, _ in errores:
            print(f"  {ubicacion(escenario, paso)}: {paso.tipo} {paso.texto}  ({escenario.nombre})")
            nota = r.fuera_de_alcance.get((str(escenario.archivo), paso.linea))
            if nota:
                print(f"      ↳ {nota}")
    if pendientes:
        print(f"\n[pendiente] Pasos sin step en escenarios aún no automatizados: {len(pendientes)}")
        for escenario, paso, _ in pendientes:
            print(f"  {ubicacion(escenario, paso)}: {paso.tipo} {paso.texto}")
    if r.ambiguos:
        print(f"\n[aviso] Pasos que coinciden con más de un step: {len(r.ambiguos)}")
        for escenario, paso, encontrados in r.ambiguos:
            print(f"  {ubicacion(escenario, paso)}: {paso.texto} -> {', '.join(d.origen for d in encontrados)}")
    if args.sugerir and r.faltantes:
        print("\n# Esqueletos sugeridos (revisar nombres y llevar la lógica al Page Object):")
        unicos = {(p.tipo, p.texto): p for _, p, _ in r.faltantes}
        for paso in unicos.values():
            print(f"\n{sugerencia(paso)}")
    if not r.faltantes and not r.ambiguos:
        print("Todos los pasos tienen su step definido.")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
