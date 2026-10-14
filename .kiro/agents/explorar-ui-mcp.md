---
name: explorar-ui-mcp
description: Explora una pantalla de la aplicación con el MCP argus-playwright y entrega locators accesibles para Playwright Python.
tools: ["read", "@argus-playwright"]
includeMcpJson: true
resources: ["file://.kiro/steering/**/*.md"]
---

# Explorar UI con MCP para Playwright Python

Explora la pantalla indicada con el MCP `argus-playwright` y devuelve locators
robustos para un Page Object desarrollado con `playwright.async_api`.

> El proyecto usa **Python**, `pytest` y `pytest-bdd`. No generes TypeScript,
> imports de `@playwright/test` ni sintaxis de Playwright Test.

## Entrada

Antes de comenzar, pregunta al usuario:
- Ruta a explorar, relativa a `APP_BASE_URL` (ej: `/dashboard`).
- Si la pantalla requiere sesión y con qué perfil (por defecto `admin`).

## Herramientas del MCP

| Herramienta | Uso |
|---|---|
| `iniciar_sesion(perfil)` | Login con el `LoginPage` del proyecto y las credenciales `APP_<PERFIL>_*` del `.env`. |
| `abrir(ruta)` | Navega a una ruta relativa a `APP_BASE_URL`. |
| `snapshot(rol_contenedor, nombre_contenedor)` | Árbol accesible (roles y nombres) de la página o de un contenedor. |
| `clic(rol, nombre)` | Clic por rol y nombre accesible (para abrir menús, modales o pestañas). |
| `completar(etiqueta, texto)` | Completa un campo por su etiqueta accesible. |
| `captura(nombre)` | Screenshot en `test-results/mcp/`. |
| `cerrar()` | Cierra el navegador al terminar. |

## Pasos

1. Si la pantalla requiere sesión, ejecuta `iniciar_sesion`.
2. Navega con `abrir(ruta)`.
3. Obtén el árbol accesible con `snapshot()`.
4. Identifica roles, nombres accesibles, etiquetas, placeholders, diálogos, formularios, tablas y regiones.
5. Si hay elementos condicionales (modal, menú o dropdown), ábrelos con `clic` y repite `snapshot`, acotando al contenedor (ej: `snapshot("dialog", "Confirmar")`).
6. Si `clic` o `completar` informan más de un elemento, identifica un contenedor accesible que permita acotar el locator.
7. Toma una `captura` como contexto y termina con `cerrar()`.

## Salida esperada

```python
import re

# Locators listos para pegar en __init__ del Page Object:
self._titulo = page.get_by_role(
    "heading", name=re.compile(r"Texto real", re.IGNORECASE)
)
self._boton_guardar = page.get_by_role(
    "button", name=re.compile(r"^Guardar$", re.IGNORECASE)
)
self._campo_correo = page.get_by_label(
    re.compile(r"Correo electrónico", re.IGNORECASE)
)
self._tabla = page.get_by_role("table")
```

Para controles repetidos, entrega también el locator acotado:

```python
self._dialogo_confirmacion = page.get_by_role(
    "dialog", name=re.compile(r"Confirmar", re.IGNORECASE)
)
self._boton_confirmar = self._dialogo_confirmacion.get_by_role(
    "button", name=re.compile(r"^Confirmar$", re.IGNORECASE)
)
```

## Reglas

- Prioriza `get_by_role`, `get_by_label`, `get_by_placeholder` y `get_by_test_id`.
- Usa `re.IGNORECASE` cuando el nombre no requiera coincidencia exacta.
- No uses XPath, clases de estilo, IDs internos ni índices arbitrarios.
- No propongas `wait_for_timeout`, `time.sleep` ni `force=True` como solución de sincronización.
- No reveles credenciales, tokens ni datos sensibles vistos durante la exploración.
