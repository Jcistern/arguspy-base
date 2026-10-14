"""Genera un reporte HTML propio de ArgusPy desde allure-results.

Este generador crea:
- `reporte-html/index.html`: UI HTML5 standalone (sin necesidad de servidor ni fetch).
- `reporte-html/runs/index.json`: catálogo/historial de ejecuciones.
- `reporte-html/runs/<run_id>/{summary.json,tests.json,assets/}`: datos por ejecución.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = Path(__file__).resolve().parent / "templates"
ESTADOS = {"failed": 0, "broken": 1, "skipped": 2, "passed": 3, "unknown": 4}


def duracion(ms: int) -> str:
    """Convierte milisegundos a una duración fácil de leer."""
    if ms < 1000:
        return f"{ms} ms"
    segundos = ms / 1000
    if segundos < 60:
        return f"{segundos:.2f} s"
    minutos, segundos = divmod(segundos, 60)
    return f"{int(minutos)}m {segundos:.1f}s"


def adjunto(item: dict[str, Any], resultados: Path, assets: Path) -> dict[str, Any]:
    """Transforma un attachment Allure para su inclusión en el reporte.

    Las imágenes y videos se copian a assets/ y se referencian por ruta relativa.
    """
    source = item.get("source", "")
    origen = resultados / source
    extension = origen.suffix.lower()
    evidencia = {
        "nombre": item.get("name", "Evidencia"),
        "imagen": False,
        "video": False,
        "texto": False,
        "ruta": None,
        "contenido": None,
    }

    if not origen.exists():
        return evidencia

    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        evidencia["imagen"] = True
        # Copiar imagen a assets/ y referenciar por ruta relativa (evita inflar el HTML con base64)
        try:
            assets.mkdir(parents=True, exist_ok=True)
            destino = assets / source
            shutil.copy2(origen, destino)
            evidencia["ruta"] = f"assets/{source}"
        except Exception:
            pass
    elif extension in {".webm", ".mp4"}:
        evidencia["video"] = True
        assets.mkdir(parents=True, exist_ok=True)
        destino = assets / source
        shutil.copy2(origen, destino)
        evidencia["ruta"] = f"assets/{source}"
    elif extension in {".txt", ".log"} or "text" in item.get("type", ""):
        evidencia["texto"] = True
        evidencia["contenido"] = origen.read_text(encoding="utf-8", errors="replace")
    else:
        assets.mkdir(parents=True, exist_ok=True)
        destino = assets / source
        shutil.copy2(origen, destino)
        evidencia["ruta"] = f"assets/{source}"

    return evidencia


def pasos(items: list[dict[str, Any]], resultados: Path, assets: Path) -> list[dict[str, Any]]:
    """Parsea steps Allure, conservando su jerarquía y adjuntos."""
    return [
        {
            "nombre": item.get("name", "Paso sin nombre"),
            "estado": item.get("status", "unknown"),
            "duracion": max(item.get("stop", 0) - item.get("start", 0), 0),
            "pasos": pasos(item.get("steps", []), resultados, assets),
            "adjuntos": [adjunto(a, resultados, assets) for a in item.get("attachments", [])],
        }
        for item in items
    ]


def etiquetas(labels: list[dict[str, str]]) -> dict[str, Any]:
    """Extrae labels funcionales desde un resultado Allure."""
    data: dict[str, Any] = {"tags": []}
    for label in labels:
        clave, valor = label.get("name"), label.get("value")
        if clave == "tag":
            data["tags"].append(valor)
        elif clave in {"epic", "feature", "story", "severity", "suite"}:
            data[clave] = valor
    return data


def adjuntos_de_fixtures(resultados: Path) -> dict[str, list[dict[str, Any]]]:
    """Relaciona los adjuntos de teardown/setup de Allure con cada test hijo.

    Allure registra las evidencias adjuntadas desde una fixture en archivos
    *-container.json, no directamente en el *-result.json del test.
    """
    por_test: dict[str, list[dict[str, Any]]] = {}
    for archivo in resultados.glob("*-container.json"):
        try:
            container = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        adjuntos = []
        for fixture in [*container.get("befores", []), *container.get("afters", [])]:
            adjuntos.extend(fixture.get("attachments", []))

        for uuid in container.get("children", []):
            por_test.setdefault(uuid, []).extend(adjuntos)
    return por_test


def cargar_resultados(resultados: Path, assets: Path) -> list[dict[str, Any]]:
    """Carga los archivos *-result.json creados por allure-pytest."""
    tests: list[dict[str, Any]] = []
    fixtures_por_test = adjuntos_de_fixtures(resultados)
    for archivo in resultados.glob("*-result.json"):
        try:
            data = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        labels = etiquetas(data.get("labels", []))
        inicio, fin = data.get("start", 0), data.get("stop", 0)
        detalle = data.get("statusDetails") or {}
        titulo_path = data.get("titlePath") or []
        tests.append(
            {
                "id": data.get("uuid", archivo.stem),
                "nombre": data.get("name", archivo.stem),
                "nombre_completo": data.get("fullName", ""),
                "estado": data.get("status", "unknown"),
                "duracion": max(fin - inicio, 0),
                "inicio": inicio,
                "epic": labels.get("epic", "Sin épica"),
                "feature": labels.get("feature", "Sin feature"),
                "story": labels.get("story", "Sin historia"),
                "severidad": labels.get("severity", "normal"),
                "suite": ".".join(titulo_path) if titulo_path else labels.get("suite", "Sin suite"),
                "tags": labels["tags"],
                "pasos": pasos(data.get("steps", []), resultados, assets),
                "adjuntos": [
                    adjunto(a, resultados, assets)
                    for a in [*data.get("attachments", []), *fixtures_por_test.get(data.get("uuid", ""), [])]
                ],
                "mensaje_error": detalle.get("message"),
                "trace_error": detalle.get("trace"),
            }
        )
    return sorted(tests, key=lambda test: (ESTADOS.get(test["estado"], 4), test["inicio"]))


def _run_id(now: datetime) -> str:
    return now.strftime("%Y-%m-%d_%H%M%S")


def _cargar_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _limpiar_adjunto_para_disco(adjunto_data: dict[str, Any]) -> dict[str, Any]:
    """Devuelve un adjunto ligero: solo metadata + ruta (sin base64 ni contenido de texto)."""
    return {
        "nombre": adjunto_data.get("nombre", "Evidencia"),
        "imagen": adjunto_data.get("imagen", False),
        "video": adjunto_data.get("video", False),
        "texto": adjunto_data.get("texto", False),
        "ruta": adjunto_data.get("ruta"),
        "contenido": None,  # No guardar contenido de texto en disco (es poco útil en historial)
    }


def _limpiar_pasos_adjuntos(pasos_list: list[dict[str, Any]]) -> None:
    """Recursivamente elimina adjuntos pesados (base64, contenido) de los pasos in-place."""
    for p in pasos_list:
        p["adjuntos"] = []
        _limpiar_pasos_adjuntos(p.get("pasos", []))


def _pasos_ligeros(pasos_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recursivamente limpia adjuntos pesados de los pasos."""
    return [
        {
            "nombre": p.get("nombre", ""),
            "estado": p.get("estado", "unknown"),
            "duracion": p.get("duracion", 0),
            "pasos": _pasos_ligeros(p.get("pasos", [])),
            "adjuntos": [_limpiar_adjunto_para_disco(a) for a in p.get("adjuntos", [])],
        }
        for p in pasos_list
    ]


