#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import json

from src.youtube_study.analyzer import (
    concept_mentions,
    detect_tools,
    flashcards,
    full_text,
    important_ideas,
    keywords,
    questions,
    section_summaries,
)
from src.youtube_study.downloader import choose_vtt, download_subtitles
from src.youtube_study.exporter import (
    write_clean_transcript,
    write_concepts,
    write_concepts_json,
    write_flashcards,
    write_info,
    write_questions,
    write_anki_csv,
    write_study_guide,
    write_study_markdown,
    write_summary,
    write_tools,
    write_tools_json,
    write_transcript,
    write_transcript_paragraphs,
)
from src.youtube_study.library import get_video, library_path_from_videos_dir, list_videos, upsert_video
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
    video = get_video(library_path_from_videos_dir(videos_dir), video_id)
    if not video:
        print(f"No existe el video {video_id} en la biblioteca.")
        return
    print(f"ID: {video.get('id')}")
    print(f"Título: {video.get('title')}")
    print(f"Canal: {video.get('channel') or 'N/D'}")
    print(f"Duración: {format_duration(video.get('duration'))}")
    print(f"URL: {video.get('url') or 'N/D'}")
    print(f"Ruta: {video.get('path')}")
    print(f"Herramientas: {', '.join(video.get('tools') or []) or 'N/D'}")
    print(f"Creado: {video.get('created_at')}")
    print(f"Actualizado: {video.get('updated_at')}")

    video_dir = Path(video.get("path") or videos_dir / video_id)
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


def generate_study_files(info: dict, video_dir: Path, subtitle: Path, library_path: Path) -> Path:
    video_id = info["id"]
    cues = clean_vtt(subtitle)
    text = full_text(cues)

    kws = keywords(text)
    tools = detect_tools(text)
    ideas = important_ideas(cues)
    sections = section_summaries(cues)
    concepts = concept_mentions(cues)
    qs = questions(cues, tools)
    cards = flashcards(tools, qs)
    title = info.get("title", video_id)

    write_info(video_dir / "info.json", info, subtitle)
    write_transcript(video_dir / "transcript.txt", cues)
    write_clean_transcript(video_dir / "transcript.clean.txt", cues)
    write_transcript_paragraphs(video_dir / "transcript.paragraphs.md", cues)
    write_summary(video_dir / "summary.md", title, kws, ideas, sections)
    write_tools(video_dir / "tools.md", tools)
    write_tools_json(video_dir / "tools.json", tools)
    write_concepts(video_dir / "concepts.md", sections)
    write_concepts_json(video_dir / "concepts.json", concepts)
    write_questions(video_dir / "questions.md", qs)
    write_flashcards(video_dir / "flashcards.md", cards)
    write_study_guide(video_dir / "study-guide.md", title, tools, qs)
    upsert_video(library_path, info, video_dir, tools)
    return video_dir


def process_video(url: str, out: Path, langs: str, *, force_download: bool = False, quiet: bool = False) -> Path:
    info = download_subtitles(url, out, langs, force_download=force_download, quiet=quiet)
    video_id = info["id"]
    video_dir = out / video_id
    subtitle = choose_vtt(video_dir, video_id, [x.strip() for x in langs.split(",") if x.strip()])
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def load_existing_video(video_id: str, out: Path, langs: str) -> tuple[dict, Path, Path]:
    video_dir = out / video_id
    if not video_dir.exists():
        raise FileNotFoundError(f"No existe el directorio del video: {video_dir}")
    info_path = video_dir / "info.json"
    if not info_path.exists():
        raise FileNotFoundError(f"No existe info.json para {video_id}: {info_path}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    info.setdefault("id", video_id)
    subtitle = choose_vtt(video_dir, video_id, [x.strip() for x in langs.split(",") if x.strip()])
    return info, video_dir, subtitle


def analyze_existing(video_id: str, out: Path, langs: str) -> Path:
    info, video_dir, subtitle = load_existing_video(video_id, out, langs)
    return generate_study_files(info, video_dir, subtitle, library_path_from_videos_dir(out))


def export_study(video_id: str, out: Path, langs: str, export_format: str) -> list[Path]:
    info, video_dir, subtitle = load_existing_video(video_id, out, langs)
    written: list[Path] = []
    if export_format in {"markdown", "all"}:
        study_path = video_dir / "study.md"
        write_study_markdown(study_path, video_dir, info.get("title", video_id))
        written.append(study_path)
    if export_format in {"anki", "all"}:
        cues = clean_vtt(subtitle)
        tools = detect_tools(full_text(cues))
        cards = flashcards(tools, questions(cues, tools))
        anki_path = video_dir / "anki.csv"
        write_anki_csv(anki_path, cards, video_id, info.get("uploader"))
        written.append(anki_path)
    return written


def main() -> None:
    argv = sys.argv[1:]
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

    search = sub.add_parser("search", help="Buscar texto dentro de transcripciones")
    search.add_argument("query")
    search.add_argument("--video", dest="video_id")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--context", type=int, default=0)
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
        try:
            video_dir = process_video(args.url, Path(args.out), args.lang, force_download=args.force_download, quiet=args.quiet)
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print("\nArchivos generados:")
        for path in sorted(video_dir.iterdir()):
            print(f"- {path}")
    elif args.command == "list":
        print_video_list(Path(args.out))
    elif args.command == "show":
        print_video_detail(Path(args.out), args.video_id)
    elif args.command == "search":
        videos_dir = Path(args.out)
        videos = list_videos(library_path_from_videos_dir(videos_dir))
        results = search_library(videos, args.query, video_id=args.video_id, limit=args.limit, context=args.context)
        print_search_results(results)
    elif args.command == "analyze":
        try:
            video_dir = analyze_existing(args.video_id, Path(args.out), args.lang)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print("\nArchivos regenerados:")
        for path in sorted(video_dir.iterdir()):
            print(f"- {path}")
    elif args.command == "export":
        try:
            paths = export_study(args.video_id, Path(args.out), args.lang, args.format)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print("\nArchivos exportados:")
        for path in paths:
            print(f"- {path}")
    else:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
