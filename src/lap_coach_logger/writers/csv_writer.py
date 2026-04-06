"""CSV fallback writer.

Used automatically when Parquet writing fails.  Streams rows
incrementally so partial data survives crashes.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.base import BaseWriter

log = logging.getLogger(__name__)


class CsvWriter(BaseWriter):
    """Streams telemetry samples to a CSV file row-by-row."""

    def __init__(self) -> None:
        self._path: Path | None = None
        self._file: io.TextIOWrapper | None = None
        self._writer: csv.DictWriter | None = None
        self._fields: list[str] = []

    def open(self, path: Path, schema_fields: list[str]) -> None:
        self._path = path
        self._fields = list(schema_fields)
        self._file = open(path, "w", newline="", encoding="utf-8")  # noqa: SIM115
        self._writer = csv.DictWriter(self._file, fieldnames=self._fields, extrasaction="ignore")
        self._writer.writeheader()
        self._file.flush()
        log.info("CsvWriter opened: %s", path)

    def write_samples(self, samples: list[TelemetrySample]) -> None:
        if not self._writer or not self._file:
            raise RuntimeError("CsvWriter not open")

        for s in samples:
              row = {k: ("" if v is None else v) for k, v in s.to_dict().items()}
              self._writer.writerow(row)
        self._file.flush()
        log.debug("Wrote %d samples to CSV", len(samples))

    def close(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()
            self._file = None
            self._writer = None
            log.info("CsvWriter closed: %s", self._path)
