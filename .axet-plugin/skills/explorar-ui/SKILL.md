---
name: explorar-ui
description: Explora una pantalla de la aplicación con su árbol accesible y entrega locators de Playwright Python listos para un Page Object. Usar cuando haya que descubrir o validar locators de una pantalla.
---

# Explorar UI para Playwright Python

Explora la pantalla indicada y devuelve locators semánticos y accesibles para un
Page Object con `playwright.async_api`. No generes TypeScript, `@playwright/test`
ni comandos `npm`/`npx`.

## Entrada

Si el usuario no lo indicó, pregunta:
- Ruta a explorar, relativa a `APP_BASE_URL` (ej: `/dashboard`).
- Si requiere sesión y con qué perfil (por defecto `admin`).

## 1. Revisar lo que ya existe

Lee `pages/` y busca un Page Object de la pantalla o del flujo (por ejemplo,
`pages/login_page.py` para el login). Reutiliza sus locators en vez de proponer
otros nuevos.

## 2. Obtener el árbol accesible

**Opción A, MCP `argus-playwright`** (si tu asistente lo tiene configurado):
`iniciar_sesion(perfil)` si corresponde, `abrir(ruta)` y `snapshot()`. Abre modales
o menús con `clic(rol, nombre)` y repite `snapshot(rol_contenedor, nombre_contenedor)`.
Termina con `cerrar()`.

**Opción B, terminal** (aXet y cualquier asistente sin el MCP). No uses el
navegador integrado del asistente.

```bash
# macOS / Linux
.venv/bin/python .kiro/mcp/explorar.py /dashboard --perfil admin
# Windows
.venv\Scripts\python .kiro\mcp\explorar.py /dashboard --perfil admin
```

- `--sin-sesion` si la pantalla no requiere login (ej: `/login`).
- `--clic "rol:nombre"` (repetible, en orden) para abrir modales, menús o pestañas.
- `--contenedor "rol:nombre"` para acotar el árbol (ej: `dialog:Nuevo usuario`).
- `--captura <nombre>` guarda un screenshot en `test-results/mcp/`; `--headed` muestra el navegador.

No leas `config/environments/*.env`: el script toma las credenciales sin mostrarlas.

## 3. Construir los locators

Por cada elemento relevante identifica rol, nombre accesible y contenedor.
Aplica las reglas de "Locators" de `AGENTS.md`:

- Prioridad: `get_by_role` > `get_by_label` > `get_by_placeholder` > `get_by_test_id` > CSS documentado.
- Siempre `re.compile(..., re.IGNORECASE)`; anclar con `^...$` para coincidencia exacta.
- Si el nombre empieza con un ícono (ej: `" Login"`), no anclar el inicio: `r"Login\s*$"`.
- Controles repetidos: acotar con un `dialog`, `form`, `group` o `region`.
- Entrega **un solo locator por elemento**, no alternativas. Si hay ambigüedad,
  vuelve a explorar con `--contenedor` hasta resolverla.
- Nada de XPath, clases de estilo, IDs internos ni índices (`.first`, `.nth`).

## Salida

```python
import re

# Locators listos para el constructor del Page Object:
self._titulo = page.get_by_role(
    "heading", name=re.compile(r"Texto real", re.IGNORECASE)
)
self._campo_correo = page.get_by_label(
    re.compile(r"Correo electrónico", re.IGNORECASE)
)
self._dialogo_confirmacion = page.get_by_role(
    "dialog", name=re.compile(r"Confirmar", re.IGNORECASE)
)
self._boton_confirmar = self._dialogo_confirmacion.get_by_role(
    "button", name=re.compile(r"^Confirmar$", re.IGNORECASE)
)
```

Indica además qué elemento estable sirve para confirmar que la página cargó.
No incluyas credenciales, tokens ni datos personales vistos durante la exploración.
