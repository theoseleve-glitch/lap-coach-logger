"""T185: ``lap_coach_logger.updates.checker`` runs a best-effort
version check on app start.

Scope (T185 only): a function ``check_for_updates(current_version,
*, http_get, manifest_url)`` fetches a JSON manifest, compares
its ``version`` field against ``current_version`` (semver-ish
tuple compare), and returns an ``UpdateCheckResult`` capturing:

- ``current_version`` (echo)
- ``latest_version`` (from manifest, or ``None`` on error)
- ``has_update`` (bool)
- ``error`` (string, or ``None`` on success)

The function MUST never raise — slow/unreachable URLs and
malformed manifests are captured as ``error`` in the result so
the bootstrap thread can't crash the app on a network blip.

T186 (UI notification), T187 (download), T188 (apply) are
separate tasks.
"""
from __future__ import annotations

from typing import Any

import pytest


# -- Result type pin ---------------------------------------------------


def test_module_exports_public_api() -> None:
    """The module must export ``check_for_updates`` and
    ``UpdateCheckResult`` so callers don't have to reach into
    internals."""
    from lap_coach_logger.updates import checker
    assert hasattr(checker, "check_for_updates")
    assert hasattr(checker, "UpdateCheckResult")


def test_result_is_immutable_dataclass() -> None:
    """``UpdateCheckResult`` should be a frozen dataclass so
    callers can't mutate the result inflight."""
    from dataclasses import is_dataclass, FrozenInstanceError
    from lap_coach_logger.updates.checker import UpdateCheckResult

    assert is_dataclass(UpdateCheckResult)
    r = UpdateCheckResult(
        current_version="2.0.0",
        latest_version="2.0.0",
        has_update=False,
        error=None,
    )
    with pytest.raises(FrozenInstanceError):
        r.has_update = True  # type: ignore[misc]


# -- Happy paths -------------------------------------------------------


def test_has_update_when_manifest_version_is_newer() -> None:
    """If the manifest reports a version greater than current,
    ``has_update`` must be True. This is the *whole point* of
    the check."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"version": "2.1.0"}

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.has_update is True
    assert result.latest_version == "2.1.0"
    assert result.current_version == "2.0.0"
    assert result.error is None


def test_no_update_when_manifest_version_equals_current() -> None:
    """Equal versions → no update."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"version": "2.0.0"}

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.has_update is False
    assert result.latest_version == "2.0.0"
    assert result.error is None


def test_no_update_when_manifest_version_is_older() -> None:
    """Downgrade scenario: if the published manifest reports
    an OLDER version (e.g., a botched server rollback), the
    user must NOT be prompted to "update" — that would actually
    downgrade them."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"version": "1.9.0"}

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.has_update is False
    assert result.latest_version == "1.9.0"


# -- Error paths -------------------------------------------------------


def test_returns_error_when_http_get_raises() -> None:
    """Network failure (timeout, DNS, 5xx, etc.) must be
    captured as ``error`` rather than propagated. Otherwise the
    daemon thread crashes silently and we lose the diagnostic."""
    from lap_coach_logger.updates.checker import check_for_updates

    def boom(url: str, timeout_s: float) -> dict:
        raise ConnectionError("DNS failed")

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=boom,
    )
    assert result.has_update is False
    assert result.latest_version is None
    assert result.error is not None
    assert "DNS failed" in result.error


def test_returns_error_when_manifest_missing_version() -> None:
    """Malformed manifest (missing 'version' field) must be a
    captured error, not a TypeError or KeyError."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"notes": "release notes only"}

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.has_update is False
    assert result.latest_version is None
    assert result.error is not None


def test_returns_error_when_manifest_version_not_a_string() -> None:
    """A manifest like ``{"version": 2.0}`` (number, not string)
    must not crash the version compare."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"version": 2.0}  # type: ignore[dict-item]

    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.error is not None
    assert result.has_update is False


def test_check_never_raises_for_arbitrary_exceptions() -> None:
    """Any exception type from http_get must be captured —
    not just ConnectionError. We can't predict every transient
    error type."""
    from lap_coach_logger.updates.checker import check_for_updates

    class WeirdError(Exception):
        pass

    def boom(url: str, timeout_s: float) -> Any:
        raise WeirdError("transient")

    # Must not raise.
    result = check_for_updates(
        "2.0.0",
        manifest_url="https://example.invalid/manifest.json",
        http_get=boom,
    )
    assert result.error is not None


# -- Semver compare ----------------------------------------------------


@pytest.mark.parametrize(
    "current,latest,expected_has_update",
    [
        ("2.0.0", "2.0.1", True),    # patch bump
        ("2.0.0", "2.1.0", True),    # minor bump
        ("2.0.0", "3.0.0", True),    # major bump
        ("2.0.0", "10.0.0", True),   # numeric, not string compare
        ("1.9.9", "1.10.0", True),   # 10 > 9 numerically
        ("2.0.0", "2.0.0", False),   # equal
        ("2.0.0", "1.9.9", False),   # older
        ("2.0.1", "2.0.0", False),   # patch downgrade
    ],
)
def test_semver_comparison_is_numeric(
    current: str, latest: str, expected_has_update: bool,
) -> None:
    """Version compare must be numeric per-component, not
    lexicographic. Lexicographic '1.10.0' < '1.9.9' would be a
    silent downgrade prompt for users on 1.9.9."""
    from lap_coach_logger.updates.checker import check_for_updates

    def fake_get(url: str, timeout_s: float) -> dict:
        return {"version": latest}

    result = check_for_updates(
        current,
        manifest_url="https://example.invalid/manifest.json",
        http_get=fake_get,
    )
    assert result.has_update is expected_has_update, (
        f"current={current!r} latest={latest!r}: "
        f"expected has_update={expected_has_update}, "
        f"got {result.has_update}"
    )


# -- Bootstrap wiring --------------------------------------------------


def test_bootstrap_imports_update_checker() -> None:
    """Bootstrap must wire the update check so it actually
    *runs* on app start. Pin the import path — if a refactor
    drops the wiring, this fails loudly."""
    import lap_coach_logger.bootstrap as bootstrap
    src = Path = __import__("pathlib").Path
    bootstrap_src = Path(bootstrap.__file__).read_text(encoding="utf-8")
    assert "lap_coach_logger.updates" in bootstrap_src or (
        "from lap_coach_logger.updates" in bootstrap_src
    ), (
        "bootstrap.py must import from `lap_coach_logger.updates` "
        "so the update check actually runs at app start"
    )
    # And it must reference check_for_updates by name (or a
    # local alias) so the import is actually invoked.
    assert "check_for_updates" in bootstrap_src, (
        "bootstrap.py must call `check_for_updates` at startup"
    )
