"""Concrete SyncService for Lap Coach API.

Uploads session bundles (telemetry CSV + manifest) to the webapp
via POST /api/v1/sessions/sync-upload using a device token.
"""
from __future__ import annotations

import gzip
import json
import logging
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from lap_coach_logger.core.sync_service import SyncAttemptResult

logger = logging.getLogger(__name__)

# HTTP status codes that should NOT be retried
_NO_RETRY_CODES = {400, 401, 403, 404, 409, 429}


class LapCoachSyncService:
    """Implements SyncService protocol for Lap Coach API."""

    def __init__(self, api_url: str, device_token: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._device_token = device_token

    @property
    def enabled(self) -> bool:
        return bool(self._device_token)

    def upload_bundle(
        self, *, bundle_dir: Path, session_id: str, bundle_hash: str
    ) -> SyncAttemptResult:
        csv_path = bundle_dir / "telemetry.csv"
        if not csv_path.exists():
            # Try parquet fallback name
            csv_path = bundle_dir / "telemetry.parquet"
            if not csv_path.exists():
                return SyncAttemptResult(
                    success=False, error="No telemetry file in bundle", retryable=False
                )

        manifest_path = bundle_dir / "session.json"
        manifest = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        manifest["bundle_hash"] = bundle_hash
        manifest["session_id"] = session_id

        try:
            body, content_type = _build_multipart(csv_path, manifest)
            compressed_body = gzip.compress(body)
            url = f"{self._api_url}/api/v1/sessions/sync-upload"
            req = urllib.request.Request(url, data=compressed_body, method="POST")
            req.add_header("Authorization", f"DeviceToken {self._device_token}")
            req.add_header("Content-Type", content_type)
            req.add_header("Content-Encoding", "gzip")
            req.add_header("Accept-Encoding", "gzip, deflate, identity")

            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = json.loads(_read_response(resp))

            if resp_body.get("ok"):
                remote_id = str(resp_body.get("data", {}).get("session_id", ""))
                return SyncAttemptResult(success=True, remote_id=remote_id)

            return SyncAttemptResult(
                success=False,
                error=resp_body.get("error", "Unknown API error"),
                retryable=True,
            )

        except urllib.error.HTTPError as e:
            retryable = e.code not in _NO_RETRY_CODES
            error_msg = f"HTTP {e.code}: {e.reason}"
            try:
                err_body = json.loads(_read_response(e))
                error_msg = err_body.get("error", error_msg)
            except Exception:
                pass
            logger.warning("Sync upload failed: %s (retryable=%s)", error_msg, retryable)
            return SyncAttemptResult(success=False, error=error_msg, retryable=retryable)

        except Exception as e:
            logger.exception("Sync upload error")
            return SyncAttemptResult(success=False, error=str(e), retryable=True)


def _read_response(resp: Any) -> bytes:
    """Read an HTTP response, decompressing gzip/deflate if needed."""
    raw = resp.read()
    encoding = ""
    if hasattr(resp, "headers") and resp.headers:
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
    if encoding == "gzip":
        raw = gzip.decompress(raw)
    elif encoding == "deflate":
        import zlib

        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


def _build_multipart(csv_path: Path, manifest: dict) -> tuple[bytes, str]:
    """Build a multipart/form-data body with telemetry file + manifest JSON."""
    boundary = uuid.uuid4().hex
    lines: list[bytes] = []

    # Telemetry file part
    lines.append(f"--{boundary}".encode())
    lines.append(
        f'Content-Disposition: form-data; name="telemetry"; filename="{csv_path.name}"'.encode()
    )
    lines.append(b"Content-Type: application/octet-stream")
    lines.append(b"")
    lines.append(csv_path.read_bytes())

    # Manifest part
    lines.append(f"--{boundary}".encode())
    lines.append(b'Content-Disposition: form-data; name="manifest"')
    lines.append(b"Content-Type: application/json")
    lines.append(b"")
    lines.append(json.dumps(manifest).encode("utf-8"))

    lines.append(f"--{boundary}--".encode())

    body = b"\r\n".join(lines)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type
