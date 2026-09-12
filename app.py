#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import json

from src.youtube_study.analyzer import analyze_cues
from src.youtube_study.downloader import SubtitleSelection, choose_subtitle, download_subtitles
from src.youtube_study.errors import AppError, VideoDataError
from src.youtube_study.exporter import (
    write_clean_transcript,
    write_concepts,
    write_concepts_json,
    write_flashcards,
    write_info,
    write_questions,
    write_anki_csv,
    write_study_guide,
    write_study_markdown_from_result,
    write_summary,
    write_tools,
    write_tools_json,
    write_transcript,
    write_transcript_paragraphs,
)
from src.youtube_study.library import (
    LibraryError,
    get_video,
    library_path_from_videos_dir,
    list_videos,
    rebuild_library,
    resolve_video_path,
    upsert_video,
)
from src.youtube_study.search import SearchResult, search_library
from src.youtube_study.transcript import clean_vtt


def format_duration(seconds: int | None) -> str:
    if not seconds:
        return "N/D"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def print_video_list(videos_dir: Path) -> None:
    videos = list_videos(library_path_from_videos_dir(videos_dir))
    if not videos:
        print("La biblioteca está vacía. Analiza un video con: python app.py URL")
        return
    for video in videos:
        tools = ", ".join(video.get("tools") or []) or "sin herramientas"
        print(f"{video.get('id')} | {format_duration(video.get('duration'))} | {video.get('title')}")
        print(f"  Canal: {video.get('channel') or 'N/D'}")
        print(f"  Herramientas: {tools}")
        print(f"  Ruta: {video.get('path')}")


def print_video_detail(videos_dir: Path, video_id: str) -> None:
    library_path = library_path_from_videos_dir(videos_dir)
    video = get_video(library_path, video_id)
    if not video:
        raise VideoDataError(f"No existe el video {video_id} en la biblioteca.")
    print(f"ID: {video.get('id')}")
    print(f"Título: {video.get('title')}")
    print(f"Canal: {video.get('channel') or 'N/D'}")
    print(f"Duración: {format_duration(video.get('duration'))}")
    print(f"URL: {video.get('url') or 'N/D'}")
    print(f"Ruta: {video.get('path')}")
    print(f"Herramientas: {', '.join(video.get('tools') or []) or 'N/D'}")
    print(f"Creado: {video.get('created_at')}")
    print(f"Actualizado: {video.get('updated_at')}")

    video_dir = resolve_video_path(library_path, video.get("path") or videos_dir / video_id)
    if video_dir.exists():
        print("\nArchivos disponibles:")
        for path in sorted(p for p in video_dir.iterdir() if p.is_file()):
            print(f"- {path.name}")


def print_search_results(results: list[SearchResult]) -> None:
    if not results:
        print("No se encontraron resultados.")
        return
    for result in results:
        location = f"{result.video_id}"
        if result.timestamp:
            location += f" [{result.timestamp}]"
        print(f"{location} | {result.title}")
        for line in result.context_before:
            print(f"  {line}")
        print(f"  > {result.line}")
        for line in result.context_after:
            print(f"  {line}")
        print()


def generate_study_files(info: dict, video_dir: Path, subtitle: SubtitleSelection, library_path: Path) -> Path:
    video_id = info["id"]
    result = analyze_cues(clean_vtt(subtitle.path))
    title = info.get("title", video_id)

    write_info(video_dir / "info.json", info, subtitle, analysis_version=result.format_version)
    write_transcript(video_dir / "transcript.txt", result.cues)
    write_clean_transcript(video_dir / "transcript.clean.txt", result.cues)
    write_transcript_paragraphs(video_dir / "transcript.paragraphs.md", result.cues)
    write_summary(video_dir / "summary.md", title, result.keywords, result.ideas, result.sections)
    write_tools(video_dir / "tools.md", result.tools)
    write_tools_json(video_dir / "tools.json", result.tools)
    write_concepts(video_dir / "concepts.md", result.sections)
    write_concepts_json(video_dir / "concepts.json", result.concepts)
    write_questions(video_dir / "questions.md", result.questions)
    write_flashcards(video_dir / "flashcards.md", result.cards)
    write_study_guide(video_dir / "study-guide.md", title, result.tools, result.questions)
    write_study_markdown_from_result(video_dir / "study.md", title, result)
    write_anki_csv(video_dir / "anki.csv", result.cards, video_id, info.get("uploader"))
    upsert_video(library_path, info, video_dir, result.tools)
    return video_dir


def process_video(url: str, out: Path, langs: str, *, force_download: bool = False, quiet: bool = False) -> Path:
    info = download_subtitles(url, out, langs, force_download=force_download, quiet=quiet)
    video_id = info["id"]
    video_dir = out / video_id
    subtitle = choose_subtitle(video_dir, video_id, [x.strip() for x in langs.split(",") if x.strip()], info=info)
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def load_existing_video(video_id: str, out: Path, langs: str) -> tuple[dict, Path, SubtitleSelection]:
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
    subtitle = choose_subtitle(video_dir, video_id, [x.strip() for x in langs.split(",") if x.strip()], info=info)
    return info, video_dir, subtitle


