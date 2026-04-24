"""T041: IngestClient typed surface in ``infra/ingest.py``.

Per ADR-012, the desktop uploads a finalized bundle via
``POST /api/v1/sessions/ingest``. The new ``IngestClient`` replaces
``BundleUploader`` as the desktop's typed entry point for the
unified ingestion endpoint. This module-level test pins the typed
contract (class + result type + method signature) so subsequent
sprint tasks (T042 upload behavior, T043 idempotency, T044 chunk
streaming, T054 happy/4xx/5xx/network) can build on it without
drifting the shape.
"""
from __future__ import annotations

import inspect
import typing
from pathlib import Path


def test_infra_ingest_module_exists() -> None:
    import lap_coach_logger.infra.ingest  # noqa: F401


def test_ingest_client_class_exposed() -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    assert inspect.isclass(IngestClient)


def test_ingest_client_init_is_typed() -> None:
    """Typed construction parameters: base_url, auth_token, timeout_s."""
    from lap_coach_logger.infra.ingest import IngestClient

    hints = typing.get_type_hints(IngestClient.__init__)
    assert hints["base_url"] is str
    assert hints["auth_token"] is str
    assert hints["timeout_s"] is float


def test_ingest_client_upload_signature_matches_adr012(tmp_path: Path) -> None:
    """``upload(bundle_dir)`` returns a typed ``IngestResult``.

    Per ADR-012 the response carries ``session_id``, ``ingest_job_id``,
    and ``status_stream`` — the typed result must expose all three.
    """
    from lap_coach_logger.infra.ingest import IngestClient, IngestResult

    hints = typing.get_type_hints(IngestClient.upload)
    assert hints["return"] is IngestResult
    sig = inspect.signature(IngestClient.upload)
    assert "bundle_dir" in sig.parameters


def test_ingest_result_fields_match_adr012() -> None:
    """``IngestResult`` carries the ADR-012 202-response payload + status."""
    from lap_coach_logger.infra.ingest import IngestResult

    hints = IngestResult.__annotations__
    for field in ("success", "session_id", "ingest_job_id", "status_stream_url"):
        assert field in hints, f"IngestResult missing {field}"


def test_ingest_client_upload_is_stub_until_t042() -> None:
    """T041 ships the typed surface only — behavior lands in T042."""
    from lap_coach_logger.infra.ingest import IngestClient

    import pytest

    client = IngestClient(
        base_url="https://api.example.test",
        auth_token="placeholder",
        timeout_s=30.0,
    )
    with pytest.raises(NotImplementedError):
        client.upload(bundle_dir=Path("."))
