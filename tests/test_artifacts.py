from __future__ import annotations

from pathlib import Path

import pytest

from src.youtube_study.artifacts import publish_artifacts, staging_directory
from src.youtube_study.errors import VideoDataError


@pytest.mark.parametrize("names", [[], ["../summary.md"], ["nested/summary.md"]])
def test_publish_artifacts_rejects_empty_or_nested_names(tmp_path: Path, names: list[str]) -> None:
    video_dir = tmp_path / "videos" / "demo"

    with pytest.raises(ValueError, match="lista de artefactos"):
        publish_artifacts(tmp_path, video_dir, names, retry_command="analyze")

    assert not video_dir.exists()


def test_publish_artifacts_validates_all_staged_files_before_replacing_anything(tmp_path: Path) -> None:
    staging_dir = tmp_path / "staging"
    video_dir = tmp_path / "video"
    staging_dir.mkdir()
    video_dir.mkdir()
    (staging_dir / "study.md").write_bytes(b"nuevo")
    (video_dir / "study.md").write_bytes(b"anterior")
    (video_dir / "anki.csv").write_bytes(b"anki anterior")

    with pytest.raises(VideoDataError, match="anki.csv"):
        publish_artifacts(staging_dir, video_dir, ["study.md", "anki.csv"], retry_command="export")

    assert (video_dir / "study.md").read_bytes() == b"anterior"
    assert (video_dir / "anki.csv").read_bytes() == b"anki anterior"


def test_staging_directory_is_adjacent_and_removed_after_failure(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos" / "demo"
    captured: Path | None = None

    with pytest.raises(RuntimeError, match="fallo de render"):
        with staging_directory(video_dir) as staging_dir:
            captured = staging_dir
            assert staging_dir.parent == video_dir.parent
            assert staging_dir != video_dir
            raise RuntimeError("fallo de render")

    assert captured is not None
    assert not captured.exists()
