"""Tests for config validation, health monitor, and autostart utilities."""

import sys
from unittest.mock import patch

from lap_coach_logger.config.models import AppConfig, QualityConfig, SessionConfig, WriterConfig
from lap_coach_logger.core.lap_analysis import LapAnalysisConfig
from lap_coach_logger.core.health import HealthMonitor
from lap_coach_logger.utils import win_autostart
from lap_coach_logger.utils.win_autostart import _current_exe


# -- Config validation --

class TestConfigValidation:

    def test_default_config_valid(self) -> None:
        cfg = AppConfig()
        assert cfg.validate() == []

    def test_invalid_sample_interval(self) -> None:
        cfg = AppConfig(sample_interval_s=0)
        errors = cfg.validate()
        assert any("sample_interval_s" in e for e in errors)

    def test_invalid_sample_interval_too_high(self) -> None:
        cfg = AppConfig(sample_interval_s=20)
        errors = cfg.validate()
        assert any("sample_interval_s" in e for e in errors)

    def test_invalid_poll_interval(self) -> None:
        cfg = AppConfig(poll_interval_s=-1)
        errors = cfg.validate()
        assert any("poll_interval_s" in e for e in errors)

    def test_invalid_min_duration(self) -> None:
        cfg = AppConfig(session=SessionConfig(min_duration_s=-5))
        errors = cfg.validate()
        assert any("min_duration_s" in e for e in errors)

    def test_invalid_data_freeze(self) -> None:
        cfg = AppConfig(session=SessionConfig(data_freeze_timeout_s=0))
        errors = cfg.validate()
        assert any("data_freeze_timeout_s" in e for e in errors)

    def test_empty_output_dir(self) -> None:
        cfg = AppConfig(output_dir="")
        errors = cfg.validate()
        assert any("output_dir" in e for e in errors)

    def test_sample_rate_hz(self) -> None:
        cfg = AppConfig(sample_interval_s=0.1)
        assert cfg.sample_rate_hz == 10.0

    def test_from_dict_ignores_unknown_keys(self) -> None:
        """Old config files with extra keys should not crash."""
        data = {"output_dir": "/tmp/test", "some_future_key": True}
        cfg = AppConfig.from_dict(data)
        assert cfg.output_dir == "/tmp/test"

    def test_roundtrip_dict(self) -> None:
        cfg = AppConfig(debug=True, start_with_windows=True)
        d = cfg.to_dict()
        cfg2 = AppConfig.from_dict(d)
        assert cfg2.debug is True
        assert cfg2.start_with_windows is True

    def test_writer_debug_csv_default_false(self) -> None:
        cfg = AppConfig()
        assert cfg.writer.debug_csv_export is False

    def test_quality_config_default_valid(self) -> None:
        cfg = AppConfig(quality=QualityConfig())
        assert cfg.validate() == []

    def test_quality_speed_threshold_name_roundtrip(self) -> None:
        cfg = AppConfig(quality=QualityConfig(min_meaningful_speed_kph=12.5))
        assert cfg.to_dict()["quality"]["min_meaningful_speed_kph"] == 12.5

    def test_quality_invalid_tolerance_rejected(self) -> None:
        cfg = AppConfig(quality=QualityConfig(interval_tolerance_ratio=1.5))
        errors = cfg.validate()
        assert any("quality.interval_tolerance_ratio" in e for e in errors)

    def test_quality_warn_ratio_must_not_exceed_fail_ratio(self) -> None:
        cfg = AppConfig(
            quality=QualityConfig(
                interval_outlier_ratio_warn=0.6,
                interval_outlier_ratio_fail=0.5,
            )
        )
        errors = cfg.validate()
        assert any("interval_outlier_ratio_warn" in e for e in errors)

    def test_lap_analysis_invalid_range_rejected(self) -> None:
        cfg = AppConfig(lap_analysis=LapAnalysisConfig())
        cfg.lap_analysis.min_lap_time_s = 100.0
        cfg.lap_analysis.max_lap_time_s = 90.0
        errors = cfg.validate()
        assert any("lap_analysis.max_lap_time_s" in e for e in errors)


# -- Health monitor --

class TestHealthMonitor:

    def test_initial_state(self) -> None:
        h = HealthMonitor()
        assert h.state == "idle"

    def test_update_and_snapshot(self) -> None:
        h = HealthMonitor()
        h.update(state="recording", sim="iRacing", sample_count=100)
        snap = h.snapshot()
        assert snap.state == "recording"
        assert snap.sim == "iRacing"
        assert snap.sample_count == 100

    def test_status_line(self) -> None:
        h = HealthMonitor()
        h.update(state="recording", sim="ACC", sample_count=200)
        line = h.status_line
        assert "Recording" in line
        assert "ACC" in line
        assert "200" in line

    def test_status_line_idle(self) -> None:
        h = HealthMonitor()
        assert "Idle" in h.status_line

    def test_update_ignores_unknown(self) -> None:
        h = HealthMonitor()
        h.update(nonexistent_field="value")  # should not raise
        assert h.state == "idle"


# -- Autostart --

class TestAutostart:

    def test_current_exe_returns_sys_executable(self) -> None:
        assert _current_exe() == sys.executable

    def test_validate_autostart_noop_when_not_registered(self) -> None:
        """validate_autostart should not crash when the key doesn't exist."""
        from lap_coach_logger.utils.win_autostart import validate_autostart
        # On a dev machine the key is probably absent — should be a no-op
        validate_autostart()  # must not raise

    def test_current_autostart_command_is_quoted(self) -> None:
        cmd = win_autostart.current_autostart_command()
        assert cmd.startswith('"')
        assert cmd.endswith('"')

    @patch("lap_coach_logger.utils.win_autostart.is_autostart_enabled", return_value=False)
    @patch("lap_coach_logger.utils.win_autostart.set_autostart", return_value=True)
    @patch("lap_coach_logger.utils.win_autostart.validate_autostart")
    def test_sync_autostart_enable(self, validate_mock, set_mock, enabled_mock) -> None:
        result = win_autostart.sync_autostart(True)
        set_mock.assert_called_with(True)
        validate_mock.assert_called_once()
        assert result is False  # mocked final state

    @patch("lap_coach_logger.utils.win_autostart.is_autostart_enabled", side_effect=[True, False])
    @patch("lap_coach_logger.utils.win_autostart.set_autostart", return_value=True)
    def test_sync_autostart_disable(self, set_mock, enabled_mock) -> None:
        result = win_autostart.sync_autostart(False)
        set_mock.assert_called_with(False)
        assert result is False
