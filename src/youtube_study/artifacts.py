from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import ArtifactRecoveryError, VideoDataError

PUBLICATION_JOURNAL = ".artifact-publication.json"


@contextmanager
def staging_directory(video_dir: Path) -> Iterator[Path]:
    """Yield a temporary directory next to the final video directory."""
    video_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{video_dir.name}.staging-", dir=video_dir.parent) as temp_dir:
        yield Path(temp_dir)


def _journal_path(video_dir: Path) -> Path:
    return video_dir / PUBLICATION_JOURNAL


def _write_journal(path: Path, payload: dict[str, Any]) -> None:
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as file:
            temp_name = file.name
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


def _load_journal(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactRecoveryError(f"No se pudo leer el journal de publicación: {path}") from exc
    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    existing = payload.get("existing") if isinstance(payload, dict) else None
    backup_name = payload.get("backup_name") if isinstance(payload, dict) else None
    if (
        payload.get("version") != 1
        or not isinstance(artifacts, list)
        or not artifacts
        or not all(isinstance(name, str) and Path(name).name == name for name in artifacts)
        or not isinstance(existing, list)
        or not all(isinstance(name, str) and name in artifacts for name in existing)
        or not isinstance(backup_name, str)
        or Path(backup_name).name != backup_name
        or not isinstance(payload.get("committed"), bool)
    ):
        raise ArtifactRecoveryError(f"El journal de publicación es inválido: {path}")
    return payload


def _cleanup_transaction(journal_path: Path, backup_dir: Path) -> None:
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    if backup_dir.exists():
        raise OSError(f"No se pudo eliminar el respaldo temporal: {backup_dir}")
    journal_path.unlink(missing_ok=True)
    if journal_path.exists():
        raise OSError(f"No se pudo eliminar el journal: {journal_path}")


def recover_pending_publication(video_dir: Path) -> bool:
    """Recover an interrupted publication. Return whether a journal was found."""
    journal_path = _journal_path(video_dir)
    if not journal_path.exists():
        return False

    payload = _load_journal(journal_path)
    if not payload["backup_name"].startswith(f".{video_dir.name}.backup-"):
        raise ArtifactRecoveryError(f"El journal referencia un respaldo inesperado: {journal_path}")
    backup_dir = video_dir.parent / payload["backup_name"]
    try:
        if payload["committed"]:
            _cleanup_transaction(journal_path, backup_dir)
            return True

        existing = set(payload["existing"])
        for name in payload["artifacts"]:
            destination = video_dir / name
            backup = backup_dir / name
            if backup.exists():
                destination.unlink(missing_ok=True)
                os.replace(backup, destination)
            elif name not in existing:
                destination.unlink(missing_ok=True)
        _cleanup_transaction(journal_path, backup_dir)
    except OSError as exc:
        raise ArtifactRecoveryError(
            f"No se pudo recuperar la publicación. Journal conservado en {journal_path}"
        ) from exc
    return True


def publish_artifacts(staging_dir: Path, video_dir: Path, artifact_names: Sequence[str]) -> None:
    """Publish staged artifacts with rollback and restart recovery."""
    names = tuple(dict.fromkeys(artifact_names))
    if not names or any(Path(name).name != name for name in names):
        raise ValueError("La lista de artefactos a publicar es inválida")
    missing = [name for name in names if not (staging_dir / name).is_file()]
    if missing:
        raise VideoDataError(f"Faltan artefactos en staging: {', '.join(missing)}")

    video_dir.mkdir(parents=True, exist_ok=True)
    recover_pending_publication(video_dir)
    backup_dir = Path(tempfile.mkdtemp(prefix=f".{video_dir.name}.backup-", dir=video_dir.parent))
    journal_path = _journal_path(video_dir)
    payload: dict[str, Any] = {
        "version": 1,
        "backup_name": backup_dir.name,
        "artifacts": list(names),
        "existing": [name for name in names if (video_dir / name).exists()],
        "committed": False,
    }
    try:
        _write_journal(journal_path, payload)
    except OSError:
        try:
            shutil.rmtree(backup_dir)
        except OSError as cleanup_error:
            raise ArtifactRecoveryError(f"No se pudo limpiar el respaldo sin journal: {backup_dir}") from cleanup_error
        raise

    try:
        for name in payload["existing"]:
            os.replace(video_dir / name, backup_dir / name)
        for name in names:
            os.replace(staging_dir / name, video_dir / name)
        payload["committed"] = True
        _write_journal(journal_path, payload)
    except OSError:
        try:
            recover_pending_publication(video_dir)
        except ArtifactRecoveryError:
            raise
        raise

    try:
        _cleanup_transaction(journal_path, backup_dir)
    except OSError as exc:
        raise ArtifactRecoveryError(
            f"La publicación terminó, pero su limpieza quedó pendiente en {journal_path}"
        ) from exc
