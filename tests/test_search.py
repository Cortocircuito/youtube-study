import tempfile
import unittest
from pathlib import Path

from src.youtube_study.search import search_library, search_transcript


class SearchTests(unittest.TestCase):
    def test_search_transcript_returns_timestamp_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            transcript = Path(temp) / "transcript.txt"
            transcript.write_text(
                "[00:00:01] Primera línea.\n[00:00:02] Tailscale conecta equipos.\n[00:00:03] Última línea.\n",
                encoding="utf-8",
            )
            results = search_transcript(transcript, "tailscale", video_id="abc", title="Video", context=1)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].timestamp, "00:00:02")
            self.assertEqual(results[0].context_before, ["[00:00:01] Primera línea."])
            self.assertEqual(results[0].context_after, ["[00:00:03] Última línea."])

    def test_search_library_honors_video_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for video_id in ("one", "two"):
                video_dir = root / video_id
                video_dir.mkdir()
                (video_dir / "transcript.txt").write_text("[00:00:01] agente activo\n", encoding="utf-8")
            videos = [
                {"id": "one", "title": "Uno", "path": str(root / "one")},
                {"id": "two", "title": "Dos", "path": str(root / "two")},
            ]
            results = search_library(videos, "agente", video_id="two")
            self.assertEqual([result.video_id for result in results], ["two"])


if __name__ == "__main__":
    unittest.main()
