"""Emit ``dist/LapCoachLogger/build_info.json`` describing the current build.

Runs after PyInstaller finishes. The JSON is the single source of truth
for "which commit produced this binary" — it gets bundled into every
artifact and referenced in the release checklist for rollback/triage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from lap_coach_logger.app_identity import VERSION  # noqa: E402


def _git_info() -> tuple[str, bool]:
    """Return (short SHA, is_dirty). ``("unknown", False)`` if git unavailable.

    Two calls rather than parsing ``git describe --always --dirty`` so the
    two facts never disagree under edge cases (tagged commits with
    detached HEAD etc.).
    """
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip() or "unknown"
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        ).strip())
        return sha, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown", False


def _pip_freeze_hash() -> str:
    """SHA256 (first 16 chars) of ``pip freeze`` output.

    Not a replacement for a proper lockfile, but enough for forensics:
    if two allegedly-identical builds have different hashes, their dep
    graphs drifted. Full pip-compile integration is deferred to GA.
    """
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze", "--disable-pip-version-check"],
            cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL,
        )
        return hashlib.sha256(out.encode("utf-8")).hexdigest()[:16]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rc", default="", help='RC tag e.g. "rc1"; empty for final release')
    parser.add_argument(
        "--dist",
        default=str(REPO_ROOT / "dist" / "LapCoachLogger"),
        help="PyInstaller COLLECT output directory",
    )
    args = parser.parse_args()

    dist_dir = Path(args.dist)
    if not dist_dir.exists():
        print(f"ERROR: dist dir {dist_dir} does not exist — run PyInstaller first", file=sys.stderr)
        return 1

    sha, dirty = _git_info()
    info = {
        "version": VERSION,
        "rc_tag": args.rc,
        "git_sha": sha,
        "git_dirty": dirty,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "python_implementation": platform.python_implementation(),
        "pip_freeze_sha256_16": _pip_freeze_hash(),
        "build_timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
    }

    out_path = dist_dir / "build_info.json"
    out_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    for key, value in info.items():
        print(f"  {key}: {value}")
    if info["git_dirty"]:
        print("WARNING: git working tree is dirty — build is not reproducible from HEAD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
