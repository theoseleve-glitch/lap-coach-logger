"""T034: desktop telemetry samples carry t_source_ns + t_canonical_ns (ADR-007).

Each recorded sample must be tagged with two timestamps per ADR-007:
* ``t_source_ns`` — ns since session start on the ORIGINAL sensor's clock.
* ``t_canonical_ns`` — ns since session start in the canonical timebase.

Desktop captures from a single coordinator clock today, so the two
values coincide — but the contract is preserved so multi-source
fusion (real-hardware phone + GPS + racebox) can diverge them later.
"""
from __future__ import annotations

from lap_coach_logger.core.canonical_time import (
    derive_canonical_timestamps,
)
from lap_coach_logger.core.schema import TelemetrySample


def _sample(t_s: float) -> TelemetrySample:
    return TelemetrySample(
        sim="iracing",
        session_uid="s1",
        session_time_s=t_s,
        lap_number=1,
        lap_dist_pct=t_s / 90.0,
        speed_kph=120.0,
    )


def test_both_ns_fields_emitted_per_sample() -> None:
    samples = [_sample(0.0), _sample(0.5), _sample(1.25)]
    rows = derive_canonical_timestamps(samples)
    assert len(rows) == 3
    for row in rows:
        assert "t_source_ns" in row
        assert "t_canonical_ns" in row
        assert "t_source_clock" in row


def test_ns_fields_are_nanosecond_precision_ints() -> None:
    row = derive_canonical_timestamps([_sample(0.5)])[0]
    assert isinstance(row["t_source_ns"], int)
    assert isinstance(row["t_canonical_ns"], int)
    # 0.5 s → 500_000_000 ns
    assert row["t_source_ns"] == 500_000_000
    assert row["t_canonical_ns"] == 500_000_000


def test_timestamps_are_monotonically_non_decreasing() -> None:
    samples = [_sample(float(i) * 0.1) for i in range(20)]
    rows = derive_canonical_timestamps(samples)
    for prev, curr in zip(rows, rows[1:]):
        assert prev["t_source_ns"] <= curr["t_source_ns"]
        assert prev["t_canonical_ns"] <= curr["t_canonical_ns"]


def test_source_clock_tag_defaults_to_irsdk_tick_for_iracing() -> None:
    row = derive_canonical_timestamps(
        [_sample(1.0)], source_clock="irsdk_tick"
    )[0]
    assert row["t_source_clock"] == "irsdk_tick"


def test_source_and_canonical_coincide_on_single_clock_capture() -> None:
    """Desktop single-source capture → canonical == source."""
    rows = derive_canonical_timestamps([_sample(2.75)])
    row = rows[0]
    assert row["t_source_ns"] == row["t_canonical_ns"], (
        "single-clock capture must produce identical source/canonical ns"
    )


def test_samples_without_session_time_yield_zero_ns() -> None:
    """Missing ``session_time_s`` defaults to 0 ns (sample appears at session start)."""
    s = TelemetrySample(sim="iracing", session_uid="x", session_time_s=None)
    rows = derive_canonical_timestamps([s])
    assert rows[0]["t_source_ns"] == 0
    assert rows[0]["t_canonical_ns"] == 0
