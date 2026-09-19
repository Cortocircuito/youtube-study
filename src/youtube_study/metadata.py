from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import VideoDataError
from .models import PersistedVideoInfo, SourceSubtitleData, VideoMetadata


def _optional_text(data: Mapping[str, Any], field: str, source: str) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise VideoDataError(f"{source}: '{field}' debe ser texto o null")
    return value or None


def _optional_duration(data: Mapping[str, Any], source: str) -> int | float | None:
    value = data.get("duration")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise VideoDataError(f"{source}: 'duration' debe ser un número no negativo o null")
    return value


def normalize_video_metadata(data: Mapping[str, Any], *, source: str, expected_id: str | None = None) -> VideoMetadata:
    raw_id = data.get("id")
    if raw_id is None and expected_id:
        video_id = expected_id
    elif not isinstance(raw_id, str) or not raw_id:
        raise VideoDataError(f"{source}: 'id' debe ser texto no vacío")
    else:
        video_id = raw_id
    if expected_id and video_id != expected_id:
        raise VideoDataError(f"{source}: el id '{video_id}' no coincide con el video esperado '{expected_id}'")

    title = _optional_text(data, "title", source) or video_id
    return VideoMetadata(
        id=video_id,
        title=title,
        uploader=_optional_text(data, "uploader", source),
        duration=_optional_duration(data, source),
        webpage_url=_optional_text(data, "webpage_url", source),
    )


def metadata_from_ytdlp(data: Any) -> VideoMetadata:
    if not isinstance(data, Mapping):
        raise VideoDataError("Metadata de yt-dlp inválida: se esperaba un objeto")
    return normalize_video_metadata(data, source="Metadata de yt-dlp")


def _validate_source_subtitle(value: Any, source: str) -> SourceSubtitleData | None:
    if value is None:
        return None
    if isinstance(value, str):
        if not value:
            raise VideoDataError(f"{source}: 'source_subtitle' no puede ser texto vacío")
        return value
    if not isinstance(value, dict):
        raise VideoDataError(f"{source}: 'source_subtitle' debe ser texto, objeto o null")
    for field in ("path", "language"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise VideoDataError(f"{source}: source_subtitle.{field} debe ser texto no vacío")
    for field in ("kind", "reason"):
        if field in value and not isinstance(value[field], str):
            raise VideoDataError(f"{source}: source_subtitle.{field} debe ser texto")
    if (
        "source_language" in value
        and value["source_language"] is not None
        and not isinstance(value["source_language"], str)
    ):
        raise VideoDataError(f"{source}: source_subtitle.source_language debe ser texto o null")
    if "is_translation" in value and not isinstance(value["is_translation"], bool):
        raise VideoDataError(f"{source}: source_subtitle.is_translation debe ser booleano")
    return value


def persisted_video_from_mapping(data: Any, *, expected_id: str, source: str) -> PersistedVideoInfo:
    if not isinstance(data, Mapping):
        raise VideoDataError(f"{source}: se esperaba un objeto JSON")
    metadata = normalize_video_metadata(data, source=source, expected_id=expected_id)
    analysis = data.get("analysis")
    if analysis is not None:
        if not isinstance(analysis, Mapping):
            raise VideoDataError(f"{source}: 'analysis' debe ser un objeto")
        value = analysis.get("format_version")
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
            raise VideoDataError(f"{source}: analysis.format_version debe ser un entero positivo")
    return PersistedVideoInfo(
        metadata=metadata,
        source_subtitle=_validate_source_subtitle(data.get("source_subtitle"), source),
    )


def load_persisted_video(path: Path, expected_id: str) -> PersistedVideoInfo:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise VideoDataError(f"info.json inválido para {expected_id}: JSON malformado en {path}") from exc
    except OSError as exc:
        raise VideoDataError(f"No se pudo leer info.json para {expected_id}: {path}") from exc
    return persisted_video_from_mapping(data, expected_id=expected_id, source=f"info.json de {expected_id}")
