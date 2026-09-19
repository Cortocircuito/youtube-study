from pathlib import Path

import pytest

from src.youtube_study.analyzer import (
    analyze_cues,
    concept_mentions,
    cue_windows,
    detect_tools,
    detect_unknown_tools,
    filler_penalty,
    informative_units,
    is_obvious_noise,
    question_topic,
    selectable_units,
    source_excerpt_for_term,
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


def test_concepts_include_compound_terms_with_exact_timestamps() -> None:
    cues = [
        Cue("00:00:01", "Antes de optimizar una base de datos conviene medir consultas lentas."),
        Cue("00:00:10", "El plan de ejecución muestra el coste de cada operación."),
        Cue("00:00:20", "Una copia de seguridad debe probarse mediante una restauración."),
    ]

    concepts = {concept.name: concept for concept in concept_mentions(cues)}

    assert concepts["base de datos"].timestamps == ("00:00:01",)
    assert concepts["plan de ejecución"].association_score is not None
    assert concepts["copia de seguridad"].timestamps == ("00:00:20",)
    assert concepts["restauración"].timestamps == ("00:00:20",)


def test_concepts_do_not_cross_sentence_boundaries_or_promote_generic_actions() -> None:
    cues = [Cue("00:00:01", "Una clave robusta protege el acceso. Una copia segura conserva los datos.")]

    names = {concept.name for concept in concept_mentions(cues, limit=50)}

    assert "clave robusta" in names
    assert "robusta protege" not in names
    assert "acceso una" not in names
    assert names.isdisjoint({"protege", "datos"})


def test_concept_distribution_rewards_mentions_spread_over_time() -> None:
    cues = [
        Cue("00:00:01", "Cifrado protege archivos e índice acelera consultas."),
        Cue("00:00:05", "Índice mejora lecturas repetidas."),
        Cue("00:10:00", "Cifrado limita el acceso no autorizado."),
    ]

    concepts = {concept.name: concept for concept in concept_mentions(cues, limit=50)}

    assert concepts["cifrado"].count == concepts["índice"].count == 2
    assert concepts["cifrado"].distribution_score > concepts["índice"].distribution_score


def test_concept_deduplication_uses_occurrence_spans() -> None:
    cues = [
        Cue("00:00:01", "Una clave robusta y una clave temporal protegen accesos distintos."),
        Cue("00:00:10", "Índice índice no debe convertirse en un concepto repetido."),
    ]

    names = {concept.name for concept in concept_mentions(cues, limit=50)}

    assert "clave" in names
    assert "clave robusta" in names
    assert "clave temporal" in names
    assert "índice índice" not in names


def test_concept_spans_distinguish_sentences_from_the_same_cue() -> None:
    cue = Cue(
        "00:00:01",
        "Una clave robusta protege el servicio. Una clave temporal permite completar la migración.",
    )

    names = {concept.name for concept in concept_mentions([cue], limit=50)}

    assert {"clave", "clave robusta", "clave temporal"} <= names


def test_concept_evidence_does_not_match_inside_hyphenated_tokens() -> None:
    cues = [
        Cue("00:00:01", "Prefijo-node.js aparece como un token diferente."),
        Cue("00:00:10", "Node.js permite ejecutar JavaScript fuera del navegador."),
    ]

    evidence = source_excerpt_for_term(cues, "node.js")

    assert evidence is not None
    assert evidence.timestamp == "00:00:10"


def test_compound_concepts_do_not_cross_dash_separators() -> None:
    names = {
        concept.name for concept in concept_mentions([Cue("00:00:01", "Node.js - servidor remoto estable.")], limit=50)
    }

    assert "node.js servidor" not in names


def test_single_sentence_does_not_fill_the_limit_with_incidental_bigrams() -> None:
    concepts = concept_mentions(
        [Cue("00:00:01", "La plataforma escalable integra servicios externos mediante conectores seguros.")]
    )
    names = {concept.name for concept in concepts}

    assert "plataforma escalable" in names
    assert names.isdisjoint({"escalable integra", "integra servicios", "servicios externos"})
    assert len(concepts) < 15


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
    assert ssh_concept.timestamps == ("00:00:01", "00:00:05")


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


def test_basic_questions_use_distinct_explanatory_evidence() -> None:
    result = analyze_cues(
        [
            Cue("00:00:01", "Un medidor enchufable registra la potencia y el consumo acumulado del aparato."),
            Cue("00:00:10", "El aislamiento reduce la pérdida de calor de la vivienda."),
        ]
    )

    questions = result.questions["basicas"]

    assert any("medidor enchufable" in item.question for item in questions)
    assert len({item.evidence.fragments for item in questions}) == len(questions)


@pytest.mark.parametrize(
    "text",
    [
        "En una base de datos, un índice acelera las consultas repetidas.",
        "En una base de datos un índice acelera las consultas repetidas.",
    ],
)
def test_basic_question_prefers_the_subject_nearest_to_the_relation(text: str) -> None:
    result = analyze_cues([Cue("00:00:01", text), Cue("00:00:10", "Después revisaremos el índice.")])

    assert result.questions["basicas"][0].question == "¿Qué se explica sobre índice?"


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("Configurar alertas permite detectar errores críticos.", "alertas"),
        ("Comparar métricas permite detectar regresiones.", "comparar métricas"),
        ("Conectar servicios permite compartir datos.", "servicios"),
    ],
)
def test_basic_question_does_not_use_a_bare_leading_infinitive(text: str, topic: str) -> None:
    result = analyze_cues([Cue("00:00:01", text)])

    assert result.questions["basicas"][0].question == f"¿Qué se explica sobre {topic}?"


