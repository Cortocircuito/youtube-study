# AGENTS.md

## Proyecto

`youtube-study` es una aplicación Python para estudiar videos de YouTube a partir de sus transcripciones.

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

Crear entorno:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

Validar sintaxis y tests:

```bash
python3 -m py_compile app.py src/youtube_study/*.py
python -m pytest
```

## Estructura

```txt
app.py                         # CLI principal
src/youtube_study/downloader.py # descarga subtítulos con yt-dlp
src/youtube_study/transcript.py # limpieza y transformación de VTT
src/youtube_study/analyzer.py   # análisis heurístico
src/youtube_study/exporter.py   # generación de archivos Markdown/JSON
PLAN.md                         # roadmap del proyecto
```

## Reglas de desarrollo

- Mantener la app usable sin Ollama por ahora.
- No depender del `yt-dlp` de `apt`; usar `requirements.txt` en un venv.
- Los archivos generados en `data/videos/` no deben versionarse.
- No leer archivos completos de `data/videos/`, `.vtt`, `transcript.txt` o transcripciones largas salvo petición explícita del usuario.
- Para revisar transcripciones largas, usar búsquedas, fragmentos pequeños o comandos con límites.
- Al ejecutar planes con `openplan`, avanzar por fases cortas y pausar después de máximo 5 pasos.
- Preferir módulos pequeños dentro de `src/youtube_study/`.
- Cada mejora debe mantener funcionando el comando `python app.py "URL"`.
- Después de cambios en código Python, ejecutar `python3 -m py_compile app.py src/youtube_study/*.py`.

## Prioridades actuales

1. Mejorar limpieza de subtítulos automáticos ruidosos.
2. Crear biblioteca local `data/library.json`.
3. Añadir comandos `list`, `show`, `search` y `analyze`.
4. Mejorar detección de herramientas y conceptos.
5. Añadir exportación Markdown consolidada y Anki CSV.

## Futuro

Ollama queda reservado para una fase posterior. Está documentado en `PLAN.md`.
