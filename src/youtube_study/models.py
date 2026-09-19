from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias, TypedDict

SourceSubtitleData: TypeAlias = str | dict[str, Any]


@dataclass(frozen=True)
class VideoMetadata:
    """Normalized video metadata used by the application core."""

    id: str
    title: str
    uploader: str | None = None
    duration: int | float | None = None
    webpage_url: str | None = None


@dataclass(frozen=True)
class PersistedVideoInfo:
    """Validated contents needed from one video's info.json."""

    metadata: VideoMetadata
    source_subtitle: SourceSubtitleData | None = None

    def subtitle_selection_info(self) -> dict[str, Any]:
        return {"source_subtitle": self.source_subtitle} if self.source_subtitle is not None else {}


class LibraryEntry(TypedDict, total=False):
    """Portable entry stored in data/library.json."""

    id: str
    title: str
    channel: str | None
    duration: int | float | None
    url: str | None
    path: str
    tools: list[str]
    created_at: str
    updated_at: str
