import tempfile
from pathlib import Path
import unittest

from src.youtube_study.analyzer import ToolMention
from src.youtube_study.library import get_video, load_library, upsert_video


class LibraryTests(unittest.TestCase):
    def test_upsert_creates_and_updates_single_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            video_dir = root / "video-1"
            info = {"id": "video-1", "title": "Primero", "uploader": "Canal", "duration": 60, "webpage_url": "https://example.test"}
            tools = [ToolMention("ssh", 2, "Acceso remoto")]

            first = upsert_video(library_path, info, video_dir, tools)
            info["title"] = "Título actualizado"
            second = upsert_video(library_path, info, video_dir, tools)

            videos = load_library(library_path)["videos"]
            self.assertEqual(len(videos), 1)
            self.assertEqual(first["created_at"], second["created_at"])
            self.assertEqual(get_video(library_path, "video-1")["title"], "Título actualizado")


if __name__ == "__main__":
    unittest.main()
