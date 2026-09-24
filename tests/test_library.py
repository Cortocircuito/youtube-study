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
    def test_missing_and_empty_library_are_read_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            missing = root / "missing.json"
            empty = root / "empty.json"
            empty.write_bytes(b"")

            self.assertEqual(load_library(missing), {"videos": []})
            self.assertFalse(missing.exists())
            self.assertEqual(load_library(empty), {"videos": []})
            self.assertEqual(empty.read_bytes(), b"")

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

    def test_invalid_library_reports_rebuild_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            original = b"{not json"
            library_path.write_bytes(original)

            with self.assertRaisesRegex(LibraryError, "rebuild-library"):
                load_library(library_path)

            self.assertEqual(library_path.read_bytes(), original)
            self.assertFalse(list(root.glob("library.json.corrupt-*")))

    def test_structurally_invalid_library_reports_rebuild_without_modifying_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            original = json.dumps({}).encode()
            library_path.write_bytes(original)

            with self.assertRaisesRegex(LibraryError, "rebuild-library"):
                load_library(library_path)

            self.assertEqual(library_path.read_bytes(), original)
            self.assertFalse(list(root.glob("library.json.corrupt-*")))

    def test_invalid_entry_is_removed_without_losing_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            valid = {"id": "valid", "title": "Válido", "path": "videos/valid", "tools": []}
            library_path.write_text(json.dumps({"videos": [valid, {"id": 7}]}), encoding="utf-8")
            original = library_path.read_bytes()

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                videos = load_library(library_path)["videos"]

            self.assertEqual([video["id"] for video in videos], ["valid"])
            self.assertEqual(library_path.read_bytes(), original)
            self.assertFalse(list(root.glob("library.json.corrupt-*")))
            self.assertTrue(caught)

    def test_upsert_rejects_invalid_entries_without_modifying_library(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            original = json.dumps({"videos": [{"id": 7}]}).encode()
            library_path.write_bytes(original)

            with self.assertRaisesRegex(LibraryError, "rebuild-library"):
                upsert_video(library_path, VideoMetadata("demo", "Demo"), root / "demo", [])

            self.assertEqual(library_path.read_bytes(), original)

    def test_legacy_entry_without_timestamps_survives_upsert_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            library_path.write_text(
                json.dumps({"videos": [{"id": "demo", "title": "Legacy", "path": "demo", "tools": []}]}),
                encoding="utf-8",
            )

            loaded = load_library(library_path)["videos"][0]
            self.assertNotIn("created_at", loaded)
            upsert_video(library_path, VideoMetadata("demo", "Actualizado"), root / "demo", [])

            updated = load_library(library_path)["videos"][0]
            self.assertTrue(updated["created_at"])
            self.assertEqual(updated["title"], "Actualizado")

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

    def test_rebuild_backs_up_corrupt_index_and_preserves_artifact_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            original = b"{corrupt"
            library_path.write_bytes(original)
            video_dir = root / "videos" / "demo"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Demo"}), encoding="utf-8")
            (video_dir / "tools.json").write_text(json.dumps([{"name": "ssh"}]), encoding="utf-8")

            result = rebuild_library(library_path, root / "videos")

            backups = list(root.glob("library.json.corrupt-*"))
            self.assertEqual(result.rebuilt, 1)
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertEqual(load_library(library_path)["videos"][0]["tools"], ["ssh"])

    def test_rebuild_backup_failure_keeps_corrupt_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            original = b"{corrupt"
            library_path.write_bytes(original)

            with patch("src.youtube_study.library.shutil.copy2", side_effect=OSError("sin espacio")):
                with self.assertRaisesRegex(LibraryError, "No se pudo respaldar"):
                    rebuild_library(library_path, root / "videos")

            self.assertEqual(library_path.read_bytes(), original)

    def test_rebuild_preserves_created_at_from_valid_previous_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            created_at = "2025-01-01T00:00:00+00:00"
            library_path.write_text(
                json.dumps(
                    {
                        "videos": [
                            {
                                "id": "demo",
                                "title": "Anterior",
                                "path": "videos/demo",
                                "tools": [],
                                "created_at": created_at,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            video_dir = root / "videos" / "demo"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Demo"}), encoding="utf-8")

            rebuild_library(library_path, root / "videos")

            self.assertEqual(load_library(library_path)["videos"][0]["created_at"], created_at)

    def test_rebuild_preserves_updated_at_from_valid_previous_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            library_path = root / "library.json"
            updated_at = "2025-02-01T00:00:00+00:00"
            library_path.write_text(
                json.dumps(
                    {
                        "videos": [
                            {
                                "id": "demo",
                                "title": "Anterior",
                                "path": "videos/demo",
                                "tools": [],
                                "created_at": "2025-01-01T00:00:00+00:00",
                                "updated_at": updated_at,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            video_dir = root / "videos" / "demo"
            video_dir.mkdir(parents=True)
            (video_dir / "info.json").write_text(json.dumps({"id": "demo", "title": "Demo"}), encoding="utf-8")

            rebuild_library(library_path, root / "videos")

            self.assertEqual(load_library(library_path)["videos"][0]["updated_at"], updated_at)


if __name__ == "__main__":
    unittest.main()
