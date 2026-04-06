"""Parquet writer using PyArrow.

Writes a single ``telemetry.parquet`` per session with Snappy
compression and schema derived from ``TelemetrySample``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.base import BaseWriter

log = logging.getLogger(__name__)

# PyArrow type mapping for schema fields
_PA_TYPES: dict[str, pa.DataType] = {
    "timestamp_utc": pa.string(),
    "sim": pa.string(),
    "session_uid": pa.string(),
    "session_time_s": pa.float64(),
    "lap_number": pa.int32(),
    "lap_distance_m": pa.float64(),
    "speed_kph": pa.float64(),
    "throttle_pct": pa.float64(),
    "brake_pct": pa.float64(),
    "steering_deg": pa.float64(),
    "gear": pa.int32(),
    "rpm": pa.float64(),
    "abs_level": pa.float64(),
    "tc_level": pa.float64(),
    "world_pos_x": pa.float64(),
    "world_pos_y": pa.float64(),
    "world_pos_z": pa.float64(),
    "yaw_deg": pa.float64(),
    "pitch": pa.float64(),
    "roll": pa.float64(),
    "long_accel_g": pa.float64(),
    "lat_accel_g": pa.float64(),
    "tyre_temp_lf": pa.float64(),
    "tyre_temp_rf": pa.float64(),
    "tyre_temp_lr": pa.float64(),
    "tyre_temp_rr": pa.float64(),
    "fuel_level": pa.float64(),
    "fuel_capacity": pa.float64(),
    "water_temp": pa.float64(),
    "oil_temp": pa.float64(),
    "track_temp_c": pa.float64(),
    "air_temp_c": pa.float64(),
    "is_on_track": pa.bool_(),
    "is_in_pits": pa.bool_(),
    "track_name": pa.string(),
    "car_name": pa.string(),
    "session_type": pa.string(),
    "raw_source_timestamp": pa.float64(),
    "lap_dist_pct": pa.float64(),
    "clutch_pct": pa.float64(),
}


class ParquetWriter(BaseWriter):
    """Writes telemetry samples to a Parquet file."""

    def __init__(self, *, compression: str = "snappy", row_group_size: int = 10_000) -> None:
        self._compression = compression
        self._row_group_size = row_group_size
        self._path: Path | None = None
        self._schema: pa.Schema | None = None
        self._pq_writer: pq.ParquetWriter | None = None

    def open(self, path: Path, schema_fields: list[str]) -> None:
        fields = [pa.field(name, _PA_TYPES.get(name, pa.string())) for name in schema_fields]
        self._schema = pa.schema(fields)
        self._path = path
        self._pq_writer = pq.ParquetWriter(
            str(path),
            self._schema,
            compression=self._compression,
        )
        log.info("ParquetWriter opened: %s", path)

    def write_samples(self, samples: list[TelemetrySample]) -> None:
        if not self._pq_writer or not self._schema:
            raise RuntimeError("ParquetWriter not open")

        columns: dict[str, list] = {f.name: [] for f in self._schema}
        for s in samples:
            d = s.to_dict()
            for col in columns:
                columns[col].append(d.get(col))

        table = pa.table(columns, schema=self._schema)
        self._pq_writer.write_table(table)
        log.debug("Wrote %d samples to parquet", len(samples))

    def close(self) -> None:
        if self._pq_writer:
            self._pq_writer.close()
            self._pq_writer = None
            log.info("ParquetWriter closed: %s", self._path)
