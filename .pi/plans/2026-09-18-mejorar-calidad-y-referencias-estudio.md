---
title: "Mejorar calidad y referencias del material de estudio"
status: draft
created: "2026-09-18T22:35:24.068Z"
updated: "2026-09-18T23:09:54.334Z"
type: feature
---

## Objetivo

Mejorar resúmenes, preguntas y flashcards sin IA, con respuestas útiles y referencias verificables al instante del video. Mantener funcionamiento offline, compatibilidad de `python app.py "URL"` y cero dependencias nuevas de runtime.

## Alcance

- Resúmenes extractivos menos repetitivos y fragmentados.
- Preguntas y flashcards con respuesta real, timestamp y, cuando exista URL, enlace al video.
- Evaluación reproducible mediante fixtures pequeños y métricas simples.
- Actualización consistente de Markdown, JSON y Anki.

Fuera de alcance: Ollama/LLMs, Whisper, PDF, GUI, búsqueda semántica y lectura completa de transcripciones reales.

## Diseño

- Tipos estructurados `StudyQuestion` y `Flashcard` con pregunta, respuesta, timestamp, extracto y tags/categoría.
- Timestamps dentro del análisis; URLs temporales construidas únicamente en exportación.
- Ranking general por keywords, longitud, densidad informativa, posición y similitud, sin prioridades temáticas fijas.
- Respuestas derivadas de fragmentos de transcript; nunca inventadas.
- Fallback legible a timestamp cuando no haya URL.

## Fase 1 — Contrato de calidad y fixtures

**Estado: [DONE:5]**

1. [DONE:1] Fixtures VTT de horticultura y bases de datos con captions solapados, repeticiones y timestamps conocidos.
2. [DONE:2] Expectativas semánticas por dominio para términos, timestamps y solapamientos.
3. [DONE:3] Helpers de tokens normalizados, similitud y proporción de respuestas referenciadas.
4. [DONE:4] Baseline protegido; déficits de deduplicación y referencias registrados inicialmente como `xfail(strict=True)`.
5. [DONE:5] Criterios basados en presencia temática, similitud y proporciones, sin red ni `data/`.

Resultado inicial: `7 passed, 2 xfailed`; Ruff y compilación correctos.

⏸️ PAUSA superada — Fixtures y expectativas revisados.

## Fase 2 — Resumen extractivo y deduplicación

**Estado: [DONE:5]**

1. [DONE:1] `TextWindow` y `cue_windows()` preservan orden y timestamp y descartan cues casi duplicados.
2. [DONE:2] `important_ideas()` usa frecuencia, densidad, longitud y posición; se eliminaron prioridades de dominio.
3. [DONE:3] `content_tokens()`, `token_similarity()` y `deduplicate_texts()` aplican deduplicación conservadora.
4. [DONE:4] `representative_sentences()` selecciona frases informativas por bloque.
5. [DONE:5] Las ideas mantienen orden cronológico y límites; tests cubren temas, ventanas y duplicados.

Resultado: `36 passed, 1 xfailed`; Ruff, formato y compilación correctos.

⏸️ PAUSA superada — Salidas de ambos fixtures revisadas en fragmentos limitados.

## Fase 3 — Preguntas, respuestas y referencias estructuradas

**Estado: [DONE:5]**

1. [DONE:1] Se añadieron las dataclasses inmutables `StudyQuestion` y `Flashcard`; `ANALYSIS_FORMAT_VERSION` subió a 2.
2. [DONE:2] Las preguntas se generan desde herramientas, conceptos e ideas, y cada una conserva respuesta extractiva, timestamp, extracto fuente y categoría.
3. [DONE:3] Se eliminaron respuestas placeholder: todas las tarjetas proceden de preguntas respondibles con contenido real del transcript.
4. [DONE:4] Las preguntas se deduplican por clave normalizada y se distribuyen entre básicas, comprensión y prácticas; estas últimas eligen recomendaciones concretas.
5. [DONE:5] Las tarjetas mantienen tags de herramienta/categoría/procedencia cuando corresponde y añaden `type::<categoría>`; Anki conserva compatibilidad con dicts existentes.

Verificación ejecutada:

```bash
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest -q
```

