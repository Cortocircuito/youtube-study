from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from yt_dlp.version import __version__ as YTDLP_VERSION

from .errors import SubtitleError
from .models import VideoInfo

MIN_YTDLP_VERSION = (2025, 1, 1)


@dataclass(frozen=True)
class SubtitleCandidate:
    path: Path
    language: str
    kind: str  # manual, automatic, unknown
    is_translation: bool = False
    source_language: str | None = None


@dataclass(frozen=True)
class SubtitleSelection:
    path: Path
    language: str
    kind: str
    reason: str
    is_translation: bool = False
    source_language: str | None = None


def version_parts(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def warn_if_outdated_ytdlp() -> None:
    if version_parts(YTDLP_VERSION) < MIN_YTDLP_VERSION:
        warnings.warn(
            f"yt-dlp {YTDLP_VERSION} puede estar desactualizado. "
            "Activa el venv e instala las dependencias con: pip install -r requirements.txt",
            RuntimeWarning,
            stacklevel=2,
        )


def download_subtitles(
    url: str,
    out_dir: Path,
    langs: str = "es-419,es,es-orig",
    *,
    force_download: bool = False,
    quiet: bool = False,
) -> VideoInfo:
    """Download subtitles/captions for a YouTube video using yt-dlp."""
    warn_if_outdated_ytdlp()
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [x.strip() for x in langs.split(",") if x.strip()],
        "subtitlesformat": "vtt",
        "outtmpl": str(out_dir / "%(id)s" / "%(id)s.%(ext)s"),
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": quiet,
        "overwrites": force_download,
        "ignore_no_formats_error": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise SubtitleError(
            "No se pudieron descargar los subtítulos. Comprueba la URL, los idiomas solicitados, "
            "los límites de YouTube y que yt-dlp esté actualizado en el venv."
        ) from exc
    if not info:
        raise SubtitleError("YouTube no devolvió información para el video solicitado.")
    return info


def _language_base(language: str) -> str:
    return language.removesuffix("-orig").split("-", 1)[0].lower()


def _language_matches(candidate_language: str, requested_language: str) -> bool:
    candidate = candidate_language.lower()
    requested = requested_language.lower()
    return (
        candidate == requested
        or candidate == f"{requested}-orig"
        or _language_base(candidate) == _language_base(requested)
    )


def _language_rank(candidate_language: str, requested_language: str) -> int:
    candidate = candidate_language.lower()
    requested = requested_language.lower()
    if candidate == requested:
        return 0
    if candidate == f"{requested}-orig":
        return 1
    if _language_base(candidate) == _language_base(requested):
        return 2
    return 99


def _candidate_path(video_dir: Path, video_id: str, language: str) -> Path | None:
    exact = video_dir / f"{video_id}.{language}.vtt"
    if exact.exists():
        return exact
    matches = sorted(video_dir.glob(f"{video_id}.{language}*.vtt"))
    return matches[0] if matches else None


def _has_vtt_format(formats: Any) -> bool:
    if not isinstance(formats, list) or not formats:
        return True
    return any(format_item.get("ext") == "vtt" for format_item in formats if isinstance(format_item, dict))


def _format_metadata(formats: Any) -> dict[str, Any]:
    if isinstance(formats, list):
        for format_item in formats:
            if isinstance(format_item, dict) and (format_item.get("ext") == "vtt" or "ext" not in format_item):
                return format_item
    return {}


def _is_translation(language: str, kind: str, metadata: dict[str, Any]) -> bool:
    if kind != "automatic":
        return False
    explicit = metadata.get("is_translation", metadata.get("is_translated"))
    if explicit is not None:
        return bool(explicit)
    source_language = metadata.get("source_language")
    if source_language:
        return _language_base(str(source_language)) != _language_base(language)
    if language.endswith("-orig"):
        return False
    return False


def _source_language(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("source_language")
    return str(value) if value else None


def subtitle_inventory(info: dict[str, Any] | None, video_dir: Path, video_id: str) -> list[SubtitleCandidate]:
    """Build a subtitle inventory from yt-dlp metadata, falling back to local files."""
    candidates_by_path: dict[Path, SubtitleCandidate] = {}
    info = info or {}
    sources = [
        (info.get("subtitles"), "manual"),
        (info.get("automatic_captions"), "automatic"),
    ]
    for subtitles, kind in sources:
        if not isinstance(subtitles, dict):
            continue
        for language, formats in subtitles.items():
            if not isinstance(language, str) or not _has_vtt_format(formats):
                continue
            path = _candidate_path(video_dir, video_id, language)
            if not path:
                continue
            metadata = _format_metadata(formats)
            candidate = SubtitleCandidate(
                path=path,
                language=language,
                kind=kind,
                is_translation=_is_translation(language, kind, metadata),
                source_language=_source_language(metadata),
            )
            previous = candidates_by_path.get(path)
            if not previous or previous.kind == "unknown" or (previous.kind == "automatic" and kind == "manual"):
                candidates_by_path[path] = candidate

    for path in sorted(video_dir.glob(f"{video_id}.*.vtt")):
        if path in candidates_by_path:
            continue
        language = path.name.removeprefix(f"{video_id}.").removesuffix(".vtt")
        candidates_by_path[path] = SubtitleCandidate(path=path, language=language, kind="unknown")

    return sorted(candidates_by_path.values(), key=lambda candidate: candidate.path.name)


def _selection_from_info(
    info: dict[str, Any] | None, video_dir: Path, preferred_langs: list[str]
) -> SubtitleSelection | None:
    if not isinstance(info, dict):
        return None
    source = info.get("source_subtitle")
    if not isinstance(source, dict):
        return None
    path_value = source.get("path")
    language = str(source.get("language") or "")
    if not path_value or not language:
        return None
    if preferred_langs and not any(_language_matches(language, requested) for requested in preferred_langs):
        return None
    path = Path(path_value)
    if not path.is_absolute() and not path.exists():
        path = video_dir / path.name
    if not path.exists():
        return None
    return SubtitleSelection(
        path=path,
        language=language,
        kind=str(source.get("kind") or "unknown"),
        reason=str(source.get("reason") or "selección registrada en info.json"),
        is_translation=bool(source.get("is_translation", False)),
        source_language=source.get("source_language"),
    )


def _select_for_requested(
    candidates: list[SubtitleCandidate],
    preferred_langs: list[str],
    *,
    kind: str,
    translation: bool | None,
    reason: str,
) -> SubtitleSelection | None:
    for requested in preferred_langs:
        matches = [
            candidate
            for candidate in candidates
            if candidate.kind == kind
            and _language_matches(candidate.language, requested)
            and (translation is None or candidate.is_translation is translation)
        ]
        if matches:
            selected = min(
                matches, key=lambda candidate: (_language_rank(candidate.language, requested), candidate.path.name)
            )
            return SubtitleSelection(
                path=selected.path,
                language=selected.language,
                kind=selected.kind,
                reason=reason,
                is_translation=selected.is_translation,
                source_language=selected.source_language,
            )
    return None


def _select_english(candidates: list[SubtitleCandidate]) -> SubtitleSelection | None:
    matches = [candidate for candidate in candidates if _language_base(candidate.language) == "en"]
    if not matches:
        return None
    kind_rank = {"manual": 0, "automatic": 1, "unknown": 2}
    selected = min(
        matches, key=lambda candidate: (kind_rank.get(candidate.kind, 3), candidate.is_translation, candidate.path.name)
    )
    return SubtitleSelection(
        path=selected.path,
        language=selected.language,
        kind=selected.kind,
        reason="fallback a subtítulo en inglés",
        is_translation=selected.is_translation,
        source_language=selected.source_language,
    )


def choose_subtitle(
    video_dir: Path,
    video_id: str,
    preferred_langs: list[str],
    info: dict[str, Any] | None = None,
) -> SubtitleSelection:
    """Choose captions using metadata when available, with legacy file fallback."""
    preferred_langs = [language for language in preferred_langs if language]
    registered = _selection_from_info(info, video_dir, preferred_langs)
    if registered:
        return registered

    candidates = subtitle_inventory(info, video_dir, video_id)
    if not candidates:
        raise SubtitleError(
            f"No se descargó ningún subtítulo .vtt en {video_dir}. "
            "Prueba otros idiomas con --lang o verifica que el video tenga subtítulos."
        )

    selectors = [
        ("manual", False, "subtítulo manual en idioma solicitado"),
        ("automatic", False, "subtítulo automático original en idioma solicitado"),
        ("automatic", True, "traducción automática en idioma solicitado"),
    ]
    for kind, translation, reason in selectors:
        selected = _select_for_requested(candidates, preferred_langs, kind=kind, translation=translation, reason=reason)
        if selected:
            return selected

    legacy = _select_for_requested(
        candidates,
        preferred_langs,
        kind="unknown",
        translation=False,
        reason="subtítulo local en idioma solicitado sin metadata",
    )
    if legacy:
        return legacy

    english = _select_english(candidates)
    if english:
        return english

    fallback = max(candidates, key=lambda candidate: candidate.path.stat().st_size)
    return SubtitleSelection(
        path=fallback.path,
        language=fallback.language,
        kind=fallback.kind,
        reason="fallback controlado al subtítulo local más grande",
        is_translation=fallback.is_translation,
        source_language=fallback.source_language,
    )
