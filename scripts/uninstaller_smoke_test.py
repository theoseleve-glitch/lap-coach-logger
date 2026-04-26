"""T197: smoke-test the uninstaller — verify it leaves no
orphan files in the install dir.

T181 declared what gets cleaned (the ``[UninstallDelete]`` and
``[Registry] uninsdeletevalue`` directives in the .iss); T197
audits the *behavior* — runs the uninstaller silently and
reports any files that survive in the install dir.

Usage (CI / manual)::

    python scripts/uninstaller_smoke_test.py \\
        --uninstaller "C:\\\\Program Files\\\\Lap Coach Logger\\\\unins000.exe" \\
        --install-dir "C:\\\\Program Files\\\\Lap Coach Logger"

Exit 0 = clean uninstall, no orphans. Exit 1 = failure (with
the orphan list / error printed to stderr).

Same shape as T196's installer smoke runner: three injection
points (``runner``, ``sleep``, ``list_remaining_files``) keep
the orchestration logic unit-testable offline.
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


SubprocessRunner = Callable[..., Any]
SleepFn = Callable[[float], None]
ListRemaining = Callable[[Path], list[Path]]

DEFAULT_GRACE_S = 5.0
DEFAULT_UNINSTALL_TIMEOUT_S = 120.0


@dataclasses.dataclass(frozen=True)
class UninstallResult:
    """Outcome of one uninstall smoke run.

    On clean uninstall: ``success=True``, ``orphan_files=[]``,
    ``error=None``. On failure: ``success=False``, ``error``
    describes what went wrong; ``orphan_files`` populated when
    the failure was orphan files surviving (may be empty for
    non-orphan failures like a non-zero exit code).
    """

    success: bool
    error: str | None
    orphan_files: list[str]


def _default_list_remaining(install_dir: Path) -> list[Path]:
    """Walk the install dir and return any surviving files
    (recursively). Empty subdirs don't count — only actual
    files. Returns ``[]`` if the install dir was fully removed.
    """
    if not install_dir.is_dir():
        return []
    survivors: list[Path] = []
    for p in install_dir.rglob("*"):
        if p.is_file():
            survivors.append(p)
    return survivors


def run_uninstaller_smoke(
    uninstaller_path: Path,
    install_dir: Path,
    *,
    runner: SubprocessRunner = subprocess.run,
    sleep: SleepFn = time.sleep,
    list_remaining_files: ListRemaining | None = None,
    grace_s: float = DEFAULT_GRACE_S,
    timeout_s: float = DEFAULT_UNINSTALL_TIMEOUT_S,
) -> UninstallResult:
    """Run the uninstaller silently and verify no files
    remain in ``install_dir``.

    Args:
        uninstaller_path: Path to ``unins000.exe`` (or
            similar) inside the install dir.
        install_dir: Directory the app was installed into.
        runner: Injectable subprocess runner.
        sleep: Injectable sleep function.
        list_remaining_files: Injectable filesystem walker
            (defaults to a real recursive walk).
        grace_s: Seconds to wait after the uninstaller
            returns, before walking for orphans (some Inno
            cleanup happens post-exit).
        timeout_s: Hard timeout on the uninstall subprocess.

    Returns:
        :class:`UninstallResult` capturing the outcome.
    """
    walker: ListRemaining = (
        list_remaining_files
        if list_remaining_files is not None
        else _default_list_remaining
    )

    if not uninstaller_path.is_file():
        return UninstallResult(
            success=False,
            error=f"uninstaller not found: {uninstaller_path}",
            orphan_files=[],
        )

    # Silent uninstall: same flag set as the installer
    # (Inno's uninstaller honors the install-side switches).
    uninst_cmd = [
        str(uninstaller_path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
    ]
    log.info("running uninstaller: %s", " ".join(uninst_cmd))

    try:
        result = runner(
            uninst_cmd,
            timeout=timeout_s,
            capture_output=True,
        )
    except Exception as exc:
        return UninstallResult(
            success=False,
            error=f"uninstall subprocess raised: {type(exc).__name__}: {exc}",
            orphan_files=[],
        )

    if getattr(result, "returncode", 0) != 0:
        return UninstallResult(
            success=False,
            error=f"uninstaller exited non-zero: {result.returncode}",
            orphan_files=[],
        )

    # Inno may continue some cleanup after the main process
    # returns (deferred file deletes via MOVEFILE_DELAY_UNTIL_REBOOT
    # don't apply here, but sometimes the .tmp helper that
    # actually removes the install dir lingers briefly).
    sleep(grace_s)

    survivors = walker(install_dir)
    if survivors:
        return UninstallResult(
            success=False,
            error=(
                f"orphan files survived uninstall: "
                f"{len(survivors)} file(s) remain in "
                f"{install_dir}"
            ),
            orphan_files=[str(p) for p in survivors],
        )

    return UninstallResult(success=True, error=None, orphan_files=[])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the uninstaller silently and verify no files "
            "remain in the install dir."
        ),
    )
    parser.add_argument(
        "--uninstaller",
        type=Path,
        required=True,
        help="Path to the uninstaller .exe (e.g. unins000.exe)",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        required=True,
        help="Install directory to audit after uninstall",
    )
    parser.add_argument(
        "--grace-seconds",
        type=float,
        default=DEFAULT_GRACE_S,
        help=(
            f"Seconds to wait after uninstaller returns "
            f"before walking for orphans (default {DEFAULT_GRACE_S})"
        ),
    )
    return parser


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run_uninstaller_smoke(
        args.uninstaller, args.install_dir,
        grace_s=args.grace_seconds,
    )
    if result.success:
        log.info("UNINSTALL OK (no orphans)")
        return 0
    log.error("UNINSTALL FAIL: %s", result.error)
    if result.orphan_files:
        for f in result.orphan_files[:20]:
            log.error("  orphan: %s", f)
        if len(result.orphan_files) > 20:
            log.error(
                "  ... and %d more orphan files",
                len(result.orphan_files) - 20,
            )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
