from __future__ import annotations

import re
import warnings
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from yt_dlp.version import __version__ as YTDLP_VERSION

MIN_YTDLP_VERSION = (2025, 1, 1)


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
) -> dict:
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
        raise RuntimeError(
            "No se pudieron descargar los subtítulos. Comprueba la URL, los idiomas solicitados, "
            "los límites de YouTube y que yt-dlp esté actualizado en el venv."
        ) from exc
    if not info:
        raise RuntimeError("YouTube no devolvió información para el video solicitado.")
    return info


def choose_vtt(video_dir: Path, video_id: str, preferred_langs: list[str]) -> Path:
    """Choose captions by quality: Spanish manual, Spanish auto-original, translated, English."""
    all_vtts = sorted(video_dir.glob(f"{video_id}.*.vtt"))
    if not all_vtts:
        raise FileNotFoundError(
            f"No se descargó ningún subtítulo .vtt en {video_dir}. "
            "Prueba otros idiomas con --lang o verifica que el video tenga subtítulos."
        )

    exact_manual = [f"{video_id}.{lang}.vtt" for lang in preferred_langs if lang.startswith("es") and lang != "es-orig"]
    priorities = [
        exact_manual,
        [f"{video_id}.es.vtt", f"{video_id}.es-419.vtt", f"{video_id}.es-MX.vtt"],
        [f"{video_id}.es-orig.vtt"],
        [path.name for path in all_vtts if ".es-" in path.name and ".es-orig." not in path.name],
        [f"{video_id}.en.vtt", f"{video_id}.en-orig.vtt"],
        [path.name for path in all_vtts if ".en" in path.name],
    ]
    by_name = {path.name: path for path in all_vtts}
    for names in priorities:
        for name in names:
            if name in by_name:
                return by_name[name]
    return max(all_vtts, key=lambda path: path.stat().st_size)
