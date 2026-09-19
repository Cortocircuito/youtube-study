from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .analyzer import analyze_cues
from .study_models import ANALYSIS_FORMAT_VERSION, AnalysisResult, StudyIdea, StudyQuestion, flatten_questions
from .transcript import clean_vtt

QUALITY_CORPUS_VERSION = 1
QUALITY_METRIC_VERSION = 1
POSITIVE_METRICS = {
    "topic_coverage",
    "standalone_claim_coverage",
    "useful_question_precision",
    "useful_question_recall",
    "useful_question_f1",
}
NEGATIVE_METRICS = {"noise_rule_violation_rate", "summary_duplicate_rate"}
SUPPORTED_NOISE_SCOPES = {"ideas", "concepts", "question_prompts", "question_answers"}
SUPPORTED_QUESTION_CATEGORIES = {"basicas", "comprension", "practicas"}
TIMESTAMP_PATTERN = re.compile(r"\d{2}:\d{2}:\d{2}")


class QualityCorpusError(ValueError):
    pass


@dataclass(frozen=True)
class TopicTarget:
    id: str
    aliases: tuple[str, ...]
    timestamps: tuple[str, ...]


@dataclass(frozen=True)
class ClaimTarget:
    id: str
    marker_groups: tuple[tuple[str, ...], ...]
    timestamps: tuple[str, ...]


@dataclass(frozen=True)
class NoiseRule:
    id: str
    scope: str
    aliases: tuple[str, ...]
    max_occurrences: int


@dataclass(frozen=True)
class QuestionTarget:
    id: str
    category: str
    prompt_groups: tuple[tuple[str, ...], ...]
    answer_groups: tuple[tuple[str, ...], ...]
    timestamps: tuple[str, ...]


@dataclass(frozen=True)
class QualityCase:
    id: str
    profile: str
    vtt_path: Path
    topics: tuple[TopicTarget, ...]
    standalone_claims: tuple[ClaimTarget, ...]
    noise_rules: tuple[NoiseRule, ...]
    question_targets: tuple[QuestionTarget, ...]


@dataclass(frozen=True)
class QualityCorpus:
    schema_version: int
    digest: str
    cases: tuple[QualityCase, ...]


@dataclass(frozen=True)
class QualityMetrics:
    topic_coverage: float
    standalone_claim_coverage: float
    noise_rule_violation_rate: float
    summary_duplicate_rate: float
    useful_question_precision: float
    useful_question_recall: float
    useful_question_f1: float


@dataclass(frozen=True)
class QualityCaseReport:
    id: str
    profile: str
    metrics: QualityMetrics
    idea_count: int
    question_count: int


@dataclass(frozen=True)
class QualityReport:
    metric_version: int
    corpus_schema_version: int
    corpus_digest: str
    analysis_format_version: int
    cases: tuple[QualityCaseReport, ...]
    macro: QualityMetrics


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualityCorpusError(f"{location} debe ser un objeto")
    return value


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityCorpusError(f"{location} debe ser un texto no vacío")
    return value.strip()


