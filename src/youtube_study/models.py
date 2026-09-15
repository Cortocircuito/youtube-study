from __future__ import annotations

from typing import Any, TypedDict


class VideoInfo(TypedDict, total=False):
    """Metadata received from yt-dlp or persisted in a video's info.json."""

    id: str
    title: str
    uploader: str
    duration: int | float
    webpage_url: str
    subtitles: dict[str, list[dict[str, Any]]]
    automatic_captions: dict[str, list[dict[str, Any]]]
    source_subtitle: str | dict[str, Any]
    analysis: dict[str, Any]


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
