from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import app


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "app.py", *args],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )


def test_search_rejects_non_positive_limit() -> None:
    result = run_cli("search", "test", "--limit", "0")
    assert result.returncode == 2
    assert "debe ser >= 1" in result.stderr


def test_show_missing_video_returns_error(tmp_path: Path) -> None:
    result = run_cli("show", "VIDEO_INEXISTENTE", "--out", str(tmp_path / "videos"))
    assert result.returncode == 1
    assert "No existe el video VIDEO_INEXISTENTE" in result.stderr
    assert "Traceback" not in result.stderr


def test_search_missing_video_filter_returns_error(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "library.json").write_text('{"videos": []}', encoding="utf-8")

    result = run_cli("search", "ssh", "--video", "missing", "--out", str(data_dir / "videos"))
    assert result.returncode == 1
    assert "No existe el video missing" in result.stderr


def test_analyze_invalid_info_json_returns_error(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "abc123"
    video_dir.mkdir(parents=True)
    (video_dir / "info.json").write_text("{", encoding="utf-8")

    result = run_cli("analyze", "abc123", "--out", str(tmp_path / "videos"))
    assert result.returncode == 1
    assert "info.json inválido" in result.stderr
    assert "Traceback" not in result.stderr


def test_help_is_available() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    assert "Descarga transcripciones de YouTube" in result.stdout
    assert "rebuild-library" in result.stdout


def test_list_and_show_successfully_display_library_entry(tmp_path: Path) -> None:
    videos_dir = tmp_path / "data" / "videos"
    video_dir = videos_dir / "demo"
    video_dir.mkdir(parents=True)
    library = {
        "videos": [
            {
                "id": "demo",
                "title": "Video de prueba",
                "channel": "Canal de prueba",
                "duration": 65,
                "url": "https://example.test/demo",
                "path": "videos/demo",
                "tools": ["ssh"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
    }
    (tmp_path / "data" / "library.json").write_text(json.dumps(library), encoding="utf-8")
    (video_dir / "summary.md").write_text("# Resumen", encoding="utf-8")

    listed = run_cli("list", "--out", str(videos_dir))
    shown = run_cli("show", "demo", "--out", str(videos_dir))

    assert listed.returncode == 0
    assert "demo | 1:05 | Video de prueba" in listed.stdout
    assert "Herramientas: ssh" in listed.stdout
    assert shown.returncode == 0
    assert "Título: Video de prueba" in shown.stdout
    assert "- summary.md" in shown.stdout


def test_rebuild_library_command_creates_and_lists_video(tmp_path: Path) -> None:
    videos_dir = tmp_path / "data" / "videos"
    video_dir = videos_dir / "demo"
    video_dir.mkdir(parents=True)
    (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Reconstruido"}), encoding="utf-8")

    rebuilt = run_cli("rebuild-library", "--out", str(videos_dir))
    listed = run_cli("list", "--out", str(videos_dir))

    assert rebuilt.returncode == 0
    assert "Biblioteca reconstruida: 1 videos." in rebuilt.stdout
    assert listed.returncode == 0
    assert "Reconstruido" in listed.stdout


def test_analyze_and_export_successfully_via_cli(tmp_path: Path) -> None:
    videos_dir = tmp_path / "videos"
    video_dir = videos_dir / "demo"
    video_dir.mkdir(parents=True)
    (video_dir / "demo.es.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n"
        "Tailscale permite usar SSH sin abrir puertos.\n",
        encoding="utf-8",
    )
    (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Demo", "uploader": "Canal"}), encoding="utf-8")

    analyzed = run_cli("analyze", "demo", "--out", str(videos_dir))
    exported = run_cli("export", "demo", "--format", "all", "--out", str(videos_dir))

    assert analyzed.returncode == 0
    assert "Archivos regenerados" in analyzed.stdout
    assert (video_dir / "tools.json").exists()
    assert exported.returncode == 0
    assert "Archivos exportados" in exported.stdout
    assert (video_dir / "study.md").exists()
    assert (video_dir / "anki.csv").exists()


def test_url_shortcut_invokes_study_command(monkeypatch, tmp_path: Path, capsys) -> None:
    generated = tmp_path / "video"
    generated.mkdir()
    (generated / "summary.md").write_text("# Resumen", encoding="utf-8")
    calls: list[tuple[str, Path, str]] = []

    def fake_process_video(url: str, out: Path, lang: str, *, force_download: bool = False, quiet: bool = False) -> Path:
        calls.append((url, out, lang))
        return generated

    monkeypatch.setattr(app, "process_video", fake_process_video)

    assert app.run(["https://youtu.be/example", "--out", str(tmp_path / "videos")]) == 0
    assert calls == [("https://youtu.be/example", tmp_path / "videos", "es-419,es,es-orig")]
    assert "Archivos generados" in capsys.readouterr().out
