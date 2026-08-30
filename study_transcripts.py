#!/usr/bin/env python3
"""Descarga subtítulos de YouTube y genera material de estudio.

Uso:
  python study_transcripts.py URL --lang es-419,es --out data
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from yt_dlp import YoutubeDL

STOPWORDS = set("""
a acá ahí al algo algunas algunos ante antes aquí así aunque cada casi como con contra cual cuando de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba están estar estas este esto estos fue han hasta hay la las le les lo los más me mi mis muy no nos o para pero por porque que se ser si sin sobre son su sus te tenía tienen todo todos tu un una unas unos y ya yo
""".split())


def download_subs(url: str, out_dir: Path, langs: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [x.strip() for x in langs.split(",") if x.strip()],
        "subtitlesformat": "vtt",
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": False,
        "ignore_no_formats_error": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return info


def clean_vtt(path: Path) -> list[tuple[str, str]]:
    cues: list[tuple[str, str]] = []
    current_time = ""
    current_lines: list[str] = []

    def flush():
        nonlocal current_time, current_lines
        if current_time and current_lines:
            text = " ".join(current_lines)
            text = html.unescape(text).replace("\xa0", " ")
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                cues.append((current_time, text))
        current_time = ""
        current_lines = []

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            flush()
            continue
        if "-->" in line:
            flush()
            current_time = line.split("-->", 1)[0].strip().split(".", 1)[0]
            continue
        if not re.fullmatch(r"\d+", line):
            current_lines.append(line)
    flush()

    # Evita líneas repetidas en subtítulos automáticos solapados.
    result: list[tuple[str, str]] = []
    prev = ""
    for ts, text in cues:
        if text != prev:
            result.append((ts, text))
        prev = text
    return result


def transcript_text(cues: Iterable[tuple[str, str]]) -> str:
    return "\n".join(f"[{ts}] {text}" for ts, text in cues)


def sentences_from(cues: list[tuple[str, str]]) -> list[tuple[str, str]]:
    joined = " ".join(text for _, text in cues)
    parts = re.split(r"(?<=[.!?])\s+", joined)
    # Si la transcripción no puntúa bien, agrupa por bloques de 2 cues.
    if len(parts) < 12:
        parts = [" ".join(text for _, text in cues[i:i+2]) for i in range(0, len(cues), 2)]
    # Timestamp aproximado por posición.
    out = []
    cue_index = 0
    for part in parts:
        part = part.strip()
        if len(part) < 50:
            continue
        ts = cues[min(cue_index, len(cues)-1)][0] if cues else "00:00:00"
        out.append((ts, part))
        cue_index += max(1, len(part) // 120)
    return out


def keywords(text: str, limit: int = 20) -> list[tuple[str, int]]:
    words = re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9_-]{2,}", text.lower())
    words = [w for w in words if w not in STOPWORDS and not w.isdigit()]
    return Counter(words).most_common(limit)


def summarize(cues: list[tuple[str, str]], title: str = "") -> str:
    full = " ".join(t for _, t in cues)
    key = keywords(full, 25)
    key_words = {w for w, _ in key[:18]}
    sents = sentences_from(cues)

    scored = []
    for ts, sent in sents:
        ws = re.findall(r"[a-záéíóúñü0-9_-]{3,}", sent.lower())
        score = sum(1 for w in ws if w in key_words) + min(len(ws), 35) / 35
        if any(x in sent.lower() for x in ["instal", "config", "herramient", "agente", "teléfono", "ssh", "tailscale", "whisper", "claude", "codex"]):
            score += 2
        scored.append((score, ts, sent))
    top = sorted(scored, reverse=True)[:10]
    top = sorted(top, key=lambda x: x[1])

    lines = []
    lines.append(f"# Resumen de estudio: {title or 'video'}")
    lines.append("")
    lines.append("## Palabras/herramientas frecuentes")
    lines.extend(f"- {w}: {n}" for w, n in key[:15])
    lines.append("")
    lines.append("## Ideas importantes con timestamp")
    lines.extend(f"- [{ts}] {sent}" for _, ts, sent in top)
    return "\n".join(lines) + "\n"


def choose_vtt(out_dir: Path, video_id: str, preferred: list[str]) -> Path:
    candidates = []
    for lang in preferred:
        candidates.extend(out_dir.glob(f"{video_id}.{lang}.vtt"))
    candidates.extend(out_dir.glob(f"{video_id}.*.vtt"))
    if not candidates:
        raise FileNotFoundError("No se descargó ningún .vtt")
    # Preferir subtítulos manuales, normalmente son más pequeños/limpios que traducciones automáticas.
    return sorted(set(candidates), key=lambda p: p.stat().st_size)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--lang", default="es-419,es,es-orig")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    out_dir = Path(args.out)
    info = download_subs(args.url, out_dir, args.lang)
    video_id = info.get("id")
    title = info.get("title", video_id)
    vtt = choose_vtt(out_dir, video_id, [x.strip() for x in args.lang.split(",")])
    cues = clean_vtt(vtt)

    base = out_dir / video_id
    (base.with_suffix(".info.json")).write_text(json.dumps({
        "id": video_id,
        "title": title,
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "source_subtitle": str(vtt),
        "webpage_url": info.get("webpage_url"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (base.with_suffix(".transcript.txt")).write_text(transcript_text(cues), encoding="utf-8")
    (base.with_suffix(".summary.md")).write_text(summarize(cues, title), encoding="utf-8")

    print(f"OK: {title}")
    print(f"Subtítulo usado: {vtt}")
    print(f"Transcripción: {base.with_suffix('.transcript.txt')}")
    print(f"Resumen: {base.with_suffix('.summary.md')}")


if __name__ == "__main__":
    main()
