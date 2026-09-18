from pathlib import Path

from src.youtube_study.analyzer import analyze_cues, concept_mentions, detect_tools, detect_unknown_tools
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
