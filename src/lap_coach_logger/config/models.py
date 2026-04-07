"""Typed configuration models.

Plain dataclasses — no heavy validation library required.  Serialised
to / from JSON via the ConfigManager.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

from lap_coach_logger.core.lap_analysis import LapAnalysisConfig
from lap_coach_logger.utils.paths import default_output_dir


@dataclass
class SimConfig:
    """Per-sim toggle and connection hints."""
    enabled: bool = True


@dataclass
class IRacingConfig(SimConfig):
    """iRacing-specific settings."""
    # Sampling mode: "auto_sdk" follows the SDK tick rate; "manual" uses sample_interval_s
    sample_mode: str = "auto_sdk"
    # Write the full raw IRSDK telemetry alongside the normalized output
    raw_capture_enabled: bool = True
    # Paths to recovered catalog files (bundled as reference metadata)
    catalog_live_var_schema: str = ""
    catalog_session_leaf_paths: str = ""
    catalog_localserver_track_fields: str = ""
    catalog_localserver_arq_messages: str = ""
    catalog_sim_param_names: str = ""


@dataclass
class SessionConfig:
    """Thresholds that guard session lifecycle transitions."""
    # Minimum number of samples before a session is worth saving
    min_samples_to_save: int = 50
    # Minimum session duration (seconds) before saving
    min_duration_s: float = 10.0
    # How long to wait (seconds) after telemetry goes stale before ending
    stale_timeout_s: float = 8.0
    # Cooldown (seconds) after finalizing before allowing a new session
    cooldown_after_finalize_s: float = 3.0
    # Maximum data-freeze time (seconds) – if all channels are frozen we
    # consider telemetry disconnected
    data_freeze_timeout_s: float = 5.0


@dataclass
class WriterConfig:
    """Tuning knobs for the session writer pipeline."""
    parquet_row_group_size: int = 10_000
    parquet_compression: str = "snappy"
    csv_fallback_enabled: bool = True
    # When True, always write a CSV alongside parquet for debugging
    debug_csv_export: bool = False


@dataclass
class QualityConfig:
    """Thresholds used by post-session data-quality validation."""
    min_samples: int = 100
    min_duration_s: float = 20.0
    max_time_gap_s: float = 1.5
    essential_missing_ratio_warn: float = 0.05
    essential_missing_ratio_fail: float = 0.20
    min_meaningful_speed_kph: float = 25.0
    flatline_speed_std_kph: float = 1.0
    flatline_control_std: float = 0.01
    min_gear: int = -1
    max_gear: int = 10
    interval_tolerance_ratio: float = 0.35
    interval_outlier_ratio_warn: float = 0.10
    interval_outlier_ratio_fail: float = 0.25


@dataclass
class OverlayWidgetConfig:
    """Per-widget overlay settings persisted to disk."""
    enabled: bool = False
    x: int = 100
    y: int = 80
    width: int = 300
    height: int = 200
    opacity: float = 0.92
    font_scale: float = 1.0
    refresh_hz: int = 60
    border_radius: int = 12


@dataclass
class OverlayConfig:
    """Overlay HUD settings."""
    widget_settings: dict[str, dict] = field(default_factory=dict)


@dataclass
class SyncConfig:
    """Remote sync settings for Lap Coach webapp."""
    enabled: bool = False
    api_url: str = "https://api.lap-coach.racing"
    device_token: str = ""
    device_name: str = ""


@dataclass
class AppConfig:
    """Top-level application configuration."""
    output_dir: str = field(default_factory=lambda: str(default_output_dir()))
    poll_interval_s: float = 1.0
    sample_interval_s: float = 0.1
    session_end_grace_s: float = 5.0
    debug: bool = False
    start_with_windows: bool = False
    driver_name: str = ""
    iracing: IRacingConfig = field(default_factory=IRacingConfig)
    acc: SimConfig = field(default_factory=SimConfig)
    writer: WriterConfig = field(default_factory=WriterConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    lap_analysis: LapAnalysisConfig = field(default_factory=LapAnalysisConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)

    # --- helpers -----------------------------------------------------------

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def sample_rate_hz(self) -> float:
        return round(1.0 / self.sample_interval_s, 2) if self.sample_interval_s > 0 else 0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Construct from a (possibly partial) dict, applying defaults."""
        iracing = IRacingConfig(**data.pop("iracing", {}))
        acc = SimConfig(**data.pop("acc", {}))
        writer = WriterConfig(**data.pop("writer", {}))
        session = SessionConfig(**data.pop("session", {}))
        quality = QualityConfig(**data.pop("quality", {}))
        lap_analysis = LapAnalysisConfig(**data.pop("lap_analysis", {}))
        sync = SyncConfig(**data.pop("sync", {}))
        overlay = OverlayConfig(**data.pop("overlay", {}))
        # Strip unknown keys that might exist in old config files
        known = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(
            iracing=iracing,
            acc=acc,
            writer=writer,
            session=session,
            quality=quality,
            lap_analysis=lap_analysis,
            sync=sync,
            overlay=overlay,
            **filtered,
        )

    def validate(self) -> list[str]:
        """Return a list of validation error strings (empty = ok)."""
        errors: list[str] = []
        if self.sample_interval_s <= 0:
            errors.append("sample_interval_s must be > 0")
        if self.sample_interval_s > 10:
            errors.append("sample_interval_s must be <= 10")
        if self.iracing.sample_mode not in ("auto_sdk", "manual"):
            errors.append("iracing.sample_mode must be 'auto_sdk' or 'manual'")
        if self.poll_interval_s <= 0:
            errors.append("poll_interval_s must be > 0")
        if self.session_end_grace_s < 0:
            errors.append("session_end_grace_s must be >= 0")
        if self.session.min_samples_to_save < 0:
            errors.append("min_samples_to_save must be >= 0")
        if self.session.min_duration_s < 0:
            errors.append("min_duration_s must be >= 0")
        if self.session.data_freeze_timeout_s <= 0:
            errors.append("data_freeze_timeout_s must be > 0")
        if self.session.cooldown_after_finalize_s < 0:
            errors.append("cooldown_after_finalize_s must be >= 0")
        if self.quality.min_samples < 1:
            errors.append("quality.min_samples must be >= 1")
        if self.quality.min_duration_s < 0:
            errors.append("quality.min_duration_s must be >= 0")
        if self.quality.max_time_gap_s <= 0:
            errors.append("quality.max_time_gap_s must be > 0")
        if not (0 <= self.quality.interval_tolerance_ratio <= 1):
            errors.append("quality.interval_tolerance_ratio must be between 0 and 1")
        if not (0 <= self.quality.interval_outlier_ratio_warn <= 1):
            errors.append("quality.interval_outlier_ratio_warn must be between 0 and 1")
        if not (0 <= self.quality.interval_outlier_ratio_fail <= 1):
            errors.append("quality.interval_outlier_ratio_fail must be between 0 and 1")
        if self.quality.interval_outlier_ratio_warn > self.quality.interval_outlier_ratio_fail:
            errors.append("quality.interval_outlier_ratio_warn must be <= interval_outlier_ratio_fail")
        if self.lap_analysis.min_samples_per_lap < 1:
            errors.append("lap_analysis.min_samples_per_lap must be >= 1")
        if not (0 <= self.lap_analysis.min_complete_ratio <= 1):
            errors.append("lap_analysis.min_complete_ratio must be between 0 and 1")
        if self.lap_analysis.min_lap_time_s < 0:
            errors.append("lap_analysis.min_lap_time_s must be >= 0")
        if self.lap_analysis.max_lap_time_s <= self.lap_analysis.min_lap_time_s:
            errors.append("lap_analysis.max_lap_time_s must be > min_lap_time_s")
        if not self.output_dir:
            errors.append("output_dir must not be empty")
        return errors
