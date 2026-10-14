---
name: limpieza-codigo-muerto
description: Limpia de forma segura codigo y archivos sin uso en un proyecto de automatizacion de pruebas (Python + Playwright + pytest-bdd). Identifica y elimina archivos huerfanos, imports muertos, funciones/fixtures sin referencias, features/datos sin uso y mecanismos desactivados, verificando en cada paso que las pruebas se sigan recolectando, el reporte HTML se genere y la publicacion de resultados no se rompa. Usar cuando el usuario pida limpiar el proyecto, eliminar codigo o archivos sin usar, quitar basura o reducir codigo muerto.
---

# Limpieza segura de código muerto

Metodología para eliminar código y archivos sin uso SIN romper la ejecución de
las pruebas, el reporte HTML ni la publicación de resultados.

## Principio rector

Nunca borrar a ciegas. Cada eliminación debe estar respaldada por evidencia de
que el elemento NO se usa, y cada tanda de borrados debe verificarse. Es
preferible dejar algo dudoso que romper el proyecto. La correctitud está por
encima de la exhaustividad.

## Flujo de trabajo

### 1. Investigar antes de tocar (mapeo)

Mapear qué se usa realmente. Para un proyecto pytest-bdd:

- **Page Objects (`pages/`)**: ¿se importan/exponen como fixtures en `conftest.py`
  o se usan en algún step? Si un page no aparece en ningún lado, es candidato.
- **Features (`*.feature`)**: cada uno debe tener un `@scenario(...)` que lo
  referencie en algún archivo de steps. Buscar features huérfanos y steps que
  apunten a features inexistentes (típico tras renombres o reestructuraciones).
- **Steps**: buscar funciones `@scenario` que apunten a features que ya no existen.
- **utils/**: ¿qué funciones se importan/llaman? Las no referenciadas son candidatas.
- **tools/**: ¿qué scripts se invocan desde `azure-pipelines.yml`, README o código?
  Los que no se invocan pueden ser utilitarios manuales legítimos (no siempre basura).
- **data/ y config/**: ¿qué JSON se leen desde algún helper/loader? Los que no
  se leen son candidatos.
- **Mecanismos desactivados**: código detrás de flags apagados por defecto
  (ej. `if os.getenv("X_ENABLED") == "true":`) que ya no se usa.

Para proyectos grandes o desconocidos, delegar el mapeo a un sub-agente de
investigación (context-gatherer) pidiéndole rutas exactas y EVIDENCIA de uso.

### 2. Confirmar cada hallazgo con evidencia (no confiar en el mapeo a ciegas)

Antes de borrar algo, confirmar con búsqueda de referencias en TODO el proyecto:

```
grep del nombre de la función / archivo / constante en todo el repo
```

Interpretación:
- **0 referencias fuera de su propia definición** -> muerto, candidato seguro.
- **Solo se referencia entre funciones que también están muertas** -> muerto en cadena.
- **Se referencia desde código vivo** -> NO tocar.

Para imports sin usar, evitar falsos positivos conocidos:
- `from __future__ import annotations`: NUNCA es "sin uso"; no borrar.
- `given/when/then/scenario` de pytest_bdd: se usan en decoradores `@given(...)`;
  solo están muertos si el archivo no tiene ese decorador.
- Tipos como `Locator`: distinguir el TIPO (`x: Locator`) del método (`page.locator()`).
  Si solo se usa el método, el import del tipo está muerto.
- No existe un linter garantizado (pyflakes/ruff pueden no estar instalados).
  Si hace falta, escribir un detector temporal por AST y borrarlo al terminar.

### 3. Clasificar por riesgo

- **Bajo riesgo (borrar directo):** archivos huérfanos sin referencias, features
  vacíos, `.pyc` de fuentes que ya no existen, carpetas sin archivos fuente,
  JSON que no se leen, imports muertos confirmados.
- **Revisar/consultar:** utilidades genéricas reutilizables (generadores de datos,
  helpers de formato), scripts manuales documentados, datos "dormidos" por el
  alcance actual de las pruebas. Estos pueden reactivarse; confirmar con el
  usuario si se busca limpieza agresiva o conservadora.

### 4. Eliminar de forma ordenada

- Borrar archivos con la herramienta de borrado (git conserva el historial).
- Al quitar funciones/fixtures, quitar también sus usos y los imports que queden
  huérfanos, y los archivos de datos que solo ellas leían.
- Al eliminar un fixture usado como parámetro de un step, quitar ese parámetro
  del step para no dejar una referencia rota.
- Al eliminar scripts documentados, actualizar el README (y el árbol de estructura).
- Para carpetas que no deben volver al repo: borrar contenido, eliminar la carpeta
  y agregarla al `.gitignore`.

### 5. Verificación obligatoria (después de cada tanda)

Ejecutar SIEMPRE, y no dar por terminada la limpieza sin esto:

1. **Compila todo:**
   `python -m py_compile <todos los .py de pages, steps, utils, conftest, tools>`
2. **Se recolectan los tests (número intacto):**
   `pytest --collect-only -q`  -> confirmar el mismo total de tests que antes.
3. **Imports sin romper:** importar todos los módulos
   (`importlib.import_module` sobre pages/utils/reporting/tools).
4. **Fixtures resuelven:** `pytest --setup-plan <un archivo de steps>` sin errores
   (detecta fixtures faltantes, ej. uno eliminado que un step aún pedía).
5. **Reporte HTML se genera:** ejecutar el generador de reporte real
   (ej. `python -m reporting.generate_report --results allure-results --output reporte-html`).
6. **Publicación de resultados intacta:** confirmar que la lógica que vuelca los
   tags `@TC_<ID>` al JUnit (`record_property("test_case_id", ...)`) y el script
   de publicación NO fueron afectados.
7. **Sin referencias colgantes:** grep de los nombres eliminados -> 0 resultados.

Si algo falla, corregir antes de continuar. No subir con verificación en rojo.

### 6. Honestidad sobre lo no verificable

La ejecución real de las pruebas contra el sistema bajo prueba puede NO estar
disponible desde el entorno de desarrollo (requiere el agente/credenciales). Declararlo explícitamente: la limpieza no
tocó código de ejecución, locators ni lógica de negocio, solo elementos muertos
confirmados; la validación 100% final es correr la regresión en el agente.

### 7. Commit

Un commit descriptivo por tanda de limpieza, listando qué se eliminó y por qué,
e incluyendo la nota de verificación (compila, N tests recolectados, HTML OK,
publicación intacta). No hacer push sin confirmación del usuario, y nunca force push
sin permiso explícito.

## Anti-patrones (qué NO hacer)

- No borrar por nombre sospechoso sin confirmar referencias.
- No borrar `from __future__ import annotations`.
- No eliminar utilidades genéricas reutilizables sin confirmar con el usuario.
- No dar por buena la limpieza solo porque "compila": recolectar tests, generar
  el HTML y revisar fixtures es obligatorio.
- No dejar imports, parámetros de fixtures o menciones en README apuntando a algo
  ya eliminado.
- No tocar código de negocio, locators ni lógica de login: la limpieza es de
  código MUERTO, no refactor de comportamiento.
