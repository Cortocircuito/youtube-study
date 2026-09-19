import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from src.youtube_study.library import (
    LibraryError,
    get_video,
    load_library,
    rebuild_library,
    resolve_video_path,
    upsert_video,
)
from src.youtube_study.models import VideoMetadata
from src.youtube_study.study_models import ToolMention


class LibraryTests(unittest.TestCase):
    def test_upsert_creates_and_updates_single_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            video_dir = root / "video-1"
            info = VideoMetadata(
                id="video-1",
                title="Primero",
                uploader="Canal",
                duration=60,
                webpage_url="https://example.test",
            )
            tools = [ToolMention("ssh", 2, "Acceso remoto")]

            first = upsert_video(library_path, info, video_dir, tools)
            info = VideoMetadata(
                id="video-1",
                title="Título actualizado",
                uploader="Canal",
                duration=60,
                webpage_url="https://example.test",
            )
            second = upsert_video(library_path, info, video_dir, tools)

            videos = load_library(library_path)["videos"]
            self.assertEqual(len(videos), 1)
            self.assertEqual(first["created_at"], second["created_at"])
            self.assertEqual(get_video(library_path, "video-1")["title"], "Título actualizado")
            self.assertEqual(resolve_video_path(library_path, second["path"]), video_dir)

    def test_invalid_library_is_backed_up_and_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            library_path.write_text("{not json", encoding="utf-8")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self.assertEqual(load_library(library_path), {"videos": []})
            self.assertTrue(list(root.glob("library.json.corrupt-*")))
            self.assertEqual(json.loads(library_path.read_text(encoding="utf-8")), {"videos": []})
            self.assertTrue(caught)

    def test_structurally_invalid_library_is_backed_up_and_recovered(self) -> None:
        for payload in ({}, {"videos": [None]}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                library_path = root / "library.json"
                library_path.write_text(json.dumps(payload), encoding="utf-8")

                with warnings.catch_warnings(record=True):
                    warnings.simplefilter("always")
                    self.assertEqual(load_library(library_path), {"videos": []})

                self.assertTrue(list(root.glob("library.json.corrupt-*")))

    def test_invalid_entry_is_removed_without_losing_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            valid = {"id": "valid", "title": "Válido", "path": "videos/valid", "tools": []}
            library_path.write_text(json.dumps({"videos": [valid, {"id": 7}]}), encoding="utf-8")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                videos = load_library(library_path)["videos"]

            self.assertEqual([video["id"] for video in videos], ["valid"])
            self.assertTrue(list(root.glob("library.json.corrupt-*")))
            self.assertTrue(caught)

    def test_library_read_error_is_not_treated_as_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            library_path.write_text('{"videos": []}', encoding="utf-8")

            with patch.object(Path, "open", side_effect=PermissionError("denegado")):
                with self.assertRaisesRegex(LibraryError, "No se pudo leer la biblioteca"):
                    load_library(library_path)

            self.assertFalse(list(root.glob("library.json.corrupt-*")))

    def test_rebuild_uses_info_files_and_skips_invalid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            videos_dir = root / "videos"
            valid_dir = videos_dir / "valid"
            valid_dir.mkdir(parents=True)
            (valid_dir / "info.json").write_text(json.dumps({"id": "valid", "title": "Video válido"}), encoding="utf-8")
            invalid_dir = videos_dir / "invalid"
            invalid_dir.mkdir()
            (invalid_dir / "info.json").write_text("{", encoding="utf-8")
            missing_dir = videos_dir / "missing"
            missing_dir.mkdir()

            result = rebuild_library(root / "library.json", videos_dir)
            self.assertEqual(result.rebuilt, 1)
            self.assertEqual(len(result.skipped), 2)
            self.assertEqual(load_library(root / "library.json")["videos"][0]["id"], "valid")

    def test_rebuild_skips_non_object_info_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            videos_dir = root / "videos"
            video_dir = videos_dir / "invalid"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text("[]", encoding="utf-8")

            result = rebuild_library(root / "library.json", videos_dir)

            self.assertEqual(result.rebuilt, 0)
            self.assertIn("se esperaba un objeto JSON", result.skipped[0])

    def test_rebuild_rejects_info_id_that_differs_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            videos_dir = root / "videos"
            video_dir = videos_dir / "expected"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text(json.dumps({"id": "other"}), encoding="utf-8")

            result = rebuild_library(root / "library.json", videos_dir)

            self.assertEqual(result.rebuilt, 0)
            self.assertIn("no coincide", result.skipped[0])

    def test_rebuild_reads_tool_names_from_tools_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            videos_dir = root / "videos"
            video_dir = videos_dir / "demo"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Demo"}), encoding="utf-8")
            (video_dir / "tools.json").write_text(
                json.dumps([{"name": "ssh"}, {"name": "tailscale"}, {"name": "ssh"}]), encoding="utf-8"
            )

            result = rebuild_library(root / "library.json", videos_dir)

            self.assertEqual(result.rebuilt, 1)
            self.assertEqual(load_library(root / "library.json")["videos"][0]["tools"], ["ssh", "tailscale"])


if __name__ == "__main__":
    unittest.main()
