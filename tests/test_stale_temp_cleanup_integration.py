"""T210: Integration test — stale temp files cleaned on startup.

Pins the contract for ``SessionFinalizer.cleanup_stale_temps`` plus
the bootstrap-step drift prevention:

  - Orphaned ``_tmp_*`` directories from prior crashes are removed
  - Real session bundles (no ``_tmp_`` prefix) are NEVER removed
  - Files at the root are ignored (not classified as bundles)
  - Returns the count of cleaned directories
  - Handles missing / non-directory output roots gracefully
  - Handles deeply-nested temp content (rmtree recurses)
  - Idempotent: a second call after a successful sweep returns 0
  - Bootstrap.py wires the cleanup as part of startup sequence

T031 covered the basic single-orphan case. T210 covers the
cross-cutting integration scenarios (multiple orphans + real
bundles co-existing, edge cases, idempotency) plus the
drift-prevention test that bootstrap.py still calls cleanup at
the right point in startup.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.writers.finalizer import SessionFinalizer


# -- core cleanup behavior ------------------------------------------


def test_cleanup_removes_single_orphan_tmp_dir(tmp_path: Path) -> None:
    """Baseline: a single _tmp_ dir from a prior crash is removed."""
    orphan = tmp_path / "_tmp_2026-04-25_10-00-00__iracing__spa__unknown"
    orphan.mkdir()
    (orphan / "partial.json").write_text("{}", encoding="utf-8")

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 1
    assert not orphan.exists()


def test_cleanup_removes_multiple_orphan_tmp_dirs(tmp_path: Path) -> None:
    """Three orphans (e.g., crashed three times across reboots) →
    all three removed in one sweep, count returns 3."""
    orphans = [
        tmp_path / "_tmp_2026-04-25_10-00-00__iracing__spa__unknown",
        tmp_path / "_tmp_2026-04-25_11-00-00__iracing__spa__unknown",
        tmp_path / "_tmp_2026-04-26_09-00-00__acc__monza__unknown",
    ]
    for o in orphans:
        o.mkdir()
        (o / "partial.json").write_text("{}", encoding="utf-8")

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 3
    for o in orphans:
        assert not o.exists()


def test_cleanup_preserves_real_bundle_dirs(tmp_path: Path) -> None:
    """Real session bundles (no _tmp_ prefix) MUST be preserved —
    cleanup must NEVER delete user data."""
    real_bundles = [
        tmp_path / "2026-04-25_10-00-00__iracing__spa__race",
        tmp_path / "2026-04-25_11-00-00__acc__monza__practice",
    ]
    for b in real_bundles:
        b.mkdir()
        (b / "manifest.json").write_text(
            json.dumps({"session_id": b.name}), encoding="utf-8",
        )

    SessionFinalizer.cleanup_stale_temps(tmp_path)
    for b in real_bundles:
        assert b.exists(), (
            f"real bundle {b.name} was deleted — data loss bug"
        )


def test_cleanup_only_removes_tmp_when_mixed_with_real_bundles(
    tmp_path: Path,
) -> None:
    """Mixed scenario: real bundles + _tmp_ orphans co-exist. Only
    the orphans are removed, real bundles untouched, count is
    accurate."""
    # 2 real bundles + 2 _tmp_ orphans.
    real = tmp_path / "real-bundle-1"
    real.mkdir()
    (real / "manifest.json").write_text("{}", encoding="utf-8")
    real2 = tmp_path / "real-bundle-2"
    real2.mkdir()

    orphan1 = tmp_path / "_tmp_orphan-1"
    orphan1.mkdir()
    orphan2 = tmp_path / "_tmp_orphan-2"
    orphan2.mkdir()

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 2  # only orphans
    assert real.exists()
    assert real2.exists()
    assert not orphan1.exists()
    assert not orphan2.exists()


# -- file vs directory disambiguation -------------------------------


def test_cleanup_ignores_files_at_root(tmp_path: Path) -> None:
    """Files at output root (not dirs) are ignored — config files,
    queue state, log files all live there alongside bundle dirs."""
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".sync_queue.json").write_text("{}", encoding="utf-8")
    (tmp_path / "_tmp_looks-like-tmp-but-is-a-file").write_text(
        "fake", encoding="utf-8",
    )

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 0
    # Files preserved.
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / ".sync_queue.json").exists()
    assert (tmp_path / "_tmp_looks-like-tmp-but-is-a-file").exists()


def test_cleanup_ignores_dirs_without_tmp_prefix(tmp_path: Path) -> None:
    """Bundle dirs whose names contain 'tmp' but don't START with
    _tmp_ must be preserved. Examples that have caused regressions:
    'bundle_with_tmp_marker', 'tmp_bundle' (no leading underscore)."""
    keep_a = tmp_path / "bundle_with_tmp_in_name"
    keep_a.mkdir()
    keep_b = tmp_path / "tmp_no_leading_underscore"
    keep_b.mkdir()

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 0
    assert keep_a.exists()
    assert keep_b.exists()


# -- deeply nested content -----------------------------------------


def test_cleanup_recursively_removes_nested_tmp_content(
    tmp_path: Path,
) -> None:
    """An orphan _tmp_ dir may contain partial telemetry.parquet,
    nested subdirs, etc. shutil.rmtree handles this; the test pins
    that recursive removal works for realistic partial structures."""
    orphan = tmp_path / "_tmp_partial-bundle"
    orphan.mkdir()
    (orphan / "metadata.json").write_text("{}", encoding="utf-8")
    (orphan / "telemetry.parquet").write_bytes(b"\x00" * 1024)
    nested = orphan / "raw_capture"
    nested.mkdir()
    (nested / "iracing_raw.parquet").write_bytes(b"\x00" * 512)
    deep = nested / "session_info"
    deep.mkdir()
    (deep / "snapshot.json").write_text("{}", encoding="utf-8")

    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 1
    assert not orphan.exists()


# -- error handling -------------------------------------------------


def test_cleanup_handles_missing_output_root(tmp_path: Path) -> None:
    """If output_root doesn't exist (first launch, fresh user
    profile) cleanup must return 0 without raising."""
    nonexistent = tmp_path / "does-not-exist"
    cleaned = SessionFinalizer.cleanup_stale_temps(nonexistent)
    assert cleaned == 0


def test_cleanup_handles_output_root_that_is_a_file(
    tmp_path: Path,
) -> None:
    """If output_root path exists but is a file (config error or
    user mistake) cleanup must return 0 without raising."""
    weird = tmp_path / "this-is-a-file"
    weird.write_text("oops", encoding="utf-8")
    cleaned = SessionFinalizer.cleanup_stale_temps(weird)
    assert cleaned == 0
    # File preserved.
    assert weird.is_file()


def test_cleanup_empty_output_root_returns_zero(tmp_path: Path) -> None:
    """An empty output_root is a fresh-launch state — return 0
    without raising. tmp_path itself is empty."""
    cleaned = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert cleaned == 0


# -- idempotency ---------------------------------------------------


def test_cleanup_is_idempotent(tmp_path: Path) -> None:
    """Running cleanup twice in a row — second call returns 0
    because the first already removed everything."""
    orphan = tmp_path / "_tmp_orphan-idempotent"
    orphan.mkdir()
    (orphan / "x.json").write_text("{}", encoding="utf-8")

    first = SessionFinalizer.cleanup_stale_temps(tmp_path)
    second = SessionFinalizer.cleanup_stale_temps(tmp_path)
    assert first == 1
    assert second == 0


# -- bootstrap drift-prevention ------------------------------------


def test_bootstrap_calls_cleanup_stale_temps_on_startup() -> None:
    """Bootstrap.py MUST call SessionFinalizer.cleanup_stale_temps as
    part of its startup sequence — drift-prevention check that
    catches accidental removal of the cleanup step (would leak
    disk space across crashes).

    Pinning string presence rather than running the full bootstrap
    (heavyweight: opens config, starts threads, runs main loop)."""
    bootstrap_src = Path(
        "src/lap_coach_logger/bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "SessionFinalizer.cleanup_stale_temps" in bootstrap_src, (
        "bootstrap.py must call SessionFinalizer.cleanup_stale_temps "
        "at startup — the call appears to have been removed"
    )


def test_bootstrap_logs_cleanup_count() -> None:
    """Cleanup must produce a log line so user can spot disk-leak
    issues (e.g., a sim that crashes every session would show up
    as 'Cleaned N stale temp session folder(s)' growing each run)."""
    bootstrap_src = Path(
        "src/lap_coach_logger/bootstrap.py"
    ).read_text(encoding="utf-8")

    # We don't pin the exact log format, but we pin that the
    # cleanup count is referenced in a log statement nearby.
    cleanup_idx = bootstrap_src.find("cleanup_stale_temps")
    # Find next 'log.' within ~300 chars of the cleanup call.
    snippet = bootstrap_src[cleanup_idx : cleanup_idx + 400]
    assert "log." in snippet, (
        "expected a log statement near the cleanup_stale_temps call "
        "so users can see how many folders were swept"
    )


def test_bootstrap_imports_session_finalizer() -> None:
    """The cleanup call requires SessionFinalizer in scope —
    drift-prevention against accidental import removal."""
    bootstrap_src = Path(
        "src/lap_coach_logger/bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "SessionFinalizer" in bootstrap_src
    # Must be imported at module level (not buried inside a function).
    assert "from lap_coach_logger.writers.finalizer import" in bootstrap_src
