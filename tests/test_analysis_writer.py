"""Tests for analysis_writer — analysis.json computation."""

from __future__ import annotations

from lap_coach_logger.writers.analysis_writer import build_analysis


def _make_laps(n: int = 5, base_time: float = 92.0) -> list[dict]:
    return [
        {
            "lap_number": i + 1,
            "lap_time_s": base_time + i * 0.1,
            "valid": True,
            "fuel_used_l": 2.1 + i * 0.01,
            "sector_times_s": [30.0, 30.0, base_time + i * 0.1 - 60.0],
        }
        for i in range(n)
    ]


class TestLapSummary:
    def test_counts_valid_laps(self) -> None:
        laps = _make_laps(5)
        laps[2]["valid"] = False
        result = build_analysis(laps=laps, events=[], sample_count=5000, duration_s=600)
        assert result["lap_summary"]["valid_laps"] == 4
        assert result["lap_summary"]["invalid_laps"] == 1

    def test_fastest_lap_identified(self) -> None:
        laps = _make_laps(5)
        result = build_analysis(laps=laps, events=[], sample_count=5000, duration_s=600)
        assert result["lap_summary"]["fastest_valid_lap_s"] == 92.0
        assert result["lap_summary"]["fastest_valid_lap_number"] == 1

    def test_empty_laps_marks_blocker(self) -> None:
        result = build_analysis(laps=[], events=[], sample_count=100, duration_s=600)
        assert "no_complete_laps" in result["recommendation"]["blockers"]
        assert result["recommendation"]["verdict"] == "not_recommended"


class TestFuelSummary:
    def test_fuel_computed(self) -> None:
        laps = _make_laps(3)
        result = build_analysis(laps=laps, events=[], sample_count=3000, duration_s=300)
        assert result["stint_summary"]["fuel_consumed_l"] > 0
        assert result["stint_summary"]["avg_fuel_per_lap_l"] is not None


class TestSectors:
    def test_best_theoretical_computed(self) -> None:
        laps = _make_laps(3)
        result = build_analysis(laps=laps, events=[], sample_count=3000, duration_s=300)
        assert result["track_position"]["best_theoretical_lap_s"] is not None
        assert len(result["track_position"]["best_sector_times_s"]) == 3


class TestRecommendation:
    def test_short_session_blocked(self) -> None:
        result = build_analysis(laps=_make_laps(1), events=[], sample_count=100, duration_s=30)
        assert "session_too_short" in result["recommendation"]["blockers"]

    def test_healthy_session_passes(self) -> None:
        result = build_analysis(laps=_make_laps(5), events=[], sample_count=5000, duration_s=600)
        assert result["recommendation"]["verdict"] == "ready_for_review"
        assert result["recommendation"]["blockers"] == []


class TestSchema:
    def test_required_top_level_fields(self) -> None:
        result = build_analysis(laps=_make_laps(3), events=[], sample_count=3000, duration_s=300)
        assert result["schema_version"] == 1
        assert result["computed_by"] == "logger"
        assert "session_quality" in result
        assert "lap_summary" in result
        assert "stint_summary" in result
        assert "track_position" in result
        assert "recommendation" in result
