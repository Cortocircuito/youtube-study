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
    else:
        h, m, s = "0", parts[0], parts[1]
    return int(h) * 3600 + int(m) * 60 + int(float(s))


def timestamp_from_seconds(total: int) -> str:
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


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
    for cue in cues:
        words = cue.text.split()
        if not words:
            continue
        if words == previous_words or (previous_words and previous_words[-len(words):] == words):
            continue
        # Remove overlap between previous tail and current head.
        overlap = 0
        max_overlap = min(len(previous_words), len(words))
        for size in range(max_overlap, 0, -1):
            if previous_words[-size:] == words[:size]:
                overlap = size
                break
        new_words = words[overlap:]
        if new_words:
            result.append(Cue(cue.start, " ".join(new_words)))
            previous_words.extend(new_words)
            previous_words = previous_words[-80:]
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
    bucket_start = (seconds_from_timestamp(cues[0].start) // size) * size
    bucket: list[str] = []

    for cue in cues:
        sec = seconds_from_timestamp(cue.start)
        while sec >= bucket_start + size and bucket:
            chunks.append((timestamp_from_seconds(bucket_start), timestamp_from_seconds(bucket_start + size), " ".join(bucket)))
            bucket = []
            bucket_start += size
        bucket.append(cue.text)
    if bucket:
        chunks.append((timestamp_from_seconds(bucket_start), timestamp_from_seconds(bucket_start + size), " ".join(bucket)))
    return chunks
