from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_review import (
    REVIEW_STATUS_IGNORED,
    load_session_review,
    reprocess_session_bundle,
    set_session_review_status,
)
from lap_coach_logger.writers.finalizer import SessionFinalizer


def _make_review_samples() -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for lap, start in ((1, 0), (2, 25), (3, 50)):
        lap_len = 25 if lap < 3 else 5
        for offset in range(lap_len):
            session_time = float(start + offset)
            samples.append(
                TelemetrySample(
                    timestamp_utc=(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=session_time)).isoformat(),
                    sim="iRacing",
                    session_uid="review-session",
                    session_time_s=session_time,
                    lap_number=lap,
                    lap_distance_m=float(offset * 120),
                    lap_dist_pct=min(0.99, offset / max(1, lap_len - 1)),
                    speed_kph=130.0 + (offset % 6),
                    throttle_pct=0.62 + ((offset % 4) * 0.03),
                    brake_pct=0.02 if offset % 7 == 0 else 0.0,
                    steering_deg=float((-3 + (offset % 7)) * 2),
                    gear=4,
                    rpm=5400.0 + (offset * 15),
                    world_pos_x=float(start + offset),
                    world_pos_y=0.0,
                    world_pos_z=float(offset),
                    yaw_deg=float(offset % 30),
                    long_accel_g=0.12,
                    lat_accel_g=0.18,
                    is_on_track=True,
                    is_in_pits=False,
                    track_name="Spa",
                    car_name="BMW M4 GT3",
                    session_type="Race",
                )
            )
    return samples


def _finalize_bundle(tmp_path: Path) -> Path:
    fin = SessionFinalizer(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = fin.finalize(
        _make_review_samples(),
        started_at=now,
        ended_at=now + timedelta(seconds=54),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="review-session",
        extra_metadata={"car": "BMW M4 GT3", "sample_rate_hz": 1.0},
    )
    assert result is not None
    return result


class TestSessionReview:

    def test_mark_ignored_updates_saved_artifacts(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)

        review = set_session_review_status(bundle, REVIEW_STATUS_IGNORED)
        assert review["review_status"] == REVIEW_STATUS_IGNORED
        assert review["session_status"] == "Ignored"
        assert review["sync_status"] == "sync_blocked"

        manifest = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
        assert manifest["review_status"] == REVIEW_STATUS_IGNORED
        assert metadata["review_status"] == REVIEW_STATUS_IGNORED
        assert manifest["review_updated_at_utc"]
        assert metadata["review_updated_at_utc"]

    def test_reprocess_bundle_rebuilds_review_data_from_saved_telemetry(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        set_session_review_status(bundle, REVIEW_STATUS_IGNORED)

        review = reprocess_session_bundle(bundle, config=AppConfig())
        assert review["review_status"] == REVIEW_STATUS_IGNORED
        assert review["sync_status"] in {"sync_blocked", "sync_failed", "queued", "synced"}
        assert review["total_laps"] == 3
        assert review["valid_laps"] >= 1
        assert review["clean_laps"] >= 1
        assert isinstance(review["best_lap_time_s"], float)

        laps = json.loads((bundle / "laps.json").read_text(encoding="utf-8"))
        quality = json.loads((bundle / "quality_report.json").read_text(encoding="utf-8"))
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))

        assert len(laps) == 3
        assert metadata["total_laps"] == 3
        assert metadata["quality_classification"] == quality["recommended_classification"]
        assert metadata["review_status"] == REVIEW_STATUS_IGNORED

    def test_load_session_review_reads_saved_bundle_artifacts(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)

        review = load_session_review(bundle)
        assert review["simulator"] == "iRacing"
        assert review["track"] == "Spa"
        assert review["car"] == "BMW M4 GT3"
        assert review["session_type"] == "Race"
        assert review["local_folder_path"] == str(bundle)
        assert review["sync_status"] in {"not_queued", "sync_ready", "sync_blocked", "queued", "synced", "sync_failed"}
        assert isinstance(review["bundle_hash"], str)