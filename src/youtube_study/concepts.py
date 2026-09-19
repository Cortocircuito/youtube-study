from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .study_models import ConceptMention
from .text_units import TextUnit
from .transcript import seconds_from_timestamp

TOKEN_PATTERN = re.compile(r"[a-záéíóúñü0-9]+(?:[.-][a-záéíóúñü0-9]+)*", re.IGNORECASE)
PHRASE_BREAK = re.compile(r"[,;:!?…—–]|\s-\s")
INTERNAL_CONNECTORS = {"de", "del", "para", "sin", "con", "entre", "no"}
DETERMINERS = {"el", "la", "los", "las", "un", "una", "unos", "unas", "cada"}
DESCRIPTIVE_ENDING = re.compile(
    r"(?:al|ales|ble|bles|ico|ica|icos|icas|ivo|iva|ivos|ivas|ado|ada|ados|adas|ido|ida|idos|idas|"
    r"oso|osa|osos|osas|ario|aria|arios|arias|ante|antes|ente|entes)$"
)
COMMON_DESCRIPTORS = {
    "lento",
    "lenta",
    "lentos",
    "lentas",
    "pequeño",
    "pequeña",
    "robusto",
    "robusta",
    "sano",
    "sana",
    "sanos",
    "sanas",
}
GENERIC_CONCEPT_TERMS = {
    "cambio",
    "cambios",
    "caso",
    "cosa",
    "cosas",
    "datos",
    "ejemplo",
    "gente",
    "hoy",
    "información",
    "momento",
    "parte",
    "persona",
    "primero",
    "resultado",
    "resultados",
    "tema",
    "tiempo",
    "uso",
    "video",
    "cuáles",
}
GENERIC_ACTION_TERMS = {
    "acelerar",
    "agrupan",
    "ajusta",
    "aumenta",
    "ayuda",
    "cambiar",
    "compara",
    "compartir",
    "compactar",
    "confirma",
    "conservan",
    "consume",
    "contiene",
    "conviene",
    "crear",
    "cultivar",
    "deja",
    "debe",
    "definen",
    "disminuye",
    "evita",
    "explicar",
    "falla",
    "funciona",
    "gastan",
    "hacer",
    "identificar",
    "integra",
    "limita",
    "leer",
    "mantener",
    "medir",
    "mezcla",
    "modificar",
    "muestra",
    "ocupa",
    "optimizar",
    "optimizando",
    "penaliza",
    "permite",
    "permiten",
    "pierde",
    "presenta",
    "preparar",
    "probar",
    "protege",
    "reduce",
    "reducir",
    "registra",
    "revisa",
    "revisar",
    "retira",
    "riega",
    "sellar",
    "seguir",
    "sirve",
    "verifica",
}


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int
    timestamp: str


@dataclass
class _Candidate:
    name: str
    tokens: tuple[str, ...]
    timestamps: list[str]
    occurrences: list[tuple[int, int, int]]
    first_position: int
    count: int = 0
    context_hits: int = 0
    frequency_score: float = 0.0
    distribution_score: float = 0.0
    association_score: float | None = None
    score: float = 0.0


def _fragment_ranges(unit: TextUnit) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    cursor = 0
    for fragment in unit.evidence.fragments:
        end = cursor + len(fragment.text)
        ranges.append((cursor, end, fragment.timestamp))
        cursor = end + 1
    return ranges


def _tokens(unit: TextUnit) -> list[_Token]:
    ranges = _fragment_ranges(unit)
    tokens: list[_Token] = []
    for match in TOKEN_PATTERN.finditer(unit.text):
        timestamp = next(timestamp for start, end, timestamp in ranges if start <= match.start() < end)
        tokens.append(_Token(match.group().casefold(), match.start(), match.end(), timestamp))
    return tokens


def _eligible(candidate: _Candidate, stopwords: set[str]) -> bool:
    tokens = candidate.tokens
    count = candidate.count
    if not tokens or tokens[0] in stopwords or tokens[-1] in stopwords:
        return False
    if any(token.isdigit() for token in tokens):
        return False
    if len(set(tokens)) != len(tokens):
        return False
    if len(tokens) == 1:
        token = tokens[0]
        return len(token) >= 3 and token not in GENERIC_CONCEPT_TERMS and token not in GENERIC_ACTION_TERMS
    if any(token in GENERIC_ACTION_TERMS for token in tokens):
        return False
    if len(tokens) == 3 and tokens[1] not in INTERNAL_CONNECTORS and count < 2:
        return False
    if len(tokens) == 2 and count < 2 and candidate.context_hits == 0:
        return False
    content = [token for token in tokens if token not in stopwords]
    return len(content) >= 2 and (count >= 2 or all(len(token) >= 4 for token in content))


