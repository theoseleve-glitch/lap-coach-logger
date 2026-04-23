"""Coaching surface policy — when to show, when to stay silent.

Pure rule engine that decides the driver-facing coaching card state
given the current ``CoachingMessage``, active alerts, and the previous
state. Isolates the UX decisions (visibility, cooldown, anti-oscillation,
formatting, carryover) from VM plumbing so they're fully deterministic
and testable.

Rules applied (in evaluation order inside ``compute_surface_state``):

1. **Suppression** — critical alerts (pit now, fuel deficit, etc.) hide
   coaching entirely. Safety-of-race info always wins.
2. **Empty-payload carryover** — when the incoming message is empty but
   the previous had a high-confidence focus within ``carryover_ttl_s``
   of its last publish, hold the previous state. The anchor is refreshed
   to ``now_s`` on the first empty tick so TTL is measured from drop-out.
3. **First-tick publish** — first message after a hidden state shows
   immediately (no cooldown gate on the very first emit).
4. **Hysteresis** — switching the focus requires the new message's loss
   to beat the previous by ``improvement_ratio``. Missing time-loss
   (``None``) skips the comparison rather than blocking the switch.
5. **Cooldown** — within ``cooldown_s`` of the last update, repeat or
   near-identical payloads are suppressed. A focus switch that passes
   hysteresis bypasses cooldown — materially better information surfaces
   immediately.

All rules are deterministic; callers pass ``now_s`` explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from lap_coach_logger.coaching.policy_config import DEFAULT_POLICY, PolicyConfig
from lap_coach_logger.coaching.presentation import CoachingMessage


# Freshness vocabulary — replaces the legacy ``time_loss_s = -1``
# sentinel with explicit state.
FRESHNESS_LIVE = "live"
FRESHNESS_CARRYOVER = "carryover"
FRESHNESS_STALE = "stale"


@dataclass(frozen=True)
class SurfaceState:
    """Overlay-specific wrapper around a CoachingMessage.

    Adds the bookkeeping the overlay policy needs: visibility, freshness,
    and the cooldown / carryover anchor. Other surfaces (Coaching tab,
    post-session card) don't need this — they bind to the message
    directly since they don't do cooldown.
    """
    message: CoachingMessage = field(default_factory=CoachingMessage)
    visible: bool = False
    freshness: str = FRESHNESS_STALE
    last_update_s: float = -1.0


def compute_surface_state(
    *,
    previous: SurfaceState | None,
    message: CoachingMessage,
    critical_alert: bool,
    now_s: float,
    config: PolicyConfig = DEFAULT_POLICY,
) -> SurfaceState:
    """Decide the next surface state from the incoming message + context.

    Pure function — identical inputs always produce identical outputs.
    ``previous`` is ``None`` on the first tick of a session.
    """
    prev = previous or SurfaceState()

    # 1. Critical alerts suppress coaching entirely (anchor preserved).
    if critical_alert:
        return SurfaceState(
            visible=False,
            freshness=FRESHNESS_STALE,
            last_update_s=prev.last_update_s,
        )

    # 2. Empty payload → carry over the previous high-confidence focus.
    if message.is_empty:
        within_ttl = now_s - prev.last_update_s <= config.carryover_ttl_s
        if prev.visible and prev.message.confidence == "high" and within_ttl:
            if prev.freshness == FRESHNESS_LIVE:
                # First empty tick — start a fresh carryover window,
                # anchoring TTL to this drop-out.
                return replace(prev, freshness=FRESHNESS_CARRYOVER, last_update_s=now_s)
            if prev.freshness == FRESHNESS_CARRYOVER:
                return prev
        return SurfaceState(
            visible=False,
            freshness=FRESHNESS_STALE,
            last_update_s=prev.last_update_s,
        )

    # 3. First-ever tick with a payload → publish immediately.
    candidate = SurfaceState(
        message=message,
        visible=True,
        freshness=FRESHNESS_LIVE,
        last_update_s=now_s,
    )
    if not prev.visible or prev.last_update_s < 0:
        return candidate

    # 4. Hysteresis — a focus switch requires clearly better time loss.
    focus_changed = bool(
        message.focus_id and prev.message.focus_id
        and message.focus_id != prev.message.focus_id
    )
    prev_loss = prev.message.time_loss_s
    new_loss = message.time_loss_s
    if (
        focus_changed
        and prev_loss is not None and prev_loss > 0
        and new_loss is not None
        and new_loss < prev_loss * config.improvement_ratio
    ):
        return prev

    # 5. Cooldown — repeat or near-identical payloads in the window are
    # suppressed. A focus switch that passed hysteresis bypasses cooldown.
    same_payload = (
        candidate.message.headline == prev.message.headline
        and candidate.message.subline == prev.message.subline
    )
    within_cooldown = now_s - prev.last_update_s < config.cooldown_s
    if (same_payload or within_cooldown) and not focus_changed:
        return prev

    return candidate
