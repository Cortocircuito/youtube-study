---
name: video-study-summary
description: Creates clean, study-friendly summaries from youtube-study materials. Use when the user asks to study or summarize a video. If no video ID, URL, or explicit video path is provided, ask which saved video they want before reading study files.
---

# Video Study Summary

Use this skill when the user asks to study a YouTube video or wants a clean summary of generated study materials.

## Goal

Transform noisy transcript-based outputs into a clear, useful study note in Spanish.

## Selección del video

1. Si el usuario proporciona un `VIDEO_ID`, URL o ruta explícita, úsalo.
2. Si no indica video, **pregunta primero qué video quiere resumir**. No leas archivos de estudio ni generes un resumen hasta recibir la respuesta.
3. Para ayudarle a elegir, ejecuta `python app.py list` y presenta los videos disponibles con su ID y título. Si la biblioteca está vacía, indícale que primero debe analizar un video con `python app.py "URL"`.
4. Si el usuario responde con un título ambiguo, pide el `VIDEO_ID` exacto o confirma una única coincidencia.

## Inputs

Con el video seleccionado, prefiere estos archivos en este orden:

1. `data/videos/<VIDEO_ID>/info.json`
2. `data/videos/<VIDEO_ID>/summary.md`
3. `data/videos/<VIDEO_ID>/study-guide.md`
4. `data/videos/<VIDEO_ID>/tools.md`
5. `data/videos/<VIDEO_ID>/concepts.md`

Avoid reading full long transcripts unless the user explicitly asks. For long files, read bounded sections or use search/context snippets.

## Style

Write in Spanish, concise but useful. Use a clean study format, not a raw transcript dump.

Use this structure by default:

```markdown
# Resumen — <título corto>

El video trata sobre <tema central en 2-4 líneas>.

## 1. Tema central
<explicación clara>

## 2. Concepto importante
<explicación>

## 3. Otro concepto importante
<explicación>

...

## Conceptos clave para memorizar

- **Concepto:** definición breve.
- **Concepto:** definición breve.

## En una frase

> <idea principal del video>
```

## Rules

- Remove filler, stream noise, music, greetings, jokes, repeated words, and transcript artifacts.
- Preserve the important technical concepts.
- Explain jargon in simple terms.
- Group related ideas instead of following every timestamp mechanically.
- Mention timestamps only when useful, not in every bullet.
- If the generated `summary.md` is noisy, synthesize from multiple generated files.
- Keep the final answer directly useful for studying.

## Optional follow-ups

After the summary, offer one next study action only if appropriate:

- glosario
- preguntas de comprensión
- flashcards
- mapa mental
- guía práctica
