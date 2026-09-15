from __future__ import annotations

import json
import os
import shutil
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analyzer import ToolMention
from .errors import AppError
from .models import LibraryEntry, VideoInfo


class LibraryError(AppError):
    """Expected error while reading or writing the local video library."""


@dataclass
class RebuildResult:
    rebuilt: int
    skipped: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def library_path_from_videos_dir(videos_dir: Path) -> Path:
    """Return the library path for a videos directory like data/videos."""
    return videos_dir.parent / "library.json"


def _empty_library() -> dict[str, list[dict[str, Any]]]:
    return {"videos": []}


def _backup_invalid_library(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    suffix = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}-{suffix}")
        suffix += 1
    shutil.copy2(path, backup)
    return backup


def load_library(path: Path) -> dict[str, Any]:
    """Load local library, preserving a backup and recovering from invalid JSON."""
    if not path.exists() or path.stat().st_size == 0:
        return _empty_library()
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        try:
            backup = _backup_invalid_library(path)
        except OSError as backup_error:
            raise LibraryError(f"No se pudo leer ni respaldar la biblioteca: {path}") from backup_error
        recovered = _empty_library()
        save_library(path, recovered)
        warnings.warn(
            f"La biblioteca estaba dañada y se respaldó en {backup}. Se creó una biblioteca vacía.",
            RuntimeWarning,
            stacklevel=2,
        )
        return recovered

    if not isinstance(data, dict) or not isinstance(data.get("videos", []), list):
        backup = _backup_invalid_library(path)
        recovered = _empty_library()
        save_library(path, recovered)
        warnings.warn(
            f"La estructura de la biblioteca era inválida y se respaldó en {backup}. Se creó una biblioteca vacía.",
            RuntimeWarning,
            stacklevel=2,
        )
        return recovered
    return data


def save_library(path: Path, data: dict[str, Any]) -> None:
    """Atomically replace the local JSON library to prevent partial writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as file:
            temp_name = file.name
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except OSError as exc:
        raise LibraryError(f"No se pudo guardar la biblioteca en {path}") from exc
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def _relative_video_path(library_path: Path, video_dir: Path) -> str:
    try:
        return str(video_dir.resolve().relative_to(library_path.parent.resolve()))
    except ValueError:
        return str(video_dir)


def resolve_video_path(library_path: Path, stored_path: str | Path) -> Path:
    """Resolve current portable paths and legacy paths saved relative to repo root."""
    candidate = Path(stored_path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    data_dir = library_path.parent
    if candidate.parts and candidate.parts[0] == data_dir.name:
        return data_dir.parent / candidate
    return data_dir / candidate


def list_videos(path: Path) -> list[LibraryEntry]:
    return load_library(path).get("videos", [])


def get_video(path: Path, video_id: str) -> LibraryEntry | None:
    for video in list_videos(path):
        if video.get("id") == video_id:
            return video
    return None


def _video_entry(
    info: VideoInfo,
    video_dir: Path,
    library_path: Path,
    tools: list[str],
    created_at: str,
    updated_at: str,
) -> LibraryEntry:
    video_id = info.get("id")
    if not video_id:
        raise LibraryError("No se puede registrar video sin id")
    return {
        "id": video_id,
        "title": info.get("title") or video_id,
        "channel": info.get("uploader"),
        "duration": info.get("duration"),
        "url": info.get("webpage_url"),
        "path": _relative_video_path(library_path, video_dir),
        "tools": tools,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def upsert_video(path: Path, info: VideoInfo, video_dir: Path, tools: list[ToolMention]) -> LibraryEntry:
    """Insert or update one video in the local library, deduplicated by id."""
    data = load_library(path)
    now = utc_now()
    video_id = info.get("id")
    if not video_id:
        raise LibraryError("No se puede registrar video sin id")

    existing = next((item for item in data["videos"] if item.get("id") == video_id), None)
    entry = _video_entry(
        info,
        video_dir,
        path,
        [tool.name for tool in tools],
        existing.get("created_at", now) if existing else now,
        now,
    )
    if existing:
        existing.clear()
        existing.update(entry)
    else:
        data["videos"].append(entry)
    data["videos"].sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    save_library(path, data)
    return entry


def rebuild_library(path: Path, videos_dir: Path) -> RebuildResult:
    """Rebuild the library from per-video metadata without reading transcripts."""
    previous = {str(video.get("id")): video for video in list_videos(path) if video.get("id")}
    videos: list[dict[str, Any]] = []
    skipped: list[str] = []
    now = utc_now()
    if not videos_dir.exists():
        save_library(path, _empty_library())
        return RebuildResult(0, skipped)

    for video_dir in sorted(path for path in videos_dir.iterdir() if path.is_dir()):
        info_path = video_dir / "info.json"
        if not info_path.exists():
            skipped.append(f"{video_dir.name}: falta info.json")
            continue
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(f"{video_dir.name}: info.json inválido")
            continue
        info.setdefault("id", video_dir.name)
        previous_entry = previous.get(str(info["id"]), {})
        try:
            videos.append(
                _video_entry(
                    info,
                    video_dir,
                    path,
                    list(previous_entry.get("tools") or []),
                    previous_entry.get("created_at") or now,
                    now,
                )
            )
        except LibraryError as exc:
            skipped.append(f"{video_dir.name}: {exc}")

    videos.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    save_library(path, {"videos": videos})
    return RebuildResult(len(videos), skipped)
