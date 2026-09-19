from dataclasses import FrozenInstanceError

import pytest

from src.youtube_study.study_models import SourceExcerpt, SourceFragment


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
