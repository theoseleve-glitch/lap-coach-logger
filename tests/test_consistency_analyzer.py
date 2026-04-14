"""Tests for self-vs-self consistency analysis."""
from __future__ import annotations

from lap_coach_logger.core.consistency_analyzer import analyze_consistency


class TestBasicConsistency:

    def test_perfectly_consistent_laps(self):
        report = analyze_consistency([90.0, 90.0, 90.0, 90.0, 90.0])
        assert report is not None
        assert report.consistency_pct == 100.0
        assert report.overall_std_dev_s == 0.0
        assert report.trend == "stable"

    def test_variable_laps(self):
        report = analyze_consistency([88.0, 92.0, 89.0, 91.0, 90.0, 93.0, 87.0])
        assert report is not None
        assert 0 < report.consistency_pct < 100
        assert report.overall_std_dev_s > 0
        assert report.best_lap_time_s == 87.0
        assert report.lap_count == 7

    def test_returns_none_with_insufficient_laps(self):
        assert analyze_consistency([90.0, 91.0]) is None
        assert analyze_consistency([]) is None

    def test_improving_trend(self):
        # First 5 laps variable, last 5 laps tight
        laps = [92.0, 95.0, 91.0, 94.0, 93.0, 90.0, 90.1, 90.0, 90.2, 90.1]
        report = analyze_consistency(laps)
        assert report is not None
        assert report.trend == "improving"

    def test_degrading_trend(self):
        # First 5 laps tight, last 5 laps variable
        laps = [90.0, 90.1, 90.0, 90.2, 90.1, 92.0, 95.0, 91.0, 94.0, 93.0]
        report = analyze_consistency(laps)
        assert report is not None
        assert report.trend == "degrading"


class TestSectorConsistency:

    def test_identifies_worst_sector(self):
        # 3 sectors, sector 1 (index 1) is most variable
        sector_times = [
            [30.0, 32.0, 28.0],  # lap 1
            [30.1, 35.0, 28.1],  # lap 2
            [29.9, 31.0, 27.9],  # lap 3
            [30.0, 34.0, 28.0],  # lap 4
        ]
        report = analyze_consistency(
            [90.0, 93.2, 88.9, 92.0],
            sector_times=sector_times,
        )
        assert report is not None
        assert report.worst_sector == 1  # sector 2 (0-indexed)
        assert len(report.per_sector_std_dev) == 3

    def test_theoretical_best_from_sectors(self):
        sector_times = [
            [30.0, 32.0, 28.0],
            [31.0, 30.0, 29.0],
            [30.5, 31.0, 27.5],
        ]
        report = analyze_consistency(
            [90.0, 90.0, 89.0],
            sector_times=sector_times,
        )
        assert report is not None
        # Best sectors: 30.0 + 30.0 + 27.5 = 87.5
        assert abs(report.theoretical_best_s - 87.5) < 0.01


class TestFocusRecommendation:

    def test_focus_on_worst_sector(self):
        sector_times = [
            [30.0, 35.0, 28.0],
            [30.1, 32.0, 28.1],
            [29.9, 38.0, 27.9],
        ]
        report = analyze_consistency(
            [93.0, 90.2, 95.8],
            sector_times=sector_times,
        )
        assert report is not None
        assert "Sector 2" in report.focus_recommendation

    def test_focus_on_consistency_when_no_sectors(self):
        report = analyze_consistency([90.0, 90.5, 89.5, 91.0])
        assert report is not None
        assert report.focus_recommendation != ""


class TestCornerAnalysis:

    def test_worst_corners_reported(self):
        corners = [
            {"name": "T1", "times": [5.0, 5.1, 5.0, 5.2]},
            {"name": "T3", "times": [8.0, 9.5, 7.5, 10.0]},  # most variable
            {"name": "T5", "times": [6.0, 6.5, 6.1, 6.3]},
        ]
        report = analyze_consistency(
            [90.0, 91.0, 89.0, 92.0],
            corner_times=corners,
        )
        assert report is not None
        assert len(report.worst_corners) >= 1
        assert report.worst_corners[0]["name"] == "T3"
