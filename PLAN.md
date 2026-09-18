# Roadmap de YouTube Study

## Estado actual

La aplicación funciona localmente sin Ollama y permite:

- Descargar y seleccionar subtítulos con `yt-dlp`.
- Limpiar captions automáticos y generar transcripciones legibles.
- Crear resúmenes extractivos deduplicados, conceptos, preguntas respondidas y flashcards.
- Referenciar el instante del video desde Markdown y Anki.
- Mantener `data/library.json` y usar `list`, `show`, `search`, `analyze`, `export` y `rebuild-library`.
- Regenerar análisis antiguos al formato v2 sin red cuando los subtítulos ya están guardados.
- Validar cambios mediante Ruff, compilación, pytest y GitHub Actions.

## Prioridades próximas sin IA

1. Ampliar fixtures de subtítulos automáticos ruidosos y mejorar puntuación/separación de párrafos.
2. Refinar conceptos y formulación de preguntas con métricas pedagógicas conservadoras.
3. Medir cobertura de tests e identificar módulos críticos antes de fijar un umbral.
4. Mejorar filtros de biblioteca por canal, herramienta, tema y estado de estudio.
5. Reforzar reintentos y recuperación ante fallos temporales de descarga sin sobrescribir resultados válidos.

## Posibles mejoras posteriores

- Exportación PDF.
- Whisper opcional para videos sin subtítulos.
- Búsqueda semántica local.
- Interfaz gráfica o web.

## Ollama, fase futura opcional

Ollama no es necesario para el funcionamiento principal. Si se incorpora, deberá ser un proveedor opcional y mantener el flujo heurístico actual como fallback.

Objetivos posibles:

- Resúmenes y explicaciones más naturales.
- Preguntas de repaso de mayor profundidad.
- Detección contextual de herramientas y conceptos.
- Preguntas y respuestas sobre una transcripción.

Ejemplo futuro:

```bash
python app.py study URL --provider ollama
python app.py ask VIDEO_ID "¿Cómo configura SSH?"
```

La integración no debe enviar contenido a servicios externos por defecto ni romper el modo completamente local actual.
