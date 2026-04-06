"""Post-session data-quality validation.

This module is simulator-agnostic: it validates normalized telemetry
samples and bundle metadata, and produces a structured quality report.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median, pstdev
from typing import Any

from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TelemetrySample


@dataclass
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class QualityReport:
    schema_version: str = "1.0.0"
    overall_quality_score: float = 0.0
    individual_checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    recommended_classification: str = "needs_review"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "overall_quality_score": self.overall_quality_score,
            "individual_checks": [c.to_dict() for c in self.individual_checks],
            "warnings": self.warnings,
            "rejection_reasons": self.rejection_reasons,
            "recommended_classification": self.recommended_classification,
        }


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def _is_active_driving_claim(session_type: str | None) -> bool:
    if not session_type:
        return False
    s = session_type.strip().lower()
    active = {"race", "practice", "qualify", "qualifying", "hotlap", "time attack", "test"}
    return s in active


def validate_session_quality(
    *,
    samples: list[TelemetrySample],
    laps: list[Any],
    track_name: str | None,
    car_name: str | None,
    session_type: str | None,
    sample_rate_hz: float | None,
    config: QualityConfig,
) -> QualityReport:
    """Validate one recorded session and return a classification report."""
    checks: list[CheckResult] = []
    warnings: list[str] = []
    rejections: list[str] = []

    # --- basic vectors -------------------------------------------------
    speeds = [_to_float(s.speed_kph) for s in samples if s.speed_kph is not None]
    throttles = [_to_float(s.throttle_pct) for s in samples if s.throttle_pct is not None]
    brakes = [_to_float(s.brake_pct) for s in samples if s.brake_pct is not None]
    gears = [s.gear for s in samples if s.gear is not None]

    # Prefer session_time_s for interval checks.
    session_times = [_to_float(s.session_time_s) for s in samples if s.session_time_s is not None]
    session_times = [x for x in session_times if x is not None]

    # Fallback wall-clock timestamps.
    wall_times: list[float] = []
    if not session_times:
        for s in samples:
            dt = _parse_iso(s.timestamp_utc)
            if dt is not None:
                wall_times.append(dt.timestamp())

    # --- too few samples ----------------------------------------------
    if len(samples) < config.min_samples:
        checks.append(CheckResult(
            name="too_few_samples",
            status="fail",
            details={"sample_count": len(samples), "min_required": config.min_samples},
        ))
        rejections.append(f"Too few samples ({len(samples)} < {config.min_samples})")
    else:
        checks.append(CheckResult(
            name="too_few_samples",
            status="pass",
            details={"sample_count": len(samples)},
        ))

    # --- duration too short -------------------------------------------
    duration_s = 0.0
    if len(session_times) >= 2:
        duration_s = max(0.0, session_times[-1] - session_times[0])
    elif len(wall_times) >= 2:
        duration_s = max(0.0, wall_times[-1] - wall_times[0])

    if duration_s < config.min_duration_s:
        checks.append(CheckResult(
            name="duration_too_short",
            status="fail",
            details={"duration_s": round(duration_s, 3), "min_required_s": config.min_duration_s},
        ))
        rejections.append(
            f"Telemetry duration too short ({round(duration_s, 2)}s < {config.min_duration_s}s)"
        )
    else:
        checks.append(CheckResult(
            name="duration_too_short",
            status="pass",
            details={"duration_s": round(duration_s, 3)},
        ))

    # --- timestamps monotonic -----------------------------------------
    monotonic = True
    regressions = 0
    base_times = session_times if session_times else wall_times
    if len(base_times) >= 2:
        for i in range(1, len(base_times)):
            if base_times[i] < base_times[i - 1]:
                regressions += 1
                monotonic = False
    if monotonic:
        checks.append(CheckResult(name="timestamps_monotonic", status="pass"))
    else:
        checks.append(CheckResult(
            name="timestamps_monotonic",
            status="fail",
            details={"regressions": regressions},
        ))
        rejections.append(f"Non-monotonic timestamps ({regressions} regressions)")

    # --- duplicate rows ------------------------------------------------
    dup_count = 0
    if samples:
        seen: set[tuple] = set()
        for s in samples:
            row = tuple(sorted(s.to_dict().items()))
            if row in seen:
                dup_count += 1
            else:
                seen.add(row)
    dup_ratio = dup_count / len(samples) if samples else 0.0
    if dup_ratio > 0.2:
        checks.append(CheckResult(
            name="duplicate_rows",
            status="warn",
            details={"duplicates": dup_count, "ratio": round(dup_ratio, 4)},
        ))
        warnings.append(f"High duplicate row ratio ({dup_count} duplicate samples)")
    else:
        checks.append(CheckResult(
            name="duplicate_rows",
            status="pass",
            details={"duplicates": dup_count, "ratio": round(dup_ratio, 4)},
        ))

    # --- missing essential channels -----------------------------------
    essential = {
        "speed_kph": speeds,
        "throttle_pct": throttles,
        "brake_pct": brakes,
        "gear": gears,
        "lap_number": [s.lap_number for s in samples if s.lap_number is not None],
    }
    missing_ratios: dict[str, float] = {}
    worst = 0.0
    for name, vals in essential.items():
        missing = len(samples) - len(vals)
        ratio = (missing / len(samples)) if samples else 1.0
        missing_ratios[name] = round(ratio, 4)
        worst = max(worst, ratio)

    if worst >= config.essential_missing_ratio_fail:
        checks.append(CheckResult(
            name="missing_essential_channels",
            status="fail",
            details={"missing_ratios": missing_ratios},
        ))
        rejections.append("Missing essential telemetry channels")
    elif worst >= config.essential_missing_ratio_warn:
        checks.append(CheckResult(
            name="missing_essential_channels",
            status="warn",
            details={"missing_ratios": missing_ratios},
        ))
        warnings.append("Essential channels have elevated missing values")
    else:
        checks.append(CheckResult(
            name="missing_essential_channels",
            status="pass",
            details={"missing_ratios": missing_ratios},
        ))

    # --- large time gaps ------------------------------------------------
    gaps: list[float] = []
    if len(base_times) >= 2:
        for i in range(1, len(base_times)):
            dt = base_times[i] - base_times[i - 1]
            if dt > config.max_time_gap_s:
                gaps.append(dt)
    if gaps:
        checks.append(CheckResult(
            name="large_time_gaps",
            status="warn",
            details={"gap_count": len(gaps), "max_gap_s": round(max(gaps), 3)},
        ))
        warnings.append(f"Large telemetry gaps detected ({len(gaps)} gaps)")
    else:
        checks.append(CheckResult(name="large_time_gaps", status="pass"))

    # --- impossible values ---------------------------------------------
    bad_speed = sum(1 for v in speeds if v is not None and v < 0)
    bad_gear = sum(1 for g in gears if g is not None and (g < config.min_gear or g > config.max_gear))
    bad_throttle = sum(1 for v in throttles if v is not None and (v < -0.05 or v > 1.05))
    bad_brake = sum(1 for v in brakes if v is not None and (v < -0.05 or v > 1.05))
    impossible_total = bad_speed + bad_gear + bad_throttle + bad_brake
    if impossible_total > 0:
        checks.append(CheckResult(
            name="impossible_values",
            status="fail",
            details={
                "negative_speed": bad_speed,
                "impossible_gear": bad_gear,
                "invalid_throttle": bad_throttle,
                "invalid_brake": bad_brake,
            },
        ))
        rejections.append("Impossible telemetry values detected")
    else:
        checks.append(CheckResult(name="impossible_values", status="pass"))

    # --- lap boundaries -------------------------------------------------
    lap_numbers = [s.lap_number for s in samples if s.lap_number is not None]
    lap_decreases = 0
    if len(lap_numbers) >= 2:
        for i in range(1, len(lap_numbers)):
            if lap_numbers[i] < lap_numbers[i - 1]:
                lap_decreases += 1

    if lap_decreases > 0:
        checks.append(CheckResult(
            name="lap_boundaries",
            status="fail",
            details={"lap_decreases": lap_decreases},
        ))
        rejections.append("Lap boundaries incoherent (lap number decreased)")
    elif not laps and _is_active_driving_claim(session_type):
        checks.append(CheckResult(
            name="lap_boundaries",
            status="warn",
            details={"lap_records": 0},
        ))
        warnings.append("No lap boundaries detected in active driving session")
    else:
        checks.append(CheckResult(
            name="lap_boundaries",
            status="pass",
            details={"lap_records": len(laps)},
        ))

    # --- meaningful driving --------------------------------------------
    max_speed = max(speeds) if speeds else 0.0
    meaningful = max_speed >= config.min_meaningful_speed_kph
    if not meaningful:
        checks.append(CheckResult(
            name="meaningful_driving",
            status="fail",
            details={"max_speed_kph": round(max_speed, 3), "min_required_kph": config.min_meaningful_speed_kph},
        ))
        rejections.append("No meaningful driving detected")
    else:
        checks.append(CheckResult(
            name="meaningful_driving",
            status="pass",
            details={"max_speed_kph": round(max_speed, 3)},
        ))

    # --- flatline controls ---------------------------------------------
    speed_std = pstdev(speeds) if len(speeds) >= 2 else 0.0
    throttle_std = pstdev(throttles) if len(throttles) >= 2 else 0.0
    brake_std = pstdev(brakes) if len(brakes) >= 2 else 0.0
    active_claim = _is_active_driving_claim(session_type) or meaningful
    flatlined = (
        active_claim
        and speed_std <= config.flatline_speed_std_kph
        and throttle_std <= config.flatline_control_std
        and brake_std <= config.flatline_control_std
    )
    if flatlined:
        checks.append(CheckResult(
            name="flatlined_controls",
            status="warn",
            details={
                "speed_std_kph": round(speed_std, 4),
                "throttle_std": round(throttle_std, 5),
                "brake_std": round(brake_std, 5),
            },
        ))
        warnings.append("Throttle/brake/speed appear flatlined for active driving")
    else:
        checks.append(CheckResult(
            name="flatlined_controls",
            status="pass",
            details={
                "speed_std_kph": round(speed_std, 4),
                "throttle_std": round(throttle_std, 5),
                "brake_std": round(brake_std, 5),
            },
        ))

    # --- track/car presence --------------------------------------------
    if not track_name or not car_name:
        checks.append(CheckResult(
            name="track_car_present",
            status="fail",
            details={"track_name": track_name, "car_name": car_name},
        ))
        rejections.append("Track or car metadata missing")
    else:
        checks.append(CheckResult(name="track_car_present", status="pass"))

    # --- interval consistency ------------------------------------------
    if len(base_times) >= 3:
        diffs = [base_times[i] - base_times[i - 1] for i in range(1, len(base_times))]
        diffs = [d for d in diffs if d > 0]
        if diffs:
            expected = (1.0 / sample_rate_hz) if (sample_rate_hz and sample_rate_hz > 0) else median(diffs)
            if expected > 0:
                outliers = [
                    d for d in diffs
                    if abs(d - expected) / expected > config.interval_tolerance_ratio
                ]
                ratio = len(outliers) / len(diffs)
                if ratio >= config.interval_outlier_ratio_fail:
                    checks.append(CheckResult(
                        name="sample_interval_consistency",
                        status="fail",
                        details={"expected_s": round(expected, 4), "outlier_ratio": round(ratio, 4)},
                    ))
                    rejections.append("Sample interval inconsistency beyond tolerance")
                elif ratio >= config.interval_outlier_ratio_warn:
                    checks.append(CheckResult(
                        name="sample_interval_consistency",
                        status="warn",
                        details={"expected_s": round(expected, 4), "outlier_ratio": round(ratio, 4)},
                    ))
                    warnings.append("Sample interval jitter above warning threshold")
                else:
                    checks.append(CheckResult(
                        name="sample_interval_consistency",
                        status="pass",
                        details={"expected_s": round(expected, 4), "outlier_ratio": round(ratio, 4)},
                    ))
            else:
                checks.append(CheckResult(name="sample_interval_consistency", status="warn"))
                warnings.append("Unable to evaluate sample interval consistency")
        else:
            checks.append(CheckResult(name="sample_interval_consistency", status="warn"))
            warnings.append("Unable to evaluate sample interval consistency")
    else:
        checks.append(CheckResult(name="sample_interval_consistency", status="warn"))
        warnings.append("Not enough timestamps for sample interval consistency check")

    # --- classification --------------------------------------------------
    n_fail = sum(1 for c in checks if c.status == "fail")
    n_warn = sum(1 for c in checks if c.status == "warn")
    total = max(1, len(checks))
    score = max(0.0, 1.0 - ((n_fail * 1.0) + (n_warn * 0.35)) / total)
    score = round(score, 4)

    if rejections:
        cls = "rejected"
    elif n_warn >= 3:
        cls = "needs_review"
    elif n_warn > 0:
        cls = "accepted_with_warnings"
    else:
        cls = "accepted"

    return QualityReport(
        overall_quality_score=score,
        individual_checks=checks,
        warnings=warnings,
        rejection_reasons=rejections,
        recommended_classification=cls,
    )
