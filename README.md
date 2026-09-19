# YouTube Study

Aplicación local para estudiar videos de YouTube a partir de sus subtítulos, sin requerir Ollama ni otros servicios de IA.

## Qué hace

- Descarga subtítulos con `yt-dlp` y elige de forma preferente español manual, español automático original, traducción solicitada, inglés y un fallback controlado.
- Limpia subtítulos VTT, elimina solapamientos cercanos y reconstruye unidades legibles conservando los rangos exactos del texto fuente.
- Excluye del material de estudio ruido inequívoco de producción y penaliza muletillas sin borrar contenido de la transcripción.
- Genera resúmenes extractivos deduplicados, conceptos, preguntas respondidas, flashcards, guía de estudio, un Markdown consolidado y CSV para Anki.
- Conserva la procedencia exacta de las respuestas por fragmento y añade referencias al instante del video en resúmenes, preguntas, tarjetas y Anki.
- Mantiene una biblioteca local y permite listar, consultar, buscar, reanalizar y exportar videos.
- Clasifica hallazgos como herramienta, protocolo, modelo, servicio o candidato heurístico.
- Genera todos los artefactos en staging y los reemplaza de forma atómica por archivo, sin modificar los subtítulos originales.

## Requisitos e instalación

Se requiere **Python 3.11 o superior**. No uses el `yt-dlp` de `apt`: puede estar desactualizado.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para ejecutar tests, lint y formato de desarrollo:

```bash
pip install -r requirements-dev.txt
python -m ruff check .
python -m coverage run -m pytest
python -m coverage combine
python -m coverage report
```

## Uso

Estudiar un video nuevo:

```bash
python app.py "https://www.youtube.com/watch?v=Yj51wXMwFwE"
python app.py study "URL" --lang "es-419,es" --out data/videos
```

Opciones de descarga:

```bash
python app.py study "URL" --quiet
python app.py study "URL" --force-download
```

Biblioteca local:

```bash
python app.py list
python app.py show VIDEO_ID
python app.py rebuild-library
```

Búsqueda, reanálisis y exportación:

```bash
python app.py search "consulta"
python app.py search "consulta" --video VIDEO_ID --limit 5 --context 1
python app.py analyze VIDEO_ID
python app.py export VIDEO_ID --format markdown|anki|all
```

Los errores previstos —video inexistente, metadata local inválida, subtítulos no disponibles o argumentos no válidos— se imprimen sin traceback y el comando termina con código distinto de cero.

Si una publicación se interrumpe, algunos archivos pueden pertenecer a generaciones distintas. Repite `study`, `analyze` o `export`, según corresponda, para completar la generación. Si `data/library.json` está dañado, los comandos de lectura no lo modifican: usa `python app.py rebuild-library`, que respalda el índice inválido antes de reconstruirlo desde `info.json` y `tools.json`.

La descarga añade inglés como fallback cuando no figura entre los idiomas solicitados. La selección distingue subtítulos manuales, automáticos originales y traducciones usando la metadata de `yt-dlp`.

## Datos y archivos generados

La biblioteca se guarda en `data/library.json`. Cada video se almacena en `data/videos/VIDEO_ID/`:

```txt
VIDEO_ID.<idioma>.vtt
info.json
transcript.txt
transcript.clean.txt
transcript.paragraphs.md
summary.md
tools.md
tools.json
concepts.md
concepts.json
questions.md
flashcards.md
study-guide.md
study.md
anki.csv
```

`tools.json` y `tools.md` incluyen la categoría y procedencia de cada hallazgo. `anki.csv` incorpora tags de video, canal, categoría, procedencia y tipo de pregunta.

El formato de análisis actual es **v3**. Las preguntas y flashcards contienen una respuesta extractiva, un timestamp y un fragmento fuente. Los conceptos incluyen unigramas y frases compuestas, componentes normalizados de puntuación y referencias temporales. `python app.py analyze VIDEO_ID` regenera análisis antiguos desde los subtítulos locales, sin descargar de nuevo el video.

## Flujo de estudio recomendado

1. Lee `summary.md`.
2. Revisa `tools.md` y `concepts.md`.
3. Intenta responder `questions.md` antes de consultar la respuesta extractiva y su referencia.
4. Repasa `flashcards.md` o importa `anki.csv` en Anki; abre el timestamp para verificar el contexto.
5. Usa `study.md` si prefieres un único documento.

## Desarrollo

La evaluación heurística usa un corpus sanitizado y una línea base versionada. Consulta [`QUALITY.md`](QUALITY.md) para conocer las métricas, inspeccionar el reporte y añadir casos sin usar datos reales ni red en CI.

Validación completa:

```bash
python -m ruff format --check .
python -m ruff check .
python -m py_compile app.py src/youtube_study/*.py
python -m coverage run -m pytest
python -m coverage combine
python -m coverage report
```

El skill compartido para resumir videos está versionado en `.pi/skills/video-study-summary/`.

## Integración continua

GitHub Actions valida cada push y pull request con Python 3.11 mediante instalación limpia, `python app.py --help`, Ruff, compilación y tests. No descarga videos ni usa red durante las pruebas.

Ollama, Whisper, GUI, PDF y búsqueda semántica permanecen fuera del alcance actual.
