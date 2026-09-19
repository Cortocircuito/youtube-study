from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.youtube_study.downloader import SubtitleSelection
from src.youtube_study.errors import VideoDataError
from src.youtube_study.service import analyze_existing, export_study, generate_study_files

ARTIFACT_NAMES = {
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
}


def write_demo_vtt(path: Path) -> None:
    path.write_text(
        "WEBVTT\n\n"
        "00:00:01.000 --> 00:00:04.000\n"
        "Tailscale conecta equipos para usar SSH sin abrir puertos.\n\n"
        "00:00:05.000 --> 00:00:08.000\n"
        "Tailscale crea una red privada y SSH da acceso remoto seguro.\n",
        encoding="utf-8",
    )


def test_generate_study_files_writes_all_artifacts_from_one_analysis(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    selection = SubtitleSelection(
        path=subtitle_path,
        language="es",
        kind="manual",
        reason="subtítulo manual en idioma solicitado",
    )

    generate_study_files(
        {
            "id": "demo",
            "title": "Demo Ñ",
            "uploader": "Canal Ñ",
            "webpage_url": "https://www.youtube.com/watch?v=demo",
        },
        video_dir,
        selection,
        tmp_path / "library.json",
    )

    assert ARTIFACT_NAMES.issubset({path.name for path in video_dir.iterdir()})

    tools = json.loads((video_dir / "tools.json").read_text(encoding="utf-8"))
    concepts = json.loads((video_dir / "concepts.json").read_text(encoding="utf-8"))
    info = json.loads((video_dir / "info.json").read_text(encoding="utf-8"))
    summary = (video_dir / "summary.md").read_text(encoding="utf-8")
    questions = (video_dir / "questions.md").read_text(encoding="utf-8")
    flashcards = (video_dir / "flashcards.md").read_text(encoding="utf-8")
    study = (video_dir / "study.md").read_text(encoding="utf-8")
    anki = (video_dir / "anki.csv").read_text(encoding="utf-8-sig")

    tailscale = next(tool for tool in tools if tool["name"] == "tailscale")
    assert tailscale["category"] == "service"
    assert tailscale["kind"] == "known"
    assert concepts and {"name", "score", "count", "timestamps"}.issubset(concepts[0])
    assert info["analysis"]["format_version"] == 2
    assert "# Estudio consolidado: Demo Ñ" in study
    assert "### tailscale" in study
    reference = "https://www.youtube.com/watch?v=demo&t=1"
    assert reference in summary
    assert reference in questions
    assert reference in flashcards
    assert reference in study
    assert "https://www.youtube.com/watch?v=demo&amp;t=1" in anki
    assert "video::demo" in anki
    assert "channel::Canal_Ñ" in anki


def test_analyze_existing_migrates_v1_artifacts_to_v2_without_network(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "legacy"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "legacy.es.vtt"
    write_demo_vtt(subtitle_path)
    (video_dir / "info.json").write_text(
        json.dumps(
            {
                "id": "legacy",
                "title": "Análisis antiguo",
                "webpage_url": "https://youtu.be/legacy",
                "source_subtitle": str(subtitle_path),
                "analysis": {"format_version": 1},
            }
        ),
        encoding="utf-8",
    )
    (video_dir / "flashcards.md").write_text(
        "Respóndelo usando la sección correspondiente de la transcripción.", encoding="utf-8"
    )

    analyzed_dir = analyze_existing("legacy", tmp_path / "videos", "es")

    info = json.loads((analyzed_dir / "info.json").read_text(encoding="utf-8"))
    flashcards = (analyzed_dir / "flashcards.md").read_text(encoding="utf-8")
    assert info["analysis"]["format_version"] == 2
    assert "Respóndelo usando" not in flashcards
    assert "https://youtu.be/legacy?t=1" in flashcards


def test_export_study_recomputes_markdown_and_anki_from_subtitle(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    (video_dir / "info.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "title": "Demo",
                "uploader": "Canal",
                "webpage_url": "https://youtu.be/demo?si=share",
                "source_subtitle": str(subtitle_path),
            }
        ),
        encoding="utf-8",
    )
    (video_dir / "summary.md").write_text("# Resumen\n\nCONTENIDO OBSOLETO", encoding="utf-8")
    (video_dir / "study.md").write_text("CONTENIDO OBSOLETO", encoding="utf-8")

    written = export_study("demo", tmp_path / "videos", "es", "all")

    assert [path.name for path in written] == ["study.md", "anki.csv"]
    study = (video_dir / "study.md").read_text(encoding="utf-8")
    anki = (video_dir / "anki.csv").read_text(encoding="utf-8-sig")
    assert "CONTENIDO OBSOLETO" not in study
    assert "### tailscale" in study
    assert "https://youtu.be/demo?si=share&t=1" in study
    assert "https://youtu.be/demo?si=share&amp;t=1" in anki
    assert "video::demo" in anki


@pytest.mark.parametrize(
    ("export_format", "expected"),
    [
        ("markdown", ["study.md"]),
        ("anki", ["anki.csv"]),
        ("all", ["study.md", "anki.csv"]),
    ],
)
def test_export_study_writes_only_requested_public_artifacts(
    export_format: str, expected: list[str], tmp_path: Path
) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    (video_dir / "info.json").write_text(
        json.dumps({"id": "demo", "title": "Demo", "source_subtitle": str(subtitle_path)}),
        encoding="utf-8",
    )

    written = export_study("demo", tmp_path / "videos", "es", export_format)

    assert [path.name for path in written] == expected


def test_export_failure_preserves_existing_public_artifacts(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    (video_dir / "info.json").write_text(
        json.dumps({"id": "demo", "title": "Demo", "source_subtitle": str(subtitle_path)}),
        encoding="utf-8",
    )
    previous = {"study.md": b"estudio anterior", "anki.csv": b"anki anterior"}
    for name, content in previous.items():
        (video_dir / name).write_bytes(content)

    def fail_writer(*args, **kwargs) -> None:
        raise OSError("fallo de exportación")

    monkeypatch.setattr("src.youtube_study.service.write_study_markdown_from_result", fail_writer)

    with pytest.raises(OSError, match="fallo de exportación"):
        export_study("demo", tmp_path / "videos", "es", "all")

    assert {name: (video_dir / name).read_bytes() for name in previous} == previous


def test_empty_subtitle_does_not_overwrite_existing_artifacts(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    subtitle_path.write_text("WEBVTT\n\n", encoding="utf-8")
    summary_path = video_dir / "summary.md"
    summary_path.write_text("resultado válido", encoding="utf-8")
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")

    with pytest.raises(VideoDataError, match="no contiene texto utilizable"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    assert summary_path.read_text(encoding="utf-8") == "resultado válido"
    assert not (video_dir / "info.json").exists()


def test_writer_failure_does_not_publish_partial_generation(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    summary_path = video_dir / "summary.md"
    summary_path.write_text("resultado anterior", encoding="utf-8")
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")

    def fail_writer(*args, **kwargs) -> None:
        raise OSError("sin espacio")

    monkeypatch.setattr("src.youtube_study.service.write_summary", fail_writer)

    with pytest.raises(OSError, match="sin espacio"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    assert summary_path.read_text(encoding="utf-8") == "resultado anterior"
    assert not (video_dir / "info.json").exists()


def test_publish_failure_restores_previous_generation(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    previous = {"info.json": b'{"id":"anterior"}', "summary.md": b"resultado anterior"}
    for name, content in previous.items():
        (video_dir / name).write_bytes(content)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def fail_while_publishing(source, destination) -> None:
        source_path = Path(source)
        if source_path.name == "summary.md" and ".staging-" in source_path.parent.name:
            raise OSError("fallo de publicación")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.service.os.replace", fail_while_publishing)

    with pytest.raises(OSError, match="fallo de publicación"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    assert {name: (video_dir / name).read_bytes() for name in previous} == previous
    assert not list(video_dir.parent.glob(".demo.backup-*"))


def test_backup_failure_keeps_previous_artifact_bytes(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    summary_path = video_dir / "summary.md"
    previous = b"resultado anterior exacto\x00"
    summary_path.write_bytes(previous)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def fail_while_backing_up(source, destination) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path == summary_path and ".backup-" in destination_path.parent.name:
            raise OSError("fallo de respaldo")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.service.os.replace", fail_while_backing_up)

    with pytest.raises(OSError, match="fallo de respaldo"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    assert summary_path.read_bytes() == previous
    assert not (video_dir / "info.json").exists()
    assert not list(video_dir.parent.glob(".demo.backup-*"))


def test_restore_failure_preserves_backup_with_previous_bytes(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    previous = {"info.json": b'{"id":"anterior"}', "summary.md": b"resultado anterior"}
    for name, content in previous.items():
        (video_dir / name).write_bytes(content)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def fail_publish_and_restore(source, destination) -> None:
        source_path = Path(source)
        if source_path.name == "summary.md" and ".staging-" in source_path.parent.name:
            raise OSError("fallo de publicación")
        if source_path.name == "info.json" and ".backup-" in source_path.parent.name:
            raise OSError("fallo de restauración")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.service.os.replace", fail_publish_and_restore)

    with pytest.raises(VideoDataError, match="Respaldo conservado en"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    backup_dirs = list(video_dir.parent.glob(".demo.backup-*"))
    assert len(backup_dirs) == 1
    assert {name: (backup_dirs[0] / name).read_bytes() for name in previous} == previous


def test_cleanup_failure_after_rollback_does_not_lose_previous_generation(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    previous = {"info.json": b'{"id":"anterior"}', "summary.md": b"resultado anterior"}
    for name, content in previous.items():
        (video_dir / name).write_bytes(content)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def fail_while_publishing(source, destination) -> None:
        source_path = Path(source)
        if source_path.name == "summary.md" and ".staging-" in source_path.parent.name:
            raise OSError("fallo de publicación")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.service.os.replace", fail_while_publishing)
    monkeypatch.setattr("src.youtube_study.service.shutil.rmtree", lambda *args, **kwargs: None)

    with pytest.raises(OSError, match="fallo de publicación"):
        generate_study_files({"id": "demo"}, video_dir, selection, tmp_path / "library.json")

    assert {name: (video_dir / name).read_bytes() for name in previous} == previous
    assert len(list(video_dir.parent.glob(".demo.backup-*"))) == 1


def test_library_failure_happens_after_complete_generation_is_published(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    library_path = tmp_path / "library.json"
    previous_library = b'{"videos": []}\n'
    library_path.write_bytes(previous_library)

    def fail_library_update(*args, **kwargs) -> None:
        raise OSError("fallo de biblioteca")

    monkeypatch.setattr("src.youtube_study.service.upsert_video", fail_library_update)

    with pytest.raises(OSError, match="fallo de biblioteca"):
        generate_study_files({"id": "demo", "title": "Demo"}, video_dir, selection, library_path)

    assert ARTIFACT_NAMES.issubset({path.name for path in video_dir.iterdir()})
    assert library_path.read_bytes() == previous_library
