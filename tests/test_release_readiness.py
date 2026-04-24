from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from lap_coach_logger import assets
from lap_coach_logger.ui.desktop.status_text import build_status_detail


def _fake_asset_path(root: Path, relative: str) -> Path:
    return root.joinpath(*relative.split("/"))


def test_resolve_asset_uses_first_existing_candidate(tmp_path: Path) -> None:
    fallback = _fake_asset_path(tmp_path, "assets/icon.ico")
    fallback.parent.mkdir(parents=True, exist_ok=True)
    fallback.write_text("icon", encoding="utf-8")

    with patch(
        "lap_coach_logger.assets.bundle_resource_path",
        side_effect=lambda relative: _fake_asset_path(tmp_path, relative),
    ):
        resolved = assets.resolve_asset("assets/branding/app.ico", "assets/icon.ico")

    assert resolved == fallback


def test_status_detail_reports_paused_state() -> None:
    detail = build_status_detail(
        raw_state="idle",
        sim=None,
        session_state="IDLE",
        last_error=None,
        is_monitoring=False,
        latest_session={},
    )

    assert detail == "Monitoring paused. Use Resume Monitoring to continue."


def test_status_detail_surfaces_last_session_when_idle() -> None:
    detail = build_status_detail(
        raw_state="idle",
        sim=None,
        session_state="IDLE",
        last_error=None,
        is_monitoring=True,
        latest_session={"ended": "2026-03-22 10:30"},
    )

    assert detail == "Waiting for a simulator  •  Last saved session: 2026-03-22 10:30"
