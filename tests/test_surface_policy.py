"""Tests for the coaching surface policy engine.

Covers visibility / suppression / cooldown / hysteresis / carryover /
formatting rules that gate the driver-facing coaching card.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.policy_config import DEFAULT_POLICY, PolicyConfig
from lap_coach_logger.coaching.presentation import CoachingMessage
from lap_coach_logger.coaching.surface_policy import (
    FRESHNESS_CARRYOVER,
    FRESHNESS_LIVE,
    FRESHNESS_STALE,
    SurfaceState,
    compute_surface_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(**overrides) -> CoachingMessage:
    defaults = dict(
        focus_id="T5",
        category="corner",
        headline="T5: Braking begins later than your best",
        subline="Brake 10m earlier, smoother release",
        confidence="high",
        severity="positive",
        time_loss_s=0.35,
    )
    defaults.update(overrides)
    return CoachingMessage(**defaults)


def _empty_msg() -> CoachingMessage:
    return CoachingMessage()


# ---------------------------------------------------------------------------
# Visibility rules
# ---------------------------------------------------------------------------

class TestVisibility:
    def test_first_tick_with_payload_becomes_visible(self):
        state = compute_surface_state(
            previous=None, message=_msg(), critical_alert=False, now_s=10.0,
        )
        assert state.visible is True
        assert "T5" in state.message.headline
        assert state.message.category == "corner"
        assert state.freshness == FRESHNESS_LIVE

    def test_empty_payload_stays_hidden(self):
        state = compute_surface_state(
            previous=None, message=_empty_msg(), critical_alert=False, now_s=10.0,
        )
        assert state.visible is False
        assert state.freshness == FRESHNESS_STALE


# ---------------------------------------------------------------------------
# Suppression under critical alerts
# ---------------------------------------------------------------------------

class TestSuppression:
    def test_critical_alert_suppresses_coaching(self):
        state = compute_surface_state(
            previous=None, message=_msg(), critical_alert=True, now_s=10.0,
        )
        assert state.visible is False

    def test_suppression_preserves_cooldown_anchor(self):
        previous = SurfaceState(
            message=_msg(),
            visible=True,
            freshness=FRESHNESS_LIVE,
            last_update_s=5.0,
        )
        state = compute_surface_state(
            previous=previous, message=_msg(), critical_alert=True, now_s=7.0,
        )
        assert state.last_update_s == previous.last_update_s

    def test_suppression_overrides_even_high_confidence(self):
        previous = SurfaceState(
            message=_msg(confidence="high"),
            visible=True,
            freshness=FRESHNESS_LIVE,
            last_update_s=5.0,
        )
        state = compute_surface_state(
            previous=previous,
            message=_msg(confidence="high"),
            critical_alert=True,
            now_s=10.0,
        )
        assert state.visible is False


# ---------------------------------------------------------------------------
# Cooldown behavior
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_same_payload_within_cooldown_is_noop(self):
        previous = compute_surface_state(
            previous=None, message=_msg(), critical_alert=False, now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous, message=_msg(), critical_alert=False, now_s=5.0,
        )
        assert next_state == previous

    def test_new_payload_within_cooldown_does_not_replace(self):
        previous = compute_surface_state(
            previous=None, message=_msg(), critical_alert=False, now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                headline="T5: different wording same idea",
                subline="Brake slightly earlier",
            ),
            critical_alert=False,
            now_s=5.0,
        )
        assert next_state.message.headline == previous.message.headline

    def test_payload_updates_after_cooldown_elapses(self):
        previous = compute_surface_state(
            previous=None, message=_msg(), critical_alert=False, now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                headline="T5: new insight that updates",
                subline="Different action",
            ),
            critical_alert=False,
            now_s=20.0,
        )
        assert "new insight" in next_state.message.headline


# ---------------------------------------------------------------------------
# Hysteresis / anti-oscillation
# ---------------------------------------------------------------------------

class TestHysteresis:
    def test_focus_sticks_when_new_corner_not_clearly_better(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(focus_id="T5", time_loss_s=0.40),
            critical_alert=False,
            now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                focus_id="T7",
                headline="T7: Different corner",
                time_loss_s=0.45,  # only 12.5% better
            ),
            critical_alert=False,
            now_s=60.0,
        )
        assert next_state.message.focus_id == "T5"

    def test_focus_switches_when_new_corner_clearly_better(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(focus_id="T5", time_loss_s=0.30),
            critical_alert=False,
            now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                focus_id="T7",
                headline="T7: clearly the bigger issue",
                time_loss_s=0.60,
            ),
            critical_alert=False,
            now_s=60.0,
        )
        assert next_state.message.focus_id == "T7"

    def test_unknown_time_loss_skips_hysteresis(self):
        """time_loss_s=None means 'unknown' — hysteresis must skip."""
        previous = compute_surface_state(
            previous=None,
            message=_msg(focus_id="T5", time_loss_s=0.30),
            critical_alert=False,
            now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                focus_id="T9",
                headline="T9: new focus, time_loss unknown",
                time_loss_s=None,
            ),
            critical_alert=False,
            now_s=60.0,
        )
        assert next_state.message.focus_id == "T9"

    def test_focus_switch_passing_hysteresis_bypasses_cooldown(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(focus_id="T5", time_loss_s=0.20),
            critical_alert=False,
            now_s=0.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                focus_id="T7",
                headline="T7: much bigger issue",
                time_loss_s=0.80,
            ),
            critical_alert=False,
            now_s=5.0,  # inside 15s cooldown
        )
        assert next_state.message.focus_id == "T7"
        assert "T7" in next_state.message.headline


# ---------------------------------------------------------------------------
# Carryover — mode switch or transient gap
# ---------------------------------------------------------------------------

class TestCarryover:
    def test_carries_over_high_confidence_when_payload_drops(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(confidence="high"),
            critical_alert=False,
            now_s=5.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_empty_msg(),
            critical_alert=False,
            now_s=35.0,
        )
        assert next_state.visible is True
        assert next_state.freshness == FRESHNESS_CARRYOVER
        assert next_state.message.headline == previous.message.headline
        assert next_state.last_update_s == 35.0

    def test_carryover_persists_across_multiple_empty_ticks(self):
        start = compute_surface_state(
            previous=None,
            message=_msg(confidence="high"),
            critical_alert=False,
            now_s=5.0,
        )
        drop_out = compute_surface_state(
            previous=start,
            message=_empty_msg(),
            critical_alert=False,
            now_s=35.0,
        )
        later = compute_surface_state(
            previous=drop_out,
            message=_empty_msg(),
            critical_alert=False,
            now_s=95.0,
        )
        assert later.visible is True
        assert later.freshness == FRESHNESS_CARRYOVER
        assert later.message.headline == start.message.headline

    def test_carryover_expires_after_ttl_from_drop_out(self):
        start = compute_surface_state(
            previous=None,
            message=_msg(confidence="high"),
            critical_alert=False,
            now_s=5.0,
        )
        drop_out = compute_surface_state(
            previous=start,
            message=_empty_msg(),
            critical_alert=False,
            now_s=35.0,
        )
        expired = compute_surface_state(
            previous=drop_out,
            message=_empty_msg(),
            critical_alert=False,
            now_s=216.0,   # 35 + 181 (just past 180s TTL from drop-out)
        )
        assert expired.visible is False

    def test_carryover_does_not_start_if_already_stale(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(confidence="high"),
            critical_alert=False,
            now_s=5.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_empty_msg(),
            critical_alert=False,
            now_s=600.0,
        )
        assert next_state.visible is False

    def test_low_confidence_does_not_carry_over(self):
        previous = compute_surface_state(
            previous=None,
            message=_msg(confidence="medium"),
            critical_alert=False,
            now_s=5.0,
        )
        next_state = compute_surface_state(
            previous=previous,
            message=_empty_msg(),
            critical_alert=False,
            now_s=10.0,
        )
        assert next_state.visible is False


# ---------------------------------------------------------------------------
# Policy config
# ---------------------------------------------------------------------------

class TestPolicyConfig:
    def test_custom_cooldown_is_honored(self):
        tight = PolicyConfig(cooldown_s=2.0)
        previous = compute_surface_state(
            previous=None, message=_msg(), critical_alert=False, now_s=0.0,
            config=tight,
        )
        # Only 3s later — outside the 2s cooldown, update allowed
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(
                headline="T5: updated within default-cooldown window",
                subline="Different",
            ),
            critical_alert=False,
            now_s=3.0,
            config=tight,
        )
        assert "updated" in next_state.message.headline

    def test_custom_improvement_ratio_is_honored(self):
        relaxed = PolicyConfig(improvement_ratio=1.05)
        previous = compute_surface_state(
            previous=None,
            message=_msg(focus_id="T5", time_loss_s=0.30),
            critical_alert=False,
            now_s=0.0,
            config=relaxed,
        )
        # New focus only 10% better — blocked by default 1.20, passes 1.05
        next_state = compute_surface_state(
            previous=previous,
            message=_msg(focus_id="T7", headline="T7: marginal win", time_loss_s=0.33),
            critical_alert=False,
            now_s=60.0,
            config=relaxed,
        )
        assert next_state.message.focus_id == "T7"

    def test_custom_carryover_ttl_is_honored(self):
        short = PolicyConfig(carryover_ttl_s=10.0)
        start = compute_surface_state(
            previous=None,
            message=_msg(confidence="high"),
            critical_alert=False,
            now_s=5.0,
            config=short,
        )
        drop_out = compute_surface_state(
            previous=start,
            message=_empty_msg(),
            critical_alert=False,
            now_s=10.0,
            config=short,
        )
        expired = compute_surface_state(
            previous=drop_out,
            message=_empty_msg(),
            critical_alert=False,
            now_s=25.0,
            config=short,
        )
        assert expired.visible is False
