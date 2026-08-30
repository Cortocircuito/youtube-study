from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analyzer import ToolMention


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def library_path_from_videos_dir(videos_dir: Path) -> Path:
    """Return the library path for a videos directory like data/videos."""
    return videos_dir.parent / "library.json"


def load_library(path: Path) -> dict[str, Any]:
    """Load library JSON, returning an empty structure when missing/empty."""
    if not path.exists() or path.stat().st_size == 0:
        return {"videos": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"videos": []}
    videos = data.get("videos")
    if not isinstance(videos, list):
        data["videos"] = []
    return data


def save_library(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_video(path: Path, info: dict[str, Any], video_dir: Path, tools: list[ToolMention]) -> dict[str, Any]:
    """Insert or update one video in the local library, deduplicated by id."""
    data = load_library(path)
    now = utc_now()
    video_id = info.get("id")
    if not video_id:
        raise ValueError("No se puede registrar video sin id")

    existing = next((item for item in data["videos"] if item.get("id") == video_id), None)
    created_at = existing.get("created_at") if existing else now
    entry = {
        "id": video_id,
        "title": info.get("title") or video_id,
        "channel": info.get("uploader"),
        "duration": info.get("duration"),
        "url": info.get("webpage_url"),
        "path": str(video_dir),
        "tools": [tool.name for tool in tools],
        "created_at": created_at,
        "updated_at": now,
    }

    if existing:
        existing.clear()
        existing.update(entry)
    else:
        data["videos"].append(entry)

    data["videos"].sort(key=lambda item: (item.get("updated_at") or ""), reverse=True)
    save_library(path, data)
    return entry
