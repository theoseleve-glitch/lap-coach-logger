"""T214: Perf profile — app start <3s on SSD.

Sprint target: cold start time of the desktop app on a Windows
SSD must be under 3 seconds. The dominant cost is Python module
imports (Qt, pyarrow, the lap_coach_logger surface). This file
pins the import-cost budget by spawning fresh subprocesses and
timing the bootstrap-relevant imports.

Real frozen-app start adds PyInstaller bootloader overhead on
top of the import time. The CI budget here (5s) is generous
enough for slow runners while still catching imports drift —
e.g., a new top-level dependency that triples cold-start cost.

Subprocess approach is essential:
  - In-process import is cached after first call → measures 0ms.
  - Subprocess captures the real first-import cost.
  - Includes Python interpreter startup (≈ 100ms baseline on
    Windows), matching what users experience.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

# Sprint target (deployment): 3s cold start on Windows SSD.
_DEPLOYMENT_TARGET_S = 3.0

# CI budget: 5s. Headroom over the 3s target accounts for slow CI
# runners (cold disk caches, virtualised filesystems) while still
# catching > 60% imports-cost regressions.
_CI_BUDGET_S = 5.0

# Path to the lap-schemas package (sibling repo) — pytest already
# wires this into pythonpath, but subprocess tests need it explicit.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_LAP_SCHEMAS_PATH = _REPO_ROOT.parent / "lap-schemas" / "python" / "src"


def _bootstrap_env() -> dict[str, str]:
    """Build a subprocess env mirroring the production sys.path —
    src/ on the path so bootstrap modules resolve, plus the
    lap-schemas sibling package."""
    env = os.environ.copy()
    pythonpath_parts = ["src"]
    if _LAP_SCHEMAS_PATH.exists():
        pythonpath_parts.append(str(_LAP_SCHEMAS_PATH))
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    # NOTE: don't disable user site-packages here — many deps
    # (pydantic, pyarrow on dev machines) live there and we want
    # to measure real cold-start cost as the user experiences it.
    return env


def _time_subprocess(script: str, timeout_s: float = 30.0) -> float:
    """Run a Python subprocess executing ``script``, return wall-
    clock seconds elapsed (including interpreter startup)."""
    env = _bootstrap_env()
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        env=env,
        timeout=timeout_s,
        cwd=_REPO_ROOT,
    )
    elapsed = time.perf_counter() - t0
    assert result.returncode == 0, (
        f"subprocess failed (rc={result.returncode}):\n"
        f"{result.stderr.decode('utf-8', errors='replace')[:500]}"
    )
    return elapsed


# ---------------------------------------------------------------------------
# Cold-start subprocess timings
# ---------------------------------------------------------------------------


def test_python_interpreter_baseline_under_budget() -> None:
    """Sanity baseline: Python interpreter alone with no imports.
    Establishes the floor cost (≈100-300ms on Windows)."""
    elapsed = _time_subprocess("pass")
    # Must be under 1s — anything more indicates a fundamentally
    # broken Python install or env issue.
    assert elapsed < 1.0, (
        f"Python interpreter cold-start took {elapsed*1000:.0f}ms "
        f"(expected < 1000ms baseline)"
    )


def test_config_import_under_budget() -> None:
    """The bootstrap step 2 (config load) needs only the config
    package + its transitive deps. Must import quickly so config
    validation can begin within the first second of cold-start."""
    elapsed = _time_subprocess(
        "from lap_coach_logger.config.manager import ConfigManager"
    )
    # Config-only import budget: 2s on CI (typical: 300-500ms).
    assert elapsed < 2.0, (
        f"config import took {elapsed*1000:.0f}ms — bootstrap step 2 "
        f"would already be over half the 3s deployment budget"
    )


def test_adapters_import_under_budget() -> None:
    """Bootstrap step 6 (build adapters) imports all four sim
    adapters. Each pulls in its native bindings (irsdk, mmap, etc.)
    so this is the heavier import path."""
    elapsed = _time_subprocess("""
from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter
from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.assetto_corsa_adapter import AssettoCorsaAdapter
from lap_coach_logger.adapters.lmu_adapter import LMUAdapter
""")
    # All adapters import budget: 3s on CI (typical: 500-800ms).
    assert elapsed < 3.0, (
        f"adapters import took {elapsed*1000:.0f}ms — would consume "
        f"the entire 3s deployment budget on its own"
    )


def test_coordinator_import_under_budget() -> None:
    """The session coordinator pulls in writers, finalizer,
    quality gates, ghost-tracker, live coach — most of the
    runtime surface."""
    elapsed = _time_subprocess("""
