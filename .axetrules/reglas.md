# Reglas de aXet para ArgusPy

Las convenciones del proyecto están en `AGENTS.md` (raíz del repositorio). Si no
aparece en tu contexto, léelo antes de escribir código. Prevalece sobre cualquier
suposición sobre el stack: es Playwright **Python** asíncrono con pytest-bdd.

## Procedimientos (skills)

Para estas tareas sigue el skill correspondiente, aunque el usuario no lo invoque:

| Tarea | Skill |
|---|---|
| Explorar una pantalla y proponer locators | `%explorar-ui` |
| Crear o mejorar un Page Object | `%crear-page-object` |
| Automatizar un caso de prueba de punta a punta | `%automatizar-caso` |
| Diagnosticar una prueba fallida | `%analizar-fallo` |
| Revisar cambios antes de commit o PR | `%revisar-cambios` |
| Pasar el plan de pruebas (.xlsx/.json) a .feature | `%importar-plan` |
| Agregar al plan (.xlsx) los escenarios que no están | `%actualizar-plan` |
| Limpiar código o archivos sin uso | `%limpieza-codigo-muerto` |
| Acortar comentarios y docstrings | `%refactor-comentarios` |

## Exploración de la UI

- **No uses `browser_action`** (navegador integrado) para descubrir locators: entrega
  capturas, no roles ni nombres accesibles, y obligaría a escribir credenciales en el chat.
- Usa `.kiro/mcp/explorar.py` con `execute_command` (detalle en `%explorar-ui`).

## Comandos

- Usa siempre el Python del `.venv`: `.venv/bin/python` en macOS/Linux y
  `.venv\Scripts\python` en Windows. Detecta el sistema operativo antes del primer comando.
- No ejecutes pruebas con `--persistir-cambios` salvo pedido explícito del usuario.
- No hagas `git commit` ni `git push` salvo pedido explícito del usuario.

## Seguridad

- Nunca leas, muestres ni edites `config/environments/*.env` (credenciales). Usa
  `*.env.example` para conocer los nombres de las variables.
- No copies al chat datos personales que aparezcan en la aplicación.

## Antes de terminar

Ejecuta `tools/validar_convenciones.py` con el Python del `.venv` y corrige los
errores que informe. Si el hook `PostToolUse` te informa infracciones, corrígelas
antes de seguir.
