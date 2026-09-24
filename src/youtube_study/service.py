from __future__ import annotations

from pathlib import Path

from .analyzer import analyze_cues
from .artifacts import publish_artifacts, staging_directory
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
from .metadata import load_persisted_video, metadata_from_ytdlp
from .models import VideoMetadata
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


def _analyze_subtitle(subtitle: SubtitleSelection) -> AnalysisResult:
    try:
        result = analyze_cues(clean_vtt(subtitle.path))
    except ValueError as exc:
        raise VideoDataError(f"No se pudo analizar el subtítulo seleccionado: {subtitle.path}") from exc
    if not result.cues:
        raise VideoDataError(f"El subtítulo seleccionado no contiene texto utilizable: {subtitle.path}")
    return result


def _render_study_files(
    metadata: VideoMetadata, output_dir: Path, subtitle: SubtitleSelection, result: AnalysisResult
) -> None:
    video_id = metadata.id
    title = metadata.title
    source_url = metadata.webpage_url

    write_info(output_dir / "info.json", metadata, subtitle, analysis_version=result.format_version)
    write_transcript(output_dir / "transcript.txt", result.cues)
    write_clean_transcript(output_dir / "transcript.clean.txt", result.cues)
    write_transcript_paragraphs(output_dir / "transcript.paragraphs.md", result.cues)
    write_summary(output_dir / "summary.md", title, result.keywords, result.ideas, result.sections, source_url)
    write_tools(output_dir / "tools.md", result.tools)
    write_tools_json(output_dir / "tools.json", result.tools)
    write_concepts(output_dir / "concepts.md", result.concepts, source_url)
    write_concepts_json(output_dir / "concepts.json", result.concepts)
    write_questions(output_dir / "questions.md", result.questions, source_url)
    write_flashcards(output_dir / "flashcards.md", result.cards, source_url)
    write_study_guide(output_dir / "study-guide.md", title, result.tools, result.questions)
    write_study_markdown_from_result(output_dir / "study.md", title, result, source_url)
    write_anki_csv(output_dir / "anki.csv", result.cards, video_id, metadata.uploader, source_url)


def generate_study_files(
    metadata: VideoMetadata, video_dir: Path, subtitle: SubtitleSelection, library_path: Path
) -> Path:
    result = _analyze_subtitle(subtitle)
    with staging_directory(video_dir) as staging_dir:
        _render_study_files(metadata, staging_dir, subtitle, result)
        publish_artifacts(staging_dir, video_dir, GENERATED_ARTIFACTS, retry_command="study o analyze")

    upsert_video(library_path, metadata, video_dir, result.tools)
    return video_dir


def process_video(url: str, out: Path, languages: str, *, force_download: bool = False, quiet: bool = False) -> Path:
    info = download_subtitles(url, out, languages, force_download=force_download, quiet=quiet)
    metadata = metadata_from_ytdlp(info)
    video_id = metadata.id
    video_dir = out / video_id
    subtitle = choose_subtitle(video_dir, video_id, requested_languages(languages), info=info)
    return generate_study_files(metadata, video_dir, subtitle, library_path_from_videos_dir(out))


def load_existing_video(video_id: str, out: Path, languages: str) -> tuple[VideoMetadata, Path, SubtitleSelection]:
    video_dir = out / video_id
    if not video_dir.exists():
        raise VideoDataError(f"No existe el directorio del video: {video_dir}")
    info_path = video_dir / "info.json"
    if not info_path.exists():
        raise VideoDataError(f"No existe info.json para {video_id}: {info_path}")
    persisted = load_persisted_video(info_path, video_id)
    subtitle = choose_subtitle(
        video_dir,
        video_id,
        requested_languages(languages),
        info=persisted.subtitle_selection_info(),
    )
    return persisted.metadata, video_dir, subtitle


def analyze_existing(video_id: str, out: Path, languages: str) -> Path:
    metadata, video_dir, subtitle = load_existing_video(video_id, out, languages)
    return generate_study_files(metadata, video_dir, subtitle, library_path_from_videos_dir(out))


def export_study(video_id: str, out: Path, languages: str, export_format: str) -> list[Path]:
    metadata, video_dir, subtitle = load_existing_video(video_id, out, languages)
    result = _analyze_subtitle(subtitle)
    title = metadata.title
    source_url = metadata.webpage_url
    names: list[str] = []
    with staging_directory(video_dir) as staging_dir:
        if export_format in {"markdown", "all"}:
            write_study_markdown_from_result(staging_dir / "study.md", title, result, source_url)
            names.append("study.md")
        if export_format in {"anki", "all"}:
            write_anki_csv(staging_dir / "anki.csv", result.cards, video_id, metadata.uploader, source_url)
            names.append("anki.csv")
        if names:
            publish_artifacts(staging_dir, video_dir, names, retry_command="export")
    return [video_dir / name for name in names]
