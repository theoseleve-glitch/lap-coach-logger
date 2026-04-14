"""Tests for ready-to-race classification."""
from __future__ import annotations

from lap_coach_logger.coaching.readiness import (
    ReadinessAssessment,
    ReadinessState,
    assess_readiness,
)
from lap_coach_logger.coaching.output import Confidence
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport


def _report(
    consistency_pct: float = 85.0,
    std_dev: float = 0.4,
    median: float = 90.0,
    best: float = 89.0,
    trend: str = "stable",
    per_sector_std_dev: list[float] | None = None,
    worst_corners: list[dict] | None = None,
    lap_count: int = 15,
) -> ConsistencyReport:
    return ConsistencyReport(
        overall_std_dev_s=std_dev,
        consistency_pct=consistency_pct,
        median_lap_time_s=median,
        best_lap_time_s=best,
        theoretical_best_s=best,
        per_sector_std_dev=per_sector_std_dev or [0.15, 0.2, 0.15],
        worst_sector=1,
        worst_corners=worst_corners or [],
        trend=trend,
        focus_recommendation="",
        lap_count=lap_count,
    )


class TestReadyState:

    def test_ready_when_all_checks_pass(self):
        result = assess_readiness(_report(consistency_pct=88, trend="stable", lap_count=15))
        assessment = result.value
        assert assessment.state == ReadinessState.READY
        assert assessment.consistency_ok is True
        assert assessment.trend_ok is True
        assert result.confidence == Confidence.HIGH

    def test_not_ready_with_low_consistency(self):
        result = assess_readiness(_report(consistency_pct=50, lap_count=15))
        assert result.value.state == ReadinessState.NOT_READY

    def test_not_ready_with_degrading_trend(self):
        result = assess_readiness(_report(trend="degrading", lap_count=15))
        assert result.value.state != ReadinessState.READY
        assert result.value.trend_ok is False

    def test_almost_with_insufficient_laps(self):
        result = assess_readiness(_report(lap_count=7))
        assert result.value.state in (ReadinessState.ALMOST, ReadinessState.NOT_READY)

    def test_not_ready_with_too_few_laps(self):
        result = assess_readiness(_report(lap_count=3))
        assert result.value.state == ReadinessState.NOT_READY

    def test_none_report_returns_not_ready(self):
        result = assess_readiness(None)
        assert result.value.state == ReadinessState.NOT_READY
        assert result.confidence == Confidence.LOW

    def test_outlier_corner_fails_check(self):
        # One corner with std_dev way above the rest
        corners = [
            {"name": "T1", "std_dev_s": 0.1},
            {"name": "T3", "std_dev_s": 0.8},  # outlier: > 3x median of [0.1, 0.8, 0.12]
            {"name": "T5", "std_dev_s": 0.12},
        ]
        result = assess_readiness(_report(worst_corners=corners, lap_count=15))
        assert result.value.no_outlier_corners is False

    def test_uneven_sector_variance_flags_instability(self):
        # Sector 1 dominates total variance
        sectors = [0.5, 0.05, 0.05]  # S1 is 83% of total
        result = assess_readiness(_report(per_sector_std_dev=sectors, lap_count=15))
        assert result.value.variance_stable is False

    def test_confidence_scales_with_lap_count(self):
        low = assess_readiness(_report(lap_count=5))
        med = assess_readiness(_report(lap_count=10))
        high = assess_readiness(_report(lap_count=20))
        assert low.confidence == Confidence.LOW
        assert med.confidence == Confidence.MEDIUM
        assert high.confidence == Confidence.HIGH

    def test_best_lap_is_not_used_for_classification(self):
        # Same consistency but very different best laps -- should classify the same
        slow = assess_readiness(_report(best=120.0, consistency_pct=88, lap_count=15))
        fast = assess_readiness(_report(best=80.0, consistency_pct=88, lap_count=15))
        assert slow.value.state == fast.value.state
