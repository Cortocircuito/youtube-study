from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .analyzer import (
    ANALYSIS_FORMAT_VERSION,
    AnalysisResult,
    ConceptMention,
    Flashcard,
    StudyQuestion,
    ToolMention,
    flatten_questions,
)
from .transcript import Cue, as_text, chunk_by_minutes, seconds_from_timestamp


def timestamp_url(source_url: str | None, timestamp: str) -> str | None:
    """Return a source URL pointing at timestamp, preserving existing query parameters."""
    if not source_url:
        return None
    try:
        seconds = seconds_from_timestamp(timestamp)
    except (ValueError, IndexError):
        return None
    parsed = urlsplit(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "t"]
    query.append(("t", str(seconds)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def markdown_reference(timestamp: str, source_url: str | None = None) -> str:
    url = timestamp_url(source_url, timestamp)
    return f"[{timestamp}]({url})" if url else f"[{timestamp}]"


def anki_answer_with_reference(answer: str, timestamp: str, source_url: str | None = None) -> str:
    if not timestamp:
        return answer
    url = timestamp_url(source_url, timestamp)
    reference = (
        f'<a href="{html.escape(url, quote=True)}">{html.escape(timestamp)}</a>' if url else html.escape(timestamp)
    )
    return f"{answer}<br><br>Referencia: {reference}"


def _source_subtitle_payload(subtitle: Any) -> str | dict[str, Any]:
    if all(hasattr(subtitle, attr) for attr in ("path", "language", "kind", "reason")):
        return {
            "path": str(subtitle.path),
            "language": subtitle.language,
            "kind": subtitle.kind,
            "reason": subtitle.reason,
            "is_translation": bool(getattr(subtitle, "is_translation", False)),
            "source_language": getattr(subtitle, "source_language", None),
        }
    return str(subtitle)


def _analysis_payload(format_version: int = ANALYSIS_FORMAT_VERSION) -> dict[str, Any]:
    return {
        "format_version": format_version,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def write_info(path: Path, info: dict, subtitle: Any, *, analysis_version: int = ANALYSIS_FORMAT_VERSION) -> None:
    payload = {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
        "source_subtitle": _source_subtitle_payload(subtitle),
        "analysis": _analysis_payload(analysis_version),
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
        lines += [
            f"## {tool.name}",
            "",
            f"- Categoría: {tool.category}",
            f"- Procedencia: {'conocida' if tool.kind == 'known' else 'posible/desconocida'}",
            f"- Menciones: {tool.count}",
            f"- Descripción: {tool.description}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_tools_json(path: Path, tools: list[ToolMention]) -> None:
    payload = [
        {
            "name": tool.name,
            "count": tool.count,
            "description": tool.description,
            "category": tool.category,
            "kind": tool.kind,
        }
        for tool in tools
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_concepts(path: Path, sections: list[tuple[str, str, list[str]]]) -> None:
    lines = ["# Conceptos por sección", ""]
    for time_range, topic, ideas in sections:
        lines += [f"## {time_range}", "", f"**Palabras clave:** {topic or 'N/D'}", "", "**Ideas:**"]
        lines += [f"- {idea}" for idea in ideas]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_concepts_json(path: Path, concepts: list[ConceptMention]) -> None:
    payload = [
        {"name": concept.name, "score": concept.score, "count": concept.count, "timestamps": concept.timestamps}
        for concept in concepts
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(
    path: Path,
    title: str,
    keywords: list[tuple[str, int]],
    ideas: list[tuple[str, str]],
    sections: list[tuple[str, str, list[str]]],
    source_url: str | None = None,
) -> None:
    lines = [f"# Resumen de estudio: {title}", "", "## Palabras clave", ""]
    lines += [f"- {w}: {n}" for w, n in keywords[:15]]
    lines += ["", "## Ideas importantes con timestamp", ""]
    lines += [f"- {markdown_reference(ts, source_url)} {idea}" for ts, idea in ideas]
    lines += ["", "## Resumen por bloques", ""]
    for time_range, topic, block_ideas in sections:
        lines += [f"### {time_range}", f"Tema aproximado: {topic or 'N/D'}", ""]
        lines += [f"- {idea}" for idea in block_ideas[:3]]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_questions(path: Path, questions: dict[str, list[StudyQuestion]], source_url: str | None = None) -> None:
    headings = {"basicas": "Básicas", "comprension": "Comprensión", "practicas": "Prácticas"}
    lines = ["# Preguntas de repaso", ""]
    for level, items in questions.items():
        lines += [f"## {headings.get(level, level.title())}", ""]
        for index, item in enumerate(items, 1):
            lines += [
                f"{index}. {item.question}",
                f"   - Respuesta: {item.answer}",
                f"   - Referencia: {markdown_reference(item.timestamp, source_url)}",
            ]
        if not items:
            lines.append("Sin preguntas generadas.")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_flashcards(path: Path, cards: list[Flashcard], source_url: str | None = None) -> None:
    lines = ["# Flashcards", ""]
    for card in cards:
        lines += [
            f"Q: {card.question}",
            f"A: {card.answer}",
            f"Referencia: {markdown_reference(card.timestamp, source_url)}",
            f"Tags: {card.tags}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_study_markdown_from_result(
    path: Path, title: str, result: AnalysisResult, source_url: str | None = None
) -> None:
    """Create one portable Markdown file from one structured analysis result."""
    lines = [f"# Estudio consolidado: {title}", "", f"_Formato de análisis: {result.format_version}_", ""]

    lines += ["## Resumen", "", "### Palabras clave", ""]
    lines += [f"- {word}: {count}" for word, count in result.keywords[:15]] or ["Sin palabras clave."]
    lines += ["", "### Ideas importantes", ""]
    lines += [f"- {markdown_reference(timestamp, source_url)} {idea}" for timestamp, idea in result.ideas] or [
        "Sin ideas generadas."
    ]
    lines.append("")

    lines += ["## Herramientas", ""]
    if result.tools:
        for tool in result.tools:
            lines += [
                f"### {tool.name}",
                "",
                f"- Categoría: {tool.category}",
                f"- Procedencia: {'conocida' if tool.kind == 'known' else 'posible/desconocida'}",
                f"- Menciones: {tool.count}",
                f"- Descripción: {tool.description}",
                "",
            ]
    else:
        lines += ["No se detectaron herramientas conocidas.", ""]

    lines += ["## Conceptos", ""]
    for time_range, topic, ideas in result.sections:
        lines += [f"### {time_range}", "", f"**Palabras clave:** {topic or 'N/D'}", "", "**Ideas:**"]
        lines += [f"- {idea}" for idea in ideas]
        lines.append("")

    lines += ["## Preguntas", ""]
    headings = {"basicas": "Básicas", "comprension": "Comprensión", "practicas": "Prácticas"}
    for level, items in result.questions.items():
        lines += [f"### {headings.get(level, level.title())}", ""]
        for index, item in enumerate(items, 1):
            lines += [
                f"{index}. {item.question}",
                f"   - Respuesta: {item.answer}",
                f"   - Referencia: {markdown_reference(item.timestamp, source_url)}",
            ]
        if not items:
            lines.append("Sin preguntas generadas.")
        lines.append("")

    lines += ["## Flashcards", ""]
    for card in result.cards:
        lines += [
            f"Q: {card.question}",
            f"A: {card.answer}",
            f"Referencia: {markdown_reference(card.timestamp, source_url)}",
            f"Tags: {card.tags}",
            "",
        ]

    path.write_text("\n".join(lines), encoding="utf-8")


def _card_field(card: Flashcard | dict[str, str], name: str) -> str:
    if isinstance(card, dict):
        return card.get(name, "")
    return getattr(card, name)


def write_anki_csv(
    path: Path,
    cards: list[Flashcard] | list[dict[str, str]],
    video_id: str,
    channel: str | None = None,
    source_url: str | None = None,
) -> None:
    """Write UTF-8 CSV ready for Anki import: Front, Back, Tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Front", "Back", "Tags"])
        channel_tag = re.sub(r"\s+", "_", channel.strip()) if channel else ""
        for card in cards:
            tags = " ".join(
                part
                for part in [
                    f"video::{video_id}",
                    f"channel::{channel_tag}" if channel_tag else "",
                    _card_field(card, "tags"),
                ]
                if part
            )
            answer = anki_answer_with_reference(_card_field(card, "answer"), _card_field(card, "timestamp"), source_url)
            writer.writerow([_card_field(card, "question"), answer, tags])


def write_study_guide(
    path: Path, title: str, tools: list[ToolMention], questions: dict[str, list[StudyQuestion]]
) -> None:
    lines = [f"# Guía de estudio: {title}", "", "## 1. Qué debes entender", ""]
    lines += [f"- {tool.name}: {tool.description}" for tool in tools[:8]]
    lines += [
        "",
        "## 2. Cómo estudiar el video",
        "",
        "1. Lee primero `summary.md`.",
        "2. Revisa `tools.md` para identificar herramientas.",
        "3. Lee `concepts.md` por bloques de tiempo.",
        "4. Contesta `questions.md` sin mirar la transcripción.",
        "5. Repasa con `flashcards.md`.",
        "",
        "## 3. Preguntas clave",
        "",
    ]
    lines += [f"- {item.question} [{item.timestamp}]" for item in flatten_questions(questions)[:8]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