def analyze_existing(video_id: str, out: Path, langs: str) -> Path:
    info, video_dir, subtitle = load_existing_video(video_id, out, langs)
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def export_study(video_id: str, out: Path, langs: str, export_format: str) -> list[Path]:
    info, video_dir, subtitle = load_existing_video(video_id, out, langs)
    result = analyze_cues(clean_vtt(subtitle.path))
    title = info.get("title", video_id)
    written: list[Path] = []
    if export_format in {"markdown", "all"}:
        study_path = video_dir / "study.md"
        write_study_markdown_from_result(study_path, title, result)
        written.append(study_path)
    if export_format in {"anki", "all"}:
        anki_path = video_dir / "anki.csv"
        write_anki_csv(anki_path, result.cards, video_id, info.get("uploader"))
        written.append(anki_path)
    return written


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("debe ser >= 1")
    return number


def nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("debe ser >= 0")
    return number


def run(argv: list[str]) -> int:
    if argv and argv[0].startswith(("http://", "https://")):
        argv = ["study", *argv]

    parser = argparse.ArgumentParser(description="Descarga transcripciones de YouTube y genera material de estudio.")
    sub = parser.add_subparsers(dest="command")

    study = sub.add_parser("study", help="Descargar y analizar un video")
    study.add_argument("url")
    study.add_argument("--lang", default="es-419,es,es-orig")
    study.add_argument("--out", default="data/videos")
    study.add_argument("--force-download", action="store_true", help="Volver a descargar subtítulos aunque ya existan")
    study.add_argument("--quiet", action="store_true", help="Reducir la salida de yt-dlp")

    list_cmd = sub.add_parser("list", help="Listar videos guardados")
    list_cmd.add_argument("--out", default="data/videos")

    show = sub.add_parser("show", help="Mostrar detalle de un video guardado")
    show.add_argument("video_id")
    show.add_argument("--out", default="data/videos")

    rebuild = sub.add_parser("rebuild-library", help="Reconstruir la biblioteca desde videos locales")
    rebuild.add_argument("--out", default="data/videos")

    search = sub.add_parser("search", help="Buscar texto dentro de transcripciones")
    search.add_argument("query")
    search.add_argument("--video", dest="video_id")
    search.add_argument("--limit", type=positive_int, default=10)
    search.add_argument("--context", type=nonnegative_int, default=0)
    search.add_argument("--out", default="data/videos")

    analyze = sub.add_parser("analyze", help="Reanalizar un video ya descargado sin usar red")
    analyze.add_argument("video_id")
    analyze.add_argument("--lang", default="es-419,es,es-orig")
    analyze.add_argument("--out", default="data/videos")

    export = sub.add_parser("export", help="Exportar material de estudio")
    export.add_argument("video_id")
    export.add_argument("--format", choices=["markdown", "anki", "all"], default="all")
    export.add_argument("--lang", default="es-419,es,es-orig")
    export.add_argument("--out", default="data/videos")

    args = parser.parse_args(argv)
    if args.command == "study":
        video_dir = process_video(args.url, Path(args.out), args.lang, force_download=args.force_download, quiet=args.quiet)
        print("\nArchivos generados:")
        for path in sorted(video_dir.iterdir()):
            print(f"- {path}")
    elif args.command == "list":
        print_video_list(Path(args.out))
    elif args.command == "show":
        print_video_detail(Path(args.out), args.video_id)
    elif args.command == "rebuild-library":
        videos_dir = Path(args.out)
        result = rebuild_library(library_path_from_videos_dir(videos_dir), videos_dir)
        print(f"Biblioteca reconstruida: {result.rebuilt} videos.")
        if result.skipped:
            print("Omitidos:")
            for reason in result.skipped:
                print(f"- {reason}")
    elif args.command == "search":
        videos_dir = Path(args.out)
        library_path = library_path_from_videos_dir(videos_dir)
        videos = list_videos(library_path)
        if args.video_id and not any(str(video.get("id") or "") == args.video_id for video in videos):
            raise VideoDataError(f"No existe el video {args.video_id} en la biblioteca.")
        results = search_library(videos, args.query, video_id=args.video_id, limit=args.limit, context=args.context, library_path=library_path)
        print_search_results(results)
    elif args.command == "analyze":
        video_dir = analyze_existing(args.video_id, Path(args.out), args.lang)
        print("\nArchivos regenerados:")
        for path in sorted(video_dir.iterdir()):
            print(f"- {path}")
    elif args.command == "export":
        paths = export_study(args.video_id, Path(args.out), args.lang, args.format)
        print("\nArchivos exportados:")
        for path in paths:
            print(f"- {path}")
    else:
        parser.print_help()
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except (AppError, LibraryError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
