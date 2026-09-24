# AGENTS.md

## Proyecto

`youtube-study` es una aplicación Python para estudiar videos de YouTube a partir de sus transcripciones. El análisis actual es v2 y genera material extractivo con referencias temporales verificables.

## Objetivo

Permitir descargar subtítulos, limpiar la transcripción y generar material de estudio:

- `transcript.txt`
- `summary.md`
- `tools.md`
- `concepts.md`
- `questions.md`
- `flashcards.md`
- `study-guide.md`
- `transcript.clean.txt`
- `transcript.paragraphs.md`
- `study.md`
- `anki.csv`

## Comandos principales

Crear entorno de runtime y desarrollo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Analizar video:

```bash
python app.py study "URL" --lang "es-419,es" --out data/videos
```

Atajo equivalente:

```bash
python app.py "URL"
```

Comandos de biblioteca y búsqueda:

```bash
python app.py list
python app.py show VIDEO_ID
python app.py search "consulta" --video VIDEO_ID --limit 5 --context 1
python app.py analyze VIDEO_ID
python app.py export VIDEO_ID --format markdown|anki|all
```

Validación local equivalente a CI:

```bash
./scripts/check.sh
```

## Estructura

```txt
app.py                          # entry point mínimo
src/youtube_study/cli.py         # argumentos, comandos y salida
src/youtube_study/service.py     # pipeline study, analyze y export
src/youtube_study/downloader.py  # descarga subtítulos con yt-dlp
src/youtube_study/transcript.py  # limpieza y transformación de VTT
src/youtube_study/analyzer.py    # análisis heurístico
src/youtube_study/study_models.py # modelos de evidencia y resultados
src/youtube_study/artifacts.py    # staging y publicación atómica por archivo
src/youtube_study/tool_catalog.* # catálogo versionado de herramientas
src/youtube_study/library.py     # biblioteca local
src/youtube_study/search.py      # búsqueda en transcripciones
src/youtube_study/exporter.py    # artefactos Markdown, JSON y Anki
.github/workflows/ci.yml         # validación automática en GitHub
PLAN.md                          # roadmap futuro del proyecto
```

## Reglas de desarrollo

- Mantener la app usable sin Ollama por ahora.
- No depender del `yt-dlp` de `apt`; usar `requirements.txt` en un venv.
- Los archivos generados en `data/videos/` no deben versionarse.
- Las lecturas de `library.json` no deben repararlo ni reescribirlo; usar `rebuild-library` para recuperación explícita.
- Una publicación interrumpida se completa repitiendo `study`, `analyze` o `export`; no añadir journals o rollback sin un requisito nuevo.
- No leer archivos completos de `data/videos/`, `.vtt`, `transcript.txt` o transcripciones largas salvo petición explícita del usuario.
- Para revisar transcripciones largas, usar búsquedas, fragmentos pequeños o comandos con límites.
- Al ejecutar planes con `openplan`, avanzar por fases cortas y pausar después de máximo 5 pasos.
- Preferir módulos pequeños dentro de `src/youtube_study/`.
- Cada mejora debe mantener funcionando el comando `python app.py "URL"`.
- Preguntas y flashcards deben conservar respuesta extractiva, timestamp y extracto fuente; no reintroducir respuestas placeholder.
- Los exportadores deben degradar a timestamp legible cuando `webpage_url` no exista.
- Los cambios incompatibles en artefactos deben incrementar `ANALYSIS_FORMAT_VERSION` y permitir regeneración local mediante `analyze`.
- Después de cambios en código Python, ejecutar `./scripts/check.sh`.
- La CI no debe descargar videos, leer datos reales de `data/`, ni usar Ollama, API keys o red; usar fixtures pequeños en `tests/`.

## Prioridades actuales

1. Mejorar la limpieza de subtítulos automáticos ruidosos con fixtures variados.
2. Refinar la utilidad pedagógica de preguntas y conceptos sin introducir sesgos de dominio.
3. Ampliar cobertura de tests de los módulos críticos manteniendo el umbral global actual.
4. Mantener compatibilidad de regeneración entre versiones de análisis.
5. Evaluar exportación PDF y búsqueda semántica solo después de estabilizar el flujo local.

## Futuro

Ollama queda reservado para una fase posterior. Está documentado en `PLAN.md`.
