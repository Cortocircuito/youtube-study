---
title: "Mejoras de YouTube Study sin Ollama"
status: in_progress
created: "2026-08-30T11:53:36.691Z"
updated: "2026-08-30T12:03:46.844Z"
type: feature
---

# Mejoras de YouTube Study sin Ollama

## Objetivo

Convertir `youtube-study` en biblioteca local de estudio para videos de YouTube, manteniendo app rápida, local y usable sin Ollama.

## Alcance

Incluye:
- Limpieza de subtítulos más robusta.
- Biblioteca local `data/library.json`.
- Comandos `list`, `show`, `search`, `analyze`.
- Mejor detección heurística de herramientas/conceptos.
- Exportación Markdown consolidada y Anki CSV.
- Tests mínimos.

No incluye por ahora:
- Ollama.
- Whisper.
- Interfaz web.
- PDF.
- Búsqueda semántica.

## Reglas de ejecución con openplan

- Ejecutar máximo 5 pasos por tanda.
- Marcar progreso con `[DONE:n]` al terminar cada fase.
- Parar en cada `⏸️ PAUSE` para verificación.
- No leer transcripciones completas ni `.vtt` grandes salvo petición explícita.

## Fase 1: Biblioteca local y metadata

1. Crear `src/youtube_study/library.py`.
2. Definir estructura de entrada para `data/library.json` con `id`, `title`, `channel`, `duration`, `url`, `path`, `tools`, `created_at`, `updated_at`.
3. Actualizar `process_video()` para registrar/actualizar video al terminar análisis.
4. Evitar duplicados por `video_id`.
5. Añadir manejo seguro si `library.json` no existe o está vacío.

Verificación:

```bash
python3 -m py_compile app.py src/youtube_study/*.py
python app.py "https://www.youtube.com/watch?v=Yj51wXMwFwE"
python -m json.tool data/library.json
```

⏸️ PAUSE - Revisar `data/library.json` antes de seguir.

## Fase 2: Comandos CLI de biblioteca

1. Añadir subcomando `list` para mostrar videos guardados.
2. Añadir subcomando `show VIDEO_ID` para mostrar metadata, ruta y archivos disponibles.
3. Añadir opción `--out` común para ubicar `data/videos` y `data/library.json`.
4. Añadir mensajes claros si biblioteca está vacía.
5. Mantener atajo `python app.py URL` funcionando.

Verificación:

```bash
python app.py list
python app.py show Yj51wXMwFwE
python app.py "https://www.youtube.com/watch?v=Yj51wXMwFwE"
```

⏸️ PAUSE - Validar UX de comandos `list` y `show`.

## Fase 3: Búsqueda textual

1. Crear `src/youtube_study/search.py`.
2. Implementar búsqueda case-insensitive en `transcript.txt`.
3. Mostrar resultados con `video_id`, título, timestamp y línea encontrada.
4. Añadir `python app.py search "consulta"` para todos los videos.
5. Añadir `--video VIDEO_ID`, `--limit N` y `--context N`.

Verificación:

```bash
python app.py search "Tailscale"
python app.py search "authorized keys" --video Yj51wXMwFwE --limit 5
python3 -m py_compile app.py src/youtube_study/*.py
```

⏸️ PAUSE - Probar búsqueda con 2 videos ya descargados.

## Fase 4: Reanalizar sin descargar

1. Añadir subcomando `analyze VIDEO_ID`.
2. Reusar `.vtt` existente si está en `data/videos/VIDEO_ID/`.
3. Regenerar `transcript.txt`, `summary.md`, `tools.md`, `concepts.md`, `questions.md`, `flashcards.md`, `study-guide.md`.
4. Actualizar `library.json` tras reanálisis.
5. Añadir error claro si no existe el video o no hay `.vtt`.

Verificación:

```bash
python app.py analyze Yj51wXMwFwE
python app.py analyze D1CFRS9Ikh8
```

⏸️ PAUSE - Validar que no vuelve a descargar subtítulos.

## Fase 5: Mejor limpieza de transcripciones

