from pathlib import Path

from src.youtube_study.analyzer import (
    analyze_cues,
    concept_mentions,
    cue_windows,
    detect_tools,
    detect_unknown_tools,
    filler_penalty,
    informative_units,
    is_obvious_noise,
    selectable_units,
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


def test_similarity_preserves_emphatic_repetition() -> None:
    repeated = "Es muy, muy importante revisar la configuración antes de publicar."
    plain = "Es muy importante revisar la configuración antes de publicar."

    assert token_similarity(repeated, plain) == 0.0


def test_obvious_noise_requires_multiple_signals_and_remains_in_source_cues() -> None:
    noise = [
        "[Música] Bueno, bueno, ahora sí comenzamos.",
        "Antes de seguir recuerden suscribirse al canal y activar las notificaciones.",
        "Eh, a ver, esperen un momento que voy a revisar el sonido.",
        "Bueno, no sé, creo que se entiende, seguimos con otra cosa.",
    ]
    useful = [
        "El sonido se representa mediante una onda que transporta energía.",
        "Suscribirse a eventos permite activar notificaciones dentro del sistema.",
        "No sé si hacen falta 10 o 20 muestras para confirmar el resultado.",
        "No se configura el servicio todavía; seguimos revisando la causa del error.",
    ]

    assert all(is_obvious_noise(text) for text in noise)
    assert not any(is_obvious_noise(text) for text in useful)

    cues = [Cue(f"00:00:{index:02d}", text) for index, text in enumerate([*noise, *useful], 1)]
    result = analyze_cues(cues)
    selected = " ".join(idea.text for idea in result.ideas)
    generated = " ".join(
        [
            *(word for word, _ in result.keywords),
            *(concept.name for concept in result.concepts),
            *(question.question for group in result.questions.values() for question in group),
            *(question.answer for group in result.questions.values() for question in group),
            *(idea for _, _, ideas in result.sections for idea in ideas),
        ]
    ).lower()

    assert result.cues == cues
    assert not any(text in selected for text in noise)
    assert all(text in selected for text in useful)
    assert "recuerden suscribirse" not in generated
    assert "esperen un momento" not in generated


def test_noise_without_punctuation_does_not_remove_the_following_explanation() -> None:
    cues = [
        Cue("00:00:01", "[Música]"),
        Cue("00:00:03", "Ahora sí comenzamos con el aislamiento que reduce la pérdida de calor."),
    ]

    result = analyze_cues(cues)

    assert "aislamiento" in " ".join(idea.text for idea in result.ideas).lower()
    assert result.cues == cues


def test_audio_explanations_are_not_confused_with_production_incidents() -> None:
    examples = [
        "Esperamos revisar el audio para identificar frecuencias anómalas.",
        "Esperamos que el problema del sonido se resuelva mediante este filtro.",
    ]

    assert not any(is_obvious_noise(text) for text in examples)


def test_repeated_informative_mentions_keep_analysis_counts() -> None:
    cues = [
        Cue("00:00:01", "SSH permite acceder al servidor remoto."),
        Cue("00:00:05", "SSH permite acceder al servidor remoto."),
    ]

    result = analyze_cues(cues)
    ssh_tool = next(tool for tool in result.tools if tool.name == "ssh")
    ssh_concept = next(concept for concept in result.concepts if concept.name == "ssh")

    assert len(informative_units(cues)) == 2
    assert len(selectable_units(cues)) == 1
    assert ssh_tool.count == 2
    assert ssh_concept.count == 2
    assert ssh_concept.timestamps == ["00:00:01", "00:00:05"]


def test_fillers_are_penalized_without_rewriting_evidence() -> None:
    noisy = "Eh, a ver, revisemos el aislamiento antes de cambiar la calefacción."
    neutral = "El aislamiento es bueno para este edificio durante el invierno."
    cue = Cue("00:02:00", noisy)

    assert filler_penalty(noisy) > 0
    assert filler_penalty(neutral) == 0
    assert selectable_units([cue])[0].text == noisy


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
