from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .errors import ArtifactPublicationError, VideoDataError


@contextmanager
def staging_directory(video_dir: Path) -> Iterator[Path]:
    """Yield a temporary directory next to the final video directory."""
    video_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{video_dir.name}.staging-", dir=video_dir.parent) as temp_dir:
        yield Path(temp_dir)


def publish_artifacts(
    staging_dir: Path,
    video_dir: Path,
    artifact_names: Sequence[str],
    *,
    retry_command: str,
) -> None:
    """Replace generated artifacts one by one after validating staging."""
    names = tuple(dict.fromkeys(artifact_names))
    if not names or any(Path(name).name != name for name in names):
        raise ValueError("La lista de artefactos a publicar es inválida")
    missing = [name for name in names if not (staging_dir / name).is_file()]
    if missing:
        raise VideoDataError(f"Faltan artefactos en staging: {', '.join(missing)}")

    try:
        video_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            os.replace(staging_dir / name, video_dir / name)
    except OSError as exc:
        raise ArtifactPublicationError(
            "La publicación quedó incompleta. Los subtítulos originales no se modificaron. "
            f"Corrige el problema y repite {retry_command}."
        ) from exc
