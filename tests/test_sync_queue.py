from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.writers.finalizer import SessionFinalizer


def _make_samples() -> list[TelemetrySample]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples: list[TelemetrySample] = []
    for i in range(180):
        samples.append(
            TelemetrySample(
                timestamp_utc=(start + timedelta(seconds=i)).isoformat(),
                sim="iRacing",
                session_uid="sync-test",
                session_time_s=float(i),
                lap_number=1 + (i // 30),
                lap_distance_m=float((i % 30) * 120),
                lap_dist_pct=float((i % 30) / 29),
                speed_kph=125.0,
                throttle_pct=0.7,
                brake_pct=0.0,
                steering_deg=0.0,
                gear=4,
                rpm=5300.0,
                world_pos_x=float(i),
                world_pos_y=0.0,
                world_pos_z=0.0,
                yaw_deg=0.0,
                long_accel_g=0.1,
                lat_accel_g=0.1,
                is_on_track=True,
                is_in_pits=False,
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
            )
        )
    return samples


def _finalize_bundle(tmp_path: Path) -> Path:
    finalizer = SessionFinalizer(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = finalizer.finalize(
        _make_samples(),
        started_at=now,
        ended_at=now + timedelta(seconds=179),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="sync-test",
        extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
    )
    assert result is not None
    return result


class TestSyncQueueManager:

    def test_ensure_sync_metadata_persists_required_fields(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)

        manifest = queue.ensure_sync_metadata(bundle)

        assert manifest["sync_status"] in {"not_queued", "sync_ready", "sync_blocked"}
        assert manifest["sync_attempt_count"] == 0
        assert manifest["last_sync_attempt_at"] is None
        assert manifest["last_sync_error"] is None
        assert manifest["remote_id"] is None
        assert isinstance(manifest["bundle_hash"], str)
        assert len(manifest["bundle_hash"]) == 64

    def test_queue_session_is_deduplicated_by_session_and_bundle_hash(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)

        ok1, msg1 = queue.queue_session(bundle)
        ok2, msg2 = queue.queue_session(bundle)

        assert ok1 is True
        assert msg1 in {"Queued", "Session already queued"}
        assert ok2 is True
        assert msg2 == "Session already queued"
        assert queue.queue_depth() == 1

        manifest = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
        assert manifest["sync_status"] == "queued"

    def test_process_queue_skips_when_sync_feature_disabled(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
        queue.queue_session(bundle)

        results = queue.process_queue(max_items=3)

        assert results == []
        assert queue.queue_depth() == 1
