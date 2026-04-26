"""T196: smoke-test the freshly-built installer on a clean
Windows runner (CI ``windows-2019`` / ``windows-2022``) or a
release manager's clean VM.

Runs the install silently, launches the resulting app exe,
verifies it survives a grace period, then cleans up. Returns
a :class:`SmokeResult` capturing success / error.

Three injection points (``runner``, ``process_starter``,
``sleep``) keep the orchestration logic unit-testable offline.
The CLI wrapper uses real ``subprocess.run`` /
``subprocess.Popen`` / ``time.sleep``.

Usage (CI / manual)::

    python scripts/installer_smoke_test.py \\
        --installer dist/LapCoachLogger-Setup-2.0.0.exe \\
        --install-dir "C:\\\\Program Files\\\\Lap Coach Logger" \\
        --app-exe "C:\\\\Program Files\\\\Lap Coach Logger\\\\LapCoachLogger.exe"

Returns exit 0 on success, 1 on failure (machine-readable for CI).
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


# Function signatures matching subprocess.run / Popen / time.sleep
# for injection.
SubprocessRunner = Callable[..., Any]
ProcessStarter = Callable[..., Any]
SleepFn = Callable[[float], None]

DEFAULT_STARTUP_GRACE_S = 10.0
DEFAULT_INSTALL_TIMEOUT_S = 120.0


@dataclasses.dataclass(frozen=True)
class SmokeResult:
    """Outcome of one smoke run.

    On success: ``success=True``, ``launched_pid`` set,
    ``error=None``. On failure: ``success=False`` with a
    description in ``error`` and (if the launch step ran)
    ``launched_pid`` set to the PID of the process that
    crashed.
    """

    success: bool
    error: str | None
    launched_pid: int | None


def run_installer_smoke(
    installer_path: Path,
    install_dir: Path,
    app_exe: Path,
    *,
    runner: SubprocessRunner = subprocess.run,
    process_starter: ProcessStarter = subprocess.Popen,
    sleep: SleepFn = time.sleep,
    startup_grace_s: float = DEFAULT_STARTUP_GRACE_S,
    install_timeout_s: float = DEFAULT_INSTALL_TIMEOUT_S,
) -> SmokeResult:
    """Run the installer silently, launch the app, verify it
    survives ``startup_grace_s``, then terminate.

    Args:
        installer_path: Path to the built installer ``.exe``.
        install_dir: ``/DIR=`` target — where the app is
            installed.
        app_exe: Path to the launched executable inside
            ``install_dir`` (post-install).
        runner: Injectable ``subprocess.run``-shaped callable.
        process_starter: Injectable ``subprocess.Popen``-shaped
            callable.
        sleep: Injectable sleep function.
        startup_grace_s: How long to wait before checking the
            launched process is alive.
        install_timeout_s: Hard timeout on the silent install
            subprocess.

    Returns:
        :class:`SmokeResult` capturing the outcome.
    """
    if not installer_path.is_file():
        return SmokeResult(
            success=False,
            error=f"installer not found: {installer_path}",
            launched_pid=None,
        )

    # Silent install. /VERYSILENT hides all UI, /SUPPRESSMSGBOXES
    # auto-answers any error popups, /DIR= forces install dir,
    # /NORESTART avoids accidental reboots on CI runners.
    install_cmd = [
        str(installer_path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        f"/DIR={install_dir}",
    ]
    log.info("running installer: %s", " ".join(install_cmd))
    try:
        result = runner(
            install_cmd,
            timeout=install_timeout_s,
            capture_output=True,
        )
    except Exception as exc:
        return SmokeResult(
            success=False,
            error=f"install subprocess raised: {type(exc).__name__}: {exc}",
            launched_pid=None,
        )

    if getattr(result, "returncode", 0) != 0:
        return SmokeResult(
            success=False,
            error=f"installer exited non-zero: {result.returncode}",
            launched_pid=None,
        )

    # Launch the installed app. We don't capture stdout because
    # the app keeps stdout open for the GUI lifetime — capturing
    # would block.
    log.info("launching app: %s", app_exe)
    try:
        proc = process_starter([str(app_exe)])
    except Exception as exc:
        return SmokeResult(
            success=False,
            error=f"launch failed: {type(exc).__name__}: {exc}",
            launched_pid=None,
        )

    pid = getattr(proc, "pid", None)
    log.info("launched pid=%s, sleeping %.1fs grace period", pid, startup_grace_s)
    sleep(startup_grace_s)

    poll_result = proc.poll()
    if poll_result is not None:
        return SmokeResult(
            success=False,
            error=(
                f"app exited during {startup_grace_s}s grace "
                f"period with code {poll_result}"
            ),
            launched_pid=pid,
        )

    # Alive after grace period — clean smoke. Terminate so CI
    # runners don't accumulate zombies.
    try:
        proc.terminate()
        proc.wait(timeout=5.0)
    except Exception:
        log.exception("failed to terminate launched app cleanly")

    return SmokeResult(success=True, error=None, launched_pid=pid)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-test a built installer: silent install, "
            "launch app, verify it survives a grace period."
        ),
    )
    parser.add_argument(
        "--installer",
        type=Path,
        required=True,
        help="Path to the built installer .exe",
    )
    parser.add_argument(
        "--install-dir",
        type=Path,
        required=True,
        help="Target install directory (passed as /DIR= to Inno)",
    )
    parser.add_argument(
        "--app-exe",
        type=Path,
        required=True,
        help="Path to the launched app .exe inside --install-dir",
    )
    parser.add_argument(
        "--grace-seconds",
        type=float,
        default=DEFAULT_STARTUP_GRACE_S,
        help=(
            f"Seconds to wait before checking app is alive "
            f"(default {DEFAULT_STARTUP_GRACE_S})"
        ),
    )
    return parser


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run_installer_smoke(
        args.installer, args.install_dir, args.app_exe,
        startup_grace_s=args.grace_seconds,
    )
    if result.success:
        log.info("SMOKE OK (pid=%s)", result.launched_pid)
        return 0
    log.error("SMOKE FAIL: %s", result.error)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
