"""T188: bail-out logic — roll back the auto-applied update if
the new version crashes on startup.

The probation pattern:

1. On apply, ``mark_version_on_probation(new, previous,
   marker_path)`` writes a marker recording the new version,
   the predecessor (so we know where to roll back to), and an
   ``attempt_count`` of 0.

2. On every launch, ``increment_probation_attempt(marker_path)``
   atomically bumps the counter BEFORE any risky init runs. If
   init crashes, the bumped counter survives.

3. After a grace period of successful runtime,
   ``confirm_version_stable(marker_path)`` removes the marker.

4. On launch, after incrementing, ``should_rollback(status,
   max_attempts)`` decides whether the new version has failed
   too many times.

T188 covers the bail-out *logic* — the actual exec-replacement
dance (kill self, swap binary, relaunch) is platform-specific
and out of scope. ``should_rollback`` returning True is the
signal to the bootstrap that rollback should happen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# -- module exports ---------------------------------------------------


def test_module_exports_public_api() -> None:
    """All five primitives + the dataclass must be exposed."""
    from lap_coach_logger.updates import rollback

    assert hasattr(rollback, "ProbationStatus")
    assert hasattr(rollback, "mark_version_on_probation")
    assert hasattr(rollback, "read_probation_status")
    assert hasattr(rollback, "increment_probation_attempt")
    assert hasattr(rollback, "confirm_version_stable")
    assert hasattr(rollback, "should_rollback")


def test_probation_status_is_immutable() -> None:
    """``ProbationStatus`` should be a frozen dataclass —
    callers passing it to ``should_rollback`` shouldn't be
    able to mutate the counter mid-decision."""
    from dataclasses import is_dataclass, FrozenInstanceError
    from lap_coach_logger.updates.rollback import ProbationStatus

    assert is_dataclass(ProbationStatus)
    s = ProbationStatus(
        new_version="2.1.0",
        previous_version="2.0.0",
        attempt_count=0,
    )
    with pytest.raises(FrozenInstanceError):
        s.attempt_count = 5  # type: ignore[misc]


# -- mark + read round-trip -------------------------------------------


def test_mark_and_read_round_trip(tmp_path: Path) -> None:
    """Writing the marker at install time and reading on next
    launch must round-trip the new and previous version
    correctly. ``attempt_count`` starts at 0."""
    from lap_coach_logger.updates.rollback import (
        mark_version_on_probation, read_probation_status,
    )

    marker = tmp_path / "probation.json"
    mark_version_on_probation(
        new_version="2.1.0",
        previous_version="2.0.0",
        marker_path=marker,
    )

    status = read_probation_status(marker)
    assert status is not None
    assert status.new_version == "2.1.0"
    assert status.previous_version == "2.0.0"
    assert status.attempt_count == 0


def test_read_probation_status_returns_none_when_absent(
    tmp_path: Path,
) -> None:
    """No marker = no probation — the steady-state happy path
    on every cold launch."""
    from lap_coach_logger.updates.rollback import read_probation_status

    assert read_probation_status(tmp_path / "missing.json") is None


def test_read_probation_status_returns_none_when_malformed(
    tmp_path: Path,
) -> None:
    """A corrupt marker (bad JSON, missing fields) must be
    treated as "no probation" — never raise. The launch path
    must not crash on a malformed marker the user can't see."""
    from lap_coach_logger.updates.rollback import read_probation_status

    marker = tmp_path / "probation.json"
    marker.write_text("not valid json }}}")
    assert read_probation_status(marker) is None

    # Missing 'new_version' field.
    marker.write_text(json.dumps({
        "previous_version": "2.0.0",
        "attempt_count": 0,
    }))
    assert read_probation_status(marker) is None


def test_read_probation_status_rejects_negative_count(
    tmp_path: Path,
) -> None:
    """A negative attempt_count is impossible from honest
    code — treat as corruption."""
    from lap_coach_logger.updates.rollback import read_probation_status

    marker = tmp_path / "probation.json"
    marker.write_text(json.dumps({
        "new_version": "2.1.0",
        "previous_version": "2.0.0",
        "attempt_count": -1,
    }))
    assert read_probation_status(marker) is None


# -- increment_probation_attempt --------------------------------------


