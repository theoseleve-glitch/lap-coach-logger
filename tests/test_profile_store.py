from __future__ import annotations

from pathlib import Path

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.profile_store import (
    apply_profile_to_config,
    build_profile,
    load_profiles,
    match_profile,
    save_profiles,
)


def test_profile_store_roundtrip_and_match(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    config = AppConfig()
    config.driver_name = "Driver One"
    profile = build_profile(
        name="ACC GT3",
        scope="car",
        config=config,
        sim="ACC",
        car="BMW M4 GT3",
        driver="Driver One",
    )

    save_profiles(path, [profile])
    loaded = load_profiles(path)
    matched = match_profile(loaded, sim="ACC", car="BMW M4 GT3", driver="Driver One")

    assert len(loaded) == 1
    assert matched is not None
    assert matched["name"] == "ACC GT3"


def test_apply_profile_to_config_updates_runtime_fields() -> None:
    config = AppConfig()
    profile = build_profile(
        name="Low resource profile",
        scope="sim",
        config=config,
        sim="iRacing",
        car=None,
        driver=None,
    )
    profile["settings"]["low_resource_mode"] = True
    profile["settings"]["overlay"]["pin_mode"] = "dashboard_on_top"
    profile["settings"]["overlay"]["refresh_rate_hz"] = 30
    profile["settings"]["iracing"]["raw_capture_enabled"] = False

    apply_profile_to_config(profile, config)

    assert config.low_resource_mode is True
    assert config.overlay.pin_mode == "dashboard_on_top"
    assert config.overlay.refresh_rate_hz == 30
    assert config.iracing.raw_capture_enabled is False
