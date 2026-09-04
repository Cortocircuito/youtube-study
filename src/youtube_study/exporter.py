from __future__ import annotations

import json
from pathlib import Path

from .analyzer import ToolMention
from .transcript import Cue, as_text, chunk_by_minutes


def write_info(path: Path, info: dict, subtitle: Path) -> None:
    payload = {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "source_subtitle": str(subtitle),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_transcript(path: Path, cues: list[Cue]) -> None:
    path.write_text(as_text(cues, timestamps=True), encoding="utf-8")


def write_clean_transcript(path: Path, cues: list[Cue]) -> None:
    path.write_text(as_text(cues, timestamps=False), encoding="utf-8")


def write_transcript_paragraphs(path: Path, cues: list[Cue], minutes: int = 5) -> None:
    lines = ["# Transcripción por bloques", ""]
    for start, end, text in chunk_by_minutes(cues, minutes):
        lines += [f"## {start} - {end}", "", text.strip(), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_tools(path: Path, tools: list[ToolMention]) -> None:
    lines = ["# Herramientas detectadas", ""]
    if not tools:
        lines.append("No se detectaron herramientas conocidas.")
    for tool in tools:
        lines += [f"## {tool.name}", "", f"- Menciones: {tool.count}", f"- Descripción: {tool.description}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_concepts(path: Path, sections: list[tuple[str, str, list[str]]]) -> None:
    lines = ["# Conceptos por sección", ""]
    for time_range, topic, ideas in sections:
        lines += [f"## {time_range}", "", f"**Palabras clave:** {topic or 'N/D'}", "", "**Ideas:**"]
        lines += [f"- {idea}" for idea in ideas]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_summary(path: Path, title: str, keywords: list[tuple[str, int]], ideas: list[tuple[str, str]], sections: list[tuple[str, str, list[str]]]) -> None:
    lines = [f"# Resumen de estudio: {title}", "", "## Palabras clave", ""]
    lines += [f"- {w}: {n}" for w, n in keywords[:15]]
    lines += ["", "## Ideas importantes con timestamp", ""]
    lines += [f"- [{ts}] {idea}" for ts, idea in ideas]
    lines += ["", "## Resumen por bloques", ""]
    for time_range, topic, block_ideas in sections:
        lines += [f"### {time_range}", f"Tema aproximado: {topic or 'N/D'}", ""]
        lines += [f"- {idea}" for idea in block_ideas[:3]]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_questions(path: Path, questions: list[str]) -> None:
    lines = ["# Preguntas de repaso", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(questions, 1)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_flashcards(path: Path, cards: list[tuple[str, str]]) -> None:
    lines = ["# Flashcards", ""]
    for q, a in cards:
        lines += [f"Q: {q}", f"A: {a}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_study_guide(path: Path, title: str, tools: list[ToolMention], questions: list[str]) -> None:
    lines = [f"# Guía de estudio: {title}", "", "## 1. Qué debes entender", ""]
    lines += [f"- {tool.name}: {tool.description}" for tool in tools[:8]]
    lines += ["", "## 2. Cómo estudiar el video", "", "1. Lee primero `summary.md`.", "2. Revisa `tools.md` para identificar herramientas.", "3. Lee `concepts.md` por bloques de tiempo.", "4. Contesta `questions.md` sin mirar la transcripción.", "5. Repasa con `flashcards.md`.", "", "## 3. Preguntas clave", ""]
    lines += [f"- {q}" for q in questions[:8]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
