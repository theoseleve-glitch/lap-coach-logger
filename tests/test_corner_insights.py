"""Tests for corner-level self-comparison coaching (Parts 1 + 2)."""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    TechniqueStatement,
    analyze_corner_comparisons,
    build_technique_statement,
    loss_zone_histogram,
    ranked_problem_corners,
    total_time_loss_s,
)
from lap_coach_logger.core.live_dashboard import CornerDefinition
from lap_coach_logger.core.live_lap_compare import (
    ComparePoint,
    LapProfile,
    SegmentMetrics,
)


# ---------------------------------------------------------------------------
# Helpers — build lap profiles directly so tests stay deterministic
# ---------------------------------------------------------------------------

def _points(
    start_pct: float,
    end_pct: float,
    *,
    step_pct: float = 0.005,
    speed_profile: list[float] | None = None,
    brake_profile: list[float] | None = None,
    throttle_profile: list[float] | None = None,
    start_time: float = 0.0,
    lap_number: int = 1,
) -> list[ComparePoint]:
    """Generate an even sample of ComparePoints across a corner window."""
    n = max(1, int((end_pct - start_pct) / step_pct))
    pts = []
    for i in range(n + 1):
        frac = i / n if n > 0 else 0.0
        pct = start_pct + frac * (end_pct - start_pct)
        t = start_time + i * 0.05  # 20 Hz
        speed = speed_profile[i] if speed_profile and i < len(speed_profile) else 100.0
        brake = brake_profile[i] if brake_profile and i < len(brake_profile) else 0.0
        throttle = (
            throttle_profile[i] if throttle_profile and i < len(throttle_profile) else 1.0
        )
        pts.append(ComparePoint(
            lap_number=lap_number,
            lap_dist_pct=pct,
            session_time_s=t,
            speed_kph=speed,
            lat_accel_g=0.0,
            brake_pct=brake,
            throttle_pct=throttle,
        ))
    return pts


def _profile(
    *,
    label: str,
    corner_start: float = 0.20,
    corner_end: float = 0.30,
    lap_time_s: float = 90.0,
    entry_speed: float = 180.0,
    apex_speed: float = 90.0,
    exit_speed: float = 150.0,
    brake_on_pct: float | None = 0.22,   # where brake crosses threshold
    brake_off_pct: float | None = 0.26,  # where brake releases
    throttle_on_pct: float | None = 0.27,  # after apex
    points: list[ComparePoint] | None = None,
) -> LapProfile:
    """Construct a minimal LapProfile for testing."""
    # Build per-sample profile for the corner window with brake/throttle
    # events at the requested positions.
    if points is None:
        samples_count = 21
        step = (corner_end - corner_start) / (samples_count - 1)
        speed_profile = []
        brake_profile = []
        throttle_profile = []
        for i in range(samples_count):
            pct = corner_start + i * step
            # Speed: linear from entry to apex then to exit
            if pct < (corner_start + corner_end) / 2:
                frac = (pct - corner_start) / ((corner_end - corner_start) / 2)
                spd = entry_speed + frac * (apex_speed - entry_speed)
            else:
                frac = (pct - (corner_start + corner_end) / 2) / ((corner_end - corner_start) / 2)
                spd = apex_speed + frac * (exit_speed - apex_speed)
            speed_profile.append(spd)
            # Brake: step up at brake_on_pct, step down at brake_off_pct
            if brake_on_pct is not None and pct >= brake_on_pct and (
                brake_off_pct is None or pct < brake_off_pct
            ):
                brake_profile.append(0.8)
            else:
                brake_profile.append(0.0)
            # Throttle: high before brake, zero during brake, high after throttle_on
            if brake_on_pct is not None and brake_on_pct <= pct < (throttle_on_pct or corner_end):
                throttle_profile.append(0.0)
            else:
                throttle_profile.append(0.9)
        points = _points(
            corner_start, corner_end,
            step_pct=step,
            speed_profile=speed_profile,
            brake_profile=brake_profile,
            throttle_profile=throttle_profile,
            lap_number=1,
        )

    segment = CornerDefinition(
        name="T5", start_pct=corner_start, end_pct=corner_end,
    )
    metric = SegmentMetrics(
        name="T5",
        start_pct=corner_start,
        end_pct=corner_end,
        lap_time_s=round(lap_time_s, 3),
        entry_speed_kph=entry_speed,
        apex_speed_kph=apex_speed,
        exit_speed_kph=exit_speed,
        complete=True,
    )
    return LapProfile(
        source_id=label,
        label=label,
        lap_number=1,
        lap_time_s=lap_time_s,
        points=points,
        segments=[segment],
        segment_metrics=[metric],
        sector_splits={},
    )


