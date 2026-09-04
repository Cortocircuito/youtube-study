# YouTube Study

Aplicación para estudiar videos de YouTube a partir de sus transcripciones.

## Qué hace

- Descarga subtítulos con `yt-dlp`.
- Limpia la transcripción.
- Extrae herramientas mencionadas.
- Genera resumen por timestamps y por bloques.
- Crea preguntas de repaso.
- Crea flashcards.
- Genera una guía de estudio.

## Instalación recomendada en Ubuntu 24.04

No uses el `yt-dlp` de `apt` para este proyecto: suele estar desactualizado.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso rápido

Analizar un video nuevo:

```bash
python app.py "https://www.youtube.com/watch?v=Yj51wXMwFwE"
```

O explícitamente:

```bash
python app.py study "https://www.youtube.com/watch?v=Yj51wXMwFwE" --lang "es-419,es" --out data/videos
```

Opciones útiles al descargar:

```bash
python app.py study "URL" --quiet
python app.py study "URL" --force-download
```

La app prioriza subtítulos españoles y muestra un error claro si no encuentra ninguno. Si `yt-dlp` está desactualizado, activa el venv y reinstala con `pip install -r requirements.txt`.

Listar videos guardados en la biblioteca local:

```bash
python app.py list
```

Ver detalle de un video estudiado:

```bash
python app.py show VIDEO_ID
```

Buscar texto dentro de transcripciones:

```bash
python app.py search "consulta"
python app.py search "consulta" --video VIDEO_ID --limit 5 --context 1
```

Reanalizar un video ya descargado sin volver a descargar subtítulos:

```bash
python app.py analyze VIDEO_ID
```

Exportar un documento consolidado o tarjetas para Anki:

```bash
python app.py export VIDEO_ID --format markdown
python app.py export VIDEO_ID --format anki
python app.py export VIDEO_ID --format all
```

## Biblioteca local

La app mantiene una biblioteca en:

```txt
data/library.json
```

Ahí guarda metadata de cada video: id, título, canal, duración, URL, ruta local, herramientas detectadas y fechas.

## Archivos generados

Para cada video se crea una carpeta:

```txt
data/videos/VIDEO_ID/
├── VIDEO_ID.es-419.vtt
├── VIDEO_ID.es.vtt
├── info.json
├── transcript.txt
├── transcript.clean.txt
├── transcript.paragraphs.md
├── summary.md
├── tools.md
├── concepts.md
├── questions.md
├── flashcards.md
├── study-guide.md
├── study.md
└── anki.csv
```

## Flujo de estudio recomendado

1. Lee `summary.md`.
2. Revisa `tools.md`.
3. Estudia `concepts.md` por bloques de tiempo.
4. Contesta `questions.md` sin mirar.
5. Repasa con `flashcards.md`.

## Próximos pasos

- Mejorar detección heurística de herramientas y conceptos.
- Exportar `tools.json` y `concepts.json`.
- Crear `study.md` consolidado.
- Exportar flashcards a Anki CSV.
- Añadir tests mínimos.
- Dejar Ollama para una fase futura opcional.
