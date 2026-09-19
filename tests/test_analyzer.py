from pathlib import Path

from src.youtube_study.analyzer import (
    analyze_cues,
    concept_mentions,
    cue_windows,
    detect_tools,
    detect_unknown_tools,
    token_similarity,
)
from src.youtube_study.transcript import Cue

FIXTURE = Path(__file__).parent / "fixtures" / "heuristics.txt"


def fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_detect_tools_recognizes_known_entries_with_explicit_categories() -> None:
    mentions = {tool.name: tool for tool in detect_tools(fixture_text())}

    assert {"ssh", "tailscale", "tmux", "claude"}.issubset(mentions)
    assert mentions["ssh"].category == "protocol"
    assert mentions["tailscale"].category == "service"
    assert mentions["tmux"].category == "tool"
    assert mentions["claude"].category == "model"
    assert all(mentions[name].kind == "known" for name in ("ssh", "tailscale", "tmux", "claude"))


def test_unknown_candidates_exclude_common_false_positives_and_are_limited() -> None:
    candidates = detect_unknown_tools(fixture_text(), {"ssh", "tailscale", "tmux", "claude"}, limit=1)

    assert [candidate.name for candidate in candidates] == ["CodePilot"]
    assert candidates[0].category == "candidate"
    assert candidates[0].kind == "unknown"
    assert {candidate.name.lower() for candidate in candidates}.isdisjoint({"qr", "sim"})


def test_concepts_exclude_fillers_and_false_positives() -> None:
    cues = [Cue(f"00:00:0{index}", line) for index, line in enumerate(fixture_text().splitlines(), 1)]
    names = {concept.name for concept in concept_mentions(cues)}

    assert {"ssh", "tailscale", "tmux", "claude"}.issubset(names)
    assert names.isdisjoint({"entonces", "ahora", "gente", "cosas", "sim"})


def test_tool_flashcards_keep_classification_and_transcript_source() -> None:
    source = "SSH permite acceder de forma remota al equipo sin exponer información sensible."
    result = analyze_cues([Cue("00:01:23", source)])
    card = next(card for card in result.cards if " ssh" in card.tags)

    assert card.answer == source
    assert card.source_excerpt == source
    assert card.timestamp == "00:01:23"
    assert "tool protocol known ssh" in card.tags
    assert "type::basicas" in card.tags


def test_similarity_preserves_negations_and_changed_numbers() -> None:
    positive = "Es recomendable abrir 22 puertos públicos para acceder al servidor."
    negative = "No es recomendable abrir 443 puertos públicos para acceder al servidor."

    assert token_similarity(positive, negative) == 0.0
    assert len(cue_windows([Cue("00:00:01", positive), Cue("00:00:02", negative)])) == 1
    assert positive in cue_windows([Cue("00:00:01", positive), Cue("00:00:02", negative)])[0].text
    assert negative in cue_windows([Cue("00:00:01", positive), Cue("00:00:02", negative)])[0].text


def test_ambiguous_names_are_not_rewritten_or_detected_as_tools() -> None:
    text = "Claudio prepara mochi en casa."

    assert detect_tools(text) == []


def test_basic_question_prefers_an_explanatory_mention() -> None:
    explanation = "SSH permite acceder de forma remota mediante una conexión cifrada."
    result = analyze_cues(
        [
            Cue("00:00:01", "Hoy vamos a mencionar SSH dentro del recorrido general."),
            Cue("00:00:10", explanation),
        ]
    )

    question = next(item for item in result.questions["basicas"] if "ssh" in item.question.lower())
    assert question.answer == explanation
    assert question.timestamp == "00:00:10"