# ---------------------------------------------------------------------------
# Part 1: corner segmentation + comparison
# ---------------------------------------------------------------------------

class TestAnalyzeCornerComparisons:
    def test_empty_profiles_return_empty_list(self):
        assert analyze_corner_comparisons(None, None) == []

    def test_missing_segments_returns_empty(self):
        p1 = _profile(label="a")
        p2 = LapProfile(
            source_id="b", label="b", lap_number=1, lap_time_s=90.0,
            points=[], segments=[], segment_metrics=[], sector_splits={},
        )
        assert analyze_corner_comparisons(p1, p2) == []

    def test_detects_corner_loss_with_speed_deltas(self):
        best = _profile(label="best", lap_time_s=29.8, apex_speed=95.0, exit_speed=155.0)
        current = _profile(
            label="cur",
            lap_time_s=30.2,   # 0.4s slower
            apex_speed=85.0,   # 10 kph slower at apex
            exit_speed=145.0,  # 10 kph slower at exit
        )
        # Ensure current lap's segment metric stores the slower time
        current = LapProfile(
            source_id=current.source_id,
            label=current.label,
            lap_number=current.lap_number,
            lap_time_s=current.lap_time_s,
            points=current.points,
            segments=current.segments,
            segment_metrics=[
                SegmentMetrics(
                    name="T5",
                    start_pct=current.segments[0].start_pct,
                    end_pct=current.segments[0].end_pct,
                    lap_time_s=5.2,  # 0.4 slower than best
                    entry_speed_kph=180.0,
                    apex_speed_kph=85.0,
                    exit_speed_kph=145.0,
                    complete=True,
                ),
            ],
            sector_splits={},
        )
        best = LapProfile(
            source_id=best.source_id,
            label=best.label,
            lap_number=best.lap_number,
            lap_time_s=best.lap_time_s,
            points=best.points,
            segments=best.segments,
            segment_metrics=[
                SegmentMetrics(
                    name="T5",
                    start_pct=best.segments[0].start_pct,
                    end_pct=best.segments[0].end_pct,
                    lap_time_s=4.8,  # faster
                    entry_speed_kph=180.0,
                    apex_speed_kph=95.0,
                    exit_speed_kph=155.0,
                    complete=True,
                ),
            ],
            sector_splits={},
        )
        insights = analyze_corner_comparisons(current, best)
        assert len(insights) == 1
        insight = insights[0]
        assert insight.corner_name == "T5"
        assert insight.time_loss_s == pytest.approx(0.4, abs=0.01)
        # Apex 10 kph slower → negative delta
        assert insight.min_speed_delta_kph == pytest.approx(-10.0)
        assert insight.exit_speed_delta_kph == pytest.approx(-10.0)

    def test_confidence_scales_with_sample_density(self):
        # Dense samples → high confidence
        best = _profile(label="best")
        cur = _profile(label="cur", lap_time_s=29.0)
        insights = analyze_corner_comparisons(cur, best)
        assert insights and insights[0].confidence in ("high", "medium")

    def test_missing_telemetry_leaves_fields_none(self):
        # Build points without brake/throttle data
        samples = 12
        step = 0.005
        pts_best = [
            ComparePoint(
                lap_number=1, lap_dist_pct=0.2 + i * step,
                session_time_s=i * 0.05, speed_kph=100.0,
            )
            for i in range(samples)
        ]
        pts_cur = [
            ComparePoint(
                lap_number=1, lap_dist_pct=0.2 + i * step,
                session_time_s=i * 0.05, speed_kph=95.0,
            )
            for i in range(samples)
        ]
        seg = CornerDefinition(name="T5", start_pct=0.20, end_pct=0.255)
        m = SegmentMetrics(
            name="T5", start_pct=0.20, end_pct=0.255,
            lap_time_s=5.0, entry_speed_kph=100.0, apex_speed_kph=90.0,
            exit_speed_kph=100.0, complete=True,
        )
        best = LapProfile(
            source_id="b", label="b", lap_number=1, lap_time_s=30.0,
            points=pts_best, segments=[seg], segment_metrics=[m], sector_splits={},
        )
        cur = LapProfile(
            source_id="c", label="c", lap_number=1, lap_time_s=30.3,
            points=pts_cur, segments=[seg],
            segment_metrics=[SegmentMetrics(
                name="T5", start_pct=0.20, end_pct=0.255,
                lap_time_s=5.3, entry_speed_kph=95.0, apex_speed_kph=85.0,
                exit_speed_kph=95.0, complete=True,
            )],
            sector_splits={},
        )
        insights = analyze_corner_comparisons(cur, best)
        assert len(insights) == 1
        # Brake/throttle deltas should be None without sim data
        assert insights[0].brake_onset_delta_pct is None
        assert insights[0].throttle_pickup_delta_pct is None

    def test_negative_time_loss_still_returns_even_zone(self):
        """A corner where the driver was *faster* than their best must
        not get a spurious loss_zone classification — the QML layer
        reads loss_zone for any corner in `cornerInsights`."""
        from lap_coach_logger.coaching.corner_insights import _compute_loss_zone

        # Negative loss (faster than best), but speed deltas would
        # otherwise sort to a "worst" zone.
        assert _compute_loss_zone(
            time_loss_s=-0.3,
            entry_speed_delta=-5.0,
            min_speed_delta=0.0,
            exit_speed_delta=2.0,
        ) == "even"

    def test_loss_zone_classified_from_speed_spread(self):
        # Construct an insight with clear exit loss: min speed matches,
        # exit is much slower
        best = _profile(label="b", apex_speed=90.0, exit_speed=150.0)
        cur = _profile(label="c", apex_speed=90.0, exit_speed=140.0)
        # Override metrics to encode the time loss clearly on exit
        cur = LapProfile(
            source_id=cur.source_id, label=cur.label,
            lap_number=cur.lap_number, lap_time_s=cur.lap_time_s,
            points=cur.points, segments=cur.segments,
            segment_metrics=[SegmentMetrics(
                name="T5", start_pct=0.20, end_pct=0.30,
                lap_time_s=5.3, entry_speed_kph=180.0, apex_speed_kph=90.0,
                exit_speed_kph=140.0, complete=True,
            )],
            sector_splits={},
        )
        best = LapProfile(
            source_id=best.source_id, label=best.label,
            lap_number=best.lap_number, lap_time_s=best.lap_time_s,
            points=best.points, segments=best.segments,
            segment_metrics=[SegmentMetrics(
                name="T5", start_pct=0.20, end_pct=0.30,
                lap_time_s=5.0, entry_speed_kph=180.0, apex_speed_kph=90.0,
                exit_speed_kph=150.0, complete=True,
            )],
            sector_splits={},
        )
        insights = analyze_corner_comparisons(cur, best)
        assert insights[0].loss_zone == "exit"


