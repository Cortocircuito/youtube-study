# Roadmap de YouTube Study

## Estado actual

La aplicación funciona localmente sin Ollama y permite:

- Descargar y seleccionar subtítulos con `yt-dlp`.
- Limpiar captions automáticos y generar transcripciones legibles.
- Crear resúmenes extractivos deduplicados, conceptos, preguntas respondidas y flashcards.
- Referenciar el instante del video desde Markdown y Anki.
- Mantener `data/library.json` y usar `list`, `show`, `search`, `analyze`, `export` y `rebuild-library`.
- Regenerar análisis antiguos al formato v3 sin red cuando los subtítulos ya están guardados.
- Propagar evidencia extractiva con posiciones y rangos exactos desde los captions hasta preguntas y tarjetas.
- Publicar generaciones y exportaciones desde staging mediante reemplazos atómicos por archivo y reintento explícito.
- Reintentar con espera exponencial los fallos temporales de descarga y rechazar colecciones de videos.
- Leer la biblioteca sin efectos secundarios y reconstruir índices dañados explícitamente con respaldo mediante `rebuild-library`.
- Validar cambios mediante Ruff, compilación, pytest y GitHub Actions.
- Medir cobertura de ramas en CI con un umbral global mínimo de 88 %. La referencia local actual es 91 %, incluyendo los subprocesos de las pruebas funcionales de CLI.

## Prioridades próximas sin IA

1. Completar la anotación humana de la muestra local de videos largos descrita en `QUALITY.md`.
2. Mejorar filtros de biblioteca por canal, herramienta, tema y estado de estudio.
3. Mejorar la separación de párrafos con fixtures variados sin reducir la fidelidad extractiva.
4. Ampliar ramas restantes de biblioteca y metadata sin reducir el umbral global actual.

La fase inicial de evaluación ya dispone de objetivos manuales sobre fixtures sanitizados, métricas direccionales y una muestra local de videos largos pendiente de anotación humana. Esta muestra no participa en CI ni convierte resultados generados en referencias de calidad.

La segunda fase reconstruye unidades legibles desde cues fragmentados, conserva evidencia exacta y filtra ruido inequívoco sólo en el material de estudio. El caso ruidoso del corpus ya no presenta violaciones; quedan pendientes los temas genéricos de preguntas y la anotación manual de videos largos.

La tercera fase extrae conceptos de una a tres palabras, puntúa frecuencia, distribución y asociación, elimina variantes redundantes y alinea `concepts.md`, `concepts.json` y la sección correspondiente de `study.md`. El formato de análisis v3 permite regenerar estos artefactos desde subtítulos locales.

La cuarta fase formula una sola pregunta básica por evidencia explicativa, usa temas prácticos breves en orden textual y reserva las preguntas de comprensión para causas o condiciones explícitas. El corpus sanitizado alcanza precisión, recall y F1 de preguntas completos para sus objetivos revisados; la métrica v3 exige además timestamp correcto y emparejamiento uno a uno.

La quinta fase cubre errores de `yt-dlp`, metadata incompleta, fallbacks de subtítulos, validación previa de staging, limpieza temporal y orquestación de `process_video`, siempre sin red. `downloader.py`, `artifacts.py` y `service.py` alcanzan 98 % de cobertura combinada y la suite completa alcanza 91 %, sin requerir cambios de producción.

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
