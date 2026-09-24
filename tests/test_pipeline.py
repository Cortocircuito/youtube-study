from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.youtube_study.downloader import SubtitleSelection
from src.youtube_study.errors import ArtifactPublicationError, VideoDataError
from src.youtube_study.models import VideoMetadata
from src.youtube_study.service import (
    analyze_existing,
    export_study,
    generate_study_files,
    load_existing_video,
    process_video,
)

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


def test_analysis_value_error_is_reported_as_video_data_error(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    selection = SubtitleSelection(subtitle_path, "es", "manual", "selección de prueba")

    def invalid_analysis(cues: object) -> object:
        raise ValueError("evidencia inconsistente")

    monkeypatch.setattr("src.youtube_study.service.analyze_cues", invalid_analysis)

    with pytest.raises(VideoDataError, match="No se pudo analizar") as error:
        generate_study_files(VideoMetadata("demo", "Demo"), video_dir, selection, tmp_path / "library.json")

    assert isinstance(error.value.__cause__, ValueError)


def test_generate_study_files_writes_all_artifacts_from_one_analysis(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    subtitle_bytes = subtitle_path.read_bytes()
    selection = SubtitleSelection(
        path=subtitle_path,
        language="es",
        kind="manual",
        reason="subtítulo manual en idioma solicitado",
    )

    generate_study_files(
        VideoMetadata(
            id="demo",
            title="Demo Ñ",
            uploader="Canal Ñ",
            webpage_url="https://www.youtube.com/watch?v=demo",
        ),
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
    assert concepts and {
        "name",
        "score",
        "count",
        "frequency_score",
        "distribution_score",
        "association_score",
        "timestamps",
    }.issubset(concepts[0])
    assert info["analysis"]["format_version"] == 3
    concept_markdown = (video_dir / "concepts.md").read_text(encoding="utf-8")
    assert all(f"## {concept['name']}" in concept_markdown for concept in concepts)
    assert all(f"### {concept['name']}" in study for concept in concepts)
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
    assert subtitle_path.read_bytes() == subtitle_bytes


@pytest.mark.parametrize("legacy_version", [1, 2])
def test_analyze_existing_migrates_old_artifacts_to_v3_without_network(legacy_version: int, tmp_path: Path) -> None:
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
                "analysis": {"format_version": legacy_version},
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
    assert info["analysis"]["format_version"] == 3
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

    monkeypatch.setattr("src.youtube_study.service.write_anki_csv", fail_writer)

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
        generate_study_files(VideoMetadata("demo", "demo"), video_dir, selection, tmp_path / "library.json")

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
        generate_study_files(VideoMetadata("demo", "demo"), video_dir, selection, tmp_path / "library.json")

    assert summary_path.read_text(encoding="utf-8") == "resultado anterior"
    assert not (video_dir / "info.json").exists()


def test_publish_failure_is_controlled_and_retry_completes(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    subtitle_bytes = subtitle_path.read_bytes()
    summary_path = video_dir / "summary.md"
    summary_path.write_bytes(b"resultado anterior")
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def fail_while_publishing(source, destination) -> None:
        source_path = Path(source)
        if source_path.name == "summary.md" and ".staging-" in source_path.parent.name:
            raise OSError("fallo de publicación")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", fail_while_publishing)

    with pytest.raises(ArtifactPublicationError, match="repite study o analyze"):
        generate_study_files(VideoMetadata("demo", "demo"), video_dir, selection, tmp_path / "library.json")

    assert json.loads((video_dir / "info.json").read_text(encoding="utf-8"))["id"] == "demo"
    assert summary_path.read_bytes() == b"resultado anterior"
    assert subtitle_path.read_bytes() == subtitle_bytes
    assert not list(video_dir.parent.glob(".demo.backup-*"))
    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", original_replace)
    analyze_existing("demo", tmp_path / "videos", "es")

    assert ARTIFACT_NAMES.issubset({path.name for path in video_dir.iterdir()})
    assert summary_path.read_bytes() != b"resultado anterior"
    assert subtitle_path.read_bytes() == subtitle_bytes


def test_interrupted_publication_is_completed_by_rerunning_analyze(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    subtitle_bytes = subtitle_path.read_bytes()
    selection = SubtitleSelection(subtitle_path, "es", "manual", "test")
    original_replace = os.replace

    def interrupt_while_publishing(source, destination) -> None:
        source_path = Path(source)
        if source_path.name == "summary.md" and ".staging-" in source_path.parent.name:
            raise KeyboardInterrupt
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", interrupt_while_publishing)

    with pytest.raises(KeyboardInterrupt):
        generate_study_files(VideoMetadata("demo", "demo"), video_dir, selection, tmp_path / "library.json")

    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", original_replace)
    analyze_existing("demo", tmp_path / "videos", "es")

    assert ARTIFACT_NAMES.issubset({path.name for path in video_dir.iterdir()})
    assert subtitle_path.read_bytes() == subtitle_bytes


def test_export_publication_failure_is_controlled_and_retry_completes(monkeypatch, tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    subtitle_bytes = subtitle_path.read_bytes()
    (video_dir / "info.json").write_text(
        json.dumps({"id": "demo", "title": "Demo", "source_subtitle": str(subtitle_path)}), encoding="utf-8"
    )
    (video_dir / "study.md").write_bytes(b"estudio anterior")
    (video_dir / "anki.csv").write_bytes(b"anki anterior")
    original_replace = os.replace

    def fail_anki(source, destination) -> None:
        if Path(destination).name == "anki.csv":
            raise OSError("fallo de publicación")
        original_replace(source, destination)

    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", fail_anki)

    with pytest.raises(ArtifactPublicationError, match="repite export"):
        export_study("demo", tmp_path / "videos", "es", "all")

    assert (video_dir / "study.md").read_bytes() != b"estudio anterior"
    assert (video_dir / "anki.csv").read_bytes() == b"anki anterior"
    assert subtitle_path.read_bytes() == subtitle_bytes
    monkeypatch.setattr("src.youtube_study.artifacts.os.replace", original_replace)
    export_study("demo", tmp_path / "videos", "es", "all")

    assert (video_dir / "anki.csv").read_bytes() != b"anki anterior"
    assert subtitle_path.read_bytes() == subtitle_bytes


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
        generate_study_files(VideoMetadata("demo", "Demo"), video_dir, selection, library_path)

    assert ARTIFACT_NAMES.issubset({path.name for path in video_dir.iterdir()})
    assert library_path.read_bytes() == previous_library


def test_process_video_passes_download_options_and_generates_selected_video(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "videos"
    video_dir = out / "demo"
    selection = SubtitleSelection(video_dir / "demo.es.vtt", "es", "manual", "test")
    calls: dict[str, object] = {}

    def fake_download(
        url: str,
        target: Path,
        languages: str,
        *,
        force_download: bool,
        quiet: bool,
    ) -> dict[str, object]:
        calls["download"] = (url, target, languages, force_download, quiet)
        return {
            "id": "demo",
            "title": "Demo",
            "uploader": "Canal",
            "duration": 125,
            "webpage_url": "https://example.test/demo",
        }

    def fake_choose(
        target: Path,
        video_id: str,
        languages: list[str],
        info: dict[str, object] | None = None,
    ) -> SubtitleSelection:
        calls["choose"] = (target, video_id, languages, info)
        return selection

    def fake_generate(
        metadata: VideoMetadata,
        target: Path,
        selected: SubtitleSelection,
        library_path: Path,
    ) -> Path:
        calls["generate"] = (metadata, target, selected, library_path)
        return target

    monkeypatch.setattr("src.youtube_study.service.download_subtitles", fake_download)
    monkeypatch.setattr("src.youtube_study.service.choose_subtitle", fake_choose)
    monkeypatch.setattr("src.youtube_study.service.generate_study_files", fake_generate)

    result = process_video(
        "https://example.test/demo",
        out,
        "es-419, es",
        force_download=True,
        quiet=True,
    )

    assert result == video_dir
    assert calls["download"] == ("https://example.test/demo", out, "es-419, es", True, True)
    downloaded_info = {
        "id": "demo",
        "title": "Demo",
        "uploader": "Canal",
        "duration": 125,
        "webpage_url": "https://example.test/demo",
    }
    assert calls["choose"] == (video_dir, "demo", ["es-419", "es"], downloaded_info)
    generated = calls["generate"]
    assert isinstance(generated, tuple)
    assert generated[0] == VideoMetadata(
        id="demo",
        title="Demo",
        uploader="Canal",
        duration=125,
        webpage_url="https://example.test/demo",
    )
    assert generated[1:] == (video_dir, selection, tmp_path / "library.json")


def test_load_existing_video_reports_missing_directory_and_info(tmp_path: Path) -> None:
    out = tmp_path / "videos"

    with pytest.raises(VideoDataError, match="No existe el directorio"):
        load_existing_video("missing", out, "es")

    (out / "demo").mkdir(parents=True)
    with pytest.raises(VideoDataError, match="No existe info.json"):
        load_existing_video("demo", out, "es")