# ---------------------------------------------------------------------------
# Part 2: technique statement generation
# ---------------------------------------------------------------------------

class TestTechniqueStatement:
    def test_returns_none_for_small_loss(self):
        insight = CornerInsight(
            corner_name="T5", time_loss_s=0.02, confidence="high",
        )
        assert build_technique_statement(insight) is None

    def test_entry_zone_statement_mentions_braking(self):
        insight = CornerInsight(
            corner_name="T5",
            time_loss_s=0.30,
            entry_speed_delta_kph=-5.0,
            brake_onset_delta_pct=0.01,  # 10m late braking (rough heuristic)
            loss_zone="entry",
            confidence="high",
        )
        stmt = build_technique_statement(insight)
        assert stmt is not None
        assert "T5" in stmt.focus
        assert "brak" in stmt.observation.lower() or "brak" in stmt.action.lower()
        assert stmt.confidence == "high"

    def test_exit_zone_mentions_throttle(self):
        insight = CornerInsight(
            corner_name="T5",
            time_loss_s=0.30,
            exit_speed_delta_kph=-4.0,
            throttle_pickup_delta_pct=0.015,
            loss_zone="exit",
            confidence="high",
        )
        stmt = build_technique_statement(insight)
        assert stmt is not None
        assert "throttle" in stmt.observation.lower() or "throttle" in stmt.action.lower()

    def test_apex_zone_mentions_minimum_speed(self):
        insight = CornerInsight(
            corner_name="T5",
            time_loss_s=0.30,
            min_speed_delta_kph=-6.0,
            loss_zone="mid",
            confidence="medium",
        )
        stmt = build_technique_statement(insight)
        assert stmt is not None
        assert "speed" in stmt.observation.lower() or "carry" in stmt.action.lower()

    def test_even_loss_returns_generic_guidance(self):
        insight = CornerInsight(
            corner_name="T3",
            time_loss_s=0.18,
            loss_zone="even",
            confidence="medium",
        )
        stmt = build_technique_statement(insight)
        assert stmt is not None
        assert stmt.focus == "T3"
        # Generic statement still produces something short
        assert len(stmt.observation) < 120
        assert len(stmt.action) < 120


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

