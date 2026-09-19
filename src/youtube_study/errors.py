from __future__ import annotations


class AppError(Exception):
    """Base class for expected application errors shown without tracebacks."""


class VideoDataError(AppError):
    """A requested local video or its metadata/artifacts are missing or invalid."""


class ArtifactRecoveryError(VideoDataError):
    """An artifact publication could not be completed or recovered safely."""


class SubtitleError(AppError):
    """Subtitle download or selection failed in an expected way."""
