"""Tests for sync payload schemas."""
from __future__ import annotations

from lap_coach_logger.sync.schema import (
    CoachingPayload,
    EventPayload,
    LapPayload,
    SessionPayload,
    SyncEnvelope,
)


def test_session_payload_validates():
    p = SessionPayload(
        session_id="s1", sim="acc", track="monza", car="gt3",
        mode="sprint", start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-01T01:00:00Z",
    )
    assert p.validate() == []
    d = p.to_dict()
    assert d["session_id"] == "s1"
    assert d["sim"] == "acc"


def test_session_payload_rejects_empty_id():
    p = SessionPayload(
        session_id="", sim="acc", track="monza", car="gt3",
        mode="sprint", start_time="t0", end_time="t1",
    )
    errors = p.validate()
    assert any("session_id" in e for e in errors)


def test_session_payload_rejects_invalid_mode():
    p = SessionPayload(
        session_id="s1", sim="acc", track="monza", car="gt3",
        mode="turbo", start_time="t0", end_time="t1",
    )
    errors = p.validate()
    assert any("mode" in e for e in errors)


def test_lap_payload_validates():
    p = LapPayload(
        session_id="s1", lap_number=1, lap_time_s=90.123,
        valid=True, fuel_used_l=2.5, sector_times_s=[30.0, 30.0, 30.123],
    )
    assert p.validate() == []
    d = p.to_dict()
    assert d["lap_time_s"] == 90.123
    assert d["sector_times_s"] == [30.0, 30.0, 30.123]


def test_lap_payload_rejects_negative_time():
    p = LapPayload(
        session_id="s1", lap_number=1, lap_time_s=-1.0,
        valid=True, fuel_used_l=2.5,
    )
    errors = p.validate()
    assert any("lap_time_s" in e for e in errors)


def test_coaching_payload_validates():
    p = CoachingPayload(
        session_id="s1", consistency_score=85.3, trend="improving",
        focus_area="braking", recommendation="Brake later into T1",
        confidence="high",
    )
    assert p.validate() == []
    d = p.to_dict()
    assert d["consistency_score"] == 85.3
    assert d["confidence"] == "high"


def test_event_payload_validates():
    p = EventPayload(
        session_id="s1", event_type="pit_stop",
        timestamp="2025-01-01T00:30:00Z",
        payload={"tire_set": 2},
    )
    assert p.validate() == []
    d = p.to_dict()
    assert d["event_type"] == "pit_stop"
    assert d["payload"]["tire_set"] == 2


def test_sync_envelope_roundtrip():
    env = SyncEnvelope(payload_type="session", payload={"session_id": "s1"})
    d = env.to_dict()
    restored = SyncEnvelope.from_dict(d)
    assert restored.envelope_id == env.envelope_id
    assert restored.payload_type == "session"
    assert restored.payload == {"session_id": "s1"}


def test_sync_envelope_idempotent_id():
    env1 = SyncEnvelope()
    env2 = SyncEnvelope()
    assert env1.envelope_id != env2.envelope_id
    assert len(env1.envelope_id) == 36  # UUID format
