from pathlib import Path

import pytest

from src.youtube_study.errors import VideoDataError
from src.youtube_study.metadata import load_persisted_video, metadata_from_ytdlp, persisted_video_from_mapping


def test_ytdlp_metadata_is_normalized() -> None:
    metadata = metadata_from_ytdlp(
        {
            "id": "demo",
            "title": "Demo",
            "uploader": "Canal",
            "duration": 12.5,
            "webpage_url": "https://example.test/demo",
            "subtitles": {"es": []},
        }
    )

    assert metadata.id == "demo"
    assert metadata.title == "Demo"
    assert metadata.duration == 12.5


@pytest.mark.parametrize(
    "payload",
    [
        {"id": 42},
        {"id": "demo", "title": []},
        {"id": "demo", "duration": True},
        {"id": "demo", "duration": -1},
    ],
)
def test_ytdlp_metadata_rejects_invalid_types(payload: dict) -> None:
    with pytest.raises(VideoDataError):
        metadata_from_ytdlp(payload)


def test_persisted_metadata_rejects_inconsistent_id() -> None:
    with pytest.raises(VideoDataError, match="no coincide"):
        persisted_video_from_mapping({"id": "otro"}, expected_id="demo", source="info.json de demo")


def test_persisted_metadata_accepts_legacy_missing_id_and_subtitle_path() -> None:
    persisted = persisted_video_from_mapping(
        {"title": "Legacy", "source_subtitle": "demo.es.vtt"},
        expected_id="demo",
        source="info.json de demo",
    )

    assert persisted.metadata.id == "demo"
    assert persisted.source_subtitle == "demo.es.vtt"


def test_load_persisted_video_distinguishes_invalid_json_from_read_error(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "info.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(VideoDataError, match="JSON malformado"):
        load_persisted_video(path, "demo")

    path.write_bytes(b"\xff")
    with pytest.raises(VideoDataError, match="JSON malformado"):
        load_persisted_video(path, "demo")

    def deny_read(*args, **kwargs) -> str:
        raise PermissionError("denegado")

    monkeypatch.setattr(Path, "read_text", deny_read)
    with pytest.raises(VideoDataError, match="No se pudo leer info.json"):
        load_persisted_video(path, "demo")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"id": "demo", "source_subtitle": {"path": "demo.es.vtt", "language": 2}}, "source_subtitle.language"),
        ({"id": "demo", "analysis": {"format_version": True}}, "analysis.format_version"),
    ],
)
def test_persisted_metadata_validates_nested_fields(payload: dict, message: str) -> None:
    with pytest.raises(VideoDataError, match=message):
        persisted_video_from_mapping(payload, expected_id="demo", source="info.json de demo")
