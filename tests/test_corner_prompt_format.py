"""T152: Corner-specific prompt formatter.

The spec example: ``"losing X at T1 — brake later"``. One concise
line per corner that names (a) the time loss, (b) the corner,
(c) the action. This is the *rules-engine* output that the
overlay surfaces — sharper than the verbose
:class:`TechniqueStatement` (which has separate focus /
observation / likely_cause / action fields for the post-race
summary).

The action vocabulary mirrors the existing technique-statement
zone branches in :func:`build_technique_statement` so a driver
sees consistent language whether they're reading a corner pill
mid-session or the technique sheet post-session:

- entry zone, braking too late ⇒ "brake earlier"
- entry zone, braking too early ⇒ "brake later"
- mid zone, low minimum speed ⇒ "carry more speed"
- mid zone, high minimum speed ⇒ "slow earlier"
- exit zone, late throttle ⇒ "throttle earlier"
- exit zone, low exit speed ⇒ "open throttle sooner"

Returns ``None`` when there's nothing meaningful to say
(``time_loss_s`` is ``None`` or below the significance
threshold). Mirrors :func:`build_technique_statement`'s gate.
"""
from __future__ import annotations

from lap_coach_logger.coaching.corner_insights import (
    CornerInsight,
    format_corner_prompt,
)


# ---------------------------------------------------------------------------
# None / empty edges
# ---------------------------------------------------------------------------


def test_returns_none_when_time_loss_is_none() -> None:
    """No measurement ⇒ no prompt."""
    insight = CornerInsight(corner_name="T1", time_loss_s=None)

    assert format_corner_prompt(insight) is None


def test_returns_none_when_loss_is_below_significance_threshold() -> None:
    """Tiny losses (< 0.08s) are noise — same gate as
    :func:`build_technique_statement` so corners that survived
    one prompt path won't surface in the other."""
    insight = CornerInsight(
        corner_name="T1", time_loss_s=0.05, loss_zone="entry",
    )

    assert format_corner_prompt(insight) is None


# ---------------------------------------------------------------------------
# Entry zone
# ---------------------------------------------------------------------------


def test_entry_zone_late_braking_says_brake_earlier() -> None:
    """Braking later than best AND losing time = over-braked /
    rushed entry. The action is to brake earlier (counter-
    intuitive but correct: late + losing = wrong-late)."""
    insight = CornerInsight(
        corner_name="T1",
        time_loss_s=0.32,
        loss_zone="entry",
        brake_onset_delta_pct=0.005,  # 0.5% lap-distance later
    )

    assert format_corner_prompt(insight) == "losing 0.3s at T1 — brake earlier"


def test_entry_zone_early_braking_says_brake_later() -> None:
    """Braking earlier than best AND losing time = hesitant
    entry. The fix is to brake later. Mirrors the spec example
    "losing X at T1 — brake later"."""
    insight = CornerInsight(
        corner_name="T1",
        time_loss_s=0.21,
        loss_zone="entry",
        brake_onset_delta_pct=-0.005,  # 0.5% lap-distance earlier
    )

    assert format_corner_prompt(insight) == "losing 0.2s at T1 — brake later"


# ---------------------------------------------------------------------------
# Mid (apex) zone
# ---------------------------------------------------------------------------


def test_mid_zone_low_min_speed_says_carry_more_speed() -> None:
    """Apex speed lower than best = scrubbing speed mid-corner.
    Action: trail-brake less / carry more speed."""
    insight = CornerInsight(
        corner_name="T3",
        time_loss_s=0.42,
        loss_zone="mid",
        min_speed_delta_kph=-3.5,
    )

    assert format_corner_prompt(insight) == "losing 0.4s at T3 — carry more speed"


def test_mid_zone_high_min_speed_says_slow_earlier() -> None:
    """Apex speed higher than best AND losing = running too
    wide. Slow the car more, tighter apex line."""
    insight = CornerInsight(
        corner_name="T4",
        time_loss_s=0.18,
        loss_zone="mid",
        min_speed_delta_kph=3.0,
    )

    assert format_corner_prompt(insight) == "losing 0.2s at T4 — slow earlier"


# ---------------------------------------------------------------------------
# Exit zone
# ---------------------------------------------------------------------------


def test_exit_zone_late_throttle_says_throttle_earlier() -> None:
    """Throttle pickup delayed vs best = unwinding steering too
    late. Action: get on throttle earlier."""
    insight = CornerInsight(
        corner_name="T5",
        time_loss_s=0.27,
        loss_zone="exit",
        throttle_pickup_delta_pct=0.006,
    )

    assert format_corner_prompt(insight) == "losing 0.3s at T5 — throttle earlier"


def test_exit_zone_low_exit_speed_says_open_throttle_sooner() -> None:
    """Exit speed deficit without late throttle pickup =
    rolling too slow off the apex (line / commitment).
    Action: open throttle sooner."""
    insight = CornerInsight(
        corner_name="T6",
        time_loss_s=0.31,
        loss_zone="exit",
        throttle_pickup_delta_pct=0.0,  # no clear pickup delta
        exit_speed_delta_kph=-3.0,
    )

    assert (
        format_corner_prompt(insight)
        == "losing 0.3s at T6 — open throttle sooner"
    )


# ---------------------------------------------------------------------------
# Even / generic zone — fallback when no dominant signal
# ---------------------------------------------------------------------------


def test_even_zone_with_no_dominant_signal_says_rebuild_corner() -> None:
    """When loss is spread evenly with no obvious input
    delta, the action is to rebuild the corner (brake / apex /
    throttle reference). Mirrors :func:`_generic_statement`."""
    insight = CornerInsight(
        corner_name="T7",
        time_loss_s=0.18,
        loss_zone="even",
    )

    assert (
        format_corner_prompt(insight)
        == "losing 0.2s at T7 — rebuild the corner"
    )


# ---------------------------------------------------------------------------
# Format pin
# ---------------------------------------------------------------------------


def test_format_uses_em_dash_separator() -> None:
    """Pin the structure: ``"losing X at <corner> — <action>"``.
    QML widget binds to this string verbatim — no further
    parsing — so the separator must be stable."""
    insight = CornerInsight(
        corner_name="T1",
        time_loss_s=0.32,
        loss_zone="entry",
        brake_onset_delta_pct=0.005,
    )

    result = format_corner_prompt(insight)

    assert result is not None
    assert " — " in result, "Prompt must use em-dash separator"
    assert result.startswith("losing "), "Prompt must lead with 'losing '"
    assert " at T1 " in result, "Prompt must name the corner"
