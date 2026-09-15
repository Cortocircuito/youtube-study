import unittest
from pathlib import Path

from src.youtube_study.transcript import Cue, clean_vtt, remove_rolling_overlaps

FIXTURE = Path(__file__).parent / "fixtures" / "sample.vtt"


class TranscriptTests(unittest.TestCase):
    def test_clean_vtt_removes_rolling_caption_overlap_and_normalizes_aliases(self) -> None:
        cues = clean_vtt(FIXTURE)
        self.assertEqual(
            [cue.text for cue in cues],
            [
                "Hola mundo",
                "esto es Moshi",
                "y Claude usa Herdr",
            ],
        )

    def test_remove_rolling_overlaps_ignores_case_and_punctuation(self) -> None:
        cues = [Cue("00:00:01", "Hola mundo."), Cue("00:00:02", "mundo, otra vez")]
        self.assertEqual(remove_rolling_overlaps(cues), [Cue("00:00:01", "Hola mundo."), Cue("00:00:02", "otra vez")])


if __name__ == "__main__":
    unittest.main()
