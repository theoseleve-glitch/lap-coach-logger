"""Corner-level technique coaching — self-comparison model.

Deterministic, rule-based analysis that compares the driver's CURRENT
lap against their OWN best valid lap, on a per-corner basis, and
produces concise technique coaching statements.

Design goals:
- No new physics, no ML, no reference-driver dependency.
- Pure functions — no Qt, no I/O, no state.
- Safe on weak / partial corner segmentation: when confidence is low,
  callers can fall back to sector-level guidance.
- Short outputs fit overlay widget sizes.

Metric vocabulary:
- *entry_speed_delta_kph*: current entry speed minus best entry speed.
  Positive → faster than best (sometimes unsustainable if braking late).
- *min_speed_delta_kph*: current apex (min) speed minus best's.
  Negative → slow mid-corner (over-slow, wrong line, scrubbed speed).
- *exit_speed_delta_kph*: current exit minus best's. Negative →
  poor exit, late throttle, corner of the car not rotated.
- *brake_onset_delta_pct*: where current driver starts braking vs best,
  in lap-distance %. Negative → braking EARLIER than best.
- *brake_release_delta_pct*: delta on where brake returns to zero.
- *throttle_pickup_delta_pct*: delta on where throttle crosses the
  re-apply threshold. Negative → throttle earlier than best. Positive
  → throttle later (most common amateur loss).
- *time_loss_s*: seconds lost in this corner vs best (corner time delta).
- *confidence*: how trustworthy the insight is (segmentation quality).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

# Import here to avoid a circular: live_lap_compare owns ComparePoint,
# and ComparePoint knows about raw telemetry; we consume it read-only.
from lap_coach_logger.core.live_lap_compare import ComparePoint, LapProfile, SegmentMetrics
from lap_coach_logger.core.live_dashboard import CornerDefinition


# Thresholds — chosen to be meaningful on amateur telemetry. Kept
# together so tuning is visible in one place.
_BRAKE_ON_FRACTION = 0.15     # >15% pedal counts as "braking"
_THROTTLE_ON_FRACTION = 0.25  # >25% pedal counts as "on throttle"
_MIN_SIGNIFICANT_LOSS_S = 0.08  # below this, corner is "optimised" (negative loss also returns "even")


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CornerInsight:
    """Per-corner self-comparison metrics + focus guidance.

    All deltas are ``current - best`` so negative = faster / earlier.
    Fields may be ``None`` when the underlying data is missing —
    callers must treat missing fields as "unknown".
    """
    corner_name: str                      # e.g. "T5" or "Corner 3"

    # Time-in-corner delta (most important single number)
    time_loss_s: float | None = None

    # Speed deltas (kph; positive = current is faster)
    entry_speed_delta_kph: float | None = None
    min_speed_delta_kph: float | None = None
    exit_speed_delta_kph: float | None = None

    # Input timing deltas (lap-distance-pct; negative = earlier than best)
    brake_onset_delta_pct: float | None = None
    brake_release_delta_pct: float | None = None
    throttle_pickup_delta_pct: float | None = None

    # Confidence in the insight — high/medium/low. Drives whether the
    # coaching layer should surface it or fall back to sector guidance.
    confidence: str = "medium"

    # Where the loss is concentrated within the corner
    # ("entry", "mid", "exit", "even")
    loss_zone: str = "even"


@dataclass(frozen=True)
class TechniqueStatement:
    """Concise coaching statement safe for overlay use.

    All strings short enough for a ~280x80 widget.
    """
    focus: str         # "T5" or "Sector 2 entry zone"
    observation: str   # "Braking begins later than your best lap"
    likely_cause: str  # "Rushed entry, pedal too hard"
    action: str        # "Brake 10m earlier, carry 4kph more"
    confidence: str    # "high" / "medium" / "low"


# ---------------------------------------------------------------------------
# Brake / throttle event extraction (per corner)
# ---------------------------------------------------------------------------

def _points_in_corner(
    points: Iterable[ComparePoint],
    corner: CornerDefinition,
) -> list[ComparePoint]:
    """Slice lap points to the corner window (inclusive of ends)."""
    return [
        p for p in points
        if corner.start_pct <= p.lap_dist_pct <= corner.end_pct
    ]


def _first_crossing_pct(
    points: list[ComparePoint],
    attr: str,
    threshold: float,
    rising: bool,
) -> float | None:
    """Find lap_dist_pct where *attr* first crosses *threshold*.

    If ``rising``, looks for first sample >= threshold. Otherwise looks
    for first sample <= threshold *after* a rising sample has been seen.
    Returns None when no crossing exists (e.g. brake never applied).
    """
    if not points:
        return None
    if rising:
        for p in points:
            v = getattr(p, attr, None)
            if v is not None and v >= threshold:
                return p.lap_dist_pct
        return None
    # Falling: need rising first, then falling
    seen_high = False
    for p in points:
        v = getattr(p, attr, None)
        if v is None:
            continue
        if not seen_high:
            if v >= threshold:
                seen_high = True
            continue
        if v <= threshold * 0.5:  # hysteresis: off is half of on
            return p.lap_dist_pct
    return None


def _brake_events(points: list[ComparePoint]) -> tuple[float | None, float | None]:
    """Return (onset_pct, release_pct) for the first braking event."""
    return (
        _first_crossing_pct(points, "brake_pct", _BRAKE_ON_FRACTION, rising=True),
        _first_crossing_pct(points, "brake_pct", _BRAKE_ON_FRACTION, rising=False),
    )


def _throttle_pickup_pct(points: list[ComparePoint]) -> float | None:
    """Pct where throttle crosses the pickup threshold *after* a minimum.

    Uses the corner min-speed sample as the "apex proxy" — throttle
    pickup is only meaningful after the slowest point.
    """
    if not points:
        return None
    min_idx = _argmin_speed(points)
    if min_idx is None:
        return None
    return _first_crossing_pct(
        points[min_idx:], "throttle_pct", _THROTTLE_ON_FRACTION, rising=True,
    )


def _argmin_speed(points: list[ComparePoint]) -> int | None:
    """Index of slowest point, or None if speeds unavailable."""
    best: tuple[float, int] | None = None
    for i, p in enumerate(points):
        if p.speed_kph is None:
            continue
        if best is None or p.speed_kph < best[0]:
            best = (p.speed_kph, i)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Confidence + loss-zone helpers
# ---------------------------------------------------------------------------

def _corner_confidence(
    current_pts: list[ComparePoint],
    best_pts: list[ComparePoint],
    corner: CornerDefinition,
) -> str:
    """Rate segmentation confidence.

    - high: >=15 points per side, span >=5% of lap
    - medium: >=8 points per side
    - low: otherwise
    """
    span = corner.end_pct - corner.start_pct
    n_cur = len(current_pts)
    n_best = len(best_pts)
    if n_cur >= 15 and n_best >= 15 and span >= 0.05:
        return "high"
    if n_cur >= 8 and n_best >= 8:
        return "medium"
    return "low"


def _compute_loss_zone(
    time_loss_s: float | None,
    entry_speed_delta: float | None,
    min_speed_delta: float | None,
    exit_speed_delta: float | None,
) -> str:
    """Classify where the loss concentrates.

    Heuristic rule: the zone with the worst (most negative) speed delta
    earns the loss assignment. When deltas are all similar, returns
    "even".
    """
    if time_loss_s is None or time_loss_s < _MIN_SIGNIFICANT_LOSS_S:
        return "even"
    candidates: list[tuple[str, float]] = []
    if entry_speed_delta is not None:
        candidates.append(("entry", entry_speed_delta))
    if min_speed_delta is not None:
        candidates.append(("mid", min_speed_delta))
    if exit_speed_delta is not None:
        candidates.append(("exit", exit_speed_delta))
    if not candidates:
        return "even"
    # Most-negative delta = slowest zone relative to best = highest loss
    candidates.sort(key=lambda kv: kv[1])
    worst_zone, worst_delta = candidates[0]
    best_zone, best_delta = candidates[-1]
    if (best_delta - worst_delta) < 3.0:  # kph spread too small
        return "even"
    return worst_zone


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze_corner_comparisons(
    current_profile: LapProfile | None,
    best_profile: LapProfile | None,
) -> list[CornerInsight]:
    """Compare every detected corner in the current vs best lap.

    Returns an empty list when either profile is missing, has no
    segments, or no shared corners. Per-corner insights may have some
    fields set to ``None`` when the underlying telemetry is missing
    (e.g. a sim that doesn't expose brake %).
    """
    if current_profile is None or best_profile is None:
        return []
    if not current_profile.segments or not best_profile.segments:
        return []

    best_metric_map: dict[str, SegmentMetrics] = {
        m.name: m for m in best_profile.segment_metrics
    }
    current_metric_map: dict[str, SegmentMetrics] = {
        m.name: m for m in current_profile.segment_metrics
    }

    insights: list[CornerInsight] = []
    for corner in current_profile.segments:
        if corner.name not in best_metric_map:
            continue
        current_pts = _points_in_corner(current_profile.points, corner)
        best_pts = _points_in_corner(best_profile.points, corner)
        if not current_pts or not best_pts:
            continue

        # Time loss from segment metrics (already computed upstream)
        current_metric = current_metric_map.get(corner.name)
        best_metric = best_metric_map.get(corner.name)
        time_loss: float | None = None
        if (
            current_metric is not None
            and best_metric is not None
            and current_metric.complete
            and current_metric.lap_time_s is not None
            and best_metric.lap_time_s is not None
        ):
            time_loss = round(current_metric.lap_time_s - best_metric.lap_time_s, 3)

        # Speed deltas from segment metrics
        entry_delta = _delta(
            current_metric.entry_speed_kph if current_metric else None,
            best_metric.entry_speed_kph if best_metric else None,
        )
        min_delta = _delta(
            current_metric.apex_speed_kph if current_metric else None,
            best_metric.apex_speed_kph if best_metric else None,
        )
        exit_delta = _delta(
            current_metric.exit_speed_kph if current_metric else None,
            best_metric.exit_speed_kph if best_metric else None,
        )

        # Brake / throttle events
        cur_on, cur_off = _brake_events(current_pts)
        best_on, best_off = _brake_events(best_pts)
        brake_onset_delta = _delta(cur_on, best_on)
        brake_release_delta = _delta(cur_off, best_off)

        cur_pickup = _throttle_pickup_pct(current_pts)
        best_pickup = _throttle_pickup_pct(best_pts)
        throttle_pickup_delta = _delta(cur_pickup, best_pickup)

        confidence = _corner_confidence(current_pts, best_pts, corner)
        loss_zone = _compute_loss_zone(time_loss, entry_delta, min_delta, exit_delta)

        insights.append(CornerInsight(
            corner_name=corner.name,
            time_loss_s=time_loss,
            entry_speed_delta_kph=_round_or_none(entry_delta, 1),
            min_speed_delta_kph=_round_or_none(min_delta, 1),
            exit_speed_delta_kph=_round_or_none(exit_delta, 1),
            brake_onset_delta_pct=_round_or_none(brake_onset_delta, 4),
            brake_release_delta_pct=_round_or_none(brake_release_delta, 4),
            throttle_pickup_delta_pct=_round_or_none(throttle_pickup_delta, 4),
            confidence=confidence,
            loss_zone=loss_zone,
        ))

    return insights


# ---------------------------------------------------------------------------
# Technique statement builder (Part 2)
# ---------------------------------------------------------------------------

def build_technique_statement(insight: CornerInsight) -> TechniqueStatement | None:
    """Turn a CornerInsight into a concise coaching statement.

    Returns ``None`` when the insight has no significant signal — use
    this to gate "should we render a technique tip for this corner?".
    Confidence gating is the caller's responsibility; this function
    will produce text for medium-confidence insights too so callers can
    decide whether to show it.
    """
    # Skip corners where the time loss is too small to act on
    if insight.time_loss_s is None or abs(insight.time_loss_s) < _MIN_SIGNIFICANT_LOSS_S:
        return None

    zone = insight.loss_zone
    corner = insight.corner_name
    loss = abs(insight.time_loss_s)

    # ---- Zone-based templates ----
    if zone == "entry":
        return _entry_statement(insight, corner, loss)
    if zone == "mid":
        return _apex_statement(insight, corner, loss)
    if zone == "exit":
        return _exit_statement(insight, corner, loss)
    # Even loss: pick the most actionable input delta
    return _generic_statement(insight, corner, loss)


def _entry_statement(
    insight: CornerInsight,
    corner: str,
    loss: float,
) -> TechniqueStatement:
    brake_delta = insight.brake_onset_delta_pct
    if brake_delta is not None and brake_delta > 0.003:
        # Braking later than best (but losing time) → over-braked or rushed
        return TechniqueStatement(
            focus=corner,
            observation=f"Braking begins {int(brake_delta * 1000)}m later than your best",
            likely_cause="Rushed entry — overshooting apex or scrubbing speed",
            action=f"Brake {int(brake_delta * 1000)}m earlier, smoother release",
            confidence=insight.confidence,
        )
    if brake_delta is not None and brake_delta < -0.003:
        # Braking earlier and losing → hesitant entry
        return TechniqueStatement(
            focus=corner,
            observation=f"Braking {abs(int(brake_delta * 1000))}m earlier than your best",
            likely_cause="Hesitant on entry — leaving time on the table",
            action="Trust the car more — brake later, carry entry speed",
            confidence=insight.confidence,
        )
    # No brake data — use entry speed
    entry = insight.entry_speed_delta_kph
    if entry is not None and entry < -2:
        return TechniqueStatement(
            focus=corner,
            observation=f"Entry speed is {abs(entry):.1f} kph lower than your best",
            likely_cause="Over-braking or early lift",
            action=f"Carry {abs(entry):.0f} kph more at the brake point",
            confidence=insight.confidence,
        )
    return TechniqueStatement(
        focus=f"{corner} entry",
        observation=f"{loss:.2f}s lost on entry",
        likely_cause="Entry phase inconsistency",
        action="Focus on a repeatable brake reference",
        confidence=insight.confidence,
    )


def _apex_statement(
    insight: CornerInsight,
    corner: str,
    loss: float,
) -> TechniqueStatement:
    min_delta = insight.min_speed_delta_kph
    if min_delta is not None and min_delta < -2:
        return TechniqueStatement(
            focus=corner,
            observation=f"Minimum speed is {abs(min_delta):.1f} kph lower than your best",
            likely_cause="Over-slowing — scrubbing speed mid-corner",
            action=f"Carry {abs(min_delta):.0f} kph more, later or trail-brake less",
            confidence=insight.confidence,
        )
    if min_delta is not None and min_delta > 2:
        return TechniqueStatement(
            focus=corner,
            observation=f"Minimum speed is {min_delta:.1f} kph higher than your best",
            likely_cause="Running too wide or not settling the car",
            action="Slow the car more, tighter apex line",
            confidence=insight.confidence,
        )
    return TechniqueStatement(
        focus=f"{corner} mid-corner",
        observation=f"{loss:.2f}s lost through the apex",
        likely_cause="Mid-corner line or rotation",
        action="Focus on a repeatable apex reference",
        confidence=insight.confidence,
    )


def _exit_statement(
    insight: CornerInsight,
    corner: str,
    loss: float,
) -> TechniqueStatement:
    throttle_delta = insight.throttle_pickup_delta_pct
    if throttle_delta is not None and throttle_delta > 0.003:
        return TechniqueStatement(
            focus=corner,
            observation="Throttle pickup is delayed vs your best",
            likely_cause="Not unwinding steering early enough",
            action="Get on throttle earlier — ride the kerb if needed",
            confidence=insight.confidence,
        )
    exit_delta = insight.exit_speed_delta_kph
    if exit_delta is not None and exit_delta < -2:
        return TechniqueStatement(
            focus=corner,
            observation=f"Exit speed is {abs(exit_delta):.1f} kph lower than your best",
            likely_cause="Rolling too slow off the apex",
            action="Earlier throttle, straighter exit",
            confidence=insight.confidence,
        )
    return TechniqueStatement(
        focus=f"{corner} exit",
        observation=f"{loss:.2f}s lost on exit",
        likely_cause="Exit phase — throttle timing or line",
        action="Unwind steering, full throttle earlier",
        confidence=insight.confidence,
    )


def _generic_statement(
    insight: CornerInsight,
    corner: str,
    loss: float,
) -> TechniqueStatement:
    return TechniqueStatement(
        focus=corner,
        observation=f"{loss:.2f}s lost in this corner",
        likely_cause="Inconsistency across entry, mid, and exit",
        action="Rebuild the corner — brake point, apex, throttle pickup",
        confidence=insight.confidence,
    )


# ---------------------------------------------------------------------------
# Aggregation helpers (Part 4 + Part 5)
# ---------------------------------------------------------------------------

def total_time_loss_s(insights: Iterable[CornerInsight]) -> float:
    """Sum the positive time losses across corners (seconds on the table)."""
    return round(
        sum(i.time_loss_s for i in insights if i.time_loss_s and i.time_loss_s > 0),
        3,
    )


def ranked_problem_corners(
    insights: Iterable[CornerInsight],
    *,
    top_n: int = 3,
    min_confidence: str = "medium",
) -> list[CornerInsight]:
    """Return the ``top_n`` corners with the biggest time loss.

    Filters out low-confidence insights unless there are no higher
    alternatives. Callers use this for next-5-laps focus and the
    post-session summary.
    """
    order = {"high": 3, "medium": 2, "low": 1}
    min_score = order.get(min_confidence, 2)
    filtered = [
        i for i in insights
        if i.time_loss_s is not None
        and i.time_loss_s >= _MIN_SIGNIFICANT_LOSS_S
        and order.get(i.confidence, 0) >= min_score
    ]
    # Fallback: include low-confidence if nothing else qualifies
    if not filtered:
        filtered = [
            i for i in insights
            if i.time_loss_s is not None and i.time_loss_s >= _MIN_SIGNIFICANT_LOSS_S
        ]
    filtered.sort(key=lambda i: i.time_loss_s or 0.0, reverse=True)
    return filtered[:top_n]


def loss_zone_histogram(
    insights: Iterable[CornerInsight],
) -> dict[str, int]:
    """Count insights per loss zone. Useful for blocker-type detection."""
    counts = {"entry": 0, "mid": 0, "exit": 0, "even": 0}
    for i in insights:
        if i.time_loss_s is None or i.time_loss_s < _MIN_SIGNIFICANT_LOSS_S:
            continue
        counts[i.loss_zone] = counts.get(i.loss_zone, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Private micro-helpers
# ---------------------------------------------------------------------------

def _delta(current: float | None, best: float | None) -> float | None:
    """Subtract best from current, preserving None when either is missing."""
    if current is None or best is None:
        return None
    return current - best


def _round_or_none(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)
