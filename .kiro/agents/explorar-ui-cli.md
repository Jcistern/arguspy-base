---
name: explorar-ui-cli
description: Explora una pantalla de la aplicación desde la terminal y documenta locators accesibles para Playwright Python.
tools: ["read", "shell"]
resources: ["file://.kiro/steering/**/*.md"]
---

# Explorar UI para Playwright Python (sin MCP)

Explora la pantalla indicada y extrae locators semánticos y accesibles, listos
para un Page Object Python. Usar cuando el MCP `argus-playwright` no esté disponible.

> El proyecto usa Playwright Python (`playwright.async_api`). No generes código
> `.ts`, `@playwright/test` ni comandos `npm`/`npx`.

## Entrada

Antes de comenzar, pregunta al usuario:
- Ruta a explorar, relativa a `APP_BASE_URL` (ej: `/dashboard`).
- Si la pantalla requiere sesión y con qué perfil (por defecto `admin`).

## Proceso

1. Verifica que exista `config/environments/<AMBIENTE>.env`, sin imprimir su contenido.
2. Obtén el árbol accesible reutilizando las herramientas del servidor MCP como
   funciones Python (no requiere `fastmcp`). Ajusta `RUTA` y `PERFIL`:

   ```bash
   .venv/bin/python - <<'EOF'
   import asyncio, importlib.util, os
   os.environ.setdefault("MCP_HEADLESS", "true")
   spec = importlib.util.spec_from_file_location("srv", ".kiro/mcp/playwright_server.py")
   srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv)

   RUTA, PERFIL = "/dashboard", "admin"   # PERFIL = None si no requiere sesión

   async def main():
       if PERFIL:
           print(await srv.iniciar_sesion(PERFIL))
       print(await srv.abrir(RUTA))
       print(await srv.snapshot())
       print(await srv.cerrar())

   asyncio.run(main())
   EOF
   ```

   En Windows, usar `.venv\Scripts\python`.
3. Si hay elementos condicionales (modal, menú, dropdown), agrega `await srv.clic(rol, nombre)`
   antes del `snapshot` y repite, acotando con `srv.snapshot("dialog", "<nombre>")`.
4. Documenta el locator Python de cada elemento relevante.

## Formato de salida

```python
import re

# Locators listos para el constructor del Page Object:
self._titulo = page.get_by_role(
    "heading", name=re.compile(r"Título real", re.IGNORECASE)
)
self._boton_guardar = page.get_by_role(
    "button", name=re.compile(r"^Guardar$", re.IGNORECASE)
)
self._campo_correo = page.get_by_label(
    re.compile(r"Correo electrónico", re.IGNORECASE)
)
self._dialogo = page.get_by_role(
    "dialog", name=re.compile(r"Nombre del diálogo", re.IGNORECASE)
)
```

## Reglas

- Prioriza `get_by_role`, `get_by_label`, `get_by_placeholder` y `get_by_test_id`.
- Documenta el rol, el nombre accesible y el contenedor accesible de cada control.
- Si hay elementos repetidos, propone un locator acotado a un `dialog`, `form`, `group` o `region`.
- No uses XPath, clases de estilo, IDs internos, texto genérico sin acotar ni índices arbitrarios.
- No imprimas ni hardcodees URLs, usuarios, contraseñas, tokens ni datos personales.
