"""Helpers for exporting saved session telemetry."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)


def export_session_telemetry_csv(session_folder: str | Path, export_path: str | Path) -> bool:
    """Export a session bundle's telemetry as CSV.

    If the bundle already contains ``telemetry.csv`` it is copied directly.
    If the bundle only contains ``telemetry.parquet`` it is converted with
    pyarrow, which is already a project dependency.
    """
    src_folder = Path(session_folder)
    target_path = Path(export_path)
    src_csv = src_folder / "telemetry.csv"
    src_parquet = src_folder / "telemetry.parquet"

    if src_csv.exists():
        shutil.copy2(src_csv, target_path)
        log.info("Exported CSV from %s to %s", src_csv, target_path)
        return True

    if src_parquet.exists():
        import pyarrow.csv as pa_csv
        import pyarrow.parquet as pq

        table = pq.read_table(src_parquet)
        pa_csv.write_csv(table, target_path)
        log.info("Converted parquet %s to CSV %s", src_parquet, target_path)
        return True

    log.warning("No telemetry file found in %s", src_folder)
    return False
