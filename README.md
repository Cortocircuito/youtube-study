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

```bash
python app.py "https://www.youtube.com/watch?v=Yj51wXMwFwE"
```

O explícitamente:

```bash
python app.py study "https://www.youtube.com/watch?v=Yj51wXMwFwE" --lang "es-419,es" --out data/videos
```

## Archivos generados

Para cada video se crea una carpeta:

```txt
data/videos/VIDEO_ID/
├── VIDEO_ID.es-419.vtt
├── VIDEO_ID.es.vtt
├── info.json
├── transcript.txt
├── summary.md
├── tools.md
├── concepts.md
├── questions.md
├── flashcards.md
└── study-guide.md
```

## Flujo de estudio recomendado

1. Lee `summary.md`.
2. Revisa `tools.md`.
3. Estudia `concepts.md` por bloques de tiempo.
4. Contesta `questions.md` sin mirar.
5. Repasa con `flashcards.md`.

## Próximos pasos

- Añadir soporte para Ollama y resúmenes con IA local.
- Añadir búsqueda semántica dentro de las transcripciones.
- Crear interfaz web con Streamlit o FastAPI.
- Exportar a Anki/PDF.
