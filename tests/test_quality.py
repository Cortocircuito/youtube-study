from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.youtube_study.analyzer import STOPWORDS, analyze_cues, cue_windows
from src.youtube_study.transcript import Cue, clean_vtt

FIXTURES = Path(__file__).parent / "fixtures"
CASES = {
    "gardening": {
        "path": FIXTURES / "quality_gardening.vtt",
        "terms": {"tomates", "riego", "humedad"},
        "first_timestamp": "00:00:01",
        "rolling_prefix": "para cultivar tomates sanos",
    },
    "databases": {
        "path": FIXTURES / "quality_databases.vtt",
        "terms": {"consultas", "índice", "transacciones"},
        "first_timestamp": "00:00:02",
        "rolling_prefix": "antes de optimizar una base de datos",
    },
    "security": {
        "path": FIXTURES / "quality_security.vtt",
        "terms": {"cifrado", "permisos", "copias"},
        "first_timestamp": "00:00:03",
        "rolling_prefix": "el cifrado protege los archivos",
    },
}


def normalized_tokens(text: str) -> set[str]:
    """Return stable content tokens for semantic quality assertions."""
    tokens = re.findall(r"[a-záéíóúñü0-9]+", text.lower())
    return {token for token in tokens if len(token) > 2 and token not in STOPWORDS}


def token_similarity(left: str, right: str) -> float:
    left_tokens = normalized_tokens(left)
    right_tokens = normalized_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def item_field(item: Any, name: str, default: str = "") -> str:
    if isinstance(item, dict):
        return str(item.get(name, default))
    return str(getattr(item, name, default))


def referenced_answer_ratio(items: list[Any]) -> float:
    if not items:
        return 0.0
    valid = 0
    for item in items:
        answer = item_field(item, "answer").strip()
        timestamp = item_field(item, "timestamp").strip()
        if answer and "respóndelo usando" not in answer.lower() and re.fullmatch(r"\d{2}:\d{2}:\d{2}", timestamp):
            valid += 1
    return valid / len(items)


def test_quality_fixtures_are_distinct_and_preserve_known_timestamps() -> None:
    vocabulary: dict[str, set[str]] = {}

    for name, case in CASES.items():
        cues = clean_vtt(case["path"])
        text = " ".join(cue.text.lower() for cue in cues)

        assert cues[0].start == case["first_timestamp"]
        assert case["terms"].issubset(normalized_tokens(text))
        assert text.count(case["rolling_prefix"]) == 1
        vocabulary[name] = normalized_tokens(text)

    assert token_similarity(" ".join(vocabulary["gardening"]), " ".join(vocabulary["databases"])) < 0.15
    assert token_similarity(" ".join(vocabulary["security"]), " ".join(vocabulary["gardening"])) < 0.15


def test_current_analysis_finds_expected_topics_without_domain_specific_setup() -> None:
    for case in CASES.values():
        result = analyze_cues(clean_vtt(case["path"]))
        selected_text = " ".join(text.lower() for _, text in result.ideas)

        assert result.ideas
        assert len(case["terms"] & normalized_tokens(selected_text)) >= 2


def test_cue_windows_preserve_timestamps_and_remove_near_duplicates() -> None:
    cues = clean_vtt(CASES["gardening"]["path"])
    windows = cue_windows(cues)
    window_text = " ".join(window.text for window in windows)

    assert windows[0].timestamp == CASES["gardening"]["first_timestamp"]
    assert window_text.count("Mantener una humedad estable reduce el estrés") == 1
    assert [window.position for window in windows] == sorted(window.position for window in windows)


def test_selected_ideas_do_not_repeat_near_identical_sentences() -> None:
    result = analyze_cues(clean_vtt(CASES["gardening"]["path"]))
    sentences = [
        sentence.strip()
        for _, idea in result.ideas
        for sentence in re.split(r"(?<=[.!?])\s+", idea)
        if sentence.strip()
    ]

    similarities = [
        token_similarity(left, right) for index, left in enumerate(sentences) for right in sentences[index + 1 :]
    ]
    assert not similarities or max(similarities) < 0.72


def test_questions_and_cards_have_source_answers_and_timestamps() -> None:
    results = [analyze_cues(clean_vtt(case["path"])) for case in CASES.values()]
    questions = [question for result in results for group in result.questions.values() for question in group]
    cards = [card for result in results for card in result.cards]

    assert questions
    assert cards
    assert referenced_answer_ratio(questions) == 1.0
    assert referenced_answer_ratio(cards) == 1.0

    for result in results:
        normalized_questions = [
            question_key(item_field(item, "question")) for group in result.questions.values() for item in group
        ]
        assert len(normalized_questions) == len(set(normalized_questions))
    assert {item_field(item, "category") for item in questions} == {"basicas", "comprension", "practicas"}
    assert all("type::" in item_field(card, "tags") for card in cards)


def test_practical_question_references_the_cue_containing_its_answer() -> None:
    result = analyze_cues(
        [
            clean_vtt(CASES["gardening"]["path"])[0],
            *clean_vtt(CASES["gardening"]["path"])[1:],
        ]
    )

    for question in result.questions["practicas"]:
        matching = [cue for cue in result.cues if normalized_tokens(question.answer) & normalized_tokens(cue.text)]
        assert matching
        assert question.timestamp in {cue.start for cue in matching}


def test_descriptive_content_does_not_invent_a_practical_recommendation() -> None:
    result = analyze_cues(
        [
            Cue("00:00:01", "La fotosíntesis transforma energía luminosa en energía química para la planta."),
            Cue("00:00:10", "La clorofila absorbe parte de la luz disponible durante este proceso."),
        ]
    )

    assert result.questions["practicas"] == []


def question_key(question: str) -> str:
    return " ".join(re.findall(r"[a-záéíóúñü0-9]+", question.lower()))
