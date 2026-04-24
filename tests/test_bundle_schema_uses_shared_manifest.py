"""Regression test: bundle_schema.SessionManifest is the shared type (T022).

T022 replaces the local ``SessionManifest`` dataclass in
``writers.bundle_schema`` with the shared Pydantic
``lap_schemas.v1.SessionManifest`` so the desktop bundle pipeline
writes to the same contract every other consumer reads. Legacy
v1-bundle code paths keep the old dataclass under ``LegacySessionManifest``
until the T025-T034 SessionFinalizer rewrite adopts the new shape.
"""
from __future__ import annotations


def test_bundle_schema_session_manifest_is_shared_pydantic_model() -> None:
    from lap_coach_logger.writers.bundle_schema import SessionManifest
    from lap_schemas.v1 import SessionManifest as SharedManifest

    assert SessionManifest is SharedManifest, (
        "writers.bundle_schema.SessionManifest must re-export the shared "
        "lap_schemas.v1.SessionManifest (T022)."
    )


def test_legacy_session_manifest_still_available_for_transition() -> None:
    # Existing callers that still use the v1-bundle dataclass shape
    # (e.g. test_session_bundle.py) migrate via LegacySessionManifest
    # until T025-T034 rewrite the SessionFinalizer.
    from lap_coach_logger.writers.bundle_schema import LegacySessionManifest

    m = LegacySessionManifest(session_id="s1", logger_version="1.0.0")
    assert m.session_id == "s1"
    assert m.logger_version == "1.0.0"


def test_bundle_schema_lap_record_is_shared_pydantic_model() -> None:
    """T023: local LapRecord dataclass replaced by shared v1 model."""
    from lap_coach_logger.writers.bundle_schema import LapRecord
    from lap_schemas.v1 import LapRecord as SharedLapRecord

    assert LapRecord is SharedLapRecord, (
        "writers.bundle_schema.LapRecord must re-export the shared "
        "lap_schemas.v1.LapRecord (T023)."
    )


def test_legacy_lap_record_still_available_for_transition() -> None:
    # Lap analysis and the v1-bundle finalizer still use the rich
    # local dataclass (start/end_session_time_s, classification flags,
    # sample_count, etc.) until the T025-T034 rewrite adopts the
    # shared tuple-based sector splits.
    from lap_coach_logger.writers.bundle_schema import LegacyLapRecord

    lap = LegacyLapRecord(
        lap_number=1, start_session_time_s=0.0, end_session_time_s=30.0
    )
    assert lap.lap_number == 1
    assert lap.start_session_time_s == 0.0
    assert lap.end_session_time_s == 30.0
    assert lap.classification == "unknown"
