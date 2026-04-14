"""Ready-to-race classification.

Based on consistency (primary), variance stability, trend,
and absence of large corner outliers. Best lap is NOT a signal.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Any

from lap_coach_logger.coaching.output import Confidence, CoachingOutput
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport


class ReadinessState(Enum):
    NOT_READY = "not_ready"
    ALMOST = "almost"
    READY = "ready"


@dataclass(frozen=True)
class ReadinessAssessment:
    state: ReadinessState
    consistency_ok: bool
    variance_stable: bool
    trend_ok: bool
    no_outlier_corners: bool
    lap_count: int
    confidence: Confidence
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "consistency_ok": self.consistency_ok,
            "variance_stable": self.variance_stable,
            "trend_ok": self.trend_ok,
            "no_outlier_corners": self.no_outlier_corners,
            "lap_count": self.lap_count,
            "confidence": self.confidence.value,
            "reason": self.reason,
        }


def _check_consistency(report: ConsistencyReport) -> bool:
    """consistency_ok: consistency_pct >= adaptive threshold.

    Threshold = max(70, 100 - report.median_lap_time_s * 0.2)
    Faster tracks (shorter laps) allow slightly more absolute variance.
    """
    threshold = max(70.0, 100.0 - report.median_lap_time_s * 0.2)
    return report.consistency_pct >= threshold


def _check_variance_stable(report: ConsistencyReport) -> bool:
    """variance_stable: no single sector dominates > 50% of total variance.

    If sector data is unavailable, defaults to True.
    """
    sectors = report.per_sector_std_dev
    if not sectors or len(sectors) < 2:
        return True
    total = sum(sectors)
    if total == 0:
        return True
    return all(s / total <= 0.5 for s in sectors)


def _check_trend(report: ConsistencyReport) -> bool:
    """trend_ok: trend is NOT 'degrading'."""
    return report.trend != "degrading"


def _check_outlier_corners(report: ConsistencyReport) -> bool:
    """no_outlier_corners: no corner has std_dev > 3x the median corner std_dev.

    If corner data is unavailable or has fewer than 2 entries,
    defaults to True.
    """
    corners = report.worst_corners
    if not corners or len(corners) < 2:
        return True
    std_devs = [c["std_dev_s"] for c in corners if "std_dev_s" in c]
    if len(std_devs) < 2:
        return True
    median_std = statistics.median(std_devs)
    if median_std == 0:
        return True
    return all(s <= 3.0 * median_std for s in std_devs)


def _compute_confidence(lap_count: int) -> Confidence:
    """Confidence scales with lap count."""
    if lap_count >= 15:
        return Confidence.HIGH
    if lap_count >= 8:
        return Confidence.MEDIUM
    return Confidence.LOW


def _classify_state(
    checks_passed: int,
    lap_count: int,
    consistency_ok: bool,
) -> ReadinessState:
    """Classify readiness state from check results and lap count.

    Consistency is the primary signal -- it gates READY and ALMOST.

    - READY:     all 4 checks pass AND lap_count >= 10
    - ALMOST:    (3 of 4 checks pass AND consistency_ok) OR
                 (consistency_ok AND lap_count >= 5 but < 10)
    - NOT_READY: fewer than 3 checks pass OR lap_count < 5 OR
                 consistency_ok is False
    """
    if lap_count < 5:
        return ReadinessState.NOT_READY
    if not consistency_ok:
        return ReadinessState.NOT_READY
    if checks_passed == 4 and lap_count >= 10:
        return ReadinessState.READY
    if checks_passed >= 3 or (lap_count >= 5 and lap_count < 10):
        return ReadinessState.ALMOST
    return ReadinessState.NOT_READY


def _build_reason(
    state: ReadinessState,
    consistency_ok: bool,
    variance_stable: bool,
    trend_ok: bool,
    no_outlier_corners: bool,
    lap_count: int,
) -> str:
    """Build a human-readable reason string."""
    if state == ReadinessState.READY:
        return "Consistency, variance, trend, and corner stability all pass."

    issues: list[str] = []
    if not consistency_ok:
        issues.append("lap-time consistency below threshold")
    if not variance_stable:
        issues.append("one sector dominates variance")
    if not trend_ok:
        issues.append("trend is degrading")
    if not no_outlier_corners:
        issues.append("corner outlier detected")
    if lap_count < 5:
        issues.append(f"only {lap_count} laps (need at least 5)")
    elif lap_count < 10:
        issues.append(f"only {lap_count} laps (need at least 10 for READY)")

    if issues:
        return "Not race-ready: " + "; ".join(issues) + "."
    return "Borderline readiness — close but not all checks pass."


def assess_readiness(report: ConsistencyReport | None) -> CoachingOutput:
    """Assess race readiness from a consistency report.

    Classification logic (all thresholds derived from data):

    1. consistency_ok: consistency_pct >= adaptive threshold
       - Threshold = max(70, 100 - report.median_lap_time_s * 0.2)
       - Faster tracks (shorter laps) allow slightly more absolute variance
       - This scales with track length rather than using a fixed number

    2. variance_stable: per-sector std devs don't have one sector
       dominating > 50% of total variance (if sectors available)

    3. trend_ok: trend is NOT "degrading"

    4. no_outlier_corners: no corner has std_dev > 3x the median
       corner std_dev (if corners available)

    State classification:
    - READY: all 4 checks pass AND lap_count >= 10
    - ALMOST: 3 of 4 checks pass OR lap_count >= 5 but < 10
    - NOT_READY: fewer than 3 checks pass OR lap_count < 5

    Confidence:
    - HIGH: lap_count >= 15
    - MEDIUM: 8 <= lap_count < 15
    - LOW: lap_count < 8
    """
    if report is None:
        assessment = ReadinessAssessment(
            state=ReadinessState.NOT_READY,
            consistency_ok=False,
            variance_stable=False,
            trend_ok=False,
            no_outlier_corners=False,
            lap_count=0,
            confidence=Confidence.LOW,
            reason="No consistency data available.",
        )
        return CoachingOutput(
            value=assessment,
            confidence=Confidence.LOW,
            reason="No consistency data available.",
        )

    consistency_ok = _check_consistency(report)
    variance_stable = _check_variance_stable(report)
    trend_ok = _check_trend(report)
    no_outlier_corners = _check_outlier_corners(report)

    checks_passed = sum([consistency_ok, variance_stable, trend_ok, no_outlier_corners])
    lap_count = report.lap_count
    confidence = _compute_confidence(lap_count)
    state = _classify_state(checks_passed, lap_count, consistency_ok)
    reason = _build_reason(
        state, consistency_ok, variance_stable, trend_ok, no_outlier_corners, lap_count,
    )

    assessment = ReadinessAssessment(
        state=state,
        consistency_ok=consistency_ok,
        variance_stable=variance_stable,
        trend_ok=trend_ok,
        no_outlier_corners=no_outlier_corners,
        lap_count=lap_count,
        confidence=confidence,
        reason=reason,
    )
    return CoachingOutput(
        value=assessment,
        confidence=confidence,
        reason=reason,
    )
