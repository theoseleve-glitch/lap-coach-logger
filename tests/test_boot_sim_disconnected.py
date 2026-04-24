"""Smoke test: app boots with no sim connected (sprint T008).

Exercises the composition path ``bootstrap.run`` walks through — config
defaults, adapter building (all sim adapters disabled → no live sim),
SessionCoordinator construction, LiveTelemetryProcessor composition —
and asserts it completes without raising. Does not start the Qt event
loop or ProcessWatcher (out of scope for a unit smoke test).
"""
from __future__ import annotations

from tests.qt_mock import install

install(mock_gui=True)


def test_bootstrap_builds_no_adapters_when_all_sims_disabled() -> None:
    from lap_coach_logger.bootstrap import _build_adapters
    from lap_coach_logger.config.models import AppConfig

    config = AppConfig()
    config.iracing.enabled = False
    config.acc.enabled = False
    config.assetto_corsa.enabled = False
    config.lmu.enabled = False

    adapters = _build_adapters(config)
    assert adapters == []


def test_session_coordinator_constructs_with_no_sim() -> None:
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.core.health import HealthMonitor
    from lap_coach_logger.core.session_coordinator import SessionCoordinator

    config = AppConfig()
    health = HealthMonitor()
    # Must not raise when no adapters are attached.
    coordinator = SessionCoordinator(config, health=health)
    assert coordinator is not None


def test_live_processor_handles_empty_live_state() -> None:
    from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor

    proc = LiveTelemetryProcessor()
    # Sim disconnected → empty live + snap dict arrives from the watcher.
    result = proc.process({}, {})
    # Processor must still return the VM contract dict, not raise.
    assert isinstance(result, dict)
    assert "live_delta_s" in result
    assert "coaching_cards" in result


def test_process_watcher_accepts_empty_adapter_list() -> None:
    from lap_coach_logger.detection.process_watcher import ProcessWatcher

    # No sim adapters → watcher still constructs cleanly.
    watcher = ProcessWatcher(
        [],
        poll_interval=1.0,
        on_sim_found=lambda *_a, **_k: None,
        on_sim_lost=lambda *_a, **_k: None,
    )
    assert watcher is not None
