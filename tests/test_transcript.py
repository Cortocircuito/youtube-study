import unittest
from pathlib import Path

from src.youtube_study.transcript import Cue, chunk_by_minutes, clean_vtt, remove_rolling_overlaps

FIXTURE = Path(__file__).parent / "fixtures" / "sample.vtt"


class TranscriptTests(unittest.TestCase):
    def test_clean_vtt_removes_rolling_caption_overlap_without_rewriting_source(self) -> None:
        cues = clean_vtt(FIXTURE)
        self.assertEqual(
            [cue.text for cue in cues],
            [
                "Hola mundo",
                "esto es Moshie",
                "y Claudio usa Herder",
            ],
        )

    def test_remove_rolling_overlaps_ignores_case_and_punctuation(self) -> None:
        cues = [Cue("00:00:01", "Hola mundo."), Cue("00:00:02", "mundo, otra vez")]
        self.assertEqual(remove_rolling_overlaps(cues), [Cue("00:00:01", "Hola mundo."), Cue("00:00:02", "otra vez")])

    def test_remove_rolling_overlaps_keeps_distant_repetition(self) -> None:
        cues = [Cue("00:00:01", "Revisa la humedad"), Cue("00:20:01", "Revisa la humedad")]

        self.assertEqual(remove_rolling_overlaps(cues), cues)

    def test_chunk_by_minutes_handles_large_timestamp_gaps(self) -> None:
        chunks = chunk_by_minutes([Cue("00:00:01", "Inicio"), Cue("00:20:01", "Final")])

        self.assertEqual(
            chunks,
            [
                ("00:00:00", "00:05:00", "Inicio"),
                ("00:20:00", "00:25:00", "Final"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
