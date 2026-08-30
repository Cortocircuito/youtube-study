# Plan de evolución de YouTube Study

## Estado actual

La aplicación ya permite:

- Descargar subtítulos de YouTube con `yt-dlp`.
- Limpiar transcripciones `.vtt`.
- Generar `transcript.txt`.
- Detectar herramientas conocidas.
- Crear `summary.md`, `tools.md`, `concepts.md`, `questions.md`, `flashcards.md` y `study-guide.md`.

## Prioridad actual

De momento **no usaremos Ollama**. Primero vamos a mejorar la aplicación sin depender de IA local.

### Próximas mejoras sin IA

1. Mejorar limpieza de subtítulos.
2. Mejorar detección de herramientas y conceptos.
3. Añadir una biblioteca local de videos estudiados.
4. Añadir comandos CLI:
   - `list`
   - `show`
   - `search`
   - `clean`
5. Añadir búsqueda textual dentro de transcripciones.
6. Añadir exportación a formatos útiles:
   - Markdown consolidado
   - Anki CSV
   - PDF más adelante
7. Añadir soporte para videos sin subtítulos usando Whisper como alternativa futura opcional.

## Plan futuro: Ollama

Ollama queda reservado como mejora futura para generar análisis más inteligentes manteniendo privacidad y sin coste por tokens.

### Objetivos con Ollama

- Resúmenes de mayor calidad.
- Explicación de conceptos con contexto.
- Detección automática de herramientas aunque no estén en una lista conocida.
- Preguntas de repaso más útiles.
- Flashcards mejores.
- Respuestas a preguntas sobre el video usando la transcripción.

### Posible flujo futuro

```bash
ollama pull llama3.1
python app.py study URL --provider ollama
python app.py ask VIDEO_ID "¿Cómo configura SSH?"
```

### Archivos o módulos futuros

```txt
src/youtube_study/ai/
├── __init__.py
├── ollama.py
├── prompts.py
└── schemas.py
```

### Modelos candidatos

- `llama3.1`
- `qwen2.5`
- `mistral`
- modelos pequeños para equipos modestos

## Nota

Ollama no es necesario para el MVP. La prioridad es construir primero una buena herramienta de estudio estable, rápida y local.
