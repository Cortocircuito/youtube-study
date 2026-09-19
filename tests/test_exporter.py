from __future__ import annotations

import csv
import json
from pathlib import Path

from src.youtube_study.analyzer import analyze_cues
from src.youtube_study.exporter import (
    markdown_reference,
    timestamp_url,
    write_anki_csv,
    write_study_markdown_from_result,
)
from src.youtube_study.study_models import Flashcard, SourceExcerpt, SourceFragment
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


def test_timestamp_url_preserves_query_replaces_time_and_supports_fallback() -> None:
    source = "https://www.youtube.com/watch?v=abc&t=4&list=xyz#chapter"

    assert timestamp_url(source, "00:01:23") == ("https://www.youtube.com/watch?v=abc&list=xyz&t=83#chapter")
    assert timestamp_url("https://youtu.be/abc?si=share", "01:00:01") == "https://youtu.be/abc?si=share&t=3601"
    assert timestamp_url(None, "00:01:23") is None
    assert timestamp_url("not-a-url", "00:01:23") is None
    assert markdown_reference("00:01:23", None) == "[00:01:23]"


def test_anki_csv_adds_clickable_reference_without_changing_columns(tmp_path: Path) -> None:
    path = tmp_path / "anki.csv"
    evidence = SourceExcerpt(
        "Respuesta",
        (SourceFragment(cue_index=0, timestamp="00:01:23", start=0, end=9, text="Respuesta"),),
    )
    card = Flashcard("Pregunta", evidence, "question type::basicas")

    write_anki_csv(path, [card], "demo", source_url="https://youtu.be/abc?si=share")

    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    assert list(rows[0]) == ["Front", "Back", "Tags"]
    assert 'href="https://youtu.be/abc?si=share&amp;t=83"' in rows[0]["Back"]
    assert "Referencia:" in rows[0]["Back"]


def test_study_markdown_is_generated_from_structured_result(tmp_path: Path) -> None:
    result = analyze_cues(
        [
            Cue("00:00:01", "Tailscale conecta equipos para usar SSH sin abrir puertos."),
            Cue("00:00:10", "Tailscale mantiene una red privada y SSH permite acceso remoto seguro."),
        ]
    )

    path = tmp_path / "study.md"
    write_study_markdown_from_result(path, "Guía Ñ", result, "https://youtu.be/demo")

    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Estudio consolidado: Guía Ñ")
    assert "## Herramientas" in content
    assert "### tailscale" in content
    assert "## Flashcards" in content
    assert "_Formato de análisis: 2_" in content
    assert "[00:00:01](https://youtu.be/demo?t=1)" in content


def test_info_written_by_pipeline_contains_analysis_metadata(tmp_path: Path) -> None:
    from src.youtube_study.downloader import SubtitleSelection
    from src.youtube_study.exporter import write_info
    from src.youtube_study.models import VideoMetadata

    info_path = tmp_path / "info.json"
    selection = SubtitleSelection(
        path=tmp_path / "demo.es.vtt",
        language="es",
        kind="manual",
        reason="subtítulo manual en idioma solicitado",
    )

    write_info(info_path, VideoMetadata("demo", "Demo"), selection, analysis_version=1)

    payload = json.loads(info_path.read_text(encoding="utf-8"))
    assert payload["analysis"]["format_version"] == 1
    assert "generated_at" in payload["analysis"]
    assert payload["source_subtitle"]["kind"] == "manual"
