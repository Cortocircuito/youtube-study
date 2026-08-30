from __future__ import annotations

from pathlib import Path
from yt_dlp import YoutubeDL


def download_subtitles(url: str, out_dir: Path, langs: str = "es-419,es,es-orig") -> dict:
    """Download subtitles/captions for a YouTube video using yt-dlp."""
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [x.strip() for x in langs.split(",") if x.strip()],
        "subtitlesformat": "vtt",
        "outtmpl": str(out_dir / "%(id)s" / "%(id)s.%(ext)s"),
        "quiet": False,
        "ignore_no_formats_error": True,
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def choose_vtt(video_dir: Path, video_id: str, preferred_langs: list[str]) -> Path:
    candidates: list[Path] = []
    for lang in preferred_langs:
        candidates.extend(video_dir.glob(f"{video_id}.{lang}.vtt"))
    candidates.extend(video_dir.glob(f"{video_id}.*.vtt"))
    candidates = sorted(set(candidates), key=lambda p: (0 if "es-419" in p.name else 1, p.stat().st_size))
    if not candidates:
        raise FileNotFoundError(f"No se descargó ningún subtítulo .vtt en {video_dir}")
    return candidates[0]
