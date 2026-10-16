---
name: refactor-comentarios
description: Refactoriza comentarios y docstrings para que sean precisos y cortos, eliminando el estilo verboso generado por IA, SIN modificar nada de codigo. Condensa docstrings multi-parrafo a una linea y acorta comentarios de bloque conservando solo la informacion tecnica util. Verifica por AST que solo cambiaron comentarios. Usar cuando el usuario pida arreglar comentarios, hacerlos mas precisos o cortos, quitar comentarios largos o que se noten hechos con IA.
---

# Refactor de comentarios y docstrings

Hacer los comentarios y docstrings precisos y concisos, eliminando verbosidad
tipo "generado por IA", SIN tocar código.

## Regla absoluta

Solo se modifican **comentarios (`# ...`) y docstrings (`"""..."""`)**. NO se
cambia nada más: ni nombres, ni lógica, ni imports, ni strings de código, ni
locators, ni firmas de funciones, ni se añaden o quitan líneas de código.

En proyectos pytest-bdd, los textos DENTRO de los decoradores
`@given("...")`, `@when("...")`, `@then("...")`, `@scenario(...)` son CÓDIGO
(definen el binding del step). NO se tocan bajo ninguna circunstancia.

## Criterios de refactor

1. **Docstrings multi-línea o multi-párrafo** -> reducir a UNA línea concisa que
   diga qué hace la función/método. Eliminar párrafos que explican contexto de
   negocio obvio, listas de pasos redundantes o justificaciones largas.

   Ejemplo:
   - ANTES: docstring de 6 líneas describiendo qué hace un fixture, listando
     cada efecto y notas de negocio.
   - DESPUES: `"""Inicia sesión con el perfil indicado por el tag del escenario."""`

2. **Comentarios de bloque `#` verbosos** (varias líneas) -> condensar a 1 línea
   con solo la información técnica útil.

   Ejemplo:
   - ANTES: 4-5 líneas explicando por qué un `<select>` no tiene label accesible
     y por qué se evita depender de clases de Angular.
   - DESPUES: `# El <select> no tiene label ni aria-label; se usa su rol implícito "combobox".`

3. **Conservar** comentarios con valor técnico real (motivos de un workaround,
   por qué un timeout extendido por SSO, notas de accesibilidad concretas), pero
   acortados.

4. **Eliminar** comentarios redundantes que solo repiten lo que el código ya dice
   de forma evidente.

5. **Mantener** los docstrings de módulo (primera línea del archivo) si ya son
   concisos, y los que ya son de una línea.

6. Sin emojis. Mantener el idioma original y la ortografía correcta (con tildes).

## Ejecución

- Para muchos archivos, procesarlos con el mismo criterio de forma consistente
  (puede delegarse a un sub-agente de ejecución dándole estos criterios y un
  archivo ya refactorizado como referencia de estilo).
- Empezar por un archivo representativo para fijar el estilo y luego replicarlo.

## Verificación obligatoria (que NO se tocó código)

Después de refactorizar, confirmar SIEMPRE:

1. **Compila:** `python -m py_compile <archivos editados>` (detecta comillas de
   docstrings rotas).
2. **Solo cambiaron comentarios/docstrings (prueba por AST):** comparar la
   estructura de código (AST sin docstrings) entre la versión en git (HEAD) y la
   versión actual de cada archivo. Si el AST de código es idéntico, se confirma
   que únicamente cambiaron comentarios/docstrings.

   Enfoque del verificador (script temporal, borrar al terminar): parsear ambas
   versiones con `ast.parse`, eliminar los docstrings de módulo/clase/función del
   árbol, y comparar `ast.dump(tree)`. Igualdad = solo comentarios cambiaron.

3. Si algún archivo muestra diferencia de código en el AST, revertir ese cambio:
   se rompió la regla de "solo comentarios".

## Anti-patrones

- No tocar los textos de `@given/@when/@then/@scenario`.
- No borrar `from __future__ import annotations` ni ningún import.
- No cambiar nombres, lógica ni firmas al "aprovechar" el paso.
- No usar emojis ni cambiar el idioma.
- No dar por terminado sin la verificación por AST: "parece que solo toqué
  comentarios" no basta, hay que probarlo.
