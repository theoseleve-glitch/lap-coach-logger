"""Configuration persistence – load, save (atomic), and defaults.

The canonical config file is ``config.json`` inside the app config dir.
On first run the file is created with sensible defaults.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from lap_coach_logger.config.migrations import migrate_to_current
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.utils.paths import config_file_path

log = logging.getLogger(__name__)


class ConfigManager:
    """Thin wrapper around JSON config with atomic writes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_file_path()

    # ------------------------------------------------------------------
    def load(self) -> AppConfig:
        """Load config from disk, or create defaults if missing / corrupt."""
        if not self.path.exists():
            log.info("No config found – creating defaults at %s", self.path)
            cfg = AppConfig()
            self.save(cfg)
            return cfg

        try:
            # Read the raw bytes first so we can back them up
            # byte-for-byte if migration is needed (T223). Don't
            # round-trip through json.dumps for the backup — that
            # would lose the user's original formatting.
            raw_bytes = self.path.read_bytes()
            data = json.loads(raw_bytes.decode("utf-8"))
            data, did_migrate = migrate_to_current(data)
            cfg = AppConfig.from_dict(data)
            if did_migrate:
                # Back up the original BEFORE re-saving — if save()
                # crashes mid-write, the user still has the
                # untouched v1 file recoverable from the .bak.
                self._write_backup_if_absent(raw_bytes)
                log.info("Config migrated to current schema; re-saving")
                self.save(cfg)
            log.info("Config loaded from %s", self.path)
            return cfg
        except Exception:
            log.exception("Failed to parse config – falling back to defaults")
            return AppConfig()

    # ------------------------------------------------------------------
    def _backup_path(self) -> Path:
        """Path for the pre-migration backup file. Suffix-style
        (``config.json.v1.bak``) so file managers keep the
        original and backup grouped alphabetically."""
        return self.path.with_suffix(self.path.suffix + ".v1.bak")

    def _write_backup_if_absent(self, raw_bytes: bytes) -> None:
        """Write the original config bytes to the backup path.
        If a backup already exists from a prior migration, leave
        it alone — the FIRST backup is the most-original state
        and is the most valuable to preserve (T223)."""
        backup = self._backup_path()
        if backup.exists():
            log.debug("Migration backup already present at %s", backup)
            return
        try:
            backup.write_bytes(raw_bytes)
            log.info("Pre-migration config backup written to %s", backup)
        except OSError:
            # Don't block migration on a backup failure (e.g.
            # read-only fs) — log loudly but continue.
            log.exception("Failed to write pre-migration backup")

    # ------------------------------------------------------------------
    def save(self, cfg: AppConfig) -> None:
        """Atomic write: write to temp file then replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix="cfg_"
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(cfg.to_dict(), f, indent=2)
            Path(tmp_path).replace(self.path)
            # DEBUG (not INFO) because SaveScheduler coalesces routine
            # writes and we do not want burst-logging in production.
            # First-run creation still emits INFO via load().
            log.debug("Config saved to %s", self.path)
        except Exception:
            log.exception("Failed to save config")
            Path(tmp_path).unlink(missing_ok=True)
            raise
