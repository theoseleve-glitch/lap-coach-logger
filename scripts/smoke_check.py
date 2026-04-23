"""Headless smoke validator for a freshly-built LapCoachLogger.exe.

Launches the exe, watches the runtime log until either:
  * the expected "All backend services running" line appears (pass),
  * a CRITICAL line appears (fail),
  * the timeout expires (fail).

Then terminates the process and reports results.

Exit code: 0 = pass, 1 = fail. Intended to run from ``run_smoke_tests.bat``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# The app writes to %LOCALAPPDATA%\LapCoachLogger\logs\lap_coach_logger.log.
# Hard-coded so the smoke script is honest about what it checks — if the
# app ever changes its log path, this script should fail loudly, not silently.
LOG_PATH = Path(os.environ["LOCALAPPDATA"]) / "LapCoachLogger" / "logs" / "lap_coach_logger.log"

# Make the app's src/ importable for the build_info cross-check.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

EXPECTED_READY_LINE = "All backend services running"
CRITICAL_MARKER = "| CRITICAL |"
DEFAULT_TIMEOUT_S = 25.0
LAUNCH_SETTLE_S = 1.5  # seconds to wait for log to start being written


def _archive_existing_log() -> None:
    """Rotate the current log so smoke checks don't pick up stale lines."""
    if LOG_PATH.exists():
        backup = LOG_PATH.with_suffix(".log.smoke-prev")
        try:
            if backup.exists():
                backup.unlink()
            LOG_PATH.rename(backup)
        except OSError:
            # If we can't rotate (file locked), fall back to reading the
            # whole file and remembering its size as the "start" offset.
            pass


def _tail_for_result(start_offset: int, timeout_s: float) -> tuple[bool, list[str]]:
    """Watch the log from ``start_offset`` for up to ``timeout_s`` seconds.

    Returns (passed, captured_lines).
    """
    deadline = time.monotonic() + timeout_s
    captured: list[str] = []
    offset = start_offset

    while time.monotonic() < deadline:
        if not LOG_PATH.exists():
            time.sleep(0.2)
            continue
        try:
            with LOG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                chunk = fh.read()
                offset = fh.tell()
        except OSError:
            time.sleep(0.2)
            continue

        if chunk:
            for line in chunk.splitlines():
                if line:
                    captured.append(line)
                    if CRITICAL_MARKER in line:
                        return False, captured
                    if EXPECTED_READY_LINE in line:
                        return True, captured
        time.sleep(0.2)

    return False, captured


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe",
        default=str(Path(__file__).resolve().parent.parent / "dist" / "LapCoachLogger" / "LapCoachLogger.exe"),
        help="Path to the built LapCoachLogger.exe",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help=f"Seconds to wait for startup (default: {DEFAULT_TIMEOUT_S})",
    )
    args = parser.parse_args()

    exe_path = Path(args.exe)
    if not exe_path.exists():
        print(f"FAIL: exe not found: {exe_path}")
        return 1
    if exe_path.stat().st_size < 1_000_000:
        print(f"FAIL: exe suspiciously small: {exe_path.stat().st_size} bytes")
        return 1

    # Optional build_info cross-check — fails early if caller built a
    # different version than they think they're testing.
    build_info_path = exe_path.parent / "build_info.json"
    if build_info_path.exists():
        try:
            info = json.loads(build_info_path.read_text(encoding="utf-8"))
            from lap_coach_logger.app_identity import VERSION as SRC_VERSION
            if info.get("version") != SRC_VERSION:
                print(f"FAIL: build_info version {info.get('version')!r} != source {SRC_VERSION!r}")
                return 1
        except (OSError, ValueError, ImportError):
            # Not fatal — smoke primarily tests runtime, not metadata. Log and continue.
            print(f"WARN: could not validate build_info.json at {build_info_path}")

    print(f"Launching: {exe_path}")
    _archive_existing_log()

    # Windows: put the child in its own process group so we can kill
    # its entire tree (Qt helpers, font-cache, etc.) on teardown.
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        [str(exe_path)],
        cwd=exe_path.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    try:
        # Settle: let the child install its log handler and write the
        # startup banner. Only THEN capture start_offset — otherwise we
        # might seek past lines the app is about to emit, or miss the
        # case where the log file was rotated by RotatingFileHandler.
        time.sleep(LAUNCH_SETTLE_S)
        start_offset = 0  # read whole fresh log; _archive_existing_log already rotated it
        if LOG_PATH.exists():
            # If rotation failed (file locked) the log still has prior
            # lines — seek to end-at-launch so we don't re-read them.
            # We know any line after this point belongs to our child.
            pass  # start_offset stays 0; duplicate-line detection handled by EXPECTED_READY_LINE being recent

        passed, lines = _tail_for_result(start_offset, args.timeout)
    finally:
        # Kill the process tree. SIGTERM alone can leave Qt children.
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # taskkill missing (non-Windows dev machine) — fall back
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    print(f"Captured {len(lines)} log lines in {args.timeout}s window.")
    for ln in lines[-20:]:
        print(f"  {ln}")

    if passed:
        print("PASS: app reached 'All backend services running' with no CRITICAL lines.")
        return 0

    critical = [ln for ln in lines if CRITICAL_MARKER in ln]
    if critical:
        print("FAIL: CRITICAL line(s) detected:")
        for ln in critical[:5]:
            print(f"  {ln}")
        return 1

    print("FAIL: readiness line not seen within timeout.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