def _string_list(value: Any, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise QualityCorpusError(f"{location} debe ser una lista no vacía")
    return tuple(_require_string(item, f"{location}[]") for item in value)


def _marker_groups(value: Any, location: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list) or not value:
        raise QualityCorpusError(f"{location} debe contener al menos un grupo")
    return tuple(_string_list(group, f"{location}[]") for group in value)


def _timestamps(value: Any, location: str) -> tuple[str, ...]:
    timestamps = _string_list(value, location)
    if any(not TIMESTAMP_PATTERN.fullmatch(timestamp) for timestamp in timestamps):
        raise QualityCorpusError(f"{location} contiene un timestamp inválido")
    return timestamps


def _unique_ids(items: tuple[Any, ...], location: str) -> None:
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise QualityCorpusError(f"{location} contiene IDs duplicados")


def load_quality_corpus(path: Path) -> QualityCorpus:
    try:
        corpus_bytes = path.read_bytes()
        root = _require_object(json.loads(corpus_bytes), "corpus")
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityCorpusError(f"No se pudo leer el corpus de calidad: {path}") from exc

    version = root.get("schema_version")
    if version != QUALITY_CORPUS_VERSION:
        raise QualityCorpusError(f"Versión de corpus no soportada: {version}")
    raw_cases = root.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise QualityCorpusError("corpus.cases debe ser una lista no vacía")

    cases: list[QualityCase] = []
    for case_index, raw_case in enumerate(raw_cases):
        location = f"corpus.cases[{case_index}]"
        case = _require_object(raw_case, location)
        case_id = _require_string(case.get("id"), f"{location}.id")
        profile = _require_string(case.get("profile"), f"{location}.profile")
        vtt_name = _require_string(case.get("vtt"), f"{location}.vtt")
        vtt_path = path.parent / vtt_name
        if not vtt_path.is_file() or not vtt_path.read_text(encoding="utf-8").strip():
            raise QualityCorpusError(f"El fixture no existe o está vacío: {vtt_path}")

        topics = tuple(
            TopicTarget(
                id=_require_string(item.get("id"), f"{location}.topics[].id"),
                aliases=_string_list(item.get("aliases"), f"{location}.topics[].aliases"),
                timestamps=_timestamps(item.get("timestamps"), f"{location}.topics[].timestamps"),
            )
            for raw_item in case.get("topics", [])
            for item in [_require_object(raw_item, f"{location}.topics[]")]
        )
        claims = tuple(
            ClaimTarget(
                id=_require_string(item.get("id"), f"{location}.standalone_claims[].id"),
                marker_groups=_marker_groups(
                    item.get("marker_groups"), f"{location}.standalone_claims[].marker_groups"
                ),
                timestamps=_timestamps(item.get("timestamps"), f"{location}.standalone_claims[].timestamps"),
            )
            for raw_item in case.get("standalone_claims", [])
            for item in [_require_object(raw_item, f"{location}.standalone_claims[]")]
        )
        noise_rules = tuple(
            NoiseRule(
                id=_require_string(item.get("id"), f"{location}.noise_rules[].id"),
                scope=_require_string(item.get("scope"), f"{location}.noise_rules[].scope"),
                aliases=_string_list(item.get("aliases"), f"{location}.noise_rules[].aliases"),
                max_occurrences=item.get("max_occurrences"),
            )
            for raw_item in case.get("noise_rules", [])
            for item in [_require_object(raw_item, f"{location}.noise_rules[]")]
        )
        question_targets = tuple(
            QuestionTarget(
                id=_require_string(item.get("id"), f"{location}.question_targets[].id"),
                category=_require_string(item.get("category"), f"{location}.question_targets[].category"),
                prompt_groups=_marker_groups(item.get("prompt_groups"), f"{location}.question_targets[].prompt_groups"),
                answer_groups=_marker_groups(item.get("answer_groups"), f"{location}.question_targets[].answer_groups"),
                timestamps=_timestamps(item.get("timestamps"), f"{location}.question_targets[].timestamps"),
            )
            for raw_item in case.get("question_targets", [])
            for item in [_require_object(raw_item, f"{location}.question_targets[]")]
        )

        if not topics or not claims or not noise_rules or not question_targets:
            raise QualityCorpusError(f"{location} necesita topics, standalone_claims, noise_rules y question_targets")
        for rule in noise_rules:
            if rule.scope not in SUPPORTED_NOISE_SCOPES:
                raise QualityCorpusError(f"Scope de ruido no soportado: {rule.scope}")
            if not isinstance(rule.max_occurrences, int) or rule.max_occurrences < 0:
                raise QualityCorpusError(f"max_occurrences inválido en la regla {rule.id}")
        for target in question_targets:
            if target.category not in SUPPORTED_QUESTION_CATEGORIES:
                raise QualityCorpusError(f"Categoría de pregunta no soportada: {target.category}")
        for name, values in (
            ("topics", topics),
            ("standalone_claims", claims),
            ("noise_rules", noise_rules),
            ("question_targets", question_targets),
        ):
            _unique_ids(values, f"{location}.{name}")
        cases.append(QualityCase(case_id, profile, vtt_path, topics, claims, noise_rules, question_targets))

    digest = hashlib.sha256(corpus_bytes)
    for case in cases:
        digest.update(case.id.encode("utf-8"))
        digest.update(case.vtt_path.read_bytes())
    result = QualityCorpus(version, digest.hexdigest(), tuple(cases))
    _unique_ids(result.cases, "corpus.cases")
    return result


def normalize_quality_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def contains_alias(text: str, alias: str) -> bool:
    normalized_text = f" {normalize_quality_text(text)} "
    normalized_alias = normalize_quality_text(alias)
    return bool(normalized_alias) and f" {normalized_alias} " in normalized_text


def matches_groups(text: str, groups: tuple[tuple[str, ...], ...]) -> bool:
    return all(any(contains_alias(text, alias) for alias in group) for group in groups)


def _reference_text(item: StudyIdea | StudyQuestion, timestamps: tuple[str, ...]) -> str:
    expected = set(timestamps)
    return " ".join(fragment.text for fragment in item.evidence.fragments if fragment.timestamp in expected)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _scope_text(result: AnalysisResult, scope: str) -> str:
    questions = flatten_questions(result.questions)
    values = {
        "ideas": [idea.text for idea in result.ideas],
        "concepts": [concept.name for concept in result.concepts],
        "question_prompts": [question.question for question in questions],
        "question_answers": [question.answer for question in questions],
    }
    return "\n".join(values[scope])


def _alias_occurrences(text: str, aliases: tuple[str, ...]) -> int:
    normalized = f" {normalize_quality_text(text)} "
    return sum(normalized.count(f" {normalize_quality_text(alias)} ") for alias in aliases)


def _duplicate_rate(ideas: list[StudyIdea]) -> float:
    pairs = 0
    duplicates = 0
    for index, left in enumerate(ideas):
        left_tokens = set(normalize_quality_text(left.text).split())
        for right in ideas[index + 1 :]:
            right_tokens = set(normalize_quality_text(right.text).split())
            if not left_tokens or not right_tokens:
                continue
            pairs += 1
            similarity = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            duplicates += similarity >= 0.72
    return _ratio(duplicates, pairs)


def _question_matches(question: StudyQuestion, target: QuestionTarget) -> bool:
    reference_text = _reference_text(question, target.timestamps)
    return (
        question.category == target.category
        and matches_groups(question.question, target.prompt_groups)
        and matches_groups(reference_text, target.answer_groups)
        and bool(TIMESTAMP_PATTERN.fullmatch(question.timestamp))
    )


def evaluate_quality_case(case: QualityCase, result: AnalysisResult | None = None) -> QualityCaseReport:
    result = result or analyze_cues(clean_vtt(case.vtt_path))
    topic_hits = sum(
        any(
            any(contains_alias(_reference_text(idea, topic.timestamps), alias) for alias in topic.aliases)
            for idea in result.ideas
        )
        for topic in case.topics
    )
    claim_hits = sum(
        any(matches_groups(_reference_text(idea, claim.timestamps), claim.marker_groups) for idea in result.ideas)
        for claim in case.standalone_claims
    )
    noise_violations = sum(
        _alias_occurrences(_scope_text(result, rule.scope), rule.aliases) > rule.max_occurrences
        for rule in case.noise_rules
    )

    questions = flatten_questions(result.questions)
    matched_targets = sum(
        any(_question_matches(question, target) for question in questions) for target in case.question_targets
    )
    useful_questions = sum(
        any(_question_matches(question, target) for target in case.question_targets) for question in questions
    )
    precision = _ratio(useful_questions, len(questions))
    recall = _ratio(matched_targets, len(case.question_targets))
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    metrics = QualityMetrics(
        topic_coverage=round(_ratio(topic_hits, len(case.topics)), 6),
        standalone_claim_coverage=round(_ratio(claim_hits, len(case.standalone_claims)), 6),
        noise_rule_violation_rate=round(_ratio(noise_violations, len(case.noise_rules)), 6),
        summary_duplicate_rate=round(_duplicate_rate(result.ideas), 6),
        useful_question_precision=round(precision, 6),
        useful_question_recall=round(recall, 6),
        useful_question_f1=round(f1, 6),
    )
    return QualityCaseReport(case.id, case.profile, metrics, len(result.ideas), len(questions))


def evaluate_quality_corpus(corpus: QualityCorpus) -> QualityReport:
    reports = tuple(evaluate_quality_case(case) for case in corpus.cases)
    metric_names = QualityMetrics.__dataclass_fields__
    macro = QualityMetrics(
        **{
            name: round(sum(getattr(report.metrics, name) for report in reports) / len(reports), 6)
            for name in metric_names
        }
    )
    return QualityReport(
        metric_version=QUALITY_METRIC_VERSION,
        corpus_schema_version=corpus.schema_version,
        corpus_digest=corpus.digest,
        analysis_format_version=ANALYSIS_FORMAT_VERSION,
        cases=reports,
        macro=macro,
    )


def quality_report_payload(report: QualityReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["cases"] = {
        case["id"]: {key: value for key, value in case.items() if key != "id"} for case in payload["cases"]
    }
    return payload


def baseline_regressions(report: QualityReport, baseline_path: Path) -> list[str]:
    try:
        baseline = _require_object(json.loads(baseline_path.read_text(encoding="utf-8")), "baseline")
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityCorpusError(f"No se pudo leer el baseline: {baseline_path}") from exc
    if baseline.get("metric_version") != report.metric_version:
        raise QualityCorpusError("El baseline usa otra versión de métricas")
    if baseline.get("corpus_schema_version") != report.corpus_schema_version:
        raise QualityCorpusError("El baseline usa otra versión del corpus")
    if baseline.get("corpus_digest") != report.corpus_digest:
        raise QualityCorpusError("El baseline no corresponde al contenido actual del corpus y sus fixtures")
    if baseline.get("analysis_format_version") != report.analysis_format_version:
        raise QualityCorpusError("El baseline usa otra versión de análisis")

    current = quality_report_payload(report)
    expected_cases = baseline.get("cases")
    if not isinstance(expected_cases, dict) or set(expected_cases) != set(current["cases"]):
        raise QualityCorpusError("Los casos del baseline no coinciden con el corpus")

    regressions: list[str] = []
    comparisons = [("macro", current["macro"], baseline.get("macro"))]
    comparisons.extend(
        (f"case:{case_id}", current["cases"][case_id]["metrics"], expected_cases[case_id]["metrics"])
        for case_id in expected_cases
    )
    for location, actual, expected in comparisons:
        if not isinstance(expected, dict):
            raise QualityCorpusError(f"Faltan métricas en {location}")
        for metric in POSITIVE_METRICS | NEGATIVE_METRICS:
            actual_value = actual[metric]
            expected_value = expected.get(metric)
            if (
                isinstance(expected_value, bool)
                or not isinstance(expected_value, int | float)
                or not math.isfinite(expected_value)
                or not 0 <= expected_value <= 1
            ):
                raise QualityCorpusError(f"Baseline inválido para {location}.{metric}")
            regressed = actual_value < expected_value if metric in POSITIVE_METRICS else actual_value > expected_value
            if regressed:
                regressions.append(f"{location}.{metric}: actual={actual_value}, baseline={expected_value}")
    return regressions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evalúa la calidad heurística sobre un corpus versionado")
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args(argv)
    report = evaluate_quality_corpus(load_quality_corpus(args.corpus))
    print(json.dumps(quality_report_payload(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
