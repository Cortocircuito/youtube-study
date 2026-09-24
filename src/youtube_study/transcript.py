from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Cue:
    start: str
    text: str


def seconds_from_timestamp(ts: str) -> int:
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = "0", parts[0], parts[1]
    else:
        raise ValueError(f"Timestamp inválido: {ts}")
    try:
        return int(h) * 3600 + int(m) * 60 + int(float(s))
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"Timestamp inválido: {ts}") from exc


def timestamp_from_seconds(total: int) -> str:
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


ALIASES = {
    r"\bmoshie\b": "Moshi",
    r"\bherder\b": "Herdr",
    r"\bgerd\b": "Herdr",
    r"\bclou\b": "Claude",
}


def normalize_aliases(text: str) -> str:
    for pattern, replacement in ALIASES.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def clean_vtt(path: Path) -> list[Cue]:
    cues: list[Cue] = []
    current_time = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_time, current_lines
        if current_time and current_lines:
            cleaned_lines = []
            for line in current_lines:
                line = html.unescape(line).replace("\xa0", " ")
                line = re.sub(r"<[^>]+>", "", line)
                line = re.sub(r"&nbsp;", " ", line)
                line = re.sub(r"\s+", " ", line).strip()
                if line:
                    cleaned_lines.append(line)
            text = merge_caption_lines(cleaned_lines)
            if text:
                cues.append(Cue(current_time, text))
        current_time = ""
        current_lines = []

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            flush()
            continue
        if "-->" in line:
            flush()
            current_time = line.split("-->", 1)[0].strip().split(".", 1)[0]
            continue
        if not re.fullmatch(r"\d+", line):
            current_lines.append(line)
    flush()

    return remove_rolling_overlaps(cues)


def merge_caption_lines(lines: list[str]) -> str:
    """Merge cue lines avoiding duplicated rolling-caption prefixes."""
    if not lines:
        return ""
    merged = lines[0]
    for line in lines[1:]:
        if line.startswith(merged):
            merged = line
        elif merged.startswith(line):
            continue
        else:
            merged = f"{merged} {line}"
    return merged.strip()


def remove_rolling_overlaps(cues: list[Cue]) -> list[Cue]:
    """Reduce duplicated text produced by YouTube rolling auto-captions."""
    result: list[Cue] = []
    previous_words: list[str] = []
    previous_start: int | None = None
    for cue in cues:
        words = cue.text.split()
        if not words:
            continue
        cue_start = seconds_from_timestamp(cue.start)
        if previous_start is None or cue_start - previous_start > 15:
            previous_words = []
        previous_norm = [word.lower().strip('.,;:!?¿¡()[]{}"') for word in previous_words]
        words_norm = [word.lower().strip('.,;:!?¿¡()[]{}"') for word in words]
        if words_norm == previous_norm or (previous_norm and previous_norm[-len(words_norm) :] == words_norm):
            previous_start = cue_start
            continue
        # Remove overlap between previous tail and current head, ignoring punctuation/case.
        overlap = 0
        max_overlap = min(len(previous_norm), len(words_norm))
        for size in range(max_overlap, 0, -1):
            if previous_norm[-size:] == words_norm[:size]:
                overlap = size
                break
        new_words = words[overlap:]
        if new_words:
            result.append(Cue(cue.start, " ".join(new_words)))
            previous_words.extend(new_words)
            previous_words = previous_words[-80:]
        previous_start = cue_start
    return result


def as_text(cues: list[Cue], timestamps: bool = True) -> str:
    if timestamps:
        return "\n".join(f"[{cue.start}] {cue.text}" for cue in cues) + "\n"
    return "\n".join(cue.text for cue in cues) + "\n"


def chunk_by_minutes(cues: list[Cue], minutes: int = 5) -> list[tuple[str, str, str]]:
    if not cues:
        return []
    size = minutes * 60
    chunks: list[tuple[str, str, str]] = []
    bucket_start: int | None = None
    bucket: list[str] = []

    for cue in cues:
        sec = seconds_from_timestamp(cue.start)
        cue_bucket_start = (sec // size) * size
        if bucket_start is not None and cue_bucket_start != bucket_start:
            chunks.append(
                (timestamp_from_seconds(bucket_start), timestamp_from_seconds(bucket_start + size), " ".join(bucket))
            )
            bucket = []
        bucket_start = cue_bucket_start
        bucket.append(cue.text)
    if bucket and bucket_start is not None:
        chunks.append(
            (timestamp_from_seconds(bucket_start), timestamp_from_seconds(bucket_start + size), " ".join(bucket))
        )
    return chunks
