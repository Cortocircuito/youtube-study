from __future__ import annotations

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