from lap_coach_logger.core.session_coordinator import SessionCoordinator
""")
    assert elapsed < 3.0, (
        f"coordinator import took {elapsed*1000:.0f}ms — runtime "
        f"surface import has regressed"
    )


def test_full_bootstrap_imports_under_ci_budget() -> None:
    """The full bootstrap import path: config + adapters +
    coordinator + finalizer. This is what bootstrap.py imports at
    module level (excluding the Qt/QML shell which is launched
    in run() not at import).

    Pins the cumulative import cost — no individual import is
    allowed, plus the *combined* cost stays under the CI budget."""
    elapsed = _time_subprocess("""
from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter
from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.assetto_corsa_adapter import AssettoCorsaAdapter
from lap_coach_logger.adapters.lmu_adapter import LMUAdapter
from lap_coach_logger.core.health import HealthMonitor
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.detection.process_watcher import ProcessWatcher
from lap_coach_logger.utils.logging_setup import setup_logging
from lap_coach_logger.utils.single_instance import SingleInstance
from lap_coach_logger.writers.finalizer import SessionFinalizer
""")
    # CI budget: 5s. Sprint target: 3s.
    assert elapsed < _CI_BUDGET_S, (
        f"full bootstrap import path took {elapsed:.2f}s "
        f"(CI budget {_CI_BUDGET_S}s, deployment target "
        f"{_DEPLOYMENT_TARGET_S}s) — cold-start regression"
    )


def test_bootstrap_module_import_under_ci_budget() -> None:
    """Importing the bootstrap module itself executes all of its
    module-level imports — the canonical 'app start' cost up to
    the point where ``run()`` is called."""
    elapsed = _time_subprocess(
        "import lap_coach_logger.bootstrap"
    )
    assert elapsed < _CI_BUDGET_S, (
        f"bootstrap module import took {elapsed:.2f}s — exceeds CI "
        f"budget {_CI_BUDGET_S}s. Check for new heavyweight "
        f"top-level imports in bootstrap.py"
    )


# ---------------------------------------------------------------------------
# Drift prevention: bootstrap doesn't pull in Qt/QML at module level
# ---------------------------------------------------------------------------


def test_bootstrap_import_with_qt_still_under_ci_budget() -> None:
    """bootstrap.py currently imports ``qml_bootstrap`` at module
    level, which transitively pulls in PySide6.{QtCore, QtGui,
    QtWidgets, QtQml}. That is the bulk of cold-start cost — pin
    that even WITH Qt eager-loaded, import stays under CI budget.

    If a future refactor defers Qt to ``run_qml_shell()`` the
    budget will get more headroom; this test will keep passing."""
    elapsed = _time_subprocess("""
import lap_coach_logger.bootstrap  # noqa: F401
import sys
# Document current behavior: Qt IS eagerly loaded today.
# The budget assertion below catches regressions where
# additional heavyweight imports get added.
qt_loaded = "PySide6.QtCore" in sys.modules
print(f"qt_loaded={qt_loaded}")
""")
    assert elapsed < _CI_BUDGET_S, (
        f"bootstrap import took {elapsed:.2f}s — exceeds CI budget "
        f"{_CI_BUDGET_S}s. Qt + bootstrap should still complete "
        f"in under {_CI_BUDGET_S}s on any modern hardware."
    )


def test_config_import_does_not_pull_in_adapters() -> None:
    """Importing config alone must NOT pull in adapter modules.
    This prevents accidental coupling that would slow the
    config-only paths (e.g., CLI tools that just read config)."""
    _time_subprocess("""
import sys
from lap_coach_logger.config.manager import ConfigManager  # noqa: F401
# Config layer is cleanly isolated — adapters must not be loaded yet.
adapters_in_modules = [
    name for name in sys.modules
    if name.startswith("lap_coach_logger.adapters.")
    and not name.endswith(".base")
    and not name.endswith(".__init__")
]
assert not adapters_in_modules, (
    f"config import pulled in adapters: {adapters_in_modules} "
    "— config layer must stay isolated"
)
""")
