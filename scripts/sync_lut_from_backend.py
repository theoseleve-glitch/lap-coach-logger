"""Build-time script: copy backend/seed/*.json → desktop normalization/lut/.

Called from scripts/build_rc1.bat before PyInstaller so the frozen
desktop ships with the latest registry snapshot.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "backend" / "seed"
LUT_DIR = REPO_ROOT / "src" / "lap_coach_logger" / "normalization" / "lut"


def main() -> int:
    LUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    for name in ("canonical_cars.json", "canonical_tracks.json"):
        src = SEED_DIR / name
        dst = LUT_DIR / name
        if not src.exists():
            print(f"WARN: {src} not found — skipping")
            continue
        shutil.copy2(src, dst)
        copied += 1
        print(f"  {src} → {dst}")

    # Write lut_version.txt
    h = hashlib.sha256()
    for p in sorted(LUT_DIR.glob("*.json")):
        h.update(p.read_bytes())
    version = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.{h.hexdigest()[:7]}"
    version_file = LUT_DIR / "lut_version.txt"
    version_file.write_text(version, encoding="utf-8")
    print(f"  lut_version: {version}")
    print(f"Synced {copied} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