def _tests_ligeros(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Crea una copia ligera de los tests: sin base64, sin contenido de texto embebido.

    Conserva: metadata del test, pasos, errores, rutas a archivos.
    Elimina: strings base64, contenido de texto de adjuntos (se mantiene la referencia por ruta).
    """
    ligeros = []
    for t in tests:
        test_ligero = {
            "id": t.get("id"),
            "nombre": t.get("nombre"),
            "nombre_completo": t.get("nombre_completo"),
            "estado": t.get("estado"),
            "duracion": t.get("duracion"),
            "inicio": t.get("inicio"),
            "epic": t.get("epic"),
            "feature": t.get("feature"),
            "story": t.get("story"),
            "severidad": t.get("severidad"),
            "suite": t.get("suite"),
            "tags": t.get("tags", []),
            "pasos": _pasos_ligeros(t.get("pasos", [])),
            "adjuntos": [_limpiar_adjunto_para_disco(a) for a in t.get("adjuntos", [])],
            "mensaje_error": t.get("mensaje_error"),
            "trace_error": t.get("trace_error"),
        }
        ligeros.append(test_ligero)
    return ligeros


def _prefixar_rutas_evidencias(tests: list[dict[str, Any]], prefix: str) -> None:
    """Añade el prefijo de run a todas las rutas de evidencias para que sean relativas al index.html."""
    for t in tests:
        for a in t.get("adjuntos", []):
            if a.get("ruta") and not a["ruta"].startswith(prefix):
                a["ruta"] = prefix + a["ruta"]
        for paso in t.get("pasos", []):
            _prefixar_rutas_pasos(paso, prefix)


def _prefixar_rutas_pasos(paso: dict[str, Any], prefix: str) -> None:
    """Recursivamente prefija rutas en adjuntos de pasos."""
    for a in paso.get("adjuntos", []):
        if a.get("ruta") and not a["ruta"].startswith(prefix):
            a["ruta"] = prefix + a["ruta"]
    for sub in paso.get("pasos", []):
        _prefixar_rutas_pasos(sub, prefix)


def _limpiar_evidencias_runs_antiguos(salida: Path, latest_run_id: str) -> None:
    """Elimina evidencias pesadas (assets) de todas las ejecuciones excepto la última.

    Mantiene `summary.json` y `tests.json` para preservar el historial.
    """
    runs_dir = salida / "runs"
    if not runs_dir.exists():
        return

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        if run_dir.name == latest_run_id:
            continue

        assets_dir = run_dir / "assets"
        if assets_dir.exists():
            shutil.rmtree(assets_dir, ignore_errors=True)


def _limpiar_tests_json_historicos(runs_dir: Path, latest_run_id: str) -> None:
    """Reescribe tests.json de runs históricos si contienen datos pesados (base64 legacy).

    Detecta archivos >50KB y los limpia eliminando base64/contenido de adjuntos.
    Solo conserva metadata ligera de cada test.
    """
    UMBRAL_BYTES = 50 * 1024  # 50KB - un tests.json limpio pesa mucho menos

    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        if run_dir.name == latest_run_id:
            continue

        tests_path = run_dir / "tests.json"
        if not tests_path.exists():
            continue

        # Solo limpiar si el archivo supera el umbral (probablemente tiene base64)
        if tests_path.stat().st_size <= UMBRAL_BYTES:
            continue

        try:
            data = json.loads(tests_path.read_text(encoding="utf-8"))
            tests_list = data.get("tests", [])
            tests_limpios = _tests_ligeros(tests_list)
            tests_path.write_text(
                json.dumps({"tests": tests_limpios}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except (OSError, json.JSONDecodeError):
            continue


def generar_reporte(carpeta_resultados: str = "allure-results", carpeta_salida: str = "reporte-html") -> Path:
    """Construye `reporte-html/index.html` + historial de ejecuciones en `reporte-html/runs/`.

    Política: solo se conserva evidencia (assets) para la última ejecución.
    El index.html es standalone: contiene todos los datos inyectados (sin necesidad de fetch).
    """
    resultados = RAIZ / carpeta_resultados
    salida = RAIZ / carpeta_salida

    if not resultados.exists():
        raise FileNotFoundError(f"No existe {resultados}. Ejecuta pytest --alluredir=allure-results.")

    salida.mkdir(parents=True, exist_ok=True)

    now = datetime.now().astimezone()
    run_id = _run_id(now)

    runs_dir = salida / "runs"
    run_dir = runs_dir / run_id
    assets = run_dir / "assets"
    run_dir.mkdir(parents=True, exist_ok=True)

    tests = cargar_resultados(resultados, assets)

    # Prefixar rutas de evidencias con la ruta relativa del run (desde index.html)
    run_prefix = f"runs/{run_id}/"
    _prefixar_rutas_evidencias(tests, run_prefix)

    conteo = {estado: 0 for estado in ESTADOS}
    for test in tests:
        conteo[test["estado"]] = conteo.get(test["estado"], 0) + 1

    total = len(tests)
    duration_ms = int(sum(test["duracion"] for test in tests))
    exito = round((conteo["passed"] / total * 100) if total else 0, 1)

    # agregaciones para dashboard
    by_epic: dict[str, dict[str, Any]] = {}
    by_severity: dict[str, int] = {}
    for t in tests:
        epic = t.get("epic", "Sin épica")
        agg = by_epic.setdefault(
            epic,
            {"name": epic, "passed": 0, "failed": 0, "broken": 0, "skipped": 0, "unknown": 0, "total": 0},
        )
        st = t.get("estado", "unknown")
        agg[st] = agg.get(st, 0) + 1
        agg["total"] += 1

        sev = t.get("severidad", "normal")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    slowest = sorted(
        [
            {
                "name": t.get("nombre"),
                "durationMs": int(t.get("duracion", 0)),
                "status": t.get("estado"),
                "epic": t.get("epic"),
                "feature": t.get("feature"),
            }
            for t in tests
        ],
        key=lambda x: x["durationMs"],
        reverse=True,
    )[:10]

    summary = {
        "runId": run_id,
        "isLatest": True,
        "generatedAt": now.isoformat(),
        "durationMs": duration_ms,
        "durationHuman": duracion(duration_ms),
        "total": total,
        "status": {k: int(conteo.get(k, 0)) for k in ["passed", "failed", "broken", "skipped", "unknown"]},
        "successRate": exito,
        "byEpic": sorted(by_epic.values(), key=lambda x: x["total"], reverse=True),
        "bySeverity": [{"name": k, "count": v} for k, v in sorted(by_severity.items(), key=lambda kv: kv[1], reverse=True)],
        "slowestTests": slowest,
    }

    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Guardar tests.json ligero (sin datos pesados de evidencias embebidas)
    # Las imágenes ya están como archivos en assets/, solo guardamos la referencia por ruta
    tests_para_disco = _tests_ligeros(tests)
    (run_dir / "tests.json").write_text(json.dumps({"tests": tests_para_disco}, ensure_ascii=False, indent=2), encoding="utf-8")

    # actualizar catálogo de runs
    runs_dir.mkdir(parents=True, exist_ok=True)
    index_json_path = runs_dir / "index.json"
    catalog = _cargar_json(index_json_path, {"latest": None, "runs": []})

    # dedupe por id
    catalog_runs = [r for r in catalog.get("runs", []) if r.get("id") != run_id]
    catalog_runs.insert(
        0,
        {
            "id": run_id,
            "generatedAt": now.isoformat(),
            "label": now.strftime("%d/%m/%Y %H:%M:%S"),
            "path": f"runs/{run_id}/",
        },
    )
    catalog["latest"] = run_id
    catalog["runs"] = catalog_runs[:200]

    index_json_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    # Limpieza: conservar evidencia solo para el último run
    _limpiar_evidencias_runs_antiguos(salida, latest_run_id=run_id)

    # Limpiar tests.json históricos que puedan contener datos pesados (base64 legacy)
    _limpiar_tests_json_historicos(runs_dir, latest_run_id=run_id)

    # Construir datos de tendencia (últimas 30 ejecuciones) leyendo summaries existentes
    trend_data: list[dict[str, Any]] = []
    # Historial: solo summaries + tests de las últimas 5 ejecuciones (para no inflar el HTML)
    # Las 30 de tendencia solo aportan successRate (ligero).
    MAX_HISTORY_WITH_TESTS = 5
    history_data: dict[str, dict[str, Any]] = {}
    for idx, run_entry in enumerate(catalog["runs"][:30]):
        run_entry_id = run_entry.get("id", "")
        summary_path = runs_dir / run_entry_id / "summary.json"
        run_summary = _cargar_json(summary_path, None)
        if run_summary is not None:
            trend_data.append({
                "runId": run_entry_id,
                "generatedAt": run_summary.get("generatedAt", run_entry.get("generatedAt", "")),
                "successRate": run_summary.get("successRate", 0),
                "total": run_summary.get("total", 0),
            })

            # Para runs que no son el actual, cargar tests solo de los más recientes
            if run_entry_id != run_id and idx < MAX_HISTORY_WITH_TESTS:
                tests_path = runs_dir / run_entry_id / "tests.json"
                run_tests_data = _cargar_json(tests_path, None)
                if run_tests_data is not None:
                    # Limpiar evidencias y datos pesados para reducir tamaño en HTML
                    hist_tests = run_tests_data.get("tests", [])
                    for t in hist_tests:
                        t["adjuntos"] = []
                        # Limpiar adjuntos de pasos recursivamente
                        _limpiar_pasos_adjuntos(t.get("pasos", []))
                        # Truncar tracebacks largos
                        if t.get("trace_error") and len(t["trace_error"]) > 500:
                            t["trace_error"] = t["trace_error"][:500] + "\n... (truncado)"
                    history_data[run_entry_id] = {
                        "summary": run_summary,
                        "tests": hist_tests,
                    }
                else:
                    history_data[run_entry_id] = {"summary": run_summary, "tests": []}
            elif run_entry_id != run_id:
                # Para runs más antiguos, solo inyectar el summary (sin tests)
                history_data[run_entry_id] = {"summary": run_summary, "tests": []}
            else:
                # El run actual ya se inyecta como CURRENT_SUMMARY y CURRENT_TESTS_PAYLOAD
                pass

    # Render del index.html CON DATOS INYECTADOS (standalone, sin necesidad de fetch)
    env = Environment(
        loader=FileSystemLoader(str(PLANTILLAS)),
        autoescape=select_autoescape(["html"]),
    )
    html = env.get_template("report_template.html").render(
        generado=now.strftime("%d/%m/%Y %H:%M:%S"),
        run_id=run_id,
        catalog_json=json.dumps(catalog, ensure_ascii=False),
        summary_json=json.dumps(summary, ensure_ascii=False),
        tests_json=json.dumps({"tests": tests}, ensure_ascii=False),
        trend_json=json.dumps(trend_data, ensure_ascii=False),
        history_json=json.dumps(history_data, ensure_ascii=False),
    )
    index = salida / "index.html"
    index.write_text(html, encoding="utf-8")

    # Copia los assets estáticos (p. ej. vendor/chart.umd.min.js) requeridos por el HTML.
    vendor_origen = PLANTILLAS / "vendor"
    if vendor_origen.exists():
        vendor_destino = salida / "vendor"
        shutil.copytree(vendor_origen, vendor_destino, dirs_exist_ok=True)

    # Generar resumen markdown para Azure DevOps (##vso[task.uploadsummary])
    _generar_summary_md(salida=salida, summary=summary, tests=tests, run_id=run_id)

    return index


def _generar_summary_md(
    salida: Path,
    summary: dict[str, Any],
    tests: list[dict[str, Any]],
    run_id: str,
) -> Path:
    """Genera summary.md para mostrar en el Summary del build de Azure DevOps.

    Este archivo se publica con ##vso[task.uploadsummary] y se renderiza
    directamente en la pestaña Extensions del pipeline sin extensiones.
    """
    status = summary.get("status", {})
    total = summary.get("total", 0)
    passed = status.get("passed", 0)
    failed = status.get("failed", 0)
    broken = status.get("broken", 0)
    skipped = status.get("skipped", 0)
    success_rate = summary.get("successRate", 0)
    duration_human = summary.get("durationHuman", "—")

    # Estado general con emoji Unicode
    if failed + broken == 0 and total > 0:
        estado_general = "PASSED"
        icono = "\u2705"  # ✅
    elif failed + broken > 0:
        estado_general = "FAILED"
        icono = "\u274C"  # ❌
    else:
        estado_general = "NO TESTS"
        icono = "\u26A0\uFE0F"  # ⚠️

    lines = [
        f"## {icono} ArgusPy \u2014 Resultados de ejecuci\u00f3n",
        "",
        f"**Run ID:** `{run_id}` | **Duraci\u00f3n:** {duration_human} | **Estado:** {estado_general}",
        "",
        "### Resumen",
        "",
        "| M\u00e9trica | Valor |",
        "|---------|-------|",
        f"| Total de pruebas | **{total}** |",
        f"| \u2705 Exitosas | **{passed}** |",
        f"| \u274C Fallidas | **{failed}** |",
        f"| \u26A0\uFE0F Interrumpidas | **{broken}** |",
        f"| \u23ED\uFE0F Omitidas | **{skipped}** |",
        f"| Porcentaje de \u00e9xito | **{success_rate}%** |",
        "",
    ]

    # Tests fallidos/interrumpidos (detalle)
    fallidos = [t for t in tests if t.get("estado") in ("failed", "broken")]
    if fallidos:
        lines.append("### \u274C Tests con fallos")
        lines.append("")
        lines.append("| Test | Estado | Error |")
        lines.append("|------|--------|-------|")
        for t in fallidos[:20]:
            nombre = t.get("nombre", "\u2014")
            estado = t.get("estado", "unknown")
            error = (t.get("mensaje_error") or "Sin mensaje de error").replace("\n", " ").replace("|", "/")
            if len(error) > 120:
                error = error[:120] + "..."
            lines.append(f"| {nombre} | {estado} | {error} |")
        lines.append("")
        if len(fallidos) > 20:
            lines.append(f"*... y {len(fallidos) - 20} tests fallidos m\u00e1s.*")
            lines.append("")

    # Tests exitosos (lista compacta)
    exitosos = [t for t in tests if t.get("estado") == "passed"]
    if exitosos:
        lines.append("### \u2705 Tests exitosos")
        lines.append("")
        for t in exitosos[:30]:
            nombre = t.get("nombre", "\u2014")
            dur = t.get("duracion", 0)
            lines.append(f"- \u2705 {nombre} ({duracion(dur)})")
        lines.append("")
        if len(exitosos) > 30:
            lines.append(f"*... y {len(exitosos) - 30} tests exitosos m\u00e1s.*")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("\U0001F4E6 **Reporte completo:** descarga el artefacto **html-report** desde la pesta\u00f1a *Summary* de este build para ver gr\u00e1ficos, tendencias y evidencias.")

    md_path = salida / "summary.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el reporte HTML propio de ArgusPy.")
    parser.add_argument("--results", default="allure-results", help="Directorio de resultados Allure.")
    parser.add_argument("--output", default="reporte-html", help="Directorio de salida del reporte.")
    args = parser.parse_args()
    print(f"Reporte generado: {generar_reporte(args.results, args.output)}")


if __name__ == "__main__":
    main()
