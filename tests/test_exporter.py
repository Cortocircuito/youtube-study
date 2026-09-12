from __future__ import annotations

import csv
import json
from pathlib import Path

from src.youtube_study.analyzer import analyze_cues
from src.youtube_study.exporter import write_anki_csv, write_study_markdown_from_result
from src.youtube_study.transcript import Cue


def test_write_anki_csv_preserves_utf8_quotes_and_tags(tmp_path: Path) -> None:
    path = tmp_path / "anki.csv"
    cards = [{"question": "¿Qué es SSH, seguro?", "answer": "Acceso remoto, cifrado", "tags": "tool ssh"}]

    write_anki_csv(path, cards, "vídeo-ñ", "Canal Ñ")

    raw = path.read_text(encoding="utf-8-sig")
    assert '"¿Qué es SSH, seguro?","Acceso remoto, cifrado"' in raw
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    assert rows[0]["Front"] == "¿Qué es SSH, seguro?"
    assert rows[0]["Back"] == "Acceso remoto, cifrado"
    assert rows[0]["Tags"] == "video::vídeo-ñ channel::Canal_Ñ tool ssh"


def test_study_markdown_is_generated_from_structured_result(tmp_path: Path) -> None:
    result = analyze_cues(
        [
            Cue("00:00:01", "Tailscale conecta equipos para usar SSH sin abrir puertos."),
            Cue("00:00:10", "Tailscale mantiene una red privada y SSH permite acceso remoto seguro."),
        ]
    )

    path = tmp_path / "study.md"
    write_study_markdown_from_result(path, "Guía Ñ", result)

    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Estudio consolidado: Guía Ñ")
    assert "## Herramientas" in content
    assert "### tailscale" in content
    assert "## Flashcards" in content
    assert "_Formato de análisis: 1_" in content


def test_info_written_by_pipeline_contains_analysis_metadata(tmp_path: Path) -> None:
    from src.youtube_study.downloader import SubtitleSelection
    from src.youtube_study.exporter import write_info

    info_path = tmp_path / "info.json"
    selection = SubtitleSelection(
        path=tmp_path / "demo.es.vtt",
        language="es",
        kind="manual",
        reason="subtítulo manual en idioma solicitado",
    )

    write_info(info_path, {"id": "demo", "title": "Demo"}, selection, analysis_version=1)

    payload = json.loads(info_path.read_text(encoding="utf-8"))
    assert payload["analysis"]["format_version"] == 1
    assert "generated_at" in payload["analysis"]
    assert payload["source_subtitle"]["kind"] == "manual"
