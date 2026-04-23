"""Compute analysis.json from existing session data at finalize time.

No new physics — derives every field from data already available in the
finalizer's in-memory state (samples, laps, events, quality report).
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from lap_coach_logger import __version__


def build_analysis(
    *,
    laps: list[dict[str, Any]],
    events: list[dict[str, Any]],
    sample_count: int,
    duration_s: float,
    target_sample_rate_hz: float = 10.0,
    quality_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the analysis.json payload.

    ``laps`` and ``events`` are the same dicts written to ``laps.json``
    and ``events.json``. ``quality_report`` is the dict from
    ``quality_report.json`` (if available).
    """
    valid_laps = [l for l in laps if l.get("valid", False)]
    valid_times = [l["lap_time_s"] for l in valid_laps if l.get("lap_time_s", 0) > 0]

    # Lap summary
    fastest = min(valid_times) if valid_times else None
    fastest_num = next(
        (l["lap_number"] for l in valid_laps if l.get("lap_time_s") == fastest), None
    ) if fastest else None
    median = statistics.median(valid_times) if valid_times else None
    std_dev = statistics.stdev(valid_times) if len(valid_times) >= 2 else None
    consistency = (1.0 - std_dev / median) * 100 if std_dev and median and median > 0 else None

    # Fuel
    fuel_values = [l.get("fuel_used_l", 0) for l in laps if l.get("fuel_used_l", 0) > 0]
    total_fuel = sum(fuel_values)
    avg_fuel = statistics.mean(fuel_values) if fuel_values else None
    fuel_std = statistics.stdev(fuel_values) if len(fuel_values) >= 2 else None

    # Stint detection (simple: count pit_stop events)
    pit_stops = [e for e in events if e.get("event_type") == "pit_stop"]
    stint_count = len(pit_stops) + 1

    # Sector times (from valid laps with sector data)
    sector_data = [l.get("sector_times_s", []) for l in valid_laps if l.get("sector_times_s")]
    best_sectors: list[float] = []
    best_theoretical: float | None = None
    if sector_data:
        n_sectors = max(len(s) for s in sector_data)
        for si in range(n_sectors):
            sector_vals = [s[si] for s in sector_data if len(s) > si and s[si] > 0]
            if sector_vals:
                best_sectors.append(min(sector_vals))
        if best_sectors:
            best_theoretical = sum(best_sectors)

    # Quality from existing report
    qr = quality_report or {}
    overall_score = qr.get("overall_score") or qr.get("quality_score", 0.0)
    completeness = qr.get("completeness", 1.0 if sample_count > 0 else 0.0)
    measured_hz = sample_count / duration_s if duration_s > 0 else 0.0

    # Recommendation
    blockers: list[str] = []
    warnings: list[str] = []
    if not valid_times:
        blockers.append("no_complete_laps")
    if duration_s < 60:
        blockers.append("session_too_short")
    if measured_hz < 5.0 and duration_s > 10:
        blockers.append("sample_rate_too_low")
    if overall_score < 0.5 and overall_score > 0:
        warnings.append("low_quality_score")

    if blockers:
        verdict = "not_recommended"
    elif warnings:
        verdict = "partial_data"
    else:
        verdict = "ready_for_review"

    return {
        "schema_version": 1,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "computed_by": "logger",
        "logger_version": __version__,
        "session_quality": {
            "overall_score": round(overall_score, 2) if overall_score else 0.0,
            "completeness": round(completeness, 2),
            "sample_rate_hz_measured": round(measured_hz, 2),
            "sample_rate_hz_target": target_sample_rate_hz,
            "telemetry_gaps_count": qr.get("telemetry_gaps_count", 0),
            "telemetry_gaps_total_s": qr.get("telemetry_gaps_total_s", 0.0),
            "channels_present_count": qr.get("channels_present_count", 0),
            "channels_missing_optional": qr.get("channels_missing_optional", []),
        },
        "lap_summary": {
            "total_laps": len(laps),
            "valid_laps": len(valid_laps),
            "invalid_laps": len(laps) - len(valid_laps),
            "incomplete_laps": sum(1 for l in laps if not l.get("complete", True)),
            "fastest_valid_lap_s": round(fastest, 3) if fastest else None,
            "fastest_valid_lap_number": fastest_num,
            "median_valid_lap_s": round(median, 3) if median else None,
            "lap_time_std_dev_s": round(std_dev, 3) if std_dev else None,
            "lap_consistency_pct": round(consistency, 1) if consistency else None,
        },
        "stint_summary": {
            "stint_count": stint_count,
            "longest_stint_laps": len(laps),  # simplified — assumes single stint when no pit events
            "fuel_consumed_l": round(total_fuel, 2),
            "avg_fuel_per_lap_l": round(avg_fuel, 3) if avg_fuel else None,
            "fuel_per_lap_std_l": round(fuel_std, 3) if fuel_std else None,
        },
        "track_position": {
            "best_sector_times_s": [round(s, 3) for s in best_sectors],
            "best_theoretical_lap_s": round(best_theoretical, 3) if best_theoretical else None,
        },
        "recommendation": {
            "verdict": verdict,
            "blockers": blockers,
            "warnings": warnings,
        },
    }
