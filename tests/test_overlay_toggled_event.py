"""T062: ``OverlayManagerService.set_instance_enabled`` fires the
``overlay_toggled`` PostHog event with the widget id.

The event is the analytics seam for "user shows/hides an overlay
widget". The natural callpoint is
``OverlayManagerService.set_instance_enabled(instance_id, enabled)``
which is what every UI path (tray menu, settings dialog, hotkey)
ultimately funnels through.

The ``widget_id`` property on the event is the **stable
overlay_id** (e.g. ``"session_delta"``), not the random per-user
``instance_id`` UUID. Funnels need cross-user comparability, so
emitting the instance_id would defeat the analytic.

Tests record what reaches ``analytics.track`` via monkeypatch —
no real PostHog network traffic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lap_coach_logger.overlays import (
    OverlayLayoutSlot,
    OverlayPresetScope,
    OverlayStateStore,
    build_default_overlay_manager,
)


@pytest.fixture
def track_recorder(monkeypatch: pytest.MonkeyPatch):
    """Replace ``analytics.track`` with a list-recorder for the test."""
    from lap_coach_logger import analytics

    calls: list[tuple[str, dict]] = []

    def _record(event_name: str, **properties: object) -> None:
        calls.append((event_name, properties))

    monkeypatch.setattr(analytics, "track", _record)
    return calls


def _build_service_with_one_instance(tmp_path: Path):
    """Build a service with a single ``session_delta`` instance ready
    to be toggled. Returns ``(service, instance)``."""
    service = build_default_overlay_manager(
        store=OverlayStateStore(path=tmp_path / "overlay_state.json")
    )
    preset = service.create_preset(
        name="T062",
        scope=OverlayPresetScope(sim="ACC"),
        slots=[OverlayLayoutSlot(slot_id="top_left", name="Top Left")],
    )
    service.activate_preset(preset.preset_id)
    instance = service.add_overlay_instance(
        "session_delta", preset_id=preset.preset_id, slot_id="top_left"
    )
    return service, instance


def test_enabling_an_instance_fires_overlay_toggled_with_widget_id(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    service, instance = _build_service_with_one_instance(tmp_path)
    track_recorder.clear()  # ignore any setup-time emissions

    service.set_instance_enabled(instance.instance_id, True)

    overlay_events = [c for c in track_recorder if c[0] == "overlay_toggled"]
    assert len(overlay_events) == 1
    props = overlay_events[0][1]
    assert props["widget_id"] == "session_delta"
    assert props["enabled"] is True


def test_disabling_an_instance_fires_overlay_toggled_with_enabled_false(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    service, instance = _build_service_with_one_instance(tmp_path)
    track_recorder.clear()

    service.set_instance_enabled(instance.instance_id, False)

    overlay_events = [c for c in track_recorder if c[0] == "overlay_toggled"]
    assert len(overlay_events) == 1
    assert overlay_events[0][1]["enabled"] is False
    assert overlay_events[0][1]["widget_id"] == "session_delta"


def test_overlay_toggled_uses_overlay_id_not_random_instance_id(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    """instance_id is a per-user UUID — emitting it would defeat
    cross-user funnels. Only the stable overlay_id is meaningful."""
    service, instance = _build_service_with_one_instance(tmp_path)
    track_recorder.clear()

    service.set_instance_enabled(instance.instance_id, True)

    props = next(c[1] for c in track_recorder if c[0] == "overlay_toggled")
    # Stable id present; random instance UUID is NOT.
    assert props["widget_id"] == "session_delta"
    assert "instance_id" not in props
    # Belt-and-suspenders: no property value equals the instance UUID.
    for value in props.values():
        if isinstance(value, str):
            assert value != instance.instance_id


def test_repeated_toggle_emits_one_event_per_call(
    tmp_path: Path,
    track_recorder: list[tuple[str, dict]],
) -> None:
    service, instance = _build_service_with_one_instance(tmp_path)
    track_recorder.clear()

    service.set_instance_enabled(instance.instance_id, True)
    service.set_instance_enabled(instance.instance_id, False)
    service.set_instance_enabled(instance.instance_id, True)

    overlay_events = [c for c in track_recorder if c[0] == "overlay_toggled"]
    assert [e[1]["enabled"] for e in overlay_events] == [True, False, True]


def test_overlay_toggled_is_safe_when_analytics_unconfigured(
    tmp_path: Path,
) -> None:
    """If overlays move before bootstrap has wired analytics
    (e.g. in headless tests), the emission must be a no-op rather
    than a crash."""
    from lap_coach_logger import analytics

    analytics.reset()
    service, instance = _build_service_with_one_instance(tmp_path)

    # Must not raise.
    result = service.set_instance_enabled(instance.instance_id, False)
    assert result.enabled is False
