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

from .errors import AppError
from .metadata import load_persisted_video
from .models import LibraryEntry, VideoMetadata
from .study_models import ToolMention


class LibraryError(AppError):
    """Expected error while reading or writing the local video library."""


class InvalidLibraryError(LibraryError):
    """The library contents are not valid JSON or do not match its schema."""


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


def _read_library(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        if not path.exists() or path.stat().st_size == 0:
            return _empty_library(), []
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidLibraryError(
            f"La biblioteca contiene JSON inválido: {path}. Ejecuta rebuild-library para reconstruirla."
        ) from exc
    except OSError as exc:
        raise LibraryError(f"No se pudo leer la biblioteca: {path}") from exc

    videos = data.get("videos") if isinstance(data, dict) else None
    if not isinstance(videos, list):
        raise InvalidLibraryError(
            f"La estructura de la biblioteca es inválida: {path}. Ejecuta rebuild-library para reconstruirla."
        )

    valid_videos: list[LibraryEntry] = []
    invalid_entries: list[str] = []
    for index, video in enumerate(videos):
        try:
            valid_videos.append(_validate_library_entry(video, index))
        except LibraryError as exc:
            invalid_entries.append(str(exc))
    return {**data, "videos": valid_videos}, invalid_entries


def load_library(path: Path) -> dict[str, Any]:
    """Load valid entries without modifying or repairing the library file."""
    data, invalid_entries = _read_library(path)
    if invalid_entries:
        warnings.warn(
            f"Se omitieron {len(invalid_entries)} entradas inválidas de la biblioteca: {'; '.join(invalid_entries)}",
            RuntimeWarning,
            stacklevel=2,
        )
    return data


def _validate_library_entry(value: Any, index: int) -> LibraryEntry:
    source = f"Entrada {index + 1} de la biblioteca"
    if not isinstance(value, dict):
        raise LibraryError(f"{source}: debe ser un objeto")

    video_id = value.get("id")
    if not isinstance(video_id, str) or not video_id:
        raise LibraryError(f"{source}: 'id' debe ser texto no vacío")
    path = value.get("path")
    if not isinstance(path, str) or not path:
        raise LibraryError(f"{source}: 'path' debe ser texto no vacío")

    title = value.get("title", video_id)
    if not isinstance(title, str) or not title:
        raise LibraryError(f"{source}: 'title' debe ser texto no vacío")
    for field in ("channel", "url"):
        if value.get(field) is not None and not isinstance(value[field], str):
            raise LibraryError(f"{source}: '{field}' debe ser texto o null")
    duration = value.get("duration")
    if duration is not None and (isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0):
        raise LibraryError(f"{source}: 'duration' debe ser un número no negativo o null")
    tools = value.get("tools", [])
    if not isinstance(tools, list) or any(not isinstance(tool, str) or not tool for tool in tools):
        raise LibraryError(f"{source}: 'tools' debe ser una lista de textos no vacíos")
    for field in ("created_at", "updated_at"):
        if field in value and (not isinstance(value[field], str) or not value[field]):
            raise LibraryError(f"{source}: '{field}' debe ser texto no vacío")

    entry: LibraryEntry = {
        "id": video_id,
        "title": title,
        "channel": value.get("channel"),
        "duration": duration,
        "url": value.get("url"),
        "path": path,
        "tools": list(tools),
    }
    if "created_at" in value:
        entry["created_at"] = value["created_at"]
    if "updated_at" in value:
        entry["updated_at"] = value["updated_at"]
    return entry


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
    metadata: VideoMetadata,
    video_dir: Path,
    library_path: Path,
    tools: list[str],
    created_at: str,
    updated_at: str,
) -> LibraryEntry:
    return {
        "id": metadata.id,
        "title": metadata.title,
        "channel": metadata.uploader,
        "duration": metadata.duration,
        "url": metadata.webpage_url,
        "path": _relative_video_path(library_path, video_dir),
        "tools": tools,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _same_library_content(left: LibraryEntry, right: LibraryEntry) -> bool:
    fields = ("id", "title", "channel", "duration", "url", "path", "tools")
    return all(left.get(field) == right.get(field) for field in fields)


def upsert_video(path: Path, metadata: VideoMetadata, video_dir: Path, tools: list[ToolMention]) -> LibraryEntry:
    """Insert or update one video in the local library, deduplicated by id."""
    data, invalid_entries = _read_library(path)
    if invalid_entries:
        raise InvalidLibraryError(
            f"La biblioteca contiene entradas inválidas. Ejecuta rebuild-library antes de actualizarla: {path}"
        )
    now = utc_now()
    video_id = metadata.id

    existing = next((item for item in data["videos"] if item.get("id") == video_id), None)
    entry = _video_entry(
        metadata,
        video_dir,
        path,
        [tool.name for tool in tools],
        (existing.get("created_at") or now) if existing else now,
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


def _tool_names_from_artifact(path: Path, fallback: list[str]) -> list[str]:
    if not path.exists():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        warnings.warn(
            f"No se pudo reconstruir herramientas desde {path}; se conserva el índice previo.", RuntimeWarning
        )
        return fallback
    except (json.JSONDecodeError, UnicodeDecodeError):
        warnings.warn(
            f"El archivo de herramientas contiene JSON inválido: {path}; se conserva el índice previo.", RuntimeWarning
        )
        return fallback
    if not isinstance(payload, list) or any(
        not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not tool["name"] for tool in payload
    ):
        warnings.warn(f"El archivo de herramientas es inválido: {path}; se conserva el índice previo.", RuntimeWarning)
        return fallback
    return list(dict.fromkeys(tool["name"] for tool in payload))


def rebuild_library(path: Path, videos_dir: Path) -> RebuildResult:
    """Rebuild the library from per-video metadata without reading transcripts."""
    needs_backup = False
    try:
        previous_data, invalid_entries = _read_library(path)
        needs_backup = bool(invalid_entries)
    except InvalidLibraryError:
        previous_data = _empty_library()
        needs_backup = True
    previous = {str(video.get("id")): video for video in previous_data["videos"] if video.get("id")}
    videos: list[dict[str, Any]] = []
    skipped: list[str] = []
    now = utc_now()
    if videos_dir.exists():
        for video_dir in sorted(path for path in videos_dir.iterdir() if path.is_dir()):
            info_path = video_dir / "info.json"
            if not info_path.exists():
                skipped.append(f"{video_dir.name}: falta info.json")
                continue
            try:
                persisted = load_persisted_video(info_path, video_dir.name)
                metadata = persisted.metadata
                previous_entry = previous.get(metadata.id, {})
                previous_tools = list(previous_entry.get("tools") or [])
                entry = _video_entry(
                    metadata,
                    video_dir,
                    path,
                    _tool_names_from_artifact(video_dir / "tools.json", previous_tools),
                    previous_entry.get("created_at") or now,
                    now,
                )
                if previous_entry and _same_library_content(previous_entry, entry):
                    entry["updated_at"] = previous_entry.get("updated_at") or now
                videos.append(entry)
            except AppError as exc:
                skipped.append(f"{video_dir.name}: {exc}")

    videos.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    if needs_backup and path.exists() and path.stat().st_size:
        try:
            _backup_invalid_library(path)
        except OSError as exc:
            raise LibraryError(f"No se pudo respaldar la biblioteca inválida: {path}") from exc
    save_library(path, {"videos": videos})
    return RebuildResult(len(videos), skipped)
