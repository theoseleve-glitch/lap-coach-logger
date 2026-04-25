"""T100: Rules engine unit coverage ≥ 80%.

Pins line coverage of ``coaching/rules_engine.py`` at or above
the 80% bar. Coverage is measured by shelling out to
:command:`coverage` (already installed), running every
``test_rules_engine_*.py`` file under it, and reading back the
JSON-formatted report.

If ``coverage`` isn't available in the env (CI variants where
the tool wasn't installed), the test SKIPS rather than fails —
the threshold check shouldn't block development on an env
problem. Production CI installs ``coverage`` explicitly.

Why subprocess (not in-process Coverage API): pytest is already
running, the module under test is already imported, and starting
a fresh tracer inside a running pytest is fragile. Subprocess
runs a clean Python with coverage from start, gets accurate
import-time + runtime numbers.

This test is slow (~5 s) because it runs the entire rules-engine
test suite under instrumentation. It's worth it as a single pin
against silent coverage regressions when new code lands without
tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[1]
_RULES_ENGINE = (
    _REPO / "src" / "lap_coach_logger" / "coaching" / "rules_engine.py"
)


def _coverage_available() -> bool:
    try:
        import coverage  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(
    not _coverage_available(),
    reason="coverage package not installed in this env",
)
def test_rules_engine_line_coverage_at_or_above_80_percent(
    tmp_path: Path,
) -> None:
    """Run every ``test_rules_engine_*.py`` under coverage,
    measure line coverage of rules_engine.py, assert ≥ 80%.

    A regression below the threshold means new code landed with
    insufficient tests — fail loudly so the gap is fixed before
    review."""
    test_files = sorted(
        _REPO.glob("tests/test_rules_engine_*.py")
    )
    # Exclude this very test file from the runner — recursing
    # into our own coverage check would loop.
    test_files = [
        p for p in test_files if p.name != "test_rules_engine_coverage.py"
    ]
    assert test_files, "No rules_engine test files found"

    cov_file = tmp_path / ".coverage"
    json_file = tmp_path / "cov.json"

    env = os.environ.copy()
    env["COVERAGE_FILE"] = str(cov_file)
    # Tell pytest not to load any project-wide coverage hooks
    # (in case a future conftest adds them) — we want this
    # subprocess to be self-contained.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    subprocess.run(
        [
            sys.executable,
            "-m", "coverage",
            "run",
            "--source=lap_coach_logger.coaching.rules_engine",
            "-m", "pytest",
            "-q",
            *[str(p) for p in test_files],
        ],
        cwd=str(_REPO),
        env=env,
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m", "coverage",
            "json",
            "--include=*rules_engine.py",
            "-o", str(json_file),
        ],
        cwd=str(_REPO),
        env=env,
        check=True,
        capture_output=True,
    )

    data = json.loads(json_file.read_text(encoding="utf-8"))
    percent_covered = data["totals"]["percent_covered"]

    assert percent_covered >= 80.0, (
        f"rules_engine.py line coverage was {percent_covered:.1f}%, "
        f"below the 80% threshold. Add tests for the missing branches "
        f"rather than relaxing the threshold."
    )
