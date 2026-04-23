"""Local sim/car/driver profile storage for lap_pc operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from lap_coach_logger.config.models import AppConfig


def load_profiles(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    profiles: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            profiles.append(dict(item))
    return profiles


def save_profiles(path: Path, profiles: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def build_profile(
    *,
    name: str,
    scope: str,
    config: AppConfig,
    sim: str | None = None,
    car: str | None = None,
    driver: str | None = None,
) -> dict[str, Any]:
    scope = scope if scope in {"sim", "car", "driver"} else "sim"
    return {
        "id": uuid4().hex,
        "name": name.strip() or _default_profile_name(scope=scope, sim=sim, car=car, driver=driver),
        "scope": scope,
        "match": {
            "sim": sim or "",
            "car": car or "",
            "driver": driver or "",
        },
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "settings": _settings_from_config(config),
    }


def apply_profile_to_config(profile: dict[str, Any], config: AppConfig) -> None:
    settings = dict(profile.get("settings") or {})
    config.driver_name = str(settings.get("driver_name") or config.driver_name).strip()
    config.poll_interval_s = float(settings.get("poll_interval_s") or config.poll_interval_s)
    config.sample_interval_s = float(settings.get("sample_interval_s") or config.sample_interval_s)
    config.start_with_windows = bool(settings.get("start_with_windows", config.start_with_windows))
    config.low_resource_mode = bool(settings.get("low_resource_mode", config.low_resource_mode))
    overlay = dict(settings.get("overlay") or {})
    config.overlay.enabled = bool(overlay.get("enabled", config.overlay.enabled))
    config.overlay.refresh_rate_hz = int(overlay.get("refresh_rate_hz", config.overlay.refresh_rate_hz))
    config.overlay.opacity = float(overlay.get("opacity", config.overlay.opacity))
    config.overlay.pin_mode = str(overlay.get("pin_mode") or config.overlay.pin_mode)
    writer = dict(settings.get("writer") or {})
    config.writer.debug_csv_export = bool(writer.get("debug_csv_export", config.writer.debug_csv_export))
    _apply_sim_settings(config, "iracing", dict(settings.get("iracing") or {}))
    _apply_sim_settings(config, "assetto_corsa", dict(settings.get("assetto_corsa") or {}))
    _apply_sim_settings(config, "acc", dict(settings.get("acc") or {}))
    _apply_sim_settings(config, "lmu", dict(settings.get("lmu") or {}))


def match_profile(
    profiles: list[dict[str, Any]],
    *,
    sim: str | None,
    car: str | None,
    driver: str | None,
) -> dict[str, Any] | None:
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    current_sim = (sim or "").strip().lower()
    current_car = (car or "").strip().lower()
    current_driver = (driver or "").strip().lower()
    for profile in profiles:
        match = dict(profile.get("match") or {})
        scope = str(profile.get("scope") or "sim")
        profile_sim = str(match.get("sim") or "").strip().lower()
        profile_car = str(match.get("car") or "").strip().lower()
        profile_driver = str(match.get("driver") or "").strip().lower()
        if profile_sim and profile_sim != current_sim:
            continue
        if scope == "car" and profile_car and profile_car != current_car:
            continue
        if scope == "driver" and profile_driver and profile_driver != current_driver:
            continue
        specificity = {"sim": 1, "driver": 2, "car": 3}.get(scope, 0)
        candidates.append((specificity, str(profile.get("saved_at_utc") or ""), profile))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def profile_label(profile: dict[str, Any]) -> str:
    match = dict(profile.get("match") or {})
    scope = str(profile.get("scope") or "sim")
    name = str(profile.get("name") or "Profile")
    sim = str(match.get("sim") or "").strip()
    car = str(match.get("car") or "").strip()
    driver = str(match.get("driver") or "").strip()
    scope_label = scope.upper()
    context = sim or "-"
    if scope == "car" and car:
        context = f"{sim or '-'} / {car}"
    elif scope == "driver" and driver:
        context = f"{sim or '-'} / {driver}"
    return f"{name} [{scope_label}]  {context}"


def _settings_from_config(config: AppConfig) -> dict[str, Any]:
    return {
        "driver_name": config.driver_name,
        "poll_interval_s": config.poll_interval_s,
        "sample_interval_s": config.sample_interval_s,
        "start_with_windows": config.start_with_windows,
        "low_resource_mode": config.low_resource_mode,
        "overlay": {
            "enabled": config.overlay.enabled,
            "refresh_rate_hz": config.overlay.refresh_rate_hz,
            "opacity": config.overlay.opacity,
            "pin_mode": config.overlay.pin_mode,
        },
        "writer": {
            "debug_csv_export": config.writer.debug_csv_export,
        },
        "iracing": {
            "enabled": config.iracing.enabled,
            "sample_mode": config.iracing.sample_mode,
            "raw_capture_enabled": config.iracing.raw_capture_enabled,
        },
        "assetto_corsa": {
            "enabled": config.assetto_corsa.enabled,
            "raw_capture_enabled": config.assetto_corsa.raw_capture_enabled,
        },
        "acc": {
            "enabled": config.acc.enabled,
            "raw_capture_enabled": config.acc.raw_capture_enabled,
        },
        "lmu": {
            "enabled": config.lmu.enabled,
            "raw_capture_enabled": config.lmu.raw_capture_enabled,
        },
    }


def _apply_sim_settings(config: AppConfig, name: str, settings: dict[str, Any]) -> None:
    sim_cfg = getattr(config, name)
    if "enabled" in settings:
        sim_cfg.enabled = bool(settings["enabled"])
    if "raw_capture_enabled" in settings:
        sim_cfg.raw_capture_enabled = bool(settings["raw_capture_enabled"])
    if name == "iracing" and "sample_mode" in settings:
        sim_cfg.sample_mode = str(settings["sample_mode"])


def _default_profile_name(
    *,
    scope: str,
    sim: str | None,
    car: str | None,
    driver: str | None,
) -> str:
    if scope == "car" and car:
        return f"{car} setup"
    if scope == "driver" and driver:
        return f"{driver} profile"
    if sim:
        return f"{sim} profile"
    return "Lap PC profile"
