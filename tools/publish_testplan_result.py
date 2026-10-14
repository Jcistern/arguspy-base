"""
Publica el resultado de un caso automatizado en un Test Plan de Azure DevOps.

Este script cierra el circuito que ``PublishTestResults@2`` no cubre: escribe el
resultado (Passed/Failed) en el **Test Point** del caso dentro de un Test Plan /
Suite, de modo que el historial de ejecucion quede visible en el apartado
"Test Plans" de Azure DevOps (no solo en la pestana Tests del build).

FLUJO
-----
1. Lee el JUnit XML generado por pytest y determina el estado del caso
   (Passed si todos sus tests pasaron; Failed si alguno fallo/erro).
2. Resuelve el Test Point correspondiente al ``planId`` / ``suiteId`` /
   ``testCaseId`` via la API REST de Azure DevOps.
3. Crea un Test Run asociado al plan y registra el resultado del punto.
4. Cierra el Test Run.

USO
---
    python tools/publish_testplan_result.py \
        --org-url https://dev.azure.com/MiOrg \
        --project "<Proyecto>" \
        --plan-id <planId> \
        --suite-id <suiteId> \
        --test-case-id <testCaseId> \
        --junit test-results/junit-results.xml \
        --run-title "BDD @revision - build 123"

El token de acceso se toma de la variable de entorno ``AZURE_DEVOPS_PAT``
(o ``SYSTEM_ACCESSTOKEN`` cuando corre dentro del pipeline).

REQUISITOS
----------
- El PAT / token debe tener permiso ``Test Management (Read & Write)``.
- El Test Case debe existir dentro de la Suite indicada del Plan.
- Paquete ``requests`` disponible en el entorno.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import requests

API_VERSION = "7.1"


@dataclass
class ResultadoJUnit:
    """Resultado agregado de un caso a partir del JUnit."""

    total: int
    fallidos: int
    errores: int
    omitidos: int
    mensaje: str

    @property
    def outcome(self) -> str:
        """Devuelve el outcome esperado por Azure DevOps."""
        if self.total == 0:
            return "NotExecuted"
        if self.fallidos > 0 or self.errores > 0:
            return "Failed"
        if self.omitidos == self.total:
            return "NotExecuted"
        return "Passed"


def _leer_junit(ruta: str, nombre_test: str | None) -> ResultadoJUnit:
    """Agrega el estado del caso a partir del archivo JUnit.

    Si ``nombre_test`` se entrega, solo considera los ``<testcase>`` cuyo
    atributo ``name`` o ``classname`` contenga ese valor (util cuando el XML
    tiene varios tests). Si no, agrega todos los testcase del archivo.
    """
    arbol = ET.parse(ruta)
    raiz = arbol.getroot()
    testcases = raiz.iter("testcase")

    total = fallidos = errores = omitidos = 0
    mensajes: list[str] = []

    for tc in testcases:
        nombre = tc.get("name", "")
        classname = tc.get("classname", "")
        if nombre_test and nombre_test not in nombre and nombre_test not in classname:
            continue

        total += 1
        falla = tc.find("failure")
        error = tc.find("error")
        skip = tc.find("skipped")
        if falla is not None:
            fallidos += 1
            mensajes.append((falla.get("message") or "failure").strip())
        elif error is not None:
            errores += 1
            mensajes.append((error.get("message") or "error").strip())
        elif skip is not None:
            omitidos += 1

    return ResultadoJUnit(
        total=total,
        fallidos=fallidos,
        errores=errores,
        omitidos=omitidos,
        mensaje=" | ".join(m for m in mensajes if m)[:1000],
    )


def _descubrir_casos(ruta: str) -> dict[str, ResultadoJUnit]:
    """Descubre todos los Test Cases ejecutados agrupando por 'test_case_id'.

    Cada ``<testcase>`` del JUnit lleva una propiedad
    ``<property name="test_case_id" value="NNNN"/>`` (grabada por el fixture
    autouse '_registrar_test_case_id' en conftest.py a partir del tag
    ``@TC_<ID>``). Esta funcion agrupa los testcases por ese id y agrega su
    resultado, de modo que un Scenario Outline con varios ejemplos cuente como
    un solo caso (Passed solo si todos sus ejemplos pasaron).

    Devuelve un dict {test_case_id: ResultadoJUnit}. Los testcase sin
    ``test_case_id`` (tests sin tag @TC_) se ignoran.
    """
    arbol = ET.parse(ruta)
    raiz = arbol.getroot()

    agregados: dict[str, dict[str, object]] = {}

    for tc in raiz.iter("testcase"):
        # Extraer el test_case_id de las properties del testcase
        case_id = None
        props = tc.find("properties")
        if props is not None:
            for prop in props.iter("property"):
                if prop.get("name") == "test_case_id":
                    case_id = (prop.get("value") or "").strip()
                    break
        if not case_id:
            continue

        datos = agregados.setdefault(
            case_id,
            {"total": 0, "fallidos": 0, "errores": 0, "omitidos": 0, "mensajes": []},
        )
        datos["total"] += 1
        falla = tc.find("failure")
        error = tc.find("error")
        skip = tc.find("skipped")
        if falla is not None:
            datos["fallidos"] += 1
            datos["mensajes"].append((falla.get("message") or "failure").strip())
        elif error is not None:
            datos["errores"] += 1
            datos["mensajes"].append((error.get("message") or "error").strip())
        elif skip is not None:
            datos["omitidos"] += 1

    resultado: dict[str, ResultadoJUnit] = {}
    for case_id, d in agregados.items():
        resultado[case_id] = ResultadoJUnit(
            total=d["total"],
            fallidos=d["fallidos"],
            errores=d["errores"],
            omitidos=d["omitidos"],
            mensaje=" | ".join(m for m in d["mensajes"] if m)[:1000],
        )
    return resultado


def _resolver_suite_de_caso(
    base: str, project: str, plan_id: int, test_case_id: int,
    headers: dict[str, str],
) -> int | None:
    """Encuentra la Suite dentro del Plan que contiene el Test Case dado.

    Recorre las suites del plan y busca en cuál está el caso. Necesario en el
    modo --auto, donde no se conoce de antemano la suite de cada caso.
    Devuelve el suiteId o None si no se encuentra.
    """
    url_suites = (
        f"{base}/{project}/_apis/testplan/Plans/{plan_id}/suites"
        f"?api-version={API_VERSION}"
    )
    resp = requests.get(url_suites, headers=headers, timeout=30)
    resp.raise_for_status()
    suites = resp.json().get("value", [])

    for suite in suites:
        suite_id = suite.get("id")
        if suite_id is None:
            continue
        url_puntos = (
            f"{base}/{project}/_apis/test/Plans/{plan_id}/Suites/{suite_id}/points"
            f"?testCaseId={test_case_id}&api-version={API_VERSION}"
        )
        try:
            r = requests.get(url_puntos, headers=headers, timeout=30)
            if r.status_code >= 400:
                continue
            if r.json().get("value"):
                return int(suite_id)
        except requests.RequestException:
            continue
    return None


def _auth_header(token: str) -> dict[str, str]:
    """Construye el header Basic esperado por la API REST (PAT como password)."""
    par = base64.b64encode(f":{token}".encode()).decode()
    return {"Authorization": f"Basic {par}", "Content-Type": "application/json"}


def _obtener_point_id(
    base: str, project: str, plan_id: int, suite_id: int, test_case_id: int,
    headers: dict[str, str],
) -> tuple[int, int]:
    """Resuelve el Test Point (pointId, configurationId) del caso en la suite."""
    url = (
        f"{base}/{project}/_apis/test/Plans/{plan_id}/Suites/{suite_id}/points"
        f"?testCaseId={test_case_id}&api-version={API_VERSION}"
    )
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    datos = resp.json()
    puntos = datos.get("value", [])
    if not puntos:
        raise SystemExit(
            f"No se encontro Test Point para el caso {test_case_id} en el plan "
            f"{plan_id} / suite {suite_id}. Verifica que el caso este en la suite."
        )
    punto = puntos[0]
    config_id = int(punto.get("configuration", {}).get("id", 1))
    return int(punto["id"]), config_id


def _crear_run(
    base: str, project: str, plan_id: int, point_id: int, titulo: str,
    headers: dict[str, str],
) -> int:
    """Crea un Test Run asociado al plan y al Test Point."""
    url = f"{base}/{project}/_apis/test/runs?api-version={API_VERSION}"
    cuerpo = {
        "name": titulo,
        "plan": {"id": str(plan_id)},
        "pointIds": [point_id],
        "automated": True,
        "state": "InProgress",
    }
    resp = requests.post(url, headers=headers, json=cuerpo, timeout=30)
    resp.raise_for_status()
    return int(resp.json()["id"])


def _actualizar_resultado(
    base: str, project: str, run_id: int, outcome: str, comentario: str,
    point_id: int, test_case_id: int, headers: dict[str, str],
) -> list[int]:
    """Actualiza el resultado del punto dentro del Test Run recien creado.

    Para que el estado se propague al Test Point del plan (y el caso muestre
    Passed/Failed en el apartado Test Plans), el resultado debe referenciar
    explicitamente ``testPoint`` y ``testCase``. Actualizar solo por ``id`` deja
    el resultado en el run pero no marca el punto del plan.

    Devuelve la lista de IDs de resultado, usada luego para adjuntar evidencia.
    """
    url_res = f"{base}/{project}/_apis/test/Runs/{run_id}/results?api-version={API_VERSION}"
    resp = requests.get(url_res, headers=headers, timeout=30)
    resp.raise_for_status()
    resultados = resp.json().get("value", [])
    if not resultados:
        raise SystemExit(f"El Test Run {run_id} no tiene resultados asociados.")

    payload = []
    for r in resultados:
        payload.append(
            {
                "id": r["id"],
                "outcome": outcome,
                "state": "Completed",
                "comment": comentario or f"Resultado automatizado: {outcome}",
                "testPoint": {"id": str(point_id)},
                "testCase": {"id": str(test_case_id)},
            }
        )
    resp = requests.patch(url_res, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return [int(r["id"]) for r in resultados]


def _adjuntar_a_resultado(
    base: str, project: str, run_id: int, result_id: int, ruta: str,
    headers: dict[str, str], comentario: str = "",
) -> bool:
    """Adjunta un archivo (evidencia) a un Test Result especifico.

    El contenido se envia en base64 segun lo espera la API de Test Attachments.
    Devuelve True si el adjunto se creo correctamente.
    """
    nombre = os.path.basename(ruta)
    with open(ruta, "rb") as fh:
        contenido = base64.b64encode(fh.read()).decode()

    url = (
        f"{base}/{project}/_apis/test/Runs/{run_id}/Results/{result_id}/attachments"
        f"?api-version={API_VERSION}"
    )
    cuerpo = {
        "attachmentType": "GeneralAttachment",
        "fileName": nombre,
        "comment": comentario or "Evidencia automatizada",
        "stream": contenido,
    }
    resp = requests.post(url, headers=headers, json=cuerpo, timeout=60)
    if resp.status_code >= 400:
        print(f"  [WARN] No se pudo adjuntar {nombre}: {resp.status_code} {resp.text[:200]}")
        return False
    return True


def _recolectar_evidencia(
    evidence_dir: str | None, evidence_files: list[str],
) -> list[str]:
    """Reune las rutas de evidencia a adjuntar (PNG/WEBM de la carpeta + archivos sueltos)."""
    rutas: list[str] = []
    if evidence_dir and os.path.isdir(evidence_dir):
        for nombre in sorted(os.listdir(evidence_dir)):
            if nombre.lower().endswith((".png", ".webm", ".jpg", ".jpeg")):
                rutas.append(os.path.join(evidence_dir, nombre))
    for f in evidence_files:
        if f and os.path.isfile(f):
            rutas.append(f)
    return rutas


def _evidencia_de_caso(case_id: str, evidence_dir: str | None) -> list[str]:
    """Devuelve las capturas del caso: ``TC_<id>.png`` y ``TC_<id>_*.png``.

    Soporta dos formas de evidencia por caso:
    - Una sola captura: ``TC_<id>.png`` (ej. la captura de fallo del teardown).
    - Varias capturas de pasos: ``TC_<id>_01_...png``, ``TC_<id>_02_...png``,
      etc. (ej. el login paso a paso). Se devuelven TODAS, ordenadas por
      nombre, para adjuntarlas al Test Point del caso.
    Solo se incluyen archivos de ESTE caso (prefijo exacto ``TC_<id>``), para no
    mezclar evidencia de otros casos.
    """
    if not evidence_dir or not os.path.isdir(evidence_dir):
        return []
    prefijo_exacto = f"TC_{case_id}.png"
    prefijo_pasos = f"TC_{case_id}_"
    rutas: list[str] = []
    for nombre in sorted(os.listdir(evidence_dir)):
        if not nombre.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        if nombre == prefijo_exacto or nombre.startswith(prefijo_pasos):
            rutas.append(os.path.join(evidence_dir, nombre))
    return rutas


def _cerrar_run(
    base: str, project: str, run_id: int, headers: dict[str, str]
) -> None:
    """Marca el Test Run como completado."""
    url = f"{base}/{project}/_apis/test/runs/{run_id}?api-version={API_VERSION}"
    resp = requests.patch(url, headers=headers, json={"state": "Completed"}, timeout=30)
    resp.raise_for_status()


def _publicar_caso(
    base: str, project: str, plan_id: int, suite_id: int, test_case_id: int,
    resultado: ResultadoJUnit, run_title: str, evidencias: list[str],
    headers: dict[str, str],
) -> bool:
    """Publica el resultado de UN caso en su Test Point y adjunta evidencia.

    Encapsula el flujo completo (resolver punto -> crear run -> actualizar
    resultado -> adjuntar evidencia -> cerrar run) para un unico caso.
    Devuelve True si se publico correctamente.
    """
    try:
        point_id, _config = _obtener_point_id(
            base, project, plan_id, suite_id, test_case_id, headers
        )
    except SystemExit as exc:
        print(f"  [WARN] Caso {test_case_id}: {exc}")
        return False

    run_id = _crear_run(base, project, plan_id, point_id, run_title, headers)
    result_ids = _actualizar_resultado(
        base, project, run_id, resultado.outcome, resultado.mensaje,
        point_id, test_case_id, headers,
    )

    if evidencias and result_ids:
        result_id = result_ids[0]
        for ruta in evidencias:
            _adjuntar_a_resultado(
                base, project, run_id, result_id, ruta, headers,
                comentario=f"Evidencia - caso {test_case_id}",
            )

    _cerrar_run(base, project, run_id, headers)
    print(
        f"  [OK] Caso {test_case_id}: '{resultado.outcome}' publicado "
        f"(suite {suite_id}, runId={run_id})."
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-url", required=True, help="Ej: https://dev.azure.com/MiOrg")
    parser.add_argument("--project", required=True, help="Nombre del proyecto en Azure DevOps")
    parser.add_argument("--plan-id", type=int, required=True)
    parser.add_argument(
        "--auto",
        action="store_true",
        help=(
            "Descubre automaticamente todos los casos ejecutados (por su tag "
            "@TC_<ID> grabado en el JUnit) y publica cada uno en su Test Point. "
            "Ignora --suite-id/--test-case-id/--test-name."
        ),
    )
    parser.add_argument(
        "--suite-id", type=int, default=None,
        help="Suite del caso (requerido en modo single; opcional/ignorado en --auto).",
    )
    parser.add_argument(
        "--test-case-id", type=int, default=None,
        help="Caso a publicar (requerido en modo single; ignorado en --auto).",
    )
    parser.add_argument("--junit", required=True, help="Ruta al JUnit XML de pytest")
    parser.add_argument("--test-name", default=None, help="Filtra el testcase por nombre")
    parser.add_argument("--run-title", default="Automated run", help="Titulo del Test Run")
    parser.add_argument(
        "--evidence-dir",
        default=None,
        help="Carpeta con evidencias (adjunta PNG/WEBM/JPG al resultado del caso).",
    )
    parser.add_argument(
        "--evidence-file",
        action="append",
        default=[],
        help="Archivo suelto de evidencia a adjuntar (repetible, ej: report.html).",
    )
    args = parser.parse_args()

    token = os.getenv("AZURE_DEVOPS_PAT") or os.getenv("SYSTEM_ACCESSTOKEN")
    if not token:
        raise SystemExit(
            "Falta el token de acceso. Define AZURE_DEVOPS_PAT o SYSTEM_ACCESSTOKEN."
        )

    if not os.path.exists(args.junit):
        raise SystemExit(f"No se encontro el JUnit XML: {args.junit}")

    base = args.org_url.rstrip("/")
    headers = _auth_header(token)
    evidencias = _recolectar_evidencia(args.evidence_dir, args.evidence_file)

    # =====================================================================
    # MODO AUTO: descubre todos los casos ejecutados y publica cada uno.
    # =====================================================================
    if args.auto:
        casos = _descubrir_casos(args.junit)
        if not casos:
            print(
                "ADVERTENCIA: no se encontraron testcase con tag @TC_<ID> en el "
                "JUnit; no se publica nada. (Verifica que los escenarios tengan "
                "su tag @TC_ y que conftest.py grabe 'test_case_id'.)"
            )
            return 0

        print(f"Casos descubiertos en el JUnit: {len(casos)}")
        fallos_publicacion = 0

        for case_id, resultado in sorted(casos.items()):
            print(
                f"- Caso {case_id}: total={resultado.total} "
                f"fallidos={resultado.fallidos} errores={resultado.errores} "
                f"omitidos={resultado.omitidos} -> {resultado.outcome}"
            )
            try:
                tc_int = int(case_id)
            except ValueError:
                print(f"  [WARN] test_case_id '{case_id}' no es numerico; se omite.")
                fallos_publicacion += 1
                continue

            # Resolver la suite del caso dentro del plan (no se conoce a priori)
            suite_id = _resolver_suite_de_caso(
                base, args.project, args.plan_id, tc_int, headers
            )
            if suite_id is None:
                print(
                    f"  [WARN] Caso {case_id}: no se encontro en ninguna suite del "
                    f"plan {args.plan_id}. Se omite."
                )
                fallos_publicacion += 1
                continue

            # Evidencia POR CASO: adjuntar solo la captura de ESTE caso
            # (test-results/evidencia/TC_<id>.png), no toda la carpeta. Asi
            # cada Test Point recibe unicamente su propia (y ultima) captura.
            evidencias_caso = _evidencia_de_caso(case_id, args.evidence_dir)
            # Los archivos sueltos (ej. report.html) se adjuntan a todos.
            for f in args.evidence_file:
                if f and os.path.isfile(f):
                    evidencias_caso.append(f)

            titulo = f"{args.run_title} - Caso {case_id}"
            ok = _publicar_caso(
                base, args.project, args.plan_id, suite_id, tc_int,
                resultado, titulo, evidencias_caso, headers,
            )
            if not ok:
                fallos_publicacion += 1

        if fallos_publicacion:
            print(
                f"[WARN] {fallos_publicacion} caso(s) no se pudieron publicar. "
                "Revisa los mensajes anteriores."
            )
            return 1
        print(f"[OK] {len(casos)} caso(s) publicados en el plan {args.plan_id}.")
        return 0

    # =====================================================================
    # MODO SINGLE (compatibilidad): publica un unico caso indicado por args.
    # =====================================================================
    if args.suite_id is None or args.test_case_id is None:
        raise SystemExit(
            "En modo single se requieren --suite-id y --test-case-id "
            "(o usa --auto para descubrir y publicar todos los casos)."
        )

    resultado = _leer_junit(args.junit, args.test_name)
    print(
        f"JUnit: total={resultado.total} fallidos={resultado.fallidos} "
        f"errores={resultado.errores} omitidos={resultado.omitidos} "
        f"-> outcome={resultado.outcome}"
    )
    if resultado.total == 0:
        print(
            "ADVERTENCIA: no se encontraron testcase que coincidan; no se publica nada."
        )
        return 0

    ok = _publicar_caso(
        base, args.project, args.plan_id, args.suite_id, args.test_case_id,
        resultado, args.run_title, evidencias, headers,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
