from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .study_models import ANALYSIS_FORMAT_VERSION as _ANALYSIS_FORMAT_VERSION
from .study_models import (
    AnalysisResult,
    ConceptMention,
    Flashcard,
    SourceExcerpt,
    SourceFragment,
    StudyIdea,
    StudyQuestion,
    ToolMention,
    flatten_questions,
)
from .tool_catalog import TOOL_CATALOG, UNKNOWN_CANDIDATE_EXCLUSIONS
from .transcript import Cue, chunk_by_minutes, normalize_aliases, seconds_from_timestamp

ANALYSIS_FORMAT_VERSION = _ANALYSIS_FORMAT_VERSION

STOPWORDS = set(
    """
    a acá ahí al algo algunas algunos ante antes aquí así aunque cada casi como con contra cual cuando
    de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba
    están estar estas esté este esto estos fue han hasta hay la las le les lo los más me mi mis muy no
    nos o para pero por porque que se ser si sin sobre son su sus te tenía tienen tenemos todo todos tu
    un una unas unos y ya yo bien entonces ejemplo ahora ver voy vos qué cómo cosa cosas hacer ahí acá
    directamente caso gente tener tiene tengo está estoy estás estamos están vas vamos puedo podés podes
    puede pueden podría verdad realmente mostrar miren vean después acá abajo arriba también qr sim
    """.split()
)


@dataclass(frozen=True)
class TextWindow:
    evidence: SourceExcerpt
    position: int

    @property
    def timestamp(self) -> str:
        return self.evidence.timestamp

    @property
    def text(self) -> str:
        return self.evidence.text


def full_text(cues: list[Cue]) -> str:
    return " ".join(cue.text for cue in cues)


def keywords(text: str, limit: int = 25) -> list[tuple[str, int]]:
    words = [word.strip(".-_") for word in re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9_.-]{2,}", text.lower())]
    words = [word for word in words if word and word not in STOPWORDS and not word.isdigit()]
    return Counter(words).most_common(limit)


def detect_tools(text: str) -> list[ToolMention]:
    lower = normalize_aliases(text).lower()
    mentions: list[ToolMention] = []
    for name, tool in TOOL_CATALOG.items():
        aliases = [name, *tool.get("aliases", [])]
        count = sum(
            len(re.findall(r"(?<![\w.-])" + re.escape(alias.lower()) + r"(?![\w.-])", lower)) for alias in aliases
        )
        if count:
            mentions.append(
                ToolMention(
                    name=name,
                    count=count,
                    description=tool["description"],
                    category=tool["category"],
                )
            )
    mentions.extend(detect_unknown_tools(text, set(TOOL_CATALOG)))
    return sorted(mentions, key=lambda item: (item.kind != "known", -item.count, item.name))


def detect_unknown_tools(text: str, known_names: set[str], limit: int = 8) -> list[ToolMention]:
    """Detect conservative candidates not present in the versioned tool catalog."""
    candidates = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*(?:[.-][a-zA-Z0-9]+)+\b", text)
    candidates += re.findall(r"\b[A-Z]{2,8}\b", text)
    candidates += re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+\b", text)
    counts = Counter(candidates)
    ignored = {"Entonces", "Ahora", "Bien", "Mirá", "Vean", "Vos", "Para", "Esto", "Como"}
    results: list[ToolMention] = []
    for name, count in counts.most_common():
        normalized = name.lower().strip(".-")
        if (
            normalized in known_names
            or normalized in STOPWORDS
            or normalized in UNKNOWN_CANDIDATE_EXCLUSIONS
            or name in ignored
            or count < 2
        ):
            continue
        results.append(
            ToolMention(
                name=name,
                count=count,
                description="Posible herramienta o nombre propio detectado heurísticamente.",
                category="candidate",
                kind="unknown",
            )
        )
        if len(results) >= limit:
            break
    return results


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    if len(parts) == 1:
        parts = re.split(r"\s+(?=(?:Entonces|Ahora|Bien|Primero|Segundo|Tercero|Si vos|La idea)\b)", normalized)
    return [part.strip() for part in parts if len(part.strip()) >= 50]


def content_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9_.-]{2,}", text.lower())
    return {word.strip(".-_") for word in words if word.strip(".-_") not in STOPWORDS and not word.isdigit()}


def semantic_markers(text: str) -> tuple[set[str], set[str]]:
    words = set(re.findall(r"\b(?:no|sin|nunca|jamás|tampoco|ni)\b", text.lower()))
    numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", text))
    return words, numbers


def token_similarity(left: str, right: str) -> float:
    if semantic_markers(left) != semantic_markers(right):
        return 0.0
    left_tokens = content_tokens(left)
    right_tokens = content_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def deduplicate_texts(texts: list[str], threshold: float = 0.72) -> list[str]:
    unique: list[str] = []
    for text in texts:
        if any(token_similarity(text, previous) >= threshold for previous in unique):
            continue
        unique.append(text)
    return unique


def source_excerpt_from_cues(indexed_cues: list[tuple[int, Cue]]) -> SourceExcerpt:
    fragments = tuple(
        SourceFragment(
            cue_index=cue_index,
            timestamp=cue.start,
            start=0,
            end=len(cue.text),
            text=cue.text,
        )
        for cue_index, cue in indexed_cues
    )
    return SourceExcerpt(" ".join(fragment.text for fragment in fragments), fragments)


def slice_source_excerpt(evidence: SourceExcerpt, text: str) -> SourceExcerpt:
    """Select an exact substring while retaining its source cue ranges."""
    selection_start = evidence.text.find(text)
    if selection_start < 0:
        raise ValueError("El texto seleccionado no pertenece al extracto fuente")
    selection_end = selection_start + len(text)
    fragments: list[SourceFragment] = []
    cursor = 0
    for fragment in evidence.fragments:
        fragment_start = cursor
        fragment_end = fragment_start + len(fragment.text)
        overlap_start = max(selection_start, fragment_start)
        overlap_end = min(selection_end, fragment_end)
        if overlap_start < overlap_end:
            local_start = overlap_start - fragment_start
            local_end = overlap_end - fragment_start
            fragments.append(
                SourceFragment(
                    cue_index=fragment.cue_index,
                    timestamp=fragment.timestamp,
                    start=fragment.start + local_start,
                    end=fragment.start + local_end,
                    text=fragment.text[local_start:local_end],
                )
            )
        cursor = fragment_end + 1
    return SourceExcerpt(text, tuple(fragments))


def cue_windows(cues: list[Cue], size: int = 3) -> list[TextWindow]:
    """Build chronological, non-overlapping windows while dropping near-duplicate cues."""
    unique_cues: list[tuple[int, Cue]] = []
    for cue_index, cue in enumerate(cues):
        if any(
            abs(seconds_from_timestamp(cue.start) - seconds_from_timestamp(previous.start)) <= 15
            and token_similarity(cue.text, previous.text) >= 0.72
            for _, previous in unique_cues[-8:]
        ):
            continue
        unique_cues.append((cue_index, cue))

    windows: list[TextWindow] = []
    for index in range(0, len(unique_cues), size):
        chunk = unique_cues[index : index + size]
        if chunk:
            windows.append(TextWindow(source_excerpt_from_cues(chunk), index))
    return windows


def text_score(text: str, frequencies: dict[str, int], position: int = 0) -> float:
    tokens = content_tokens(text)
    words = re.findall(r"[a-záéíóúñü0-9_.-]+", text.lower())
    keyword_weight = sum(frequencies.get(token, 0) for token in tokens)
    density = len(tokens) / max(len(words), 1)
    length_score = min(len(words), 60) / 60
    position_bonus = 1 / (position + 2)
    short_penalty = 3 if len(words) < 10 else 0
    return keyword_weight + density * 3 + length_score + position_bonus - short_penalty


def representative_sentences(text: str, limit: int = 3) -> list[str]:
    candidates = deduplicate_texts(split_sentences(text))
    if not candidates:
        excerpt = text[:240].strip()
        return [f"{excerpt}..." if len(text) > 240 else excerpt] if excerpt else []
    frequencies = dict(keywords(text, 20))
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: text_score(item[1], frequencies, item[0]),
        reverse=True,
    )
    chosen = sorted(ranked[:limit], key=lambda item: item[0])
    return [sentence for _, sentence in chosen]


def important_ideas(cues: list[Cue], limit: int = 12) -> list[StudyIdea]:
    windows = cue_windows(cues)
    frequencies = dict(keywords(full_text(cues), 25))
    scored = [(text_score(window.text, frequencies, window.position), window) for window in windows]

    selected: list[TextWindow] = []
    for _, window in sorted(scored, key=lambda item: item[0], reverse=True):
        if any(token_similarity(window.text, previous.text) >= 0.72 for previous in selected):
            continue
        selected.append(window)
        if len(selected) >= limit:
            break
    return [StudyIdea(window.evidence) for window in sorted(selected, key=lambda item: item.position)]


def section_summaries(cues: list[Cue], minutes: int = 5) -> list[tuple[str, str, list[str]]]:
    sections = []
    for start, end, text in chunk_by_minutes(cues, minutes):
        kws = [word for word, _ in keywords(text, 8)]
        ideas = representative_sentences(text)
        sections.append((f"{start} - {end}", ", ".join(kws[:5]), ideas))
    return sections


def concept_mentions(cues: list[Cue], limit: int = 20) -> list[ConceptMention]:
    text = full_text(cues)
    top = keywords(text, limit)
    concepts: list[ConceptMention] = []
    for word, count in top:
        timestamps: list[str] = []
        pattern = re.compile(r"(?<![\w.-])" + re.escape(word) + r"(?![\w.-])", re.IGNORECASE)
        for cue in cues:
            if pattern.search(cue.text):
                timestamps.append(cue.start)
            if len(timestamps) >= 5:
                break
        score = count + min(len(timestamps), 5) * 2
        concepts.append(ConceptMention(word, score, count, timestamps))
    return sorted(concepts, key=lambda item: item.score, reverse=True)


def source_excerpt_for_term(cues: list[Cue], term: str) -> SourceExcerpt | None:
    pattern = re.compile(r"(?<![\w.-])" + re.escape(term) + r"(?![\w.-])", re.IGNORECASE)
    matches = [(cue_index, cue) for cue_index, cue in enumerate(cues) if pattern.search(cue.text)]
    if not matches:
        return None
    explanation = re.compile(
        r"\b(?:es|son|permite|sirve|consiste|significa|funciona|se usa|se utiliza|ayuda|protege|conecta)\b",
        re.IGNORECASE,
    )
    selected = max(
        enumerate(matches),
        key=lambda item: (
            bool(explanation.search(item[1][1].text)),
            len(content_tokens(item[1][1].text)),
            -item[0],
        ),
    )[1]
    return source_excerpt_from_cues([selected])


def question_key(question: str) -> str:
    return " ".join(re.findall(r"[a-záéíóúñü0-9]+", question.lower()))


QUESTION_TOPIC_EXCLUSIONS = {
    "evita",
    "evitar",
    "mantener",
    "revisa",
    "revisar",
    "probar",
    "optimizar",
    "conviene",
    "presenta",
    "reduce",
    "aumenta",
    "ayuda",
    "permite",
}


def question_topic(text: str, excluded: set[str] | None = None) -> str:
    ignored = QUESTION_TOPIC_EXCLUSIONS | (excluded or set())
    return next((word for word, _ in keywords(text, 8) if word not in ignored), "este tema")


def practical_excerpt(evidence: SourceExcerpt) -> SourceExcerpt | None:
    sentences = split_sentences(evidence.text)
    action_pattern = re.compile(
        r"\b(?:debe|debería|conviene|primero|evita|revisa|compara|ajusta|deja|riega|hay que|no conviene)\b",
        re.IGNORECASE,
    )
    sentence = next((sentence for sentence in sentences if action_pattern.search(sentence)), None)
    return slice_source_excerpt(evidence, sentence) if sentence else None


def questions(
    cues: list[Cue],
    tools: list[ToolMention],
    concepts: list[ConceptMention],
    ideas: list[StudyIdea],
    limit: int = 10,
) -> dict[str, list[StudyQuestion]]:
    groups: dict[str, list[StudyQuestion]] = {"basicas": [], "comprension": [], "practicas": []}
    seen: set[str] = set()

    def add(category: str, question: str, evidence: SourceExcerpt) -> None:
        key = question_key(question)
        if key in seen or len(groups[category]) >= limit:
            return
        seen.add(key)
        groups[category].append(StudyQuestion(question, evidence, category))

    used_topics: set[str] = set()
    for tool in tools[:4]:
        evidence = source_excerpt_for_term(cues, tool.name)
        if evidence:
            add("basicas", f"¿Qué se explica sobre {tool.name}?", evidence)
            used_topics.add(tool.name.lower())

    for concept in concepts:
        if len(groups["basicas"]) >= 4:
            break
        if concept.name in used_topics or concept.name in QUESTION_TOPIC_EXCLUSIONS:
            continue
        evidence = source_excerpt_for_term(cues, concept.name)
        if evidence:
            add("basicas", f"¿Qué se explica sobre {concept.name}?", evidence)
            used_topics.add(concept.name)

    for idea in ideas[:4]:
        topic = question_topic(idea.text, used_topics)
        add(
            "comprension",
            f"¿Cuál es la idea principal relacionada con {topic}?",
            idea.evidence,
        )
        used_topics.add(topic)

    practical_candidates = [excerpt for idea in ideas if (excerpt := practical_excerpt(idea.evidence)) is not None]
    for excerpt in practical_candidates[-3:]:
        topic = question_topic(excerpt.text)
        add(
            "practicas",
            f"¿Qué recomendación o criterio práctico se presenta sobre {topic}?",
            excerpt,
        )

    return groups


def flashcards(tools: list[ToolMention], qs: dict[str, list[StudyQuestion]]) -> list[Flashcard]:
    cards: list[Flashcard] = []
    for item in flatten_questions(qs):
        matching_tool = next((tool for tool in tools if tool.name.lower() in item.question.lower()), None)
        if matching_tool:
            tags = f"tool {matching_tool.category} {matching_tool.kind} {matching_tool.name} type::{item.category}"
        else:
            tags = f"question review type::{item.category}"
        cards.append(
            Flashcard(
                question=item.question,
                evidence=item.evidence,
                tags=tags,
            )
        )
    return cards


def analyze_cues(cues: list[Cue]) -> AnalysisResult:
    text = full_text(cues)
    tools = detect_tools(text)
    ideas = important_ideas(cues)
    concepts = concept_mentions(cues)
    qs = questions(cues, tools, concepts, ideas)
    return AnalysisResult(
        cues=cues,
        keywords=keywords(text),
        tools=tools,
        ideas=ideas,
        sections=section_summaries(cues),
        concepts=concepts,
        questions=qs,
        cards=flashcards(tools, qs),
    )
