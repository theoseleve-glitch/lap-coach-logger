"""Regression test: SessionCoordinator logging is consistent (sprint T018).

Locks the contract that ``session_coordinator.py`` uses a single
``logging.getLogger(__name__)`` instance throughout — no bare
``logging.info``/``logging.warning`` module-function calls, no
``print()`` in the runtime path, and no alternate logger names.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPO_ROOT / "src" / "lap_coach_logger" / "core" / "session_coordinator.py"
)


def _source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def test_module_logger_is_named_logger() -> None:
    from lap_coach_logger.core import session_coordinator

    assert isinstance(session_coordinator.log, logging.Logger)
    assert session_coordinator.log.name == (
        "lap_coach_logger.core.session_coordinator"
    )


def test_no_bare_logging_level_calls() -> None:
    # Bare ``logging.info(...)`` / ``logging.warning(...)`` / etc. would
    # publish through the root logger and lose the module attribution.
    banned = re.compile(
        r"\blogging\.(info|warning|error|exception|debug|critical)\s*\("
    )
    hits = banned.findall(_source())
    assert hits == [], f"bare logging level calls found: {hits}"


def test_no_print_calls_in_runtime_path() -> None:
    # Match ``print(`` with nothing but whitespace in front of it so
    # commented-out / string-embedded mentions don't trigger.
    runtime_print = re.compile(r"^\s*print\(", re.MULTILINE)
    src = _source()
    hits = runtime_print.findall(src)
    assert hits == [], "print() call found in session_coordinator runtime path"


def test_only_one_module_logger_assignment() -> None:
    pattern = re.compile(r"^log\s*=\s*logging\.getLogger", re.MULTILINE)
    matches = pattern.findall(_source())
    assert len(matches) == 1, (
        f"expected exactly one module-level ``log = logging.getLogger(...)`` "
        f"assignment, found {len(matches)}"
    )
