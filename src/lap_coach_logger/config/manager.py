"""Configuration persistence – load, save (atomic), and defaults.

The canonical config file is ``config.json`` inside the app config dir.
On first run the file is created with sensible defaults.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

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
            data = json.loads(self.path.read_text(encoding="utf-8"))
            cfg = AppConfig.from_dict(data)
            log.info("Config loaded from %s", self.path)
            return cfg
        except Exception:
            log.exception("Failed to parse config – falling back to defaults")
            return AppConfig()

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
            log.info("Config saved to %s", self.path)
        except Exception:
            log.exception("Failed to save config")
            Path(tmp_path).unlink(missing_ok=True)
            raise
