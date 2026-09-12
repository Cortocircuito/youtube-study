---
title: "Endurecer y refactorizar YouTube Study"
status: in_progress
created: "2026-09-04T15:46:11.517Z"
updated: "2026-09-12T01:08:11.783Z"
type: refactor
---

# Endurecer y refactorizar YouTube Study

## Objetivo

Convertir MVP funcional en aplicación local confiable, mantenible y verificable, sin añadir Ollama ni ampliar alcance innecesariamente.

## Diagnóstico confirmado

- `data/library.json` puede lanzar `JSONDecodeError` si queda vacío a medias, corrupto o editado incorrectamente.
- `save_library()` escribe directamente al archivo final; una interrupción puede dañarlo.
- Biblioteca guarda rutas relativas dependientes del directorio desde el que se ejecuta la app.
- `search --limit` y `--context` aceptan negativos; `limit <= 0` produce comportamiento incorrecto.
- `show VIDEO_ID` inexistente imprime mensaje pero devuelve código de éxito.
- `analyze` y `export` no manejan JSON inválido en `info.json`.
- `choose_vtt()` llama “manual” a archivos que no puede distinguir como manuales solo por nombre; prioridad documentada no está garantizada.
- `study.md` consolida archivos existentes y puede exportar datos antiguos si no se reanalizó primero.
- `app.py` mezcla parsing CLI, presentación y pipeline de negocio.
- Cobertura actual (5 tests) no cubre CLI, downloader, exportadores ni fallos de datos.
- `README.md` conserva próximos pasos ya implementados y omite `tools.json`/`concepts.json` en árbol.
- `.pi/skills/video-study-summary/` está sin trackear; falta decidir si es parte compartida del proyecto o configuración local.

## Criterios de prioridad

1. Evitar pérdida de datos y resultados incorrectos.
2. Hacer fallos observables con códigos de salida útiles.
3. Proteger comportamiento mediante tests.
4. Reducir acoplamiento antes de nuevas funciones.
5. Mejorar calidad heurística y experiencia de desarrollo.

## Reglas de ejecución

- Máximo 5 pasos por fase.
- Mantener `python app.py "URL"` compatible.
- No leer transcripciones completas; usar fixtures y fragmentos limitados.
- Ejecutar al final de cada fase:

```bash
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

- Marcar cada fase con `[DONE:n]` y parar en cada `⏸️ PAUSE`.

## Fase 1 — Integridad de biblioteca y datos locales (prioridad crítica)

1. Hacer `load_library()` tolerante a JSON vacío, corrupto y estructura inválida, con error de dominio claro y respaldo del archivo dañado.
2. Implementar escritura atómica: temporal en mismo directorio, `flush`/`fsync` cuando corresponda y `replace` final.
3. Guardar rutas portables relativas al directorio de datos y resolverlas de forma centralizada; aceptar entradas antiguas.
4. Añadir comando `rebuild-library` que reconstruya `data/library.json` desde `data/videos/*/info.json` sin leer transcripciones completas salvo para recuperar herramientas cuando sea necesario.
5. Manejar `info.json` ausente o inválido por video sin abortar toda reconstrucción; mostrar resumen de recuperados/omitidos.

Verificación:

```bash
.venv/bin/python app.py rebuild-library
.venv/bin/python app.py list
.venv/bin/python -m pytest tests/test_library.py
```

Criterio de aceptación: interrupción o JSON corrupto no destruye biblioteca recuperable; app ofrece mensaje accionable.

⏸️ PAUSE — Revisar respaldo, formato final y portabilidad de rutas.

## Fase 2 — Contrato CLI y manejo uniforme de errores (prioridad alta) [DONE:5]

1. Crear excepciones de aplicación (`LibraryError`, `VideoDataError`, `SubtitleError`) sin mostrar tracebacks al usuario en errores esperables.
2. Validar con `argparse` que `--limit >= 1` y `--context >= 0`.
3. Hacer que `show`, `search --video`, `analyze` y `export` devuelvan código distinto de cero cuando video/datos no existen.
4. Centralizar impresión de errores y códigos de salida en `main()`.
5. Probar comandos exitosos y fallidos mediante `subprocess`, incluyendo el atajo `python app.py URL` sin efectuar red mediante mocks.

Verificación ejecutada:

```bash
.venv/bin/python app.py search test --limit 0
.venv/bin/python app.py show VIDEO_INEXISTENTE
.venv/bin/python -m pytest tests/test_cli.py
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

Criterio de aceptación: entradas inválidas fallan de forma predecible, sin traceback y con exit code no cero.

⏸️ PAUSE — Validar mensajes y códigos de salida.

## Fase 3 — Selección y descarga fiable de subtítulos (prioridad alta) [DONE:5]

1. Separar inventario de subtítulos manuales y automáticos usando metadata de `yt-dlp` (`subtitles` y `automatic_captions`), sin inferir origen únicamente por nombre.
2. Definir política explícita y comprobable: manual en idioma solicitado, automático original solicitado, traducción solicitada, inglés, fallback controlado.
3. Corregir `choose_vtt()` para consumir candidatos con metadata o una estructura de selección persistida; mantener compatibilidad al reanalizar descargas antiguas.
4. Añadir tests sin red para orden de idiomas, ausencia de subtítulos, `--force-download`, `--quiet` y traducciones.
5. Documentar qué subtítulo se eligió y por qué en `info.json` (`source_subtitle`, idioma y tipo).

Verificación ejecutada:

```bash
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest tests/test_downloader.py
.venv/bin/python app.py analyze Yj51wXMwFwE
.venv/bin/python -m pytest
```

Criterio de aceptación: selección coincide con política en fixtures; documentación deja de prometer distinción no garantizada.

⏸️ PAUSE — Revisar política con ejemplos español manual/automático/inglés.

## Fase 4 — Consistencia de análisis y exportaciones (prioridad alta)

1. Crear estructura `AnalysisResult` con cues, keywords, tools, concepts, questions y cards para calcular una sola vez.
2. Hacer que `analyze` escriba todos los artefactos desde mismo resultado y registre versión/formato del análisis.
3. Hacer que `export` valide frescura de artefactos o reanalice explícitamente; evitar consolidar archivos antiguos silenciosamente.
4. Generar `study.md` desde datos estructurados o resultado de análisis, no releyendo Markdown generado.
5. Añadir tests de `tools.json`, `concepts.json`, `study.md` y `anki.csv`, incluyendo UTF-8, quoting CSV y tags.

Verificación:

```bash
.venv/bin/python app.py analyze Yj51wXMwFwE
.venv/bin/python app.py export Yj51wXMwFwE --format all
.venv/bin/python -m pytest tests/test_exporter.py tests/test_pipeline.py
```

Criterio de aceptación: todos los archivos de una ejecución representan mismo análisis y exportar nunca usa contenido obsoleto sin avisar.

⏸️ PAUSE — Comparar metadata/versiones de artefactos.

## Fase 5 — Refactor arquitectónico sin cambio funcional (prioridad media)

1. Extraer pipeline de `app.py` a `src/youtube_study/service.py` o `pipeline.py`.
2. Extraer construcción/parsing CLI y presentación a `src/youtube_study/cli.py`; dejar `app.py` como entrypoint mínimo.
3. Introducir tipos para metadata de video y entradas de biblioteca (`TypedDict` o dataclasses), evitando `dict` sin forma en fronteras principales.
4. Reducir duplicación en opciones comunes `--out`/`--lang` y formateo de resultados.
5. Ejecutar suite completa y comparar salidas CLI principales antes/después.

Verificación:

```bash
.venv/bin/python app.py --help
.venv/bin/python app.py list
.venv/bin/python -m pytest
```

Criterio de aceptación: `app.py` solo inicia CLI; no cambia contrato público.

⏸️ PAUSE — Revisar límites entre CLI, servicio, dominio y persistencia.

## Fase 6 — Calidad heurística medible (prioridad media)

1. Crear fixtures pequeños etiquetados con herramientas/conceptos esperados y falsos positivos conocidos (`QR`, `SIM`, nombres comunes).
2. Separar “herramienta”, “protocolo”, “modelo”, “servicio” y “candidato desconocido” en categoría explícita.
3. Mover aliases y catálogo de herramientas a datos configurables versionados, conservando defaults.
4. Mejorar stopwords y ranking de conceptos con criterios medibles; excluir verbos/muletillas frecuentes.
5. Añadir métricas simples sobre fixtures (precisión de herramientas conocidas y lista máxima de falsos positivos) para impedir regresiones.

Verificación:

```bash
.venv/bin/python -m pytest tests/test_analyzer.py
```

Criterio de aceptación: fixtures no clasifican `QR`/`SIM` como herramientas y conceptos principales evitan muletillas conocidas.

⏸️ PAUSE — Revisar resultados heurísticos en fragmentos limitados de ambos videos locales.

## Fase 7 — Documentación, dependencias y calidad de desarrollo (prioridad media-baja)

## Fase 7 — Documentación, dependencias y calidad de desarrollo (prioridad media-baja)

1. Actualizar árbol y “Próximos pasos” de `README.md`; incluir `tools.json`, `concepts.json`, `rebuild-library` y comportamiento de errores.
2. Separar dependencias runtime y desarrollo (`requirements.txt` + `requirements-dev.txt`, o `pyproject.toml` con extras).
3. Añadir configuración mínima de `ruff` y aplicar formato/import sorting sin cambios funcionales.
4. Documentar versión mínima de Python y flujo reproducible de instalación/tests.
5. Resolver `.pi/skills/video-study-summary/`: versionarlo si es recurso compartido o añadirlo a `.gitignore` si es personal; nunca dejar estado ambiguo.

Verificación:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
git status --short
```

Criterio de aceptación: instalación runtime no incluye pytest; README describe estado real; working tree esperado y limpio.

⏸️ PAUSE — Revisar documentación desde perspectiva de usuario nuevo.

## Fase 8 — Automatización CI y cierre (prioridad baja)

1. Añadir workflow de GitHub Actions para Python soportado, compilación, Ruff y pytest sin usar datos reales ni red.
2. Añadir tests de instalación limpia y smoke test de `--help`.
3. Revisar cobertura e identificar módulos críticos sin tests; fijar umbral inicial razonable solo después de medirlo.
4. Ejecutar validación final local equivalente a CI.
5. Actualizar plan, roadmap y changelog/resumen de versión; marcar plan `done` solo con CI verde.

Verificación:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest
```

Criterio de aceptación: validación automatizada reproducible sin YouTube, API keys ni archivos de `data/`.

⏸️ PAUSE — Cierre final y revisión del roadmap.

## Exclusiones

- Ollama, LLMs o búsqueda semántica.
- Whisper y transcripción de audio.
- Interfaz web o GUI.
- PDF.
- Base de datos SQL antes de demostrar que JSON ya no escala.

## Riesgos y mitigaciones

- **Refactor rompe CLI:** tests de contrato antes de mover módulos.
- **Reconstrucción pisa datos útiles:** backup + escritura atómica + modo de previsualización si resulta necesario.
- **Metadata de yt-dlp cambia:** aislar adaptación en downloader y probar con fixtures.
- **Heurísticas sobreajustadas a dos videos:** usar fixtures variados y reglas conservadoras.
- **Plan demasiado amplio:** fases independientes, máximo 5 pasos y pausa obligatoria.

## Definición de terminado

- Datos locales sobreviven corrupción/interrupción recuperable.
- CLI devuelve códigos y mensajes coherentes.
- Selección de subtítulos cumple política probada.
- Exportaciones son consistentes y no silenciosamente obsoletas.
- `app.py` es entrypoint pequeño y arquitectura tiene límites claros.
- Heurísticas tienen fixtures y objetivos medibles.
- README, dependencias, lint, tests y CI reflejan estado real.