1. Generar `transcript.clean.txt` sin timestamps.
2. Generar `transcript.paragraphs.md` agrupado por párrafos o bloques de tiempo.
3. Mejorar eliminación de rolling captions repetidos en videos largos.
4. Añadir normalización de aliases comunes: `Moshie/Mochi -> Moshi`, `Herder/Gerd -> Herdr`, `Claudio -> Claude`.
5. Mantener `transcript.txt` con timestamps como fuente principal.

Verificación:

```bash
python app.py analyze D1CFRS9Ikh8
wc -c data/videos/D1CFRS9Ikh8/transcript.txt data/videos/D1CFRS9Ikh8/transcript.clean.txt
```

⏸️ PAUSE - Revisar fragmentos pequeños de transcripción limpia.

## Fase 6: Mejor análisis heurístico

1. Exportar también `tools.json`.
2. Detectar herramientas desconocidas por patrones de mayúsculas/nombres compuestos.
3. Crear `concepts.json` con conceptos, score y timestamps aproximados.
4. Separar preguntas en niveles: básicas, comprensión, prácticas.
5. Mejorar flashcards con tags por herramienta/concepto.

Verificación:

```bash
python app.py analyze Yj51wXMwFwE
python -m json.tool data/videos/Yj51wXMwFwE/tools.json
python -m json.tool data/videos/Yj51wXMwFwE/concepts.json
```

⏸️ PAUSE - Revisar calidad de `tools.md`, `concepts.md`, `questions.md`.

## Fase 7: Exportación para estudio

1. Crear `study.md` consolidado con metadata, resumen, herramientas, conceptos, preguntas y flashcards.
2. Crear exportador Anki CSV `anki.csv`.
3. Añadir subcomando `export VIDEO_ID --format markdown|anki|all`.
4. Añadir tags útiles en Anki: canal, video_id, herramientas.
5. Documentar flujo de estudio en `README.md`.

Verificación:

```bash
python app.py export Yj51wXMwFwE --format all
head data/videos/Yj51wXMwFwE/study.md
head data/videos/Yj51wXMwFwE/anki.csv
```

⏸️ PAUSE - Importar `anki.csv` manualmente si se quiere validar formato.

## Fase 8: Robustez y errores

1. Detectar `yt-dlp` desactualizado y mostrar recomendación de venv.
2. Manejar errores de subtítulos no disponibles.
3. Mejorar selector de subtítulos: manual español > auto español original > español traducido > inglés.
4. Añadir `--force-download` para volver a descargar subtítulos.
5. Añadir `--quiet` para reducir salida de `yt-dlp`.

Verificación:

```bash
python app.py study "URL_SIN_SUBTITULOS"
python app.py study "https://www.youtube.com/watch?v=Yj51wXMwFwE" --quiet
```

⏸️ PAUSE - Revisar mensajes de error y UX.

## Fase 9: Tests mínimos

1. Crear `tests/fixtures/sample.vtt` pequeño.
2. Crear tests para `clean_vtt()` y rolling captions.
3. Crear tests para aliases de herramientas.
4. Crear tests para biblioteca local con archivo temporal.
5. Crear tests para búsqueda textual.

Verificación:

```bash
python3 -m py_compile app.py src/youtube_study/*.py
python -m pytest
```

⏸️ PAUSE - Revisar cobertura mínima antes de nuevas features.

## Resultado esperado

Al final, la app debe funcionar como biblioteca de estudio:

```bash
python app.py "URL"
python app.py list
python app.py show VIDEO_ID
python app.py search "concepto"
python app.py analyze VIDEO_ID
python app.py export VIDEO_ID --format all
```

Archivos clave por video:

```txt
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

## Riesgos

- Subtítulos automáticos largos pueden seguir siendo ruidosos.
- Detección heurística nunca será perfecta sin IA.
- `yt-dlp` cambia con frecuencia por cambios de YouTube.

## Criterios de éxito

- `python app.py "URL"` sigue funcionando.
- Videos ya descargados se pueden reanalizar sin red.
- Biblioteca lista videos y permite búsquedas útiles.
- Archivos generados sirven para estudiar sin abrir YouTube.
- No se usa Ollama en esta fase.