def _distribution_score(timestamps: list[str], all_timestamps: list[str]) -> float:
    seconds = [seconds_from_timestamp(timestamp) for timestamp in all_timestamps]
    start, end = min(seconds), max(seconds)
    bin_count = min(5, len(set(all_timestamps)))
    if bin_count <= 1 or start == end:
        return 1.0
    span = end - start + 1
    bins = {
        min(bin_count - 1, (seconds_from_timestamp(timestamp) - start) * bin_count // span) for timestamp in timestamps
    }
    return len(bins) / bin_count


def _is_nested(left: _Candidate, right: _Candidate) -> bool:
    if len(left.tokens) >= len(right.tokens):
        return False
    size = len(left.tokens)
    contained = any(right.tokens[index : index + size] == left.tokens for index in range(len(right.tokens) - size + 1))
    if not contained:
        return False
    contained_occurrences = sum(
        any(
            short_position == long_position and long_start <= short_start and short_end <= long_end
            for long_position, long_start, long_end in right.occurrences
        )
        for short_position, short_start, short_end in left.occurrences
    )
    overlap = contained_occurrences / max(len(left.occurrences), len(right.occurrences))
    return overlap >= 0.8


def extract_concepts(units: list[TextUnit], stopwords: set[str], limit: int = 15) -> list[ConceptMention]:
    """Extract ranked one-to-three-token concepts from informative text units."""
    candidates: dict[str, _Candidate] = {}
    token_counts: Counter[str] = Counter()
    all_timestamps = [unit.timestamp for unit in units]

    for unit_index, unit in enumerate(units):
        tokens = _tokens(unit)
        token_counts.update(token.text for token in tokens if token.text not in stopwords)
        for size in (1, 2, 3):
            for index in range(len(tokens) - size + 1):
                selected = tokens[index : index + size]
                separators = (unit.text[left.end : right.start] for left, right in zip(selected, selected[1:]))
                if any(PHRASE_BREAK.search(separator) for separator in separators):
                    continue
                values = tuple(token.text for token in selected)
                name = " ".join(values)
                candidate = candidates.setdefault(
                    name,
                    _Candidate(name, values, [], [], unit.position),
                )
                candidate.count += 1
                preceded_by_determiner = index > 0 and tokens[index - 1].text in DETERMINERS
                descriptive_ending = bool(DESCRIPTIVE_ENDING.search(values[-1])) or values[-1] in COMMON_DESCRIPTORS
                candidate.context_hits += preceded_by_determiner or descriptive_ending
                candidate.timestamps.append(selected[0].timestamp)
                candidate.occurrences.append((unit_index, selected[0].start, selected[-1].end))

    eligible = [candidate for candidate in candidates.values() if _eligible(candidate, stopwords)]
    if not eligible:
        return []
    max_count = max(candidate.count for candidate in eligible)
    frequency_denominator = math.log1p(max_count)
    for candidate in eligible:
        candidate.frequency_score = math.log1p(candidate.count) / frequency_denominator
        candidate.distribution_score = _distribution_score(candidate.timestamps, all_timestamps)
        if len(candidate.tokens) > 1:
            content_counts = [token_counts[token] for token in candidate.tokens if token not in stopwords]
            candidate.association_score = candidate.count / max(content_counts)
            candidate.score = (
                0.45 * candidate.frequency_score
                + 0.25 * candidate.distribution_score
                + 0.30 * candidate.association_score
            )
            candidate.score = min(1.0, candidate.score + 0.08)
            if len(candidate.tokens) == 3 and candidate.tokens[1] in INTERNAL_CONNECTORS:
                candidate.score = min(1.0, candidate.score + 0.12)
        else:
            candidate.score = 0.65 * candidate.frequency_score + 0.35 * candidate.distribution_score

    ranked = sorted(
        eligible,
        key=lambda candidate: (
            -candidate.score,
            -candidate.count,
            -len(candidate.tokens),
            candidate.first_position,
            candidate.name,
        ),
    )
    selected: list[_Candidate] = []
    for candidate in ranked:
        skip = False
        for previous in list(selected):
            if not (_is_nested(candidate, previous) or _is_nested(previous, candidate)):
                continue
            if len(candidate.tokens) > len(previous.tokens):
                selected.remove(previous)
            elif len(previous.tokens) > len(candidate.tokens):
                skip = True
                break
        if skip:
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break

    return [
        ConceptMention(
            name=candidate.name,
            score=round(candidate.score, 6),
            count=candidate.count,
            frequency_score=round(candidate.frequency_score, 6),
            distribution_score=round(candidate.distribution_score, 6),
            association_score=(
                round(candidate.association_score, 6) if candidate.association_score is not None else None
            ),
            timestamps=tuple(dict.fromkeys(candidate.timestamps))[:5],
        )
        for candidate in selected
    ]
