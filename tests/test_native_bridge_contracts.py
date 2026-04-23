from lap_coach_logger.native_bridge.contracts import (
    build_dashboard_state,
    build_history_state,
    build_live_state,
    build_overlay_state,
    build_review_state,
    build_shell_state,
)
from lap_coach_logger.overlays.browser import (
    OverlayBrowserAction,
    OverlayBrowserCategoryItem,
    OverlayBrowserEntitlementState,
    OverlayBrowserFilterState,
    OverlayBrowserLayoutItem,
    OverlayBrowserOverlayDetail,
    OverlayBrowserOverlayItem,
    OverlayBrowserPageState,
    OverlayBrowserPreviewState,
    OverlayBrowserSelectionState,
    OverlayBrowserSettingFieldView,
    OverlayBrowserSettingOption,
    OverlayBrowserSettingsSectionView,
)
from lap_coach_logger.ui.desktop.overlay_browser.controller import (
    OverlayBrowserPreviewCardModel,
    OverlayBrowserPreviewStat,
)


def test_shell_dashboard_and_live_contracts_map_core_fields() -> None:
    snapshot = {
        "status": "Recording",
        "status_detail": "ACC / Race / Lap 7",
        "is_monitoring": True,
        "sim": "ACC",
        "stream_status": "ok",
        "update_hz_est": 9.8,
        "data_staleness_s": 0.12,
        "sync_feature_enabled": True,
        "operations": {
            "matched_profile_label": "ACC GT3 / Ferrari 296",
            "raw_capture_status": "Armed",
        },
        "live": {
            "speed_kph": 214.2,
            "gear": 5,
            "rpm": 7125,
            "fuel_level": 48.6,
            "throttle_pct": 0.81,
            "brake_pct": 0.04,
            "steering_deg": -12.4,
            "session_type": "Race",
        },
        "live_coaching": {
            "alerts": [
                {"title": "Trail braking", "message": "Brake release is 6% later than reference."},
            ]
        },
    }

    shell = build_shell_state(snapshot)
    dashboard = build_dashboard_state(snapshot)
    live = build_live_state(snapshot)

    assert shell["status"] == "Recording"
    assert shell["monitoringActive"] is True
    assert dashboard["metrics"][0]["value"] == "214.2 km/h"
    assert dashboard["operations"]["profile"] == "ACC GT3 / Ferrari 296"
    assert live["health"][0]["value"] == "ok"


def test_overlay_contract_preserves_selection_actions_and_settings() -> None:
    page_state = OverlayBrowserPageState(
        filters=OverlayBrowserFilterState(),
        selection=OverlayBrowserSelectionState(
            selected_category="Awareness",
            selected_overlay_id="blind_spot",
            selected_layout_id="broadcast",
        ),
        entitlement=OverlayBrowserEntitlementState(
            premium_active=False,
            locked_overlays_visible=True,
        ),
        categories=(
            OverlayBrowserCategoryItem(category="Awareness", label="Awareness", count=5, selected=True),
        ),
        overlays=(
            OverlayBrowserOverlayItem(
                overlay_id="blind_spot",
                display_name="Blind Spot Radar",
                category="Awareness",
                tags=("traffic",),
                favorite=True,
                selected=True,
                installed=True,
                active=True,
                locked=False,
                entitled=True,
                access_state="accessible",
                access_badge="Installed",
                premium_tier="free",
                availability_status="available",
                preview_asset="",
                supported_simulators=("ACC", "LMU"),
                status="active",
            ),
        ),
        layouts=(
            OverlayBrowserLayoutItem(
                layout_id="broadcast",
                display_name="Broadcast",
                description="",
                favorite=True,
                selected=True,
                active=True,
                tags=(),
                simulator_filter=(),
                car_filter=(),
                session_type_filter=(),
            ),
        ),
        selected_overlay=OverlayBrowserOverlayDetail(
            overlay_id="blind_spot",
            display_name="Blind Spot Radar",
            short_description="Side proximity awareness for close traffic.",
            category="Awareness",
            tags=("traffic",),
            supported_simulators=("ACC", "LMU"),
            premium_tier="free",
            availability_status="available",
            favorite=True,
            entitled=True,
            locked=False,
            access_state="accessible",
            access_badge="Installed",
            lock_reason="",
            installed=True,
            active=True,
            installed_instance_ids=("inst-1",),
            selected_layout_id="broadcast",
            preview=OverlayBrowserPreviewState(
                session_id="preview-1",
                overlay_id="blind_spot",
                mode="preview",
                title="Blind Spot Preview",
            ),
            actions=(
                OverlayBrowserAction(action_id="activate", label="Activate", enabled=False),
                OverlayBrowserAction(action_id="deactivate", label="Deactivate", enabled=True),
            ),
            settings_sections=(
                OverlayBrowserSettingsSectionView(
                    section_key="placement",
                    label="Placement",
                    description="",
                    fields=(
                        OverlayBrowserSettingFieldView(
                            field_key="anchor",
                            label="Anchor",
                            description="",
                            kind="enum",
                            section_key="placement",
                            current_value="right",
                            default_value="right",
                            source="layout",
                            editable=True,
                            options=(
                                OverlayBrowserSettingOption(value="left", label="Left"),
                                OverlayBrowserSettingOption(value="right", label="Right"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    preview = OverlayBrowserPreviewCardModel(
        overlay_id="blind_spot",
        title="Blind Spot Radar",
        subtitle="Awareness",
        badge="Live layout preview",
        message="",
        asset_ref="",
        locked=False,
        active=True,
        stats=(OverlayBrowserPreviewStat(label="Sim", value="ACC"),),
    )

    payload = build_overlay_state(page_state, preview)

    assert payload["selection"]["selectedOverlayId"] == "blind_spot"
    assert payload["overlays"][0]["compatibility"] == "ACC / LMU"
    assert payload["selectedOverlay"]["actions"][1]["actionId"] == "deactivate"
    assert payload["selectedOverlay"]["settingsSections"][0]["fields"][0]["fieldKey"] == "anchor"


def test_history_and_review_contracts_preserve_rows() -> None:
    history = build_history_state(
        [
            {
                "date": "2026-04-03 15:58",
                "simulator": "ACC",
                "track": "Spa-Francorchamps",
                "car": "Ferrari 296 GT3",
                "duration": "22m",
                "laps": 14,
                "quality": "Ready",
            }
        ]
    )
    review = build_review_state(
        {
            "status": "Ready",
            "summary": "Clean session with one warning.",
            "warnings": ["Minor data freeze during pit entry"],
        }
    )

    assert history["rows"][0]["sim"] == "ACC"
    assert review["warnings"][0] == "Minor data freeze during pit entry"
