from __future__ import annotations

from lap_coach_logger.core.live_dashboard import LiveCornerTracker, LiveSamplePoint, detect_corners


def test_detect_corners_finds_two_turn_zones() -> None:
    samples: list[LiveSamplePoint] = []
    for index in range(51):
        lap_dist = index / 50
        lat_g = 0.02
        if 0.18 <= lap_dist <= 0.32:
            lat_g = 0.78
        elif 0.58 <= lap_dist <= 0.74:
            lat_g = -0.91
        samples.append(
            LiveSamplePoint(
                lap_number=1,
                lap_dist_pct=lap_dist,
                session_time_s=90.0 * lap_dist,
                speed_kph=220.0,
                lat_accel_g=lat_g,
            )
        )

    corners = detect_corners(samples)

    assert [corner.name for corner in corners] == ["T01", "T02"]
    assert corners[0].start_pct < 0.18
    assert corners[0].end_pct > 0.32
    assert corners[1].start_pct < 0.58
    assert corners[1].end_pct > 0.74


def test_live_corner_tracker_updates_last_and_best_after_each_lap() -> None:
    tracker = LiveCornerTracker()
    lap_one = _build_lap_snapshots(session_uid="live-abc", lap_number=1, lap_duration_s=90.0, start_time_s=0.0)
    lap_two = _build_lap_snapshots(session_uid="live-abc", lap_number=2, lap_duration_s=88.0, start_time_s=90.0)

    for snapshot in lap_one:
        tracker.push_snapshot(snapshot)

    assert tracker.rows() == []

    tracker.push_snapshot(lap_two[0])
    rows_after_lap_one = tracker.rows()

    assert len(rows_after_lap_one) == 2
    assert [row["corner"] for row in rows_after_lap_one] == ["T01", "T02"]
    assert all(row["last_time_s"] == row["best_time_s"] for row in rows_after_lap_one)

    first_best_times = {row["corner"]: row["best_time_s"] for row in rows_after_lap_one}

    for snapshot in lap_two[1:]:
        tracker.push_snapshot(snapshot)

    tracker.push_snapshot(
        {
            "session_uid": "live-abc",
            "lap_number": 3,
            "lap_dist_pct": 0.0,
            "session_time_s": 178.0,
            "speed_kph": 240.0,
            "lat_accel_g": 0.0,
            "world_pos_x": 0.0,
            "world_pos_z": 0.0,
        }
    )
    rows_after_lap_two = tracker.rows()

    assert len(rows_after_lap_two) == 2
    assert all(row["last_time_s"] is not None for row in rows_after_lap_two)
    assert any(row["best_time_s"] < first_best_times[row["corner"]] for row in rows_after_lap_two)


def _build_lap_snapshots(
    *,
    session_uid: str,
    lap_number: int,
    lap_duration_s: float,
    start_time_s: float,
) -> list[dict[str, float | int | str]]:
    snapshots: list[dict[str, float | int | str]] = []
    for index in range(51):
        lap_dist = index / 50
        lat_g = 0.02
        speed_kph = 245.0
        if 0.18 <= lap_dist <= 0.32:
            lat_g = 0.82
            speed_kph = 118.0
        elif 0.58 <= lap_dist <= 0.74:
            lat_g = -0.96
            speed_kph = 142.0

        snapshots.append(
            {
                "session_uid": session_uid,
                "lap_number": lap_number,
                "lap_dist_pct": lap_dist,
                "session_time_s": start_time_s + lap_duration_s * lap_dist,
                "speed_kph": speed_kph,
                "lat_accel_g": lat_g,
                "long_accel_g": 0.12,
                "world_pos_x": 100.0 * lap_dist,
                "world_pos_z": 50.0 * lap_dist,
            }
        )
    return snapshots
