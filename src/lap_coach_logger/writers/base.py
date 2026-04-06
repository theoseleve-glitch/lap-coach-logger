"""Abstract writer interface for session data persistence."""

from __future__ import annotations

import abc
from pathlib import Path

from lap_coach_logger.core.schema import TelemetrySample


class BaseWriter(abc.ABC):
    """Contract for telemetry file writers."""

    @abc.abstractmethod
    def open(self, path: Path, schema_fields: list[str]) -> None:
        """Prepare the writer for a new session file at *path*."""

    @abc.abstractmethod
    def write_samples(self, samples: list[TelemetrySample]) -> None:
        """Persist a batch of samples."""

    @abc.abstractmethod
    def close(self) -> None:
        """Flush buffers and close the file handle."""
