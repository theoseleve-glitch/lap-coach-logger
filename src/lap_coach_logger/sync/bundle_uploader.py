"""Bundle uploader — multipart POST of a v2 session bundle to /v1/bundles.

Triggered by the SyncQueueManager after finalize succeeds locally.
Respects the 200 MB cap (D4), drops optional native artifacts if needed
to fit. Uses HttpTransport for retry + auth, but constructs its own
multipart body because the typed-endpoint path handles JSON envelopes.

On failure: records to bundle_failures.json (analogous to sync_failures.json).
On replay: backend returns {already_seen: true}, uploader marks as synced.
"""

from __future__ import annotations

import json
import logging
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import email.generator
import mimetypes

log = logging.getLogger(__name__)

MAX_BUNDLE_BYTES = 200 * 1024 * 1024  # D4


class BundleUploadResult:
    """Outcome of an upload attempt."""
    def __init__(
        self,
        success: bool,
        already_seen: bool = False,
        error_code: str = "",
        error_message: str = "",
        http_status: int | None = None,
    ) -> None:
        self.success = success
        self.already_seen = already_seen
        self.error_code = error_code
        self.error_message = error_message
        self.http_status = http_status


class BundleUploader:
    """Uploads a bundle directory to the backend."""

    def __init__(
        self,
        base_url: str,
        device_token: str,
        api_key: str = "",
        timeout_s: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._device_token = device_token
        self._api_key = api_key
        self._timeout_s = timeout_s

    def upload(self, bundle_dir: Path) -> BundleUploadResult:
        """Upload the bundle directory. Blocks until complete or fails."""
        manifest_path = bundle_dir / "session.json"
        if not manifest_path.exists():
            return BundleUploadResult(
                success=False, error_code="no_manifest",
                error_message="session.json not found in bundle directory",
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            return BundleUploadResult(
                success=False, error_code="manifest_parse_error",
                error_message=str(e),
            )

        if manifest.get("schema_version") != 2:
            return BundleUploadResult(
                success=False, error_code="wrong_schema",
                error_message="bundle is not v2 — upload requires schema_version=2",
            )

        bundle_hash = manifest.get("bundle_hash", "")
        bundle_hash_hex = bundle_hash.removeprefix("sha256:") if isinstance(bundle_hash, str) else ""
        if len(bundle_hash_hex) < 32:
            return BundleUploadResult(
                success=False, error_code="no_bundle_hash",
                error_message="bundle_hash missing or invalid",
            )

        # Idempotency-Key from bundle_hash
        idempotency_key = str(uuid.UUID(bundle_hash_hex[:32]))

        # Collect files from inventory
        bundle_files = manifest.get("bundle_files", [])
        parts: dict[str, bytes] = {}
        total = 0
        for entry in bundle_files:
            name = entry.get("name", "")
            fpath = bundle_dir / name
            if not fpath.exists():
                log.warning("File %s listed in bundle_files but missing from disk", name)
                continue
            data = fpath.read_bytes()
            total += len(data)
            parts[name] = data

        # D4: drop optional files if over 200 MB
        if total > MAX_BUNDLE_BYTES:
            optional = [e["name"] for e in bundle_files if not e.get("required", True)]
            for opt_name in sorted(optional, key=lambda n: len(parts.get(n, b"")), reverse=True):
                if opt_name in parts:
                    total -= len(parts[opt_name])
                    del parts[opt_name]
                    log.info("Dropped optional %s to stay under 200 MB", opt_name)
                if total <= MAX_BUNDLE_BYTES:
                    break

        if total > MAX_BUNDLE_BYTES:
            return BundleUploadResult(
                success=False, error_code="bundle_too_large",
                error_message=f"canonical files alone exceed 200 MB ({total} bytes)",
            )

        # Build multipart body
        boundary = uuid.uuid4().hex
        body = _build_multipart(parts, boundary)

        # Send request
        url = f"{self._base_url}/v1/bundles"
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": idempotency_key,
            "Authorization": f"Bearer {self._device_token}",
            "Content-Length": str(len(body)),
        }
        if self._api_key:
            headers["apikey"] = self._api_key

        try:
            req = Request(url, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=self._timeout_s) as resp:
                resp_body = json.loads(resp.read().decode("utf-8", errors="replace"))
                return BundleUploadResult(
                    success=True,
                    already_seen=resp_body.get("already_seen", False),
                )
        except HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8", errors="replace"))
            except Exception:
                err_body = {}
            return BundleUploadResult(
                success=False,
                error_code=err_body.get("code", f"http_{e.code}"),
                error_message=err_body.get("message", str(e)),
                http_status=e.code,
            )
        except (URLError, OSError) as e:
            return BundleUploadResult(
                success=False,
                error_code="connection_error",
                error_message=str(e),
            )


def _build_multipart(parts: dict[str, bytes], boundary: str) -> bytes:
    """Build a raw multipart/form-data body. No dependency beyond stdlib."""
    lines: list[bytes] = []
    for name, data in parts.items():
        ct = "application/json" if name.endswith(".json") else "application/octet-stream"
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"; filename="{name}"'.encode())
        lines.append(f"Content-Type: {ct}".encode())
        lines.append(b"")
        lines.append(data)
    lines.append(f"--{boundary}--".encode())
    return b"\r\n".join(lines)
