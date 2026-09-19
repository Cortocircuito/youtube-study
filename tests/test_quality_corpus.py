from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.youtube_study.analyzer import analyze_cues
from src.youtube_study.quality import (
    NEGATIVE_METRICS,
    POSITIVE_METRICS,
    QualityCorpusError,
    baseline_regressions,
    contains_alias,
    evaluate_quality_corpus,
    load_quality_corpus,
    matches_groups,
    quality_report_payload,
)
from src.youtube_study.study_models import flatten_questions
from src.youtube_study.transcript import clean_vtt

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_PATH = FIXTURES / "quality_corpus.v1.json"
BASELINE_PATH = FIXTURES / "quality_baseline.v1.json"


def test_quality_corpus_contract_and_reference_timestamps() -> None:
    corpus = load_quality_corpus(CORPUS_PATH)

    assert corpus.schema_version == 1
    assert {case.id for case in corpus.cases} == {"gardening", "databases", "security", "noisy_energy"}
    assert len({case.profile for case in corpus.cases}) == len(corpus.cases)
    for case in corpus.cases:
        cue_timestamps = {cue.start for cue in clean_vtt(case.vtt_path)}
        referenced = {
            timestamp
            for target in (*case.topics, *case.standalone_claims, *case.question_targets)
            for timestamp in target.timestamps
        }
        assert referenced <= cue_timestamps


def test_quality_matcher_normalizes_accents_and_respects_word_boundaries() -> None:
    text = "La RESTAURACIÓN verificada confirma que los datos pueden recuperarse."

    assert contains_alias(text, "restauracion")
    assert contains_alias(text, "datos")
    assert not contains_alias(text, "dato")
    assert matches_groups(text, (("restaurar", "restauración"), ("recuperarse",)))
    assert not matches_groups(text, (("restauración",), ("cifrado",)))


def test_quality_corpus_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    payload["cases"].append(payload["cases"][0])
    invalid_path = tmp_path / "quality_corpus.v1.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    for fixture in FIXTURES.glob("quality_*.vtt"):
        (tmp_path / fixture.name).write_bytes(fixture.read_bytes())

    with pytest.raises(QualityCorpusError, match="IDs duplicados"):
        load_quality_corpus(invalid_path)


def test_quality_corpus_requires_noise_annotations(tmp_path: Path) -> None:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    payload["cases"][0]["noise_rules"] = []
    invalid_path = tmp_path / "quality_corpus.v1.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    for fixture in FIXTURES.glob("quality_*.vtt"):
        (tmp_path / fixture.name).write_bytes(fixture.read_bytes())

    with pytest.raises(QualityCorpusError, match="noise_rules"):
        load_quality_corpus(invalid_path)


def test_quality_report_preserves_extract_source_invariants() -> None:
    corpus = load_quality_corpus(CORPUS_PATH)

    for case in corpus.cases:
        result = analyze_cues(clean_vtt(case.vtt_path))
        items = [*result.ideas, *flatten_questions(result.questions), *result.cards]
        for item in items:
            assert item.evidence.text == " ".join(fragment.text for fragment in item.evidence.fragments)
            assert item.timestamp == item.evidence.fragments[0].timestamp
            for fragment in item.evidence.fragments:
                cue = result.cues[fragment.cue_index]
                assert cue.text[fragment.start : fragment.end] == fragment.text


def test_current_quality_does_not_regress_from_versioned_baseline() -> None:
    report = evaluate_quality_corpus(load_quality_corpus(CORPUS_PATH))

    assert baseline_regressions(report, BASELINE_PATH) == []
    assert set(report.macro.__dataclass_fields__) == POSITIVE_METRICS | NEGATIVE_METRICS
    assert all(0.0 <= value <= 1.0 for value in report.macro.__dict__.values())


def test_baseline_comparison_reports_positive_and_negative_regressions(tmp_path: Path) -> None:
    report = evaluate_quality_corpus(load_quality_corpus(CORPUS_PATH))
    baseline = quality_report_payload(report)
    baseline["macro"]["useful_question_precision"] += 0.1
    baseline["macro"]["noise_rule_violation_rate"] -= 0.1
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    regressions = baseline_regressions(report, baseline_path)

    assert any("macro.useful_question_precision" in item for item in regressions)
    assert any("macro.noise_rule_violation_rate" in item for item in regressions)


def test_baseline_is_bound_to_corpus_content(tmp_path: Path) -> None:
    report = evaluate_quality_corpus(load_quality_corpus(CORPUS_PATH))
    baseline = quality_report_payload(report)
    baseline["corpus_digest"] = "0" * 64
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    with pytest.raises(QualityCorpusError, match="contenido actual"):
        baseline_regressions(report, baseline_path)


@pytest.mark.parametrize("invalid_value", [True, -0.1, 1.1, float("nan")])
def test_baseline_rejects_invalid_metric_values(tmp_path: Path, invalid_value: object) -> None:
    report = evaluate_quality_corpus(load_quality_corpus(CORPUS_PATH))
    baseline = quality_report_payload(report)
    baseline["macro"]["topic_coverage"] = invalid_value
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    with pytest.raises(QualityCorpusError, match="Baseline inválido"):
        baseline_regressions(report, baseline_path)
