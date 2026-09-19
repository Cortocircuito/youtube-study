from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.youtube_study.downloader import SubtitleError, choose_subtitle, download_subtitles
from src.youtube_study.exporter import write_info
from src.youtube_study.models import VideoMetadata


def write_vtt(video_dir: Path, video_id: str, language: str, body: str = "caption") -> Path:
    path = video_dir / f"{video_id}.{language}.vtt"
    path.write_text(f"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n{body}\n", encoding="utf-8")
    return path


def test_choose_subtitle_prefers_manual_requested_language(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es", "manual")
    write_vtt(tmp_path, video_id, "es-orig", "auto")
    info = {
        "subtitles": {"es": [{"ext": "vtt"}]},
        "automatic_captions": {"es-orig": [{"ext": "vtt"}]},
    }

    selected = choose_subtitle(tmp_path, video_id, ["es"], info=info)

    assert selected.path.name == "vid.es.vtt"
    assert selected.kind == "manual"
    assert selected.language == "es"
    assert selected.reason == "subtítulo manual en idioma solicitado"


def test_choose_subtitle_honors_requested_language_order(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es")
    write_vtt(tmp_path, video_id, "es-419")
    info = {"subtitles": {"es": [{"ext": "vtt"}], "es-419": [{"ext": "vtt"}]}}

    selected = choose_subtitle(tmp_path, video_id, ["es-419", "es"], info=info)

    assert selected.path.name == "vid.es-419.vtt"
    assert selected.language == "es-419"


def test_choose_subtitle_prefers_original_auto_before_translation(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es", "translated")
    write_vtt(tmp_path, video_id, "es-orig", "original auto")
    info = {
        "automatic_captions": {
            "es": [{"ext": "vtt", "is_translation": True, "source_language": "en"}],
            "es-orig": [{"ext": "vtt"}],
        }
    }

    selected = choose_subtitle(tmp_path, video_id, ["es", "es-orig"], info=info)

    assert selected.path.name == "vid.es-orig.vtt"
    assert selected.kind == "automatic"
    assert selected.is_translation is False
    assert selected.reason == "subtítulo automático original en idioma solicitado"


def test_choose_subtitle_uses_translation_before_english_fallback(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es", "translated")
    write_vtt(tmp_path, video_id, "en", "english")
    info = {
        "subtitles": {"en": [{"ext": "vtt"}]},
        "automatic_captions": {"es": [{"ext": "vtt", "is_translation": True, "source_language": "en"}]},
    }

    selected = choose_subtitle(tmp_path, video_id, ["es"], info=info)

    assert selected.path.name == "vid.es.vtt"
    assert selected.is_translation is True
    assert selected.reason == "traducción automática en idioma solicitado"


def test_choose_subtitle_detects_translation_from_ytdlp_url_metadata(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es", "translated")
    write_vtt(tmp_path, video_id, "en", "english")
    info = {
        "automatic_captions": {
            "es": [
                {
                    "ext": "vtt",
                    "url": "https://www.youtube.com/api/timedtext?lang=en&tlang=es&fmt=vtt",
                }
            ],
            "en": [{"ext": "vtt", "url": "https://www.youtube.com/api/timedtext?lang=en&fmt=vtt"}],
        }
    }

    selected = choose_subtitle(tmp_path, video_id, ["es"], info=info)

    assert selected.path.name == "vid.es.vtt"
    assert selected.is_translation is True
    assert selected.source_language == "en"
    assert selected.reason == "traducción automática en idioma solicitado"


def test_choose_subtitle_keeps_legacy_file_fallback_without_metadata(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "en", "english")
    write_vtt(tmp_path, video_id, "es", "spanish")

    selected = choose_subtitle(tmp_path, video_id, ["es"], info={})

    assert selected.path.name == "vid.es.vtt"
    assert selected.kind == "unknown"
    assert selected.reason == "subtítulo local en idioma solicitado sin metadata"


def test_choose_subtitle_errors_when_no_vtt_exists(tmp_path: Path) -> None:
    with pytest.raises(SubtitleError):
        choose_subtitle(tmp_path, "vid", ["es"], info={})


def test_download_subtitles_passes_force_and_quiet_options(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, opts: dict[str, object]) -> None:
            captured.update(opts)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, object]:
            captured["url"] = url
            captured["download"] = download
            return {"id": "vid"}

    monkeypatch.setattr("src.youtube_study.downloader.YoutubeDL", FakeYoutubeDL)

    info = download_subtitles("https://example.test/video", tmp_path, "es,en", force_download=True, quiet=True)

    assert info == {"id": "vid"}
    assert captured["subtitleslangs"] == ["es", "en"]
    assert captured["overwrites"] is True
    assert captured["quiet"] is True
    assert captured["no_warnings"] is True
    assert captured["noprogress"] is True
    assert captured["download"] is True


def test_download_subtitles_adds_english_as_fallback(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, opts: dict[str, object]) -> None:
            captured.update(opts)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, object]:
            return {"id": "vid"}

    monkeypatch.setattr("src.youtube_study.downloader.YoutubeDL", FakeYoutubeDL)

    download_subtitles("https://example.test/video", tmp_path, "es-419,es")

    assert captured["subtitleslangs"] == ["es-419", "es", "en.*"]


def test_write_info_documents_selected_subtitle(tmp_path: Path) -> None:
    video_id = "vid"
    write_vtt(tmp_path, video_id, "es")
    selection = choose_subtitle(
        tmp_path,
        video_id,
        ["es"],
        info={"subtitles": {"es": [{"ext": "vtt"}]}},
    )

    info_path = tmp_path / "info.json"
    write_info(info_path, VideoMetadata(video_id, "Demo"), selection)

    payload = json.loads(info_path.read_text(encoding="utf-8"))
    assert payload["source_subtitle"]["path"].endswith("vid.es.vtt")
    assert payload["source_subtitle"]["language"] == "es"
    assert payload["source_subtitle"]["kind"] == "manual"
    assert payload["source_subtitle"]["reason"] == "subtítulo manual en idioma solicitado"
