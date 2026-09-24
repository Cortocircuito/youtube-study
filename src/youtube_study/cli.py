from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import AppError, VideoDataError
from .library import get_video, library_path_from_videos_dir, list_videos, rebuild_library, resolve_video_path
from .search import SearchResult, search_library
from .service import analyze_existing, export_study, process_video

DEFAULT_LANGUAGES = "es-419,es,es-orig"
DEFAULT_OUTPUT = "data/videos"


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "N/D"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    remaining = total % 60
    if hours:
        return f"{hours}:{minutes:02d}:{remaining:02d}"
    return f"{minutes}:{remaining:02d}"


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
        for path in sorted(path for path in video_dir.iterdir() if path.is_file()):
            print(f"- {path.name}")


def print_search_results(results: list[SearchResult]) -> None:
    if not results:
        print("No se encontraron resultados.")
        return
    for result in results:
        location = result.video_id
        if result.timestamp:
            location += f" [{result.timestamp}]"
        print(f"{location} | {result.title}")
        for line in result.context_before:
            print(f"  {line}")
        print(f"  > {result.line}")
        for line in result.context_after:
            print(f"  {line}")
        print()


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


def add_output_option(command: argparse.ArgumentParser) -> None:
    command.add_argument("--out", default=DEFAULT_OUTPUT)


def add_language_option(command: argparse.ArgumentParser) -> None:
    command.add_argument("--lang", default=DEFAULT_LANGUAGES)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descarga transcripciones de YouTube y genera material de estudio.")
    sub = parser.add_subparsers(dest="command")

    study = sub.add_parser("study", help="Descargar y analizar un video")
    study.add_argument("url")
    add_language_option(study)
    add_output_option(study)
    study.add_argument("--force-download", action="store_true", help="Volver a descargar subtítulos aunque ya existan")
    study.add_argument("--quiet", action="store_true", help="Reducir la salida de yt-dlp")

    list_cmd = sub.add_parser("list", help="Listar videos guardados")
    add_output_option(list_cmd)

    show = sub.add_parser("show", help="Mostrar detalle de un video guardado")
    show.add_argument("video_id")
    add_output_option(show)

    rebuild = sub.add_parser("rebuild-library", help="Reconstruir la biblioteca desde videos locales")
    add_output_option(rebuild)

    search = sub.add_parser("search", help="Buscar texto dentro de transcripciones")
    search.add_argument("query")
    search.add_argument("--video", dest="video_id")
    search.add_argument("--limit", type=positive_int, default=10)
    search.add_argument("--context", type=nonnegative_int, default=0)
    add_output_option(search)

    analyze = sub.add_parser("analyze", help="Reanalizar un video ya descargado sin usar red")
    analyze.add_argument("video_id")
    add_language_option(analyze)
    add_output_option(analyze)

    export = sub.add_parser("export", help="Exportar material de estudio")
    export.add_argument("video_id")
    export.add_argument("--format", choices=["markdown", "anki", "all"], default="all")
    add_language_option(export)
    add_output_option(export)
    return parser


def run(argv: list[str]) -> int:
    if argv and argv[0].startswith(("http://", "https://")):
        argv = ["study", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "study":
        video_dir = process_video(
            args.url, Path(args.out), args.lang, force_download=args.force_download, quiet=args.quiet
        )
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
        results = search_library(
            videos,
            args.query,
            video_id=args.video_id,
            limit=args.limit,
            context=args.context,
            library_path=library_path,
        )
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
    except KeyboardInterrupt:
        print("Interrumpido.", file=sys.stderr)
        return 130
    except (AppError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