def test_increment_bumps_counter(tmp_path: Path) -> None:
    """First call: 0 → 1. Second call: 1 → 2. The bumped value
    is what ``read_probation_status`` returns afterward."""
    from lap_coach_logger.updates.rollback import (
        increment_probation_attempt, mark_version_on_probation,
        read_probation_status,
    )

    marker = tmp_path / "probation.json"
    mark_version_on_probation("2.1.0", "2.0.0", marker_path=marker)

    bumped = increment_probation_attempt(marker)
    assert bumped is not None
    assert bumped.attempt_count == 1

    bumped2 = increment_probation_attempt(marker)
    assert bumped2 is not None
    assert bumped2.attempt_count == 2

    # Persisted to disk:
    assert read_probation_status(marker).attempt_count == 2


def test_increment_returns_none_when_no_probation(
    tmp_path: Path,
) -> None:
    """No marker → nothing to increment. Return None so the
    caller can take the happy-path branch."""
    from lap_coach_logger.updates.rollback import (
        increment_probation_attempt,
    )

    assert increment_probation_attempt(tmp_path / "absent.json") is None


def test_increment_preserves_versions(tmp_path: Path) -> None:
    """The version fields must survive incrementing — the
    rollback target depends on knowing the predecessor across
    multiple failed launches."""
    from lap_coach_logger.updates.rollback import (
        increment_probation_attempt, mark_version_on_probation,
    )

    marker = tmp_path / "probation.json"
    mark_version_on_probation("2.1.0", "2.0.0", marker_path=marker)
    bumped = increment_probation_attempt(marker)
    assert bumped is not None
    assert bumped.new_version == "2.1.0"
    assert bumped.previous_version == "2.0.0"


# -- confirm_version_stable -------------------------------------------


def test_confirm_version_stable_removes_marker(
    tmp_path: Path,
) -> None:
    """After the new version has run cleanly past the grace
    period, the marker is cleared — future launches don't
    increment a counter."""
    from lap_coach_logger.updates.rollback import (
        confirm_version_stable, mark_version_on_probation,
        read_probation_status,
    )

    marker = tmp_path / "probation.json"
    mark_version_on_probation("2.1.0", "2.0.0", marker_path=marker)
    assert read_probation_status(marker) is not None

    confirm_version_stable(marker)
    assert read_probation_status(marker) is None


def test_confirm_version_stable_is_idempotent(
    tmp_path: Path,
) -> None:
    """Calling confirm when no marker exists is a no-op —
    safer for the success-path code which calls confirm
    unconditionally."""
    from lap_coach_logger.updates.rollback import confirm_version_stable

    marker = tmp_path / "absent.json"
    confirm_version_stable(marker)  # must not raise
    confirm_version_stable(marker)  # still must not raise


# -- should_rollback decision -----------------------------------------


@pytest.mark.parametrize(
    "attempt_count,max_attempts,expected",
    [
        (0, 2, False),  # never tried
        (1, 2, False),  # one failure — give it another chance
        (2, 2, True),   # at threshold — roll back
        (3, 2, True),   # past threshold — roll back
        (5, 3, True),   # higher threshold, way over
        (1, 1, True),   # stricter threshold of 1
    ],
)
def test_should_rollback_threshold(
    attempt_count: int, max_attempts: int, expected: bool,
) -> None:
    """``attempt_count >= max_attempts`` triggers rollback.
    Below the threshold, give the new version another chance
    (transient OS issue, AV interference, etc.)."""
    from lap_coach_logger.updates.rollback import (
        ProbationStatus, should_rollback,
    )

    status = ProbationStatus(
        new_version="2.1.0",
        previous_version="2.0.0",
        attempt_count=attempt_count,
    )
    assert should_rollback(status, max_attempts=max_attempts) is expected


def test_should_rollback_default_max_attempts() -> None:
    """Default ``max_attempts`` should be a reasonable
    conservative value — pin it so a future change is
    deliberate. T188 default is 2."""
    import inspect
    from lap_coach_logger.updates.rollback import should_rollback

    sig = inspect.signature(should_rollback)
    default = sig.parameters["max_attempts"].default
    assert default == 2, (
        f"should_rollback default max_attempts should be 2 "
        f"(give the new version one retry before bailing); "
        f"got {default}"
    )
