"""JSON contract mappers for the native Qt frontend."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from lap_coach_logger.ui.desktop.overlay_browser.controller import OverlayBrowserPreviewCardModel
from lap_coach_logger.overlays.browser import OverlayBrowserPageState


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def build_shell_state(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "screenTitle": "LAP COACH",
        "status": str(snapshot.get("status") or "Idle"),
        "statusDetail": str(snapshot.get("status_detail") or "Waiting for simulator"),
        "connected": True,
        "connectionLabel": "Bridge connected",
        "monitoringActive": bool(snapshot.get("is_monitoring")),
        "simulator": str(snapshot.get("sim") or snapshot.get("detected_sim") or "-"),
        "sessionType": str((snapshot.get("live") or {}).get("session_type") or "-"),
        "liveState": str(snapshot.get("stream_status") or "ok"),
    }


def build_dashboard_state(snapshot: dict[str, object]) -> dict[str, object]:
    live = snapshot.get("live") if isinstance(snapshot.get("live"), dict) else {}
    operations = snapshot.get("operations") if isinstance(snapshot.get("operations"), dict) else {}
    live_coaching = snapshot.get("live_coaching") if isinstance(snapshot.get("live_coaching"), dict) else {}
    return {
        "metrics": [
            {"label": "Speed", "value": _speed_value(live), "tone": "neutral"},
            {"label": "Gear", "value": str(live.get("gear") or "-"), "tone": "neutral"},
            {"label": "RPM", "value": _rpm_value(live), "tone": "accent"},
            {"label": "Fuel", "value": _fuel_value(live), "tone": "neutral"},
        ],
        "operations": {
            "profile": str(operations.get("matched_profile_label") or operations.get("matched_profile") or "-"),
            "rawCapture": str(operations.get("raw_capture_status") or "-"),
            "sync": "Online" if bool(snapshot.get("sync_feature_enabled")) else "Offline",
            "sim": str(snapshot.get("sim") or "-"),
        },
        "coaching": [
            {"label": str(item.get("title") or item.get("label") or "Coaching"),
             "message": str(item.get("message") or item.get("detail") or "")}
            for item in (live_coaching.get("alerts") or live_coaching.get("items") or [])
            if isinstance(item, dict)
        ],
        "source": _plain(snapshot),
    }


def build_live_state(snapshot: dict[str, object]) -> dict[str, object]:
    live = snapshot.get("live") if isinstance(snapshot.get("live"), dict) else {}
    return {
        "metrics": [
            {"label": "Speed", "value": _speed_value(live), "tone": "neutral"},
            {"label": "Throttle", "value": _pct_value(live.get("throttle_pct")), "tone": "neutral"},
            {"label": "Brake", "value": _pct_value(live.get("brake_pct")), "tone": "neutral"},
            {"label": "Steering", "value": _deg_value(live.get("steering_deg")), "tone": "neutral"},
        ],
        "health": [
            {"label": "Stream", "value": str(snapshot.get("stream_status") or "-")},
            {"label": "Update rate", "value": f"{snapshot.get('update_hz_est') or 0} Hz"},
            {"label": "Staleness", "value": f"{snapshot.get('data_staleness_s') or 0} s"},
        ],
        "source": _plain(snapshot),
    }


def build_logs_state(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"rows": _plain(rows)}


def build_history_state(rows: list[dict[str, object]]) -> dict[str, object]:
    mapped: list[dict[str, object]] = []
    for row in rows:
        mapped.append(
            {
                "date": str(row.get("date") or row.get("started") or ""),
                "sim": str(row.get("simulator") or row.get("sim") or ""),
                "track": str(row.get("track") or ""),
                "car": str(row.get("car") or ""),
                "duration": str(row.get("duration") or ""),
                "laps": str(row.get("laps") or ""),
                "quality": str(row.get("quality") or row.get("review_status") or ""),
                "source": _plain(row),
            }
        )
    return {"rows": mapped}


def build_review_state(review: dict[str, object] | None) -> dict[str, object]:
    payload = dict(review or {})
    return {
        "title": "Session Review",
        "status": str(payload.get("status") or payload.get("review_status") or "-"),
        "summary": str(payload.get("summary") or payload.get("quality_summary") or payload.get("notes") or ""),
        "warnings": [str(item) for item in payload.get("warnings", []) if str(item).strip()],
        "source": _plain(payload),
    }


def build_overlay_state(page_state: OverlayBrowserPageState, preview: OverlayBrowserPreviewCardModel | None = None) -> dict[str, object]:
    selected = page_state.selected_overlay
    preview_payload = _plain(preview) if preview is not None else {}
    return {
        "selection": {
            "selectedCategory": page_state.selection.selected_category,
            "selectedOverlayId": page_state.selection.selected_overlay_id,
            "selectedLayoutId": page_state.selection.selected_layout_id,
        },
        "categories": [
            {
                "category": item.category,
                "label": item.label,
                "count": item.count,
                "selected": item.selected,
            }
            for item in page_state.categories
        ],
        "overlays": [
            {
                "overlayId": item.overlay_id,
                "displayName": item.display_name,
                "category": item.category,
                "favorite": item.favorite,
                "selected": item.selected,
                "installed": item.installed,
                "active": item.active,
                "locked": item.locked,
                "compatibility": " / ".join(item.supported_simulators),
                "status": item.status,
            }
            for item in page_state.overlays
        ],
        "layouts": [
            {
                "layoutId": item.layout_id,
                "displayName": item.display_name,
                "selected": item.selected,
                "active": item.active,
                "favorite": item.favorite,
            }
            for item in page_state.layouts
        ],
        "selectedOverlay": {
            "overlayId": selected.overlay_id if selected else "",
            "displayName": selected.display_name if selected else "",
            "shortDescription": selected.short_description if selected else "",
            "category": selected.category if selected else "",
            "active": selected.active if selected else False,
            "favorite": selected.favorite if selected else False,
            "installed": selected.installed if selected else False,
            "compatibility": " / ".join(selected.supported_simulators) if selected else "",
            "previewMode": str(preview_payload.get("badge") or preview_payload.get("subtitle") or "Preview"),
            "actions": [
                {
                    "actionId": action.action_id,
                    "label": action.label,
                    "enabled": action.enabled,
                    "visible": action.visible,
                    "tone": action.tone,
                }
                for action in (selected.actions if selected else ())
            ],
            "settingsSections": [
                {
                    "sectionKey": section.section_key,
                    "label": section.label,
                    "description": section.description,
                    "fields": [
                        {
                            "fieldKey": field.field_key,
                            "label": field.label,
                            "description": field.description,
                            "kind": field.kind,
                            "currentValue": _plain(field.current_value),
                            "defaultValue": _plain(field.default_value),
                            "unit": field.unit,
                            "editable": field.editable,
                            "options": [
                                {
                                    "value": option.value,
                                    "label": option.label,
                                    "description": option.description,
                                }
                                for option in field.options
                            ],
                        }
                        for field in section.fields
                    ],
                }
                for section in (selected.settings_sections if selected else ())
            ],
            "preview": preview_payload,
        },
        "source": _plain(page_state),
    }


def _speed_value(live: dict[str, object]) -> str:
    speed = live.get("speed_kph")
    return f"{round(float(speed), 1)} km/h" if isinstance(speed, (int, float)) else "-"


def _rpm_value(live: dict[str, object]) -> str:
    rpm = live.get("rpm")
    return f"{int(rpm)}" if isinstance(rpm, (int, float)) else "-"


def _fuel_value(live: dict[str, object]) -> str:
    fuel = live.get("fuel_level") or live.get("fuel_l")
    return f"{round(float(fuel), 1)} L" if isinstance(fuel, (int, float)) else "-"


def _pct_value(value: object) -> str:
    return f"{round(float(value) * 100)}%" if isinstance(value, (int, float)) else "-"


def _deg_value(value: object) -> str:
    return f"{round(float(value), 1)}°" if isinstance(value, (int, float)) else "-"