class TestAggregations:
    def test_ranked_problem_corners_prefers_high_confidence(self):
        high = CornerInsight(corner_name="T1", time_loss_s=0.25, confidence="high")
        low = CornerInsight(corner_name="T2", time_loss_s=0.40, confidence="low")
        mid = CornerInsight(corner_name="T3", time_loss_s=0.18, confidence="medium")
        ranked = ranked_problem_corners([low, high, mid], top_n=3, min_confidence="medium")
        # Low confidence filtered out; ordering by loss within remaining set
        names = [r.corner_name for r in ranked]
        assert "T2" not in names
        assert names[0] == "T1"  # highest loss among medium+
        assert names[1] == "T3"

    def test_ranked_problem_corners_falls_back_when_all_low(self):
        low1 = CornerInsight(corner_name="T1", time_loss_s=0.25, confidence="low")
        low2 = CornerInsight(corner_name="T2", time_loss_s=0.40, confidence="low")
        ranked = ranked_problem_corners([low1, low2], top_n=2, min_confidence="medium")
        # Fallback: include low-confidence when nothing else qualifies
        assert len(ranked) == 2
        assert ranked[0].corner_name == "T2"  # ordered by loss

    def test_total_time_loss_sums_positive_only(self):
        insights = [
            CornerInsight(corner_name="T1", time_loss_s=0.2),
            CornerInsight(corner_name="T2", time_loss_s=-0.1),  # faster than best
            CornerInsight(corner_name="T3", time_loss_s=None),
            CornerInsight(corner_name="T4", time_loss_s=0.15),
        ]
        assert total_time_loss_s(insights) == pytest.approx(0.35)

    def test_loss_zone_histogram_counts_correctly(self):
        insights = [
            CornerInsight(corner_name="A", time_loss_s=0.2, loss_zone="exit"),
            CornerInsight(corner_name="B", time_loss_s=0.3, loss_zone="exit"),
            CornerInsight(corner_name="C", time_loss_s=0.1, loss_zone="entry"),
            CornerInsight(corner_name="D", time_loss_s=0.05, loss_zone="mid"),  # below floor
        ]
        hist = loss_zone_histogram(insights)
        assert hist["exit"] == 2
        assert hist["entry"] == 1
        assert hist["mid"] == 0
