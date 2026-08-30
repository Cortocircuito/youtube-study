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

Validar sintaxis:

```bash
python3 -m py_compile app.py src/youtube_study/*.py
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
