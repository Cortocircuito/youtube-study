from __future__ import annotations

import json
from pathlib import Path

import app
from src.youtube_study.downloader import SubtitleSelection


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

    app.generate_study_files(
        {"id": "demo", "title": "Demo Ñ", "uploader": "Canal Ñ"},
        video_dir,
        selection,
        tmp_path / "library.json",
    )

    expected = {
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
    assert expected.issubset({path.name for path in video_dir.iterdir()})

    tools = json.loads((video_dir / "tools.json").read_text(encoding="utf-8"))
    concepts = json.loads((video_dir / "concepts.json").read_text(encoding="utf-8"))
    info = json.loads((video_dir / "info.json").read_text(encoding="utf-8"))
    study = (video_dir / "study.md").read_text(encoding="utf-8")
    anki = (video_dir / "anki.csv").read_text(encoding="utf-8-sig")

    assert any(tool["name"] == "tailscale" for tool in tools)
    assert concepts and {"name", "score", "count", "timestamps"}.issubset(concepts[0])
    assert info["analysis"]["format_version"] == 1
    assert "# Estudio consolidado: Demo Ñ" in study
    assert "### tailscale" in study
    assert "video::demo" in anki
    assert "channel::Canal_Ñ" in anki


def test_export_study_recomputes_markdown_and_anki_from_subtitle(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    video_dir.mkdir(parents=True)
    subtitle_path = video_dir / "demo.es.vtt"
    write_demo_vtt(subtitle_path)
    (video_dir / "info.json").write_text(
        json.dumps({"id": "demo", "title": "Demo", "uploader": "Canal", "source_subtitle": str(subtitle_path)}),
        encoding="utf-8",
    )
    (video_dir / "summary.md").write_text("# Resumen\n\nCONTENIDO OBSOLETO", encoding="utf-8")
    (video_dir / "study.md").write_text("CONTENIDO OBSOLETO", encoding="utf-8")

    written = app.export_study("demo", tmp_path / "videos", "es", "all")

    assert [path.name for path in written] == ["study.md", "anki.csv"]
    study = (video_dir / "study.md").read_text(encoding="utf-8")
    anki = (video_dir / "anki.csv").read_text(encoding="utf-8-sig")
    assert "CONTENIDO OBSOLETO" not in study
    assert "### tailscale" in study
    assert "video::demo" in anki
