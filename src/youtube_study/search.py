from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SearchResult:
    video_id: str
    title: str
    timestamp: str
    line: str
    context_before: list[str]
    context_after: list[str]


def parse_transcript_line(line: str) -> tuple[str, str]:
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", line.strip())
    if match:
        return match.group(1), match.group(2)
    return "", line.strip()


def search_transcript(
    transcript_path: Path,
    query: str,
    *,
    video_id: str,
    title: str,
    limit: int = 10,
    context: int = 0,
) -> list[SearchResult]:
    if not transcript_path.exists():
        return []

    lines = transcript_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    query_lower = query.lower()
    results: list[SearchResult] = []

    for index, line in enumerate(lines):
        if query_lower not in line.lower():
            continue
        timestamp, text = parse_transcript_line(line)
        before = lines[max(0, index - context):index] if context > 0 else []
        after = lines[index + 1:index + 1 + context] if context > 0 else []
        results.append(
            SearchResult(
                video_id=video_id,
                title=title,
                timestamp=timestamp,
                line=text,
                context_before=before,
                context_after=after,
            )
        )
        if len(results) >= limit:
            break
    return results


def search_library(
    videos: list[dict[str, Any]],
    query: str,
    *,
    video_id: str | None = None,
    limit: int = 10,
    context: int = 0,
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for video in videos:
        current_id = str(video.get("id") or "")
        if video_id and current_id != video_id:
            continue
        video_dir = Path(str(video.get("path") or ""))
        remaining = limit - len(results)
        if remaining <= 0:
            break
        results.extend(
            search_transcript(
                video_dir / "transcript.txt",
                query,
                video_id=current_id,
                title=str(video.get("title") or current_id),
                limit=remaining,
                context=context,
            )
        )
    return results
