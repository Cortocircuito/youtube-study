#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.youtube_study.analyzer import (
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
    write_concepts,
    write_flashcards,
    write_info,
    write_questions,
    write_study_guide,
    write_summary,
    write_tools,
    write_transcript,
)
from src.youtube_study.library import library_path_from_videos_dir, upsert_video
from src.youtube_study.transcript import clean_vtt


def process_video(url: str, out: Path, langs: str) -> Path:
    info = download_subtitles(url, out, langs)
    video_id = info["id"]
    video_dir = out / video_id
    subtitle = choose_vtt(video_dir, video_id, [x.strip() for x in langs.split(",") if x.strip()])
    cues = clean_vtt(subtitle)
    text = full_text(cues)

    kws = keywords(text)
    tools = detect_tools(text)
    ideas = important_ideas(cues)
    sections = section_summaries(cues)
    qs = questions(cues, tools)
    cards = flashcards(tools, qs)
    title = info.get("title", video_id)

    write_info(video_dir / "info.json", info, subtitle)
    write_transcript(video_dir / "transcript.txt", cues)
    write_summary(video_dir / "summary.md", title, kws, ideas, sections)
    write_tools(video_dir / "tools.md", tools)
    write_concepts(video_dir / "concepts.md", sections)
    write_questions(video_dir / "questions.md", qs)
    write_flashcards(video_dir / "flashcards.md", cards)
    write_study_guide(video_dir / "study-guide.md", title, tools, qs)
    upsert_video(library_path_from_videos_dir(out), info, video_dir, tools)
    return video_dir


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

    args = parser.parse_args(argv)
    if args.command == "study":
        video_dir = process_video(args.url, Path(args.out), args.lang)
    else:
        parser.print_help()
        return

    print("\nArchivos generados:")
    for path in sorted(video_dir.iterdir()):
        print(f"- {path}")


if __name__ == "__main__":
    main()
