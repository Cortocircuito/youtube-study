from src.youtube_study.text_units import pack_units, sentence_units
from src.youtube_study.transcript import Cue


def test_sentence_units_reconstruct_an_incomplete_sentence_across_cues() -> None:
    cues = [
        Cue("00:00:01", "No conviene abrir"),
        Cue("00:00:04", "22 puertos públicos porque"),
        Cue("00:00:07", "aumenta la superficie de ataque."),
    ]

    units = sentence_units(cues)

    assert len(units) == 1
    assert units[0].text == "No conviene abrir 22 puertos públicos porque aumenta la superficie de ataque."
    assert units[0].timestamp == "00:00:01"
    assert units[0].evidence.cue_positions == (0, 1, 2)
    for fragment in units[0].evidence.fragments:
        cue = cues[fragment.cue_index]
        assert cue.text[fragment.start : fragment.end] == fragment.text


def test_sentence_units_keep_exact_offsets_for_multiple_sentences_in_one_cue() -> None:
    cue = Cue("00:01:00", "Primero mide el consumo. Después compara el resultado.")

    units = sentence_units([cue])

    assert [unit.text for unit in units] == ["Primero mide el consumo.", "Después compara el resultado."]
    assert [fragment.start for unit in units for fragment in unit.evidence.fragments] == [0, 25]
    assert [fragment.end for unit in units for fragment in unit.evidence.fragments] == [24, len(cue.text)]


def test_sentence_units_do_not_join_text_across_a_large_gap() -> None:
    cues = [Cue("00:00:01", "La primera explicación queda abierta"), Cue("00:00:30", "Otro tema comienza aquí.")]

    units = sentence_units(cues)

    assert [unit.text for unit in units] == [
        "La primera explicación queda abierta",
        "Otro tema comienza aquí.",
    ]


def test_sentence_units_do_not_split_abbreviations_or_version_numbers() -> None:
    cues = [
        Cue("00:00:01", "Consulta al Dr. Pérez antes de continuar."),
        Cue("00:00:05", "La versión es 3. 11 y corrige el problema anterior."),
    ]

    units = sentence_units(cues)

    assert [unit.text for unit in units] == [
        "Consulta al Dr. Pérez antes de continuar.",
        "La versión es 3. 11 y corrige el problema anterior.",
    ]


def test_pack_units_respects_size_and_preserves_fragments() -> None:
    cues = [
        Cue("00:00:01", "Primera frase completa."),
        Cue("00:00:03", "Segunda frase completa."),
        Cue("00:00:05", "Tercera frase completa."),
        Cue("00:00:07", "Cuarta frase completa."),
    ]

    packed = pack_units(sentence_units(cues), size=3)

    assert len(packed) == 2
    assert packed[0].evidence.cue_positions == (0, 1, 2)
    assert packed[1].evidence.cue_positions == (3,)
