"""T110: ``ReviewMode`` — no live coaching, readiness guidance.

Review mode is the desktop's playback / post-session-view
profile. The user is studying a past session, not driving live,
so:

- Live coaching cards have nothing to fire on (no telemetry
  stream); ``coaching_verbosity = "off"``.
- Strategy assumptions don't apply (no live fuel / time
  decisions to make); ``strategy_safety_margin = 0.0``.
- Readiness guidance lives elsewhere in the UI (the Review
  page itself shows quality grade, lap counts, etc. per T071);
  Review mode just doesn't *block* its display.

Distinct from PracticeMode (verbose, live coaching) and
SprintMode/EnduranceMode (race racing, pace focus). Review is
the only mode where ``coaching_verbosity == "off"`` — the
others all surface insights at varying cadences.
"""
from __future__ import annotations

from lap_coach_logger.core.modes import Mode
from lap_coach_logger.core.modes.review import ReviewMode


def test_review_mode_is_a_concrete_mode_subclass() -> None:
    assert issubclass(ReviewMode, Mode)


def test_review_mode_can_be_instantiated() -> None:
    ReviewMode()


def test_review_mode_has_review_id() -> None:
    assert ReviewMode().id == "review"


def test_review_mode_display_name_is_review() -> None:
    assert ReviewMode().name == "Review"


def test_review_mode_coaching_is_off() -> None:
    """Review mode has no live telemetry stream — coaching has
    nothing to fire on. Pinning ``"off"`` here catches a
    refactor that would silently surface zombie cards on a
    paused session."""
    assert ReviewMode().coaching_verbosity == "off"


def test_review_mode_environment_tag_is_sim_review() -> None:
    """Server uses the tag to filter out review-mode "sessions"
    from competitive aggregation. Without it, a user
    re-watching a race would pollute their pace stats with
    duplicate-lap records."""
    assert ReviewMode().environment_tag == "sim_review"


def test_review_mode_strategy_safety_margin_is_zero() -> None:
    """No live strategy in review — no fuel / time projections
    to pad."""
    assert ReviewMode().strategy_safety_margin == 0.0


def test_review_mode_is_unique_in_having_no_coaching() -> None:
    """Cross-mode invariant: ReviewMode is the ONLY mode where
    coaching is fully off. Practice / Sprint / Endurance all
    surface insights at varying cadences. Pinning this
    invariant catches a refactor that would accidentally
    disable coaching for, say, Sprint."""
    from lap_coach_logger.core.modes.endurance import EnduranceMode
    from lap_coach_logger.core.modes.practice import PracticeMode
    from lap_coach_logger.core.modes.sprint import SprintMode

    assert ReviewMode().coaching_verbosity == "off"
    assert PracticeMode().coaching_verbosity != "off"
    assert SprintMode().coaching_verbosity != "off"
    assert EnduranceMode().coaching_verbosity != "off"
