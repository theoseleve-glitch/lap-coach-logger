from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_review import load_history_entry
from lap_coach_logger.ui.desktop.session_index import SessionIndex
from lap_coach_logger.writers.finalizer import SessionFinalizer


def _make_samples(count: int = 40) -> list[TelemetrySample]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples: list[TelemetrySample] = []
    for i in range(count):
        lap = 1 + (i // 20)
        lap_idx = i % 20
        samples.append(
            TelemetrySample(
                timestamp_utc=(start + timedelta(seconds=i)).isoformat(),
                sim="iRacing",
                session_uid=f"s-{count}",
                session_time_s=float(i),
                lap_number=lap,
                lap_distance_m=float(lap_idx * 100),
                lap_dist_pct=float(lap_idx / 19),
                speed_kph=120.0 + (i % 3),
                throttle_pct=0.7,
                brake_pct=0.0,
                steering_deg=0.0,
                gear=4,
                rpm=5200.0,
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


def _finalize_bundle(root: Path, *, session_uid: str) -> Path:
    fin = SessionFinalizer(root)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = fin.finalize(
        _make_samples(),
        started_at=now,
        ended_at=now + timedelta(seconds=39),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid=session_uid,
        extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
    )
    assert result is not None
    return result


class TestSessionIndexSqlite:

    def test_rebuild_and_incremental_sync(self, tmp_path: Path) -> None:
        output_root = tmp_path / "sessions"
        output_root.mkdir(parents=True, exist_ok=True)
        _finalize_bundle(output_root, session_uid="uid-1")
        _finalize_bundle(output_root, session_uid="uid-2")

        # Partial folder should be ignored safely
        partial = output_root / "_tmp_partial_bundle"
        partial.mkdir(parents=True, exist_ok=True)

        idx = SessionIndex(tmp_path / "index")
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
            max_dirs=150,
        )

        assert len(entries) == 2
        first = entries[0]
        assert first["session_id"]
        assert first["folder"]
        assert "created_at" in first
        assert "sim" in first
        assert "track" in first
        assert "car" in first
        assert "session_type" in first
        assert "duration_s" in first
        assert "total_laps" in first
        assert "clean_laps" in first
        assert "best_lap" in first
        assert "quality" in first
        assert "sync_status" in first
        assert "bundle_hash" in first
        assert "schema_version" in first

        # Second sync should reuse index and produce same count
        entries_second = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
            max_dirs=150,
        )
        assert len(entries_second) == 2

    def test_corruption_recovery_rebuilds_index(self, tmp_path: Path) -> None:
        output_root = tmp_path / "sessions"
        output_root.mkdir(parents=True, exist_ok=True)
        _finalize_bundle(output_root, session_uid="uid-corrupt")

        index_dir = tmp_path / "index"
        index_dir.mkdir(parents=True, exist_ok=True)
        db_path = index_dir / "session_index.sqlite3"
        db_path.write_text("this is not sqlite", encoding="utf-8")

        idx = SessionIndex(index_dir)
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
            max_dirs=150,
        )

        assert len(entries) == 1
        # Ensure recreated DB is valid SQLite
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM sessions")
            assert cur.fetchone()[0] == 1
        finally:
            conn.close()

    def test_index_refreshes_after_bundle_update(self, tmp_path: Path) -> None:
        output_root = tmp_path / "sessions"
        output_root.mkdir(parents=True, exist_ok=True)
        bundle = _finalize_bundle(output_root, session_uid="uid-update")

        idx = SessionIndex(tmp_path / "index")
        before = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
            max_dirs=150,
        )
        assert len(before) == 1
        original_duration = float(before[0]["duration_s"])

        # Simulate reprocess/update by editing manifest and bumping directory mtime.
        session_path = bundle / "session.json"
        manifest = json.loads(session_path.read_text(encoding="utf-8"))
        # v2: duration_s lives in the session block
        if "session" in manifest and isinstance(manifest["session"], dict):
            manifest["session"]["duration_s"] = 999.0
        else:
            manifest["duration_s"] = 999.0
        session_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.utime(bundle, None)

        after = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
            max_dirs=150,
        )
        assert len(after) == 1
        assert float(after[0]["duration_s"]) == 999.0
        assert float(after[0]["duration_s"]) != original_duration
