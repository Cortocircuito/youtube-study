from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from .analyzer import analyze_cues
from .downloader import SubtitleSelection, choose_subtitle, download_subtitles
from .errors import VideoDataError
from .exporter import (
    write_anki_csv,
    write_clean_transcript,
    write_concepts,
    write_concepts_json,
    write_flashcards,
    write_info,
    write_questions,
    write_study_guide,
    write_study_markdown_from_result,
    write_summary,
    write_tools,
    write_tools_json,
    write_transcript,
    write_transcript_paragraphs,
)
from .library import library_path_from_videos_dir, upsert_video
from .models import VideoInfo
from .study_models import AnalysisResult
from .transcript import clean_vtt

GENERATED_ARTIFACTS = (
    "info.json",
    "transcript.txt",
    "transcript.clean.txt",
    "transcript.paragraphs.md",
    "summary.md",
    "tools.md",
    "tools.json",
    "concepts.md",
    "concepts.json",
    "questions.md",
    "flashcards.md",
    "study-guide.md",
    "study.md",
    "anki.csv",
)


def requested_languages(languages: str) -> list[str]:
    return [language.strip() for language in languages.split(",") if language.strip()]


def _write_study_files(info: VideoInfo, output_dir: Path, subtitle: SubtitleSelection) -> AnalysisResult:
    video_id = info["id"]
    result = analyze_cues(clean_vtt(subtitle.path))
    if not result.cues:
        raise VideoDataError(f"El subtítulo seleccionado no contiene texto utilizable: {subtitle.path}")
    title = info.get("title", video_id)
    source_url = info.get("webpage_url")

    write_info(output_dir / "info.json", info, subtitle, analysis_version=result.format_version)
    write_transcript(output_dir / "transcript.txt", result.cues)
    write_clean_transcript(output_dir / "transcript.clean.txt", result.cues)
    write_transcript_paragraphs(output_dir / "transcript.paragraphs.md", result.cues)
    write_summary(output_dir / "summary.md", title, result.keywords, result.ideas, result.sections, source_url)
    write_tools(output_dir / "tools.md", result.tools)
    write_tools_json(output_dir / "tools.json", result.tools)
    write_concepts(output_dir / "concepts.md", result.sections)
    write_concepts_json(output_dir / "concepts.json", result.concepts)
    write_questions(output_dir / "questions.md", result.questions, source_url)
    write_flashcards(output_dir / "flashcards.md", result.cards, source_url)
    write_study_guide(output_dir / "study-guide.md", title, result.tools, result.questions)
    write_study_markdown_from_result(output_dir / "study.md", title, result, source_url)
    write_anki_csv(output_dir / "anki.csv", result.cards, video_id, info.get("uploader"), source_url)
    return result


def _publish_staged_files(staging_dir: Path, video_dir: Path) -> None:
    """Publish one complete generation and restore previous files if replacement fails."""
    video_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix=f".{video_dir.name}.backup-", dir=video_dir.parent))
    published: list[str] = []
    backed_up: list[str] = []
    keep_backup = False
    try:
        for name in GENERATED_ARTIFACTS:
            destination = video_dir / name
            if destination.exists():
                os.replace(destination, backup_dir / name)
                backed_up.append(name)
        for name in GENERATED_ARTIFACTS:
            os.replace(staging_dir / name, video_dir / name)
            published.append(name)
    except OSError:
        for name in published:
            (video_dir / name).unlink(missing_ok=True)
        try:
            for name in backed_up:
                backup = backup_dir / name
                if backup.exists():
                    os.replace(backup, video_dir / name)
        except OSError as rollback_error:
            keep_backup = True
            raise VideoDataError(
                f"Falló la publicación y no se pudo restaurar completamente. Respaldo conservado en {backup_dir}"
            ) from rollback_error
        raise
    finally:
        if not keep_backup:
            shutil.rmtree(backup_dir, ignore_errors=True)


def generate_study_files(info: VideoInfo, video_dir: Path, subtitle: SubtitleSelection, library_path: Path) -> Path:
    video_id = info.get("id")
    if not video_id:
        raise VideoDataError("No se puede analizar un video sin id.")
    video_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{video_id}.staging-", dir=video_dir.parent) as temp_dir:
        staging_dir = Path(temp_dir)
        result = _write_study_files(info, staging_dir, subtitle)
        _publish_staged_files(staging_dir, video_dir)

    upsert_video(library_path, info, video_dir, result.tools)
    return video_dir


def process_video(url: str, out: Path, languages: str, *, force_download: bool = False, quiet: bool = False) -> Path:
    info: VideoInfo = download_subtitles(url, out, languages, force_download=force_download, quiet=quiet)
    video_id = info.get("id")
    if not video_id:
        raise VideoDataError("YouTube no devolvió un id para el video solicitado.")
    video_dir = out / video_id
    subtitle = choose_subtitle(video_dir, video_id, requested_languages(languages), info=info)
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def load_existing_video(video_id: str, out: Path, languages: str) -> tuple[VideoInfo, Path, SubtitleSelection]:
    video_dir = out / video_id
    if not video_dir.exists():
        raise VideoDataError(f"No existe el directorio del video: {video_dir}")
    info_path = video_dir / "info.json"
    if not info_path.exists():
        raise VideoDataError(f"No existe info.json para {video_id}: {info_path}")
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VideoDataError(f"info.json inválido para {video_id}: {info_path}") from exc
    if not isinstance(info, dict):
        raise VideoDataError(f"info.json inválido para {video_id}: se esperaba un objeto JSON")
    info.setdefault("id", video_id)
    subtitle = choose_subtitle(video_dir, video_id, requested_languages(languages), info=info)
    return info, video_dir, subtitle


def analyze_existing(video_id: str, out: Path, languages: str) -> Path:
    info, video_dir, subtitle = load_existing_video(video_id, out, languages)
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def export_study(video_id: str, out: Path, languages: str, export_format: str) -> list[Path]:
    info, video_dir, subtitle = load_existing_video(video_id, out, languages)
    result = analyze_cues(clean_vtt(subtitle.path))
    title = info.get("title", video_id)
    source_url = info.get("webpage_url")
    written: list[Path] = []
    if export_format in {"markdown", "all"}:
        study_path = video_dir / "study.md"
        write_study_markdown_from_result(study_path, title, result, source_url)
        written.append(study_path)
    if export_format in {"anki", "all"}:
        anki_path = video_dir / "anki.csv"
        write_anki_csv(anki_path, result.cards, video_id, info.get("uploader"), source_url)
        written.append(anki_path)
    return written
