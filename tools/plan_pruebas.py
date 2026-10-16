"""Sincroniza el plan de pruebas (.xlsx o .json) con los .feature del proyecto.

Subcomandos:
    leer      Lee la hoja «Casos» y entrega los casos normalizados en JSON.
    revisar   Señala casos incompletos o ambiguos antes de pasarlos a .feature.
    comparar  Cruza el plan con los .feature (tags @CP_<PANTALLA>_<NN>) y los steps.
    agregar   Agrega casos nuevos al plan en una COPIA del .xlsx (nunca el original).

Ejemplos:
    python tools/plan_pruebas.py leer data/planes/plan.xlsx --resumen
    python tools/plan_pruebas.py leer data/planes/plan.xlsx --pantalla PRY
    python tools/plan_pruebas.py comparar data/planes/plan.xlsx --plantilla test-results/plan_nuevos.json
    python tools/plan_pruebas.py agregar data/planes/plan.xlsx --casos test-results/plan_nuevos.json \\
        --salida data/planes/plan_actualizado.xlsx --marcar-automaticos --etiquetar-features

Formato .json de entrada (equivalente a la hoja «Casos»): una lista de objetos, o
{"casos": [...]}, con las claves de CAMPOS (``pasos`` puede ser lista o texto).
Requiere ``openpyxl`` (requirements-dev.txt) solo para archivos .xlsx.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from copy import copy
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DIR_FEATURES = RAIZ / "tests" / "bdd" / "features"
DIR_STEPS = RAIZ / "tests" / "bdd" / "steps"
HOJA_CASOS = "Casos"
HOJA_EJECUCIONES = "Ejecuciones"
HOJA_DUDAS = "Dudas"
# Clave del JSON -> encabezado de la hoja «Dudas».
CAMPOS_DUDA = {
    "id": "Duda",
    "tarea": "Tarea",
    "que_no_esta_claro": "Qué no está claro",
    "supuesto": "Supuesto con que se probó",
    "casos": "Casos que afecta",
    "bloquea": "Bloquea",
}
PATRON_VAGO = re.compile(
    r"\b(correctamente|de forma correcta|funciona|sin errores|seg[uú]n lo esperado|lo esperado|ok|adecuadamente|como corresponde)\b",
    re.IGNORECASE,
)
PATRON_SOLO_VERIFICAR = re.compile(r"^(validar|verificar|comprobar|revisar|probar)\b", re.IGNORECASE)

# Clave normalizada -> encabezado de la hoja «Casos». Las columnas se ubican por
# nombre, así el script sigue funcionando si se mueven o se agregan columnas.
CAMPOS = {
    "id": "Caso",
    "riesgo": "Riesgo de la tarea",
    "requisito": "Texto del requisito",
    "nombre": "Nombre del caso",
    "precondicion": "Precondición",
    "pasos": "Pasos",
    "datos_entrada": "Datos de entrada",
    "resultado_esperado": "Resultado esperado",
    "tecnica": "Técnica",
    "prioridad": "Prioridad",
    "ejecucion": "Ejecución",
    "camino_critico": "Camino crítico",
    "detalle": "Detalle",
    "bloqueado_por": "Bloqueado por",
    "ambito": "Ámbito",
}
CAMPOS_CALCULADOS = ("Última iteración", "Estado actual")
OBLIGATORIOS_NUEVO = ("pantalla", "nombre", "precondicion", "pasos", "resultado_esperado", "prioridad")
PATRON_ID = re.compile(r"^CP-([A-Z]+)-(N?)(\d+)$")
PATRON_TAG = re.compile(r"^CP_([A-Z]+)_(N?\d+)$")
# Escenarios propios del framework (ej: login base) que no pertenecen al plan del cliente.
TAG_SIN_PLAN = "sin_plan"


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def id_a_tag(id_caso: str) -> str:
    """CP-PRY-01 -> CP_PRY_01 (tag Gherkin sin @)."""
    return id_caso.replace("-", "_")


def tag_a_id(tag: str) -> str | None:
    coincidencia = PATRON_TAG.match(tag.lstrip("@"))
    return f"CP-{coincidencia.group(1)}-{coincidencia.group(2)}" if coincidencia else None


def _pantalla(id_caso: str) -> str:
    coincidencia = PATRON_ID.match(id_caso)
    return coincidencia.group(1) if coincidencia else ""


def separar_pasos(texto: str) -> list[str]:
    """Divide «1. … 2. …» en una lista; las líneas sin número continúan el paso anterior."""
    pasos: list[str] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        numerado = re.match(r"^\d+[.)]\s*(.*)$", linea)
        if numerado or not pasos:
            pasos.append(numerado.group(1) if numerado else linea)
        else:
            pasos[-1] += " " + linea
    return pasos


# ---------------------------------------------------------------------------
# Lectura del plan
# ---------------------------------------------------------------------------


def _cargar_openpyxl():
    try:
        import openpyxl
    except ImportError:
        sys.exit("Falta openpyxl: instala requirements-dev.lock en el .venv del proyecto.")
    return openpyxl


def _columnas(hoja) -> dict[str, int]:
    """Encabezado -> número de columna (1-based) de la fila 1."""
    return {_texto(c.value): c.column for c in hoja[1] if _texto(c.value)}


def leer_plan(ruta: Path) -> list[dict]:
    if ruta.suffix.lower() == ".json":
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        casos = datos.get("casos", []) if isinstance(datos, dict) else datos
        for caso in casos:
            if isinstance(caso.get("pasos"), str):
                caso["pasos"] = separar_pasos(caso["pasos"])
            caso.setdefault("pantalla", _pantalla(caso.get("id", "")))
        return casos

    hoja = _cargar_openpyxl().load_workbook(ruta)[HOJA_CASOS]
    columnas = _columnas(hoja)
    faltantes = [h for h in ("Caso", "Nombre del caso", "Pasos") if h not in columnas]
    if faltantes:
        sys.exit(f"La hoja «{HOJA_CASOS}» no tiene las columnas: {', '.join(faltantes)}")

    casos = []
    for fila in range(2, hoja.max_row + 1):
        id_caso = _texto(hoja.cell(fila, columnas["Caso"]).value)
        if not id_caso:
            continue
        caso = {"fila": fila, "pantalla": _pantalla(id_caso)}
        for clave, encabezado in CAMPOS.items():
            caso[clave] = _texto(hoja.cell(fila, columnas[encabezado]).value) if encabezado in columnas else ""
        caso["pasos"] = separar_pasos(caso["pasos"])
        casos.append(caso)
    return casos


def advertencias_plan(casos: list[dict]) -> list[str]:
    vistos: dict[str, int] = {}
    avisos = []
    for caso in casos:
        id_caso = caso["id"]
        if id_caso in vistos:
            avisos.append(f"ID duplicado {id_caso} (filas {vistos[id_caso]} y {caso.get('fila', '?')}).")
        vistos[id_caso] = caso.get("fila", 0)
        if not PATRON_ID.match(id_caso):
            avisos.append(f"ID con formato no reconocido: {id_caso!r} (se espera CP-<PANTALLA>-<NN>).")
    return avisos


# ---------------------------------------------------------------------------
# Lectura de .feature y steps
# ---------------------------------------------------------------------------


@dataclass
class Escenario:
    archivo: Path
    linea: int
    nombre: str
    tags: list[str] = field(default_factory=list)
    pasos: list[str] = field(default_factory=list)
    ejemplos: list[str] = field(default_factory=list)

    @property
    def ids_plan(self) -> list[str]:
        return [i for i in (tag_a_id(t) for t in self.tags) if i]

    @property
    def ubicacion(self) -> str:
        return f"{self.archivo.relative_to(RAIZ).as_posix()}:{self.linea}"


def leer_features(carpeta: Path = DIR_FEATURES) -> list[Escenario]:
    escenarios: list[Escenario] = []
    for archivo in sorted(carpeta.rglob("*.feature")):
        tags_feature: list[str] = []
        tags_pendientes: list[str] = []
        actual: Escenario | None = None
        en_ejemplos = False
        for numero, bruta in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
            linea = bruta.strip()
            if not linea or linea.startswith("#"):
                continue
            if linea.startswith("@"):
                tags_pendientes += re.findall(r"@([^\s@]+)", linea)
                continue
            clave = linea.split(":", 1)[0].strip()
            if clave == "Feature":
                tags_feature, tags_pendientes = tags_pendientes, []
            elif clave in ("Scenario", "Scenario Outline", "Escenario", "Esquema del escenario"):
                actual = Escenario(archivo, numero, linea.split(":", 1)[1].strip(), tags_feature + tags_pendientes)
                escenarios.append(actual)
                tags_pendientes, en_ejemplos = [], False
            elif clave in ("Background", "Antecedentes", "Rule", "Regla"):
                actual, tags_pendientes = None, []
            elif clave in ("Examples", "Ejemplos"):
                en_ejemplos = True
            elif actual is not None:
                (actual.ejemplos if en_ejemplos else actual.pasos).append(linea)
    return escenarios


def escenarios_automatizados(carpeta: Path = DIR_STEPS) -> set[str]:
    """Nombres de escenario enlazados con @scenario(...) en los archivos de steps."""
    nombres: set[str] = set()
    for archivo in carpeta.rglob("*.py"):
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", getattr(nodo.func, "attr", "")) == "scenario"
                    and len(nodo.args) >= 2 and isinstance(nodo.args[1], ast.Constant)):
                nombres.add(str(nodo.args[1].value))
    return nombres


# ---------------------------------------------------------------------------
# comparar
# ---------------------------------------------------------------------------


def comparar(casos: list[dict], escenarios: list[Escenario], automatizados: set[str]) -> dict:
    ids_plan = {c["id"]: c for c in casos}
    ids_en_features = {i for e in escenarios for i in e.ids_plan}
    return {
        "sin_escenario": [c["id"] for c in casos if c["id"] not in ids_en_features],
        "faltan_en_plan": [e for e in escenarios if not e.ids_plan and TAG_SIN_PLAN not in e.tags],
        "tag_inexistente": [(e, i) for e in escenarios for i in e.ids_plan if i not in ids_plan],
        "marcar_automatico": sorted({i for e in escenarios if e.nombre in automatizados for i in e.ids_plan
                                     if i in ids_plan and ids_plan[i].get("ejecucion") != "automática"}),
        "sin_automatizar": [e for e in escenarios if e.ids_plan and e.nombre not in automatizados],
    }


def _plantilla_nuevo(escenario: Escenario, automatizados: set[str]) -> dict:
    return {
        "feature": escenario.archivo.relative_to(RAIZ).as_posix(),
        "escenario": escenario.nombre,
        "gherkin": escenario.pasos,
        "ejemplos": escenario.ejemplos,
        "pantalla": "",
        "riesgo": "",
        "requisito": "",
        "nombre": "",
        "precondicion": "",
        "pasos": [],
        "datos_entrada": "",
        "resultado_esperado": "",
        "tecnica": "",
        "prioridad": "",
        "ejecucion": "automática" if escenario.nombre in automatizados else "manual",
        "camino_critico": "no",
        "ambito": "",
    }


# ---------------------------------------------------------------------------
# agregar
# ---------------------------------------------------------------------------


def _siguiente_provisional(ids: list[str], pantalla: str) -> str:
    usados = [int(m.group(3)) for i in ids if (m := PATRON_ID.match(i)) and m.group(1) == pantalla and m.group(2) == "N"]
    return f"CP-{pantalla}-N{max(usados, default=0) + 1:02d}"


def _ultima_fila(hoja, columna: int) -> int:
    fila = hoja.max_row
    while fila > 1 and hoja.cell(fila, columna).value in (None, ""):
        fila -= 1
    return fila


def _fila_modelo(hoja, columnas: dict[str, int], caso: dict, ultima: int) -> int:
    """Fila cuyo formato se copia: la última del mismo ámbito (el color de la fila
    depende del ámbito), si no la última de la misma pantalla, si no la última."""
    for clave, valor in (("ambito", caso.get("ambito")), ("pantalla", caso["pantalla"])):
        if not valor:
            continue
        for fila in range(ultima, 1, -1):
            celda = _texto(hoja.cell(fila, columnas["Caso"]).value)
            actual = _pantalla(celda) if clave == "pantalla" else _texto(hoja.cell(fila, columnas.get("Ámbito", 0) or 1).value)
            if celda and actual == valor and (clave == "pantalla" or "Ámbito" in columnas):
                return fila
    return ultima


def _copiar_fila(hoja, origen: int, destino: int) -> None:
    """Copia estilos y fórmulas (ajustando el número de fila) de una fila a otra."""
    for col in range(1, hoja.max_column + 1):
        celda_origen, celda = hoja.cell(origen, col), hoja.cell(destino, col)
        if celda_origen.has_style:
            celda.font, celda.fill, celda.border = copy(celda_origen.font), copy(celda_origen.fill), copy(celda_origen.border)
            celda.alignment, celda.number_format = copy(celda_origen.alignment), celda_origen.number_format
        valor = celda_origen.value
        if isinstance(valor, str) and valor.startswith("=") and celda.value in (None, ""):
            # Solo referencias relativas (A2, O2); las absolutas ($A$2) se mantienen.
            celda.value = re.sub(rf"(?<![$\w])([A-Z]{{1,3}}){origen}(?!\d)", rf"\g<1>{destino}", valor)
        if hoja.row_dimensions[origen].height:
            hoja.row_dimensions[destino].height = hoja.row_dimensions[origen].height


def _extender_validaciones(hoja, origen: int, destino: int) -> None:
    for validacion in hoja.data_validations.dataValidation:
        for col in range(1, hoja.max_column + 1):
            letra = hoja.cell(origen, col).column_letter
            if any(rango.min_row <= origen <= rango.max_row and rango.min_col <= col <= rango.max_col
                   for rango in validacion.sqref.ranges):
                validacion.add(f"{letra}{destino}")


def _escribir_caso(hoja, columnas: dict[str, int], fila: int, caso: dict) -> None:
    valores = dict(caso)
    valores["pasos"] = "\n".join(f"{n}. {p}" for n, p in enumerate(caso.get("pasos") or [], start=1))
    for clave, encabezado in CAMPOS.items():
        if encabezado in columnas and valores.get(clave) not in (None, ""):
            hoja.cell(fila, columnas[encabezado]).value = valores[clave]


def _etiquetar_feature(nuevo: dict) -> str | None:
    """Agrega el tag @CP_… sobre el escenario indicado en su .feature."""
    ruta = RAIZ / nuevo["feature"]
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    for indice, linea in enumerate(lineas):
        partes = linea.strip().split(":", 1)
        if len(partes) == 2 and partes[0] in ("Scenario", "Scenario Outline") and partes[1].strip() == nuevo["escenario"]:
            tag = "@" + id_a_tag(nuevo["id"])
            sangria = linea[: len(linea) - len(linea.lstrip())]
            if indice > 0 and lineas[indice - 1].strip().startswith("@"):
                lineas[indice - 1] = lineas[indice - 1].rstrip("\r\n") + f" {tag}\n"
            else:
                lineas.insert(indice, f"{sangria}{tag}\n")
            ruta.write_text("".join(lineas), encoding="utf-8")
            return None
    return f"No se encontró el escenario «{nuevo['escenario']}» en {nuevo['feature']}; etiquétalo a mano con @{id_a_tag(nuevo['id'])}."


def _agregar_dudas(libro, dudas: list[dict]) -> list[str]:
    hoja = libro[HOJA_DUDAS]
    columnas = _columnas(hoja)
    ids = [_texto(hoja.cell(f, columnas["Duda"]).value) for f in range(2, hoja.max_row + 1)]
    mensajes = []
    for duda in dudas:
        pantalla = (duda.get("pantalla") or "GEN").upper()
        usados = [int(m.group(1)) for i in ids if (m := re.match(rf"^D-{pantalla}-N(\d+)$", i))]
        duda["id"] = f"D-{pantalla}-N{max(usados, default=0) + 1:02d}"
        ids.append(duda["id"])
        if isinstance(duda.get("casos"), list):
            duda["casos"] = ", ".join(duda["casos"])
        ultima = _ultima_fila(hoja, columnas["Duda"])
        _copiar_fila(hoja, ultima, ultima + 1)
        for clave, encabezado in CAMPOS_DUDA.items():
            if encabezado in columnas:
                hoja.cell(ultima + 1, columnas[encabezado]).value = duda.get(clave) or None
        for encabezado in ("Respuesta", "Respondido por", "Fecha"):
            if encabezado in columnas:
                hoja.cell(ultima + 1, columnas[encabezado]).value = None
        mensajes.append(f"? {duda['id']} (fila {ultima + 1}): {duda.get('que_no_esta_claro', '')[:80]}")
    return mensajes


def agregar(plan: Path, nuevos: list[dict], salida: Path, marcar: list[str], etiquetar: bool,
            dudas: list[dict] | None = None) -> list[str]:
    if plan.suffix.lower() != ".xlsx":
        sys.exit("agregar solo escribe planes .xlsx.")
    if salida.resolve() == plan.resolve():
        sys.exit("La salida debe ser otro archivo: el plan original nunca se modifica.")
    errores = [f"Caso nuevo #{n}: falta «{campo}»." for n, caso in enumerate(nuevos, start=1)
               for campo in OBLIGATORIOS_NUEVO if not caso.get(campo)]
    errores += [f"Duda #{n}: falta «que_no_esta_claro»." for n, d in enumerate(dudas or [], start=1)
                if not d.get("que_no_esta_claro")]
    if errores:
        sys.exit("\n".join(errores))

    libro = _cargar_openpyxl().load_workbook(plan)
    hoja, ejecuciones = libro[HOJA_CASOS], libro[HOJA_EJECUCIONES]
    columnas, col_ejec = _columnas(hoja), _columnas(ejecuciones)
    ids = [_texto(hoja.cell(f, columnas["Caso"]).value) for f in range(2, hoja.max_row + 1)]
    mensajes = []

    for caso in nuevos:
        caso["id"] = _siguiente_provisional(ids, caso["pantalla"])
        ids.append(caso["id"])
        caso.setdefault("detalle", f"ID provisional · agregado desde automatización ({caso.get('feature', '-')}) el {date.today():%Y-%m-%d}")
        ultima = _ultima_fila(hoja, columnas["Caso"])
        modelo = _fila_modelo(hoja, columnas, caso, ultima)
        _copiar_fila(hoja, modelo, ultima + 1)
        _extender_validaciones(hoja, modelo, ultima + 1)
        _escribir_caso(hoja, columnas, ultima + 1, caso)

        # Toda fila de «Casos» tiene su iteración 1 en «Ejecuciones».
        fila_ejec = _ultima_fila(ejecuciones, col_ejec["Caso"]) + 1
        _copiar_fila(ejecuciones, fila_ejec - 1, fila_ejec)
        ejecuciones.cell(fila_ejec, col_ejec["Caso"]).value = caso["id"]
        ejecuciones.cell(fila_ejec, col_ejec["Iteración"]).value = 1
        ejecuciones.cell(fila_ejec, col_ejec["Estado"]).value = "No ejecutado"
        for encabezado in ("Fecha de ejecución", "Ejecutado por", "Ambiente", "Versión probada",
                           "Resultado obtenido", "Evidencia (enlace o archivo)", "Defecto", "Observación"):
            if encabezado in col_ejec:
                ejecuciones.cell(fila_ejec, col_ejec[encabezado]).value = None
        mensajes.append(f"+ {caso['id']} (fila {ultima + 1}): {caso['nombre']}")

    for id_caso in marcar:
        for fila in range(2, hoja.max_row + 1):
            if _texto(hoja.cell(fila, columnas["Caso"]).value) == id_caso:
                hoja.cell(fila, columnas["Ejecución"]).value = "automática"
                mensajes.append(f"~ {id_caso} (fila {fila}): Ejecución → automática")

    if dudas:
        mensajes += _agregar_dudas(libro, dudas)

    salida.parent.mkdir(parents=True, exist_ok=True)
    libro.save(salida)
    if etiquetar:
        mensajes += [m for m in (_etiquetar_feature(c) for c in nuevos if c.get("feature")) if m]
    return mensajes


# ---------------------------------------------------------------------------
# revisar (calidad del caso)
# ---------------------------------------------------------------------------


def revisar_calidad(caso: dict) -> list[str]:
    """Problemas que impiden escribir el escenario sin suponer cosas."""
    problemas = []
    pasos, esperado = caso.get("pasos") or [], caso.get("resultado_esperado", "")
    datos, texto_pasos = caso.get("datos_entrada", ""), " ".join(caso.get("pasos") or [])
    if not caso.get("precondicion"):
        problemas.append("sin precondición (cuenta y estado inicial)")
    if not pasos:
        problemas.append("sin pasos")
    elif all(PATRON_SOLO_VERIFICAR.match(p) for p in pasos):
        problemas.append("los pasos solo dicen qué validar, no qué acción hacer")
    if len(esperado.split()) < 6:
        problemas.append("resultado esperado vacío o demasiado corto")
    elif PATRON_VAGO.search(esperado) and len(esperado.split()) < 25:
        problemas.append(f"resultado esperado vago («{PATRON_VAGO.search(esperado).group(0)}»): no dice qué se ve")
    if re.search(r"\b(dato|escenario) [A-Z]\b", texto_pasos) and not re.search(r"\b[A-Z]:", datos):
        problemas.append("los pasos usan «dato A/B» pero «Datos de entrada» no los define")
    elif not datos and re.search(r"\b(escribe|ingresa|completa|pega|elige)\b", texto_pasos, re.IGNORECASE):
        problemas.append("los pasos ingresan datos pero «Datos de entrada» está vacío")
    if caso.get("bloqueado_por"):
        problemas.append(f"bloqueado por {caso['bloqueado_por']}")
    pendientes = [l for l in (caso.get("detalle") or "").splitlines() if l.strip().startswith("*")]
    if pendientes:
        problemas.append(f"{len(pendientes)} validación(es) «*» en Detalle sin diseñar")
    return problemas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_leer(args: argparse.Namespace) -> int:
    casos = leer_plan(args.plan)
    for aviso in advertencias_plan(casos):
        print(f"[aviso] {aviso}", file=sys.stderr)
    if args.pantalla:
        casos = [c for c in casos if c["pantalla"] == args.pantalla.upper()]
    if args.caso:
        casos = [c for c in casos if c["id"] in args.caso]
    if args.resumen:
        for c in casos:
            print(f"{c['id']:<12} {c.get('ejecucion', ''):<11} {c['nombre'][:90]}")
        pantallas: dict[str, int] = {}
        for c in casos:
            pantallas[c["pantalla"]] = pantallas.get(c["pantalla"], 0) + 1
        print(f"\n{len(casos)} casos · por pantalla: " + ", ".join(f"{p}={n}" for p, n in pantallas.items()))
        return 0
    texto = json.dumps(casos, ensure_ascii=False, indent=2)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
        print(f"{len(casos)} casos escritos en {args.salida}")
    else:
        print(texto)
    return 0


def _cmd_revisar(args: argparse.Namespace) -> int:
    casos = leer_plan(args.plan)
    for aviso in advertencias_plan(casos):
        print(f"[aviso] {aviso}")
    if args.pantalla:
        casos = [c for c in casos if c["pantalla"] == args.pantalla.upper()]
    completos = 0
    repetidos = {c["id"] for c in casos if sum(o["id"] == c["id"] for o in casos) > 1}
    for caso in casos:
        etiqueta = f"{caso['id']} (fila {caso.get('fila', '?')})" if caso["id"] in repetidos else caso["id"]
        hallazgos = revisar_calidad(caso)
        # Las viñetas «*» de Detalle son casos aún no diseñados: no impiden importar el caso principal.
        problemas = [h for h in hallazgos if "en Detalle" not in h]
        notas = [h for h in hallazgos if "en Detalle" in h]
        if problemas:
            print(f"[falta]  {etiqueta}: " + "; ".join(problemas + notas))
        else:
            completos += 1
            if notas:
                print(f"[nota]   {etiqueta}: " + "; ".join(notas))
    print(f"\n{completos} de {len(casos)} casos se pueden pasar a .feature sin supuestos.")
    return 0


def _cmd_comparar(args: argparse.Namespace) -> int:
    casos = leer_plan(args.plan)
    for aviso in advertencias_plan(casos):
        print(f"[aviso] {aviso}")
    escenarios, automatizados = leer_features(), escenarios_automatizados()
    r = comparar(casos, escenarios, automatizados)

    print(f"Plan: {len(casos)} casos · Features: {len(escenarios)} escenarios ({len(automatizados)} automatizados)\n")
    print(f"Casos del plan sin escenario: {len(r['sin_escenario'])}")
    for id_caso in r["sin_escenario"]:
        print(f"  - {id_caso}")
    print(f"\nEscenarios que faltan en el plan: {len(r['faltan_en_plan'])}")
    for e in r["faltan_en_plan"]:
        print(f"  - {e.ubicacion} · {e.nombre}")
    print(f"\nTags @CP_ que no existen en el plan: {len(r['tag_inexistente'])}")
    for e, id_caso in r["tag_inexistente"]:
        print(f"  - {e.ubicacion} · {id_caso}")
    print(f"\nCasos automatizados a marcar como «automática»: {len(r['marcar_automatico'])}")
    for id_caso in r["marcar_automatico"]:
        print(f"  - {id_caso}")
    print(f"\nEscenarios del plan aún sin steps (@scenario): {len(r['sin_automatizar'])}")

    if args.plantilla:
        plantilla = {"marcar_automaticos": r["marcar_automatico"], "dudas": [],
                     "casos": [_plantilla_nuevo(e, automatizados) for e in r["faltan_en_plan"]]}
        args.plantilla.parent.mkdir(parents=True, exist_ok=True)
        args.plantilla.write_text(json.dumps(plantilla, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nPlantilla para completar: {args.plantilla}")
    return 0


def _cmd_agregar(args: argparse.Namespace) -> int:
    datos = json.loads(args.casos.read_text(encoding="utf-8"))
    nuevos = datos.get("casos", []) if isinstance(datos, dict) else datos
    marcar = (datos.get("marcar_automaticos", []) if isinstance(datos, dict) else []) if args.marcar_automaticos else []
    for caso in nuevos:
        if isinstance(caso.get("pasos"), str):
            caso["pasos"] = separar_pasos(caso["pasos"])
        caso["pantalla"] = (caso.get("pantalla") or "").upper()
    dudas = datos.get("dudas", []) if isinstance(datos, dict) else []
    for mensaje in agregar(args.plan, nuevos, args.salida, marcar, args.etiquetar_features, dudas):
        print(mensaje)
    print(f"\nPlan actualizado: {args.salida} (el original no se modificó)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincroniza el plan de pruebas con los .feature.")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_leer = sub.add_parser("leer", help="Casos del plan en JSON normalizado.")
    p_leer.add_argument("plan", type=Path)
    p_leer.add_argument("--pantalla", help="Filtra por pantalla (ej: PRY).")
    p_leer.add_argument("--caso", nargs="+", help="Filtra por ID (ej: CP-PRY-01).")
    p_leer.add_argument("--resumen", action="store_true", help="Lista compacta en vez de JSON.")
    p_leer.add_argument("--salida", type=Path, help="Escribe el JSON en un archivo.")
    p_leer.set_defaults(funcion=_cmd_leer)

    p_rev = sub.add_parser("revisar", help="Casos incompletos o ambiguos.")
    p_rev.add_argument("plan", type=Path)
    p_rev.add_argument("--pantalla", help="Filtra por pantalla (ej: PRY).")
    p_rev.set_defaults(funcion=_cmd_revisar)

    p_comp = sub.add_parser("comparar", help="Cruza el plan con los .feature y los steps.")
    p_comp.add_argument("plan", type=Path)
    p_comp.add_argument("--plantilla", type=Path, help="Escribe un JSON con los casos nuevos por completar.")
    p_comp.set_defaults(funcion=_cmd_comparar)

    p_agr = sub.add_parser("agregar", help="Agrega casos nuevos y dudas en una copia del .xlsx.")
    p_agr.add_argument("plan", type=Path)
    p_agr.add_argument("--casos", type=Path, required=True, help="JSON con los casos nuevos (salida de comparar, completada).")
    p_agr.add_argument("--salida", type=Path, required=True, help="Archivo .xlsx de salida (distinto del original).")
    p_agr.add_argument("--marcar-automaticos", action="store_true", help="Pone «automática» en los casos ya automatizados.")
    p_agr.add_argument("--etiquetar-features", action="store_true", help="Agrega el tag @CP_… a los escenarios nuevos.")
    p_agr.set_defaults(funcion=_cmd_agregar)

    args = parser.parse_args(argv)
    return args.funcion(args)


if __name__ == "__main__":
    sys.exit(main())
