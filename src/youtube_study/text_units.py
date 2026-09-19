from __future__ import annotations

import re
from dataclasses import dataclass

from .study_models import SourceExcerpt, SourceFragment
from .transcript import Cue, seconds_from_timestamp

SENTENCE_END = re.compile(r"[.!?…][\"'»”\)\]]*$")
SENTENCE_PARTS = re.compile(r".*?[.!?…]+[\"'»”\)\]]*(?=\s|$)|.+$", re.DOTALL)
ABBREVIATION_END = re.compile(r"\b(?:sr|sra|srta|dr|dra|ing|lic|etc|ej|núm|num)\.$", re.IGNORECASE)
STAGE_ONLY = re.compile(r"^(?:\s*\[[^\]]+\]\s*)+$")


@dataclass(frozen=True)
class TextUnit:
    evidence: SourceExcerpt
    position: int

    @property
    def timestamp(self) -> str:
        return self.evidence.timestamp

    @property
    def text(self) -> str:
        return self.evidence.text


def _sentence_ranges(text: str) -> list[tuple[int, int, bool]]:
    ranges: list[tuple[int, int, bool]] = []
    for match in SENTENCE_PARTS.finditer(text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            ranges.append((start, end, bool(SENTENCE_END.search(text[start:end]))))

    merged: list[tuple[int, int, bool]] = []
    for start, end, complete in ranges:
        if merged:
            previous_start, previous_end, _ = merged[-1]
            previous_text = text[previous_start:previous_end]
            next_text = text[start:end]
            version_boundary = bool(re.search(r"\b\d+\.$", previous_text)) and bool(re.match(r"\d", next_text))
            if ABBREVIATION_END.search(previous_text) or version_boundary:
                merged[-1] = (previous_start, end, complete)
                continue
        merged.append((start, end, complete))
    return merged


def _excerpt(fragments: list[SourceFragment]) -> SourceExcerpt:
    return SourceExcerpt(" ".join(fragment.text for fragment in fragments), tuple(fragments))


def _word_count(fragments: list[SourceFragment]) -> int:
    return sum(len(re.findall(r"\w+", fragment.text, re.UNICODE)) for fragment in fragments)


def sentence_units(
    cues: list[Cue], *, max_gap_seconds: int = 15, max_cues: int = 4, max_words: int = 80
) -> list[TextUnit]:
    """Reconstruct sentence-like units while retaining exact cue ranges."""
    units: list[TextUnit] = []
    pending: list[SourceFragment] = []
    pending_position = 0
    pending_cues: set[int] = set()
    previous_seconds: int | None = None

    def flush() -> None:
        nonlocal pending, pending_cues
        if pending:
            units.append(TextUnit(_excerpt(pending), pending_position))
        pending = []
        pending_cues = set()

    for cue_index, cue in enumerate(cues):
        cue_seconds = seconds_from_timestamp(cue.start)
        if pending and previous_seconds is not None and cue_seconds - previous_seconds > max_gap_seconds:
            flush()
        if pending and STAGE_ONLY.fullmatch(cue.text):
            flush()

        for start, end, complete in _sentence_ranges(cue.text):
            fragment = SourceFragment(cue_index, cue.start, start, end, cue.text[start:end])
            exceeds_limit = pending and (
                _word_count([*pending, fragment]) > max_words
                or (cue_index not in pending_cues and len(pending_cues) >= max_cues)
            )
            if exceeds_limit:
                flush()
            if not pending:
                pending_position = cue_index
            pending.append(fragment)
            pending_cues.add(cue_index)
            if complete:
                flush()
        if STAGE_ONLY.fullmatch(cue.text):
            flush()
        previous_seconds = cue_seconds

    flush()
    return units


def combine_units(units: list[TextUnit]) -> TextUnit:
    fragments = [fragment for unit in units for fragment in unit.evidence.fragments]
    return TextUnit(_excerpt(fragments), units[0].position)


def pack_units(
    units: list[TextUnit], *, size: int = 3, max_words: int = 90, max_gap_seconds: int = 15
) -> list[TextUnit]:
    """Pack complete units into readable windows without crossing large gaps."""
    packed: list[TextUnit] = []
    pending: list[TextUnit] = []

    def flush() -> None:
        nonlocal pending
        if pending:
            packed.append(combine_units(pending))
        pending = []

    for unit in units:
        gap = 0
        if pending:
            previous_timestamp = pending[-1].evidence.fragments[-1].timestamp
            gap = seconds_from_timestamp(unit.timestamp) - seconds_from_timestamp(previous_timestamp)
        pending_words = sum(len(re.findall(r"\w+", item.text, re.UNICODE)) for item in pending)
        unit_words = len(re.findall(r"\w+", unit.text, re.UNICODE))
        if pending and (len(pending) >= size or pending_words + unit_words > max_words or gap > max_gap_seconds):
            flush()
        pending.append(unit)
    flush()
    return packed
