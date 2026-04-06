"""Tests for LapCoachSyncService."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lap_coach_logger.core.lap_coach_sync import LapCoachSyncService


def test_disabled_when_no_token():
    svc = LapCoachSyncService(api_url="https://example.com", device_token="")
    assert svc.enabled is False


def test_enabled_when_token_present():
    svc = LapCoachSyncService(api_url="https://example.com", device_token="abc123")
    assert svc.enabled is True


def test_upload_bundle_reads_csv_and_manifest(tmp_path):
    """upload_bundle reads telemetry.csv and session.json from the bundle dir."""
    (tmp_path / "telemetry.csv").write_text("Time,Speed\n0,10\n", encoding="utf-8")
    manifest = {"session_id": "test_001", "bundle_hash": "hash123"}
    (tmp_path / "session.json").write_text(json.dumps(manifest), encoding="utf-8")

    svc = LapCoachSyncService(api_url="https://example.com", device_token="tok")

    with patch("lap_coach_logger.core.lap_coach_sync.urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "ok": True,
            "data": {"session_id": 42, "status": "pending_analysis", "analyze_triggered": False},
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = svc.upload_bundle(
            bundle_dir=tmp_path,
            session_id="test_001",
            bundle_hash="hash123",
        )

    assert result.success is True
    assert result.remote_id == "42"


def test_upload_bundle_401_not_retryable(tmp_path):
    """401 (revoked token) should not be retryable."""
    (tmp_path / "telemetry.csv").write_text("Time,Speed\n0,10\n", encoding="utf-8")
    (tmp_path / "session.json").write_text("{}", encoding="utf-8")

    svc = LapCoachSyncService(api_url="https://example.com", device_token="tok")

    with patch("lap_coach_logger.core.lap_coach_sync.urllib.request.urlopen") as mock_urlopen:
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="", code=401, msg="Unauthorized", hdrs=None, fp=None,
        )

        result = svc.upload_bundle(
            bundle_dir=tmp_path, session_id="test", bundle_hash="hash",
        )

    assert result.success is False
    assert result.retryable is False


def test_upload_bundle_500_retryable(tmp_path):
    """5xx should be retryable."""
    (tmp_path / "telemetry.csv").write_text("Time,Speed\n0,10\n", encoding="utf-8")
    (tmp_path / "session.json").write_text("{}", encoding="utf-8")

    svc = LapCoachSyncService(api_url="https://example.com", device_token="tok")

    with patch("lap_coach_logger.core.lap_coach_sync.urllib.request.urlopen") as mock_urlopen:
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="", code=503, msg="Service Unavailable", hdrs=None, fp=None,
        )

        result = svc.upload_bundle(
            bundle_dir=tmp_path, session_id="test", bundle_hash="hash",
        )

    assert result.success is False
    assert result.retryable is True