def test_tool_questions_require_explanation_and_distinct_evidence() -> None:
    result = analyze_cues(
        [
            Cue("00:00:01", "Hoy mencionaremos SSH y Tailscale durante el recorrido."),
            Cue("00:00:10", "SSH y Tailscale permiten acceder a la red privada."),
        ]
    )

    assert len(result.questions["basicas"]) == 1
    assert result.questions["basicas"][0].timestamp == "00:00:10"


def test_practical_topic_keeps_a_short_specific_phrase() -> None:
    assert (
        question_topic("Programar el termostato evita calentar la vivienda cuando está vacía.")
        == "programar termostato"
    )
    assert question_topic("Primero conviene sellar ventanas y puertas antes de cambiar la calefacción.") == (
        "sellar ventanas puertas"
    )
    assert question_topic("Antes de optimizar una base de datos hay que medir consultas lentas.") == (
        "optimizar base datos"
    )


def test_comprehension_questions_require_an_explicit_non_practical_cause() -> None:
    result = analyze_cues(
        [Cue("00:00:01", "La caché reduce la latencia porque conserva respuestas frecuentes en memoria.")]
    )

    assert [item.question for item in result.questions["comprension"]] == [
        "¿Por qué se afirma que la caché reduce la latencia?"
    ]
    assert result.questions["comprension"][0].timestamp == "00:00:01"


def test_causal_effect_does_not_turn_an_explanation_into_a_recommendation() -> None:
    result = analyze_cues([Cue("00:00:01", "El cifrado es importante porque evita accesos no autorizados.")])

    assert result.questions["practicas"] == []
    assert result.questions["comprension"][0].question == "¿Por qué se afirma que el cifrado es importante?"


def test_conditional_effect_does_not_turn_an_explanation_into_a_recommendation() -> None:
    result = analyze_cues([Cue("00:00:01", "El aislamiento funciona cuando evita puentes térmicos en la vivienda.")])

    assert result.questions["practicas"] == []
    assert result.questions["comprension"][0].question == ("¿En qué situación se afirma que el aislamiento funciona?")


def test_comprehension_question_preserves_leading_acronyms() -> None:
    examples = [
        ("SSH resulta útil porque protege la conexión remota.", "SSH"),
        ("GitHub resulta útil porque centraliza la revisión del código.", "GitHub"),
        ("Node.js resulta útil porque ejecuta JavaScript fuera del navegador.", "Node.js"),
    ]

    for text, name in examples:
        result = analyze_cues([Cue("00:00:01", text)])
        assert result.questions["comprension"][0].question.startswith(f"¿Por qué se afirma que {name} ")


def test_generic_idea_windows_do_not_create_comprehension_questions() -> None:
    result = analyze_cues([Cue("00:00:01", "El panel presenta métricas útiles para revisar el servicio.")])

    assert result.questions["comprension"] == []
