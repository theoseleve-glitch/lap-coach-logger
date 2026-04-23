"""Example overlay layout presets bundled with LAP COACH."""

from __future__ import annotations

from lap_coach_logger.overlays.layouts import OverlayLayoutTemplate
from lap_coach_logger.overlays.models import (
    OverlayAutoApplyRule,
    OverlayInstance,
    OverlayPlacement,
    OverlayPreset,
)

_ALL_SIMS = ("iRacing", "ACC", "Assetto Corsa", "Le Mans Ultimate")


def example_overlay_layout_templates() -> tuple[OverlayLayoutTemplate, ...]:
    return (
        OverlayLayoutTemplate(
            layout=OverlayPreset(
                preset_id="layout-qualifying-focus",
                name="Qualifying Focus",
                description="Delta-first layout for reference chasing and sector execution.",
                simulator_filter=_ALL_SIMS,
                session_type_filter=("qualifying",),
                tags=("qualifying", "delta", "timing"),
                auto_apply_rules=[
                    OverlayAutoApplyRule(
                        rule_id="qualifying-session",
                        name="Qualifying Session",
                        priority=200,
                        simulators=_ALL_SIMS,
                        session_types=("qualifying",),
                    )
                ],
            ),
            instances=[
                OverlayInstance(
                    instance_id="layout-qualifying-focus-session-delta",
                    overlay_id="session_delta",
                    preset_id="layout-qualifying-focus",
                    name="Session Delta",
                    placement=OverlayPlacement(x=80, y=60, width=420, height=180, monitor_id="primary"),
                    settings={"scale": 1.1},
                ),
                OverlayInstance(
                    instance_id="layout-qualifying-focus-sector-table",
                    overlay_id="sector_table",
                    preset_id="layout-qualifying-focus",
                    name="Sector Table",
                    placement=OverlayPlacement(x=520, y=60, width=320, height=170, monitor_id="primary"),
                    settings={"rows": 3},
                ),
                OverlayInstance(
                    instance_id="layout-qualifying-focus-track-map",
                    overlay_id="track_map",
                    preset_id="layout-qualifying-focus",
                    name="Track Map",
                    placement=OverlayPlacement(x=860, y=60, width=280, height=280, monitor_id="primary"),
                    settings={"show_sector_coloring": True},
                ),
            ],
        ),
        OverlayLayoutTemplate(
            layout=OverlayPreset(
                preset_id="layout-race-focus",
                name="Race Focus",
                description="Awareness, strategy, and race-control overlays for race sessions.",
                favorite=True,
                simulator_filter=("iRacing", "ACC", "Le Mans Ultimate"),
                session_type_filter=("race",),
                tags=("race", "strategy", "awareness"),
                active=True,
                auto_apply_rules=[
                    OverlayAutoApplyRule(
                        rule_id="race-session",
                        name="Race Session",
                        priority=220,
                        simulators=("iRacing", "ACC", "Le Mans Ultimate"),
                        session_types=("race",),
                    )
                ],
            ),
            instances=[
                OverlayInstance(
                    instance_id="layout-race-focus-radar",
                    overlay_id="radar_awareness",
                    preset_id="layout-race-focus",
                    name="Radar",
                    placement=OverlayPlacement(x=640, y=900, width=360, height=96, monitor_id="primary"),
                ),
                OverlayInstance(
                    instance_id="layout-race-focus-fuel",
                    overlay_id="fuel_strategy",
                    preset_id="layout-race-focus",
                    name="Fuel Strategy",
                    placement=OverlayPlacement(x=40, y=760, width=360, height=200, monitor_id="primary"),
                    settings={"compact_mode": False},
                ),
                OverlayInstance(
                    instance_id="layout-race-focus-standings",
                    overlay_id="standings",
                    preset_id="layout-race-focus",
                    name="Standings",
                    placement=OverlayPlacement(x=1510, y=80, width=360, height=260, monitor_id="primary"),
                ),
                OverlayInstance(
                    instance_id="layout-race-focus-race-control",
                    overlay_id="race_control",
                    preset_id="layout-race-focus",
                    name="Race Control",
                    placement=OverlayPlacement(x=800, y=40, width=320, height=150, monitor_id="primary"),
                ),
            ],
        ),
        OverlayLayoutTemplate(
            layout=OverlayPreset(
                preset_id="layout-telemetry-lab",
                name="Telemetry Lab",
                description="Debug-oriented layout for input analysis and setup work.",
                simulator_filter=_ALL_SIMS,
                session_type_filter=("practice", "test"),
                tags=("telemetry", "analysis", "debug"),
                auto_apply_rules=[
                    OverlayAutoApplyRule(
                        rule_id="telemetry-practice",
                        name="Telemetry Practice",
                        priority=180,
                        simulators=_ALL_SIMS,
                        session_types=("practice", "test"),
                    )
                ],
            ),
            instances=[
                OverlayInstance(
                    instance_id="layout-telemetry-lab-pedal-trace",
                    overlay_id="pedal_trace",
                    preset_id="layout-telemetry-lab",
                    name="Pedal Trace",
                    placement=OverlayPlacement(x=40, y=740, width=420, height=160, monitor_id="primary"),
                ),
                OverlayInstance(
                    instance_id="layout-telemetry-lab-input-diagnostics",
                    overlay_id="input_diagnostics",
                    preset_id="layout-telemetry-lab",
                    name="Input Diagnostics",
                    placement=OverlayPlacement(x=40, y=500, width=420, height=220, monitor_id="primary"),
                ),
                OverlayInstance(
                    instance_id="layout-telemetry-lab-track-map",
                    overlay_id="track_map",
                    preset_id="layout-telemetry-lab",
                    name="Track Map",
                    placement=OverlayPlacement(x=1510, y=80, width=280, height=280, monitor_id="primary"),
                ),
                OverlayInstance(
                    instance_id="layout-telemetry-lab-engineer-debug",
                    overlay_id="engineer_debug_panel",
                    preset_id="layout-telemetry-lab",
                    name="Engineer Debug",
                    enabled=False,
                    placement=OverlayPlacement(x=1510, y=400, width=460, height=280, monitor_id="primary"),
                ),
            ],
        ),
    )