Resultado: `38 passed`; ya no quedan pruebas `xfail`. Se revisaron preguntas y referencias de ambos fixtures sin acceder a transcripciones reales.

Criterio de aceptación cumplido: 100% de preguntas y tarjetas de fixtures tienen respuesta no-placeholder y timestamp válido, sin preguntas normalizadas duplicadas.

⏸️ PAUSA — Revisar utilidad pedagógica y trazabilidad de una muestra pequeña.

## Fase 4 — Enlaces temporales y exportadores

**Estado: [DONE:5]**

1. [DONE:1] Se añadieron `timestamp_url()`, `markdown_reference()` y `anki_answer_with_reference()`; conservan query/fragmento, reemplazan `t` previo y rechazan URLs inválidas.
2. [DONE:2] `service.py` pasa `webpage_url` como contexto a los exportadores, sin acoplar el analizador con YouTube.
3. [DONE:3] `summary.md`, `questions.md`, `flashcards.md` y `study.md` muestran timestamps enlazados; sin URL conservan `[HH:MM:SS]` legible.
4. [DONE:4] Anki conserva `Front`, `Back`, `Tags` y UTF-8 BOM; el reverso añade una referencia HTML clicable o un timestamp sin enlace.
5. [DONE:5] No se añadieron salidas JSON nuevas ni se modificaron `tools.json`/`concepts.json`; los tests cubren YouTube, `youtu.be`, query previa, reemplazo de tiempo y fallback.

Verificación ejecutada:

```bash
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest -q
```

Resultado: `40 passed`. Se revisó Markdown y Anki generados desde el fixture pequeño de horticultura; los enlaces apuntan a los segundos esperados.

Criterio de aceptación cumplido: enlaces correctos con URL, fallback temporal sin URL y CSV compatible con sus tres columnas.

⏸️ PAUSA — Revisar Markdown y una importación manual opcional de Anki.

## Fase 5 — Integración, migración y cierre

**Estado: [DONE:4] — cierre remoto pendiente**

1. [DONE:1] `generate_study_files()` y `export_study()` generan Markdown y Anki desde el mismo `AnalysisResult` v2 y comparten contexto de fuente.
2. [DONE:2] Se añadió una prueba que migra artefactos v1 con `analyze_existing()` usando subtítulos locales: actualiza metadata a v2, elimina placeholders y conserva enlaces, sin red.
3. [DONE:3] `README.md`, `AGENTS.md` y `PLAN.md` reflejan análisis v2, referencias temporales, regeneración local y prioridades actuales.
4. [DONE:4] Pasaron smoke tests de `--help`, `list`, `rebuild-library`, atajo URL simulado y migración v1→v2, además de la validación completa equivalente a CI.
5. [PENDING] El diff está revisado y el contrato `python app.py "URL"` está cubierto; falta commit, push y confirmar CI verde antes de cerrar el plan.

Verificación ejecutada:

```bash
.venv/bin/python app.py --help
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m py_compile app.py src/youtube_study/*.py
.venv/bin/python -m pytest -q
```

Resultado local: `41 passed`; Ruff, formato, compilación y `git diff --check` correctos.

Criterio local cumplido: migración v2, documentación, CLI y suite están validados sin red. El criterio final requiere CI remoto verde.

⏸️ PAUSA FINAL — Autorizar commit/push y confirmar CI antes de marcar `[DONE:5]` y cerrar.

## Riesgos y mitigaciones

- Resúmenes fragmentados: ventanas y mínimos de longitud probados con fixtures.
- Deduplicación excesiva: umbral conservador y frases similares pero distintas en tests.
- Enlaces incorrectos: `urllib.parse` y casos de URLs variadas.
- Cambio de tipos: migración por fase, tests de contrato y versión 2.
- Sobreajuste: fixtures de dominios distintos y ausencia de prioridades temáticas.

## Definición de terminado

- Sin ideas cercanas duplicadas en fixtures.
- Preguntas y tarjetas con respuesta extractiva y timestamp.
- Enlaces correctos o fallback temporal.
- Markdown, JSON aplicable y Anki representan el mismo análisis v2.
- Ruff, compilación, tests y CI pasan sin red, datos reales ni servicios externos.