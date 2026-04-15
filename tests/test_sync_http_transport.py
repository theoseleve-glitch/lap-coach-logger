"""Tests for HTTP transport retry/backoff/auth."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from lap_coach_logger.sync.http_transport import (
    HttpTransport,
    TransportConfig,
    TransportOutcome,
)


def _make_config(**overrides) -> TransportConfig:
    defaults = {
        "base_url": "https://api.example.com",
        "device_token": "tok",
        "api_key": "key",
        "timeout_s": 1.0,
        "max_attempts": 3,
        "initial_backoff_s": 0.01,  # fast for tests
        "max_backoff_s": 0.05,
    }
    defaults.update(overrides)
    return TransportConfig(**defaults)


def _mock_response(status: int, body: str = "{}"):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body.encode("utf-8")
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=None)
    return resp


class TestSuccess:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_200_is_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(200, '{"ok": true}')
        transport = HttpTransport(_make_config())
        result = transport.post("/sessions/start", {"x": 1}, "envelope-1")
        assert result.outcome == TransportOutcome.SUCCESS
        assert result.http_status == 200
        assert result.attempt_count == 1

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_201_is_success(self, mock_urlopen):
        mock_urlopen.return_value = _mock_response(201, "")
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.SUCCESS


class TestAuthFailure:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_401_returns_auth_failure(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 401, "Unauthorized", {}, MagicMock(read=lambda: b'{"error": "bad token"}')
        )
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.AUTH_FAILURE
        assert result.http_status == 401
        assert result.attempt_count == 1  # no retry on auth failure

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_403_returns_auth_failure(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 403, "Forbidden", {}, MagicMock(read=lambda: b"")
        )
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.AUTH_FAILURE


class TestIdempotentDuplicate:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_409_is_treated_as_success(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 409, "Conflict", {}, MagicMock(read=lambda: b'{"duplicate": true}')
        )
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.SUCCESS
        assert result.http_status == 409


class TestClientError:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_400_is_permanent_failure(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 400, "Bad Request", {}, MagicMock(read=lambda: b'{"error": "bad payload"}')
        )
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.PERMANENT_FAILURE
        assert result.http_status == 400
        assert result.attempt_count == 1  # no retry

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_422_is_permanent_failure(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 422, "Unprocessable", {}, MagicMock(read=lambda: b"")
        )
        transport = HttpTransport(_make_config())
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.PERMANENT_FAILURE


class TestServerError:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_500_retries_then_gives_up(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://x", 500, "Server Error", {}, MagicMock(read=lambda: b"")
        )
        transport = HttpTransport(_make_config(max_attempts=3))
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.RETRY
        assert result.attempt_count == 3

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_500_then_200_succeeds(self, mock_urlopen):
        err = HTTPError("https://x", 500, "x", {}, MagicMock(read=lambda: b""))
        mock_urlopen.side_effect = [err, _mock_response(200, "{}")]
        transport = HttpTransport(_make_config(max_attempts=3))
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.SUCCESS
        assert result.attempt_count == 2


class TestConnectionError:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_urlerror_retries(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("no network")
        transport = HttpTransport(_make_config(max_attempts=2))
        result = transport.post("/x", {}, "k")
        assert result.outcome == TransportOutcome.RETRY
        assert result.attempt_count == 2


class TestHeaders:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_auth_header_set_from_token(self, mock_urlopen):
        captured = []
        def capture(req, timeout):
            captured.append(dict(req.headers))
            return _mock_response(200, "{}")
        mock_urlopen.side_effect = capture
        transport = HttpTransport(_make_config(device_token="abc123"))
        transport.post("/x", {}, "k")
        assert captured[0].get("Authorization") == "Bearer abc123"

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_idempotency_key_header(self, mock_urlopen):
        captured = []
        def capture(req, timeout):
            captured.append(dict(req.headers))
            return _mock_response(200, "{}")
        mock_urlopen.side_effect = capture
        transport = HttpTransport(_make_config())
        transport.post("/x", {}, "envelope-xyz", idempotency_header="Idempotency-Key")
        assert captured[0].get("Idempotency-key") == "envelope-xyz" or captured[0].get("Idempotency-Key") == "envelope-xyz"

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_apikey_header_for_supabase(self, mock_urlopen):
        captured = []
        def capture(req, timeout):
            captured.append(dict(req.headers))
            return _mock_response(200, "{}")
        mock_urlopen.side_effect = capture
        transport = HttpTransport(_make_config(api_key="supabase-anon-xyz"))
        transport.post("/x", {}, "k")
        assert captured[0].get("Apikey") == "supabase-anon-xyz" or captured[0].get("apikey") == "supabase-anon-xyz"


class TestUrlBuilding:

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_base_url_with_trailing_slash(self, mock_urlopen):
        captured = []
        def capture(req, timeout):
            captured.append(req.full_url)
            return _mock_response(200, "{}")
        mock_urlopen.side_effect = capture
        transport = HttpTransport(_make_config(base_url="https://api.example.com/"))
        transport.post("/sessions/start", {}, "k")
        assert captured[0] == "https://api.example.com/sessions/start"

    @patch("lap_coach_logger.sync.http_transport.urlopen")
    def test_path_without_leading_slash(self, mock_urlopen):
        captured = []
        def capture(req, timeout):
            captured.append(req.full_url)
            return _mock_response(200, "{}")
        mock_urlopen.side_effect = capture
        transport = HttpTransport(_make_config())
        transport.post("sessions/start", {}, "k")
        assert captured[0] == "https://api.example.com/sessions/start"
