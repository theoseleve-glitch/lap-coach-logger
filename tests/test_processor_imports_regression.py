"""Regression test: all processor classes are importable (sprint T012).

Locks the contract that every ``LiveProcessor`` implementation in
``core/`` is reachable, implements the ABC, and composes cleanly inside
the aggregated ``LiveTelemetryProcessor`` pipeline. A broken import or
renamed class here would silently break the overlay pipeline at boot.
"""
from __future__ import annotations

import importlib


_PROCESSOR_MODULES: dict[str, str] = {
    "lap_coach_logger.core.live_processor": "LiveProcessor",
    "lap_coach_logger.core.coaching_live_processor": "CoachingLiveProcessor",
    "lap_coach_logger.core.dashboard_live_processor": "DashboardLiveProcessor",
    "lap_coach_logger.core.input_diagnostics_processor": "InputDiagnosticsProcessor",
    "lap_coach_logger.core.live_telemetry_processor": "LiveTelemetryProcessor",
}


def test_every_processor_module_imports() -> None:
    for mod_name in _PROCESSOR_MODULES:
        module = importlib.import_module(mod_name)
        assert module is not None


def test_every_processor_class_is_exposed() -> None:
    for mod_name, cls_name in _PROCESSOR_MODULES.items():
        module = importlib.import_module(mod_name)
        assert hasattr(module, cls_name), (
            f"{mod_name} is missing {cls_name}"
        )


def test_concrete_processors_implement_live_processor_abc() -> None:
    from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
    from lap_coach_logger.core.dashboard_live_processor import DashboardLiveProcessor
    from lap_coach_logger.core.input_diagnostics_processor import (
        InputDiagnosticsProcessor,
    )
    from lap_coach_logger.core.live_processor import LiveProcessor

    for cls in (
        CoachingLiveProcessor,
        DashboardLiveProcessor,
        InputDiagnosticsProcessor,
    ):
        assert issubclass(cls, LiveProcessor), (
            f"{cls.__name__} does not implement LiveProcessor"
        )


def test_aggregator_composes_each_sub_processor() -> None:
    from lap_coach_logger.core.coaching_live_processor import CoachingLiveProcessor
    from lap_coach_logger.core.dashboard_live_processor import DashboardLiveProcessor
    from lap_coach_logger.core.input_diagnostics_processor import (
        InputDiagnosticsProcessor,
    )
    from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor

    agg = LiveTelemetryProcessor()
    assert isinstance(agg._coaching, CoachingLiveProcessor)  # noqa: SLF001
    assert isinstance(agg._dashboard, DashboardLiveProcessor)  # noqa: SLF001
    assert isinstance(agg._input, InputDiagnosticsProcessor)  # noqa: SLF001
