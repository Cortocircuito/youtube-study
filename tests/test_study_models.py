from dataclasses import FrozenInstanceError

import pytest

from src.youtube_study.study_models import ConceptMention, SourceExcerpt, SourceFragment


def test_source_evidence_is_immutable_and_exposes_cue_positions() -> None:
    fragment = SourceFragment(2, "00:01:23", 4, 13, "Respuesta")
    evidence = SourceExcerpt("Respuesta", (fragment,))

    assert evidence.timestamp == "00:01:23"
    assert evidence.cue_positions == (2,)
    with pytest.raises(FrozenInstanceError):
        evidence.text = "otro texto"


def test_source_fragment_rejects_inconsistent_offsets() -> None:
    with pytest.raises(ValueError, match="no coincide"):
        SourceFragment(0, "00:00:01", 3, 20, "texto")


def test_source_excerpt_rejects_text_not_reconstructed_from_fragments() -> None:
    fragment = SourceFragment(0, "00:00:01", 0, 5, "texto")

    with pytest.raises(ValueError, match="no coincide"):
        SourceExcerpt("otro", (fragment,))


def test_concept_mention_is_immutable_and_validates_scores() -> None:
    concept = ConceptMention("base de datos", 0.8, 2, 0.7, 0.6, 0.9, ("00:00:01", "00:05:00"))

    with pytest.raises(FrozenInstanceError):
        concept.score = 0.5
    with pytest.raises(ValueError, match="entre 0 y 1"):
        ConceptMention("cifrado", 1.1, 1, 1.0, 1.0, None, ("00:00:01",))
    with pytest.raises(ValueError, match="asociación"):
        ConceptMention("base de datos", 0.8, 1, 0.7, 0.6, None, ("00:00:01",))


def test_concept_mention_requires_count_and_unique_timestamps() -> None:
    with pytest.raises(ValueError, match="al menos una mención"):
        ConceptMention("cifrado", 0.8, 0, 0.7, 0.6, None, ("00:00:01",))
    with pytest.raises(ValueError, match="únicos"):
        ConceptMention("cifrado", 0.8, 2, 0.7, 0.6, None, ("00:00:01", "00:00:01"))
