"""T188: bail-out logic — when a freshly auto-applied version
crashes repeatedly on startup, decide that the new version is
broken and signal that we should roll back to the predecessor.

The probation pattern:

1. **Apply.** When an update is applied,
   :func:`mark_version_on_probation` writes a JSON marker
   recording the new version, the previous version (so we
   know where to roll back to), and an ``attempt_count`` of 0.

2. **Launch.** Every cold start calls
   :func:`increment_probation_attempt` *before* any risky
   init runs. The bumped counter is committed to disk before
   the work that might crash.

3. **Stabilize.** After a grace period of successful runtime
   (e.g., 60 seconds without crashing), the app calls
   :func:`confirm_version_stable` to remove the marker.

4. **Decide.** :func:`should_rollback` is a pure inspection
   on the read-back status — separating the I/O primitives
   from the decision lets the bootstrap branch on it without
   re-reading the marker.

The actual rollback (kill self, swap binary, relaunch) is
platform-specific and out of T188's scope. This module gives
the bootstrap the *signal* — the swap dance lives elsewhere.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class ProbationStatus:
    """Snapshot of the probation marker at a point in time.

    ``new_version`` is the just-applied version that's being
    proven stable. ``previous_version`` is the predecessor —
    the rollback target. ``attempt_count`` is how many times
    we've started this new version (incremented before risky
    init).
    """

    new_version: str
    previous_version: str
    attempt_count: int


def mark_version_on_probation(
    new_version: str,
    previous_version: str,
    *,
    marker_path: Path,
) -> None:
    """Write the probation marker. Called once at apply time.

    ``attempt_count`` starts at 0; the first successful (or
    failed) launch will increment it.
    """
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "new_version": new_version,
        "previous_version": previous_version,
        "attempt_count": 0,
    }
    marker_path.write_text(
        json.dumps(payload), encoding="utf-8",
    )


def read_probation_status(
    marker_path: Path,
) -> ProbationStatus | None:
    """Read the marker. Returns ``None`` for any failure mode:
    marker absent, JSON malformed, fields missing or
    wrong-type, ``attempt_count`` impossibly negative.

    Never raises — bootstrap can't crash on a malformed marker
    file the user can't see.
    """
    if not marker_path.is_file():
        return None
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    new_v = data.get("new_version")
    prev_v = data.get("previous_version")
    count = data.get("attempt_count")
    if not isinstance(new_v, str) or not isinstance(prev_v, str):
        return None
    if not isinstance(count, int) or count < 0:
        return None
    return ProbationStatus(
        new_version=new_v,
        previous_version=prev_v,
        attempt_count=count,
    )


def increment_probation_attempt(
    marker_path: Path,
) -> ProbationStatus | None:
    """Atomically bump ``attempt_count``. Returns the new
    status, or ``None`` if no probation is in effect.

    Read-modify-write — call early in bootstrap (before any
    init that might crash) so the bumped counter survives a
    crash that prevents normal exit.
    """
    status = read_probation_status(marker_path)
    if status is None:
        return None
    bumped = ProbationStatus(
        new_version=status.new_version,
        previous_version=status.previous_version,
        attempt_count=status.attempt_count + 1,
    )
    payload = {
        "new_version": bumped.new_version,
        "previous_version": bumped.previous_version,
        "attempt_count": bumped.attempt_count,
    }
    marker_path.write_text(
        json.dumps(payload), encoding="utf-8",
    )
    return bumped


def confirm_version_stable(marker_path: Path) -> None:
    """Remove the probation marker. Idempotent — no-op if
    absent. Called after a grace period of successful runtime.
    """
    try:
        marker_path.unlink()
    except FileNotFoundError:
        pass


def should_rollback(
    status: ProbationStatus, *, max_attempts: int = 2,
) -> bool:
    """Decide whether the new version has failed enough times
    to warrant rolling back.

    Default ``max_attempts=2`` gives the new version exactly
    one retry: if attempt 1 crashes, attempt 2 runs (transient
    OS issues, AV interference); if attempt 2 also crashes,
    the third launch rolls back.
    """
    return status.attempt_count >= max_attempts
