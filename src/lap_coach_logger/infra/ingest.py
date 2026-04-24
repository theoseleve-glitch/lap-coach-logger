"""IngestClient — typed client for ADR-012 unified ingestion endpoint.

Per ADR-012, the desktop uploads a finalized session bundle via::

    POST /api/v1/sessions/ingest
      Headers: Idempotency-Key, Authorization
      Body:    multipart/form-data
        - manifest: SessionManifest JSON
        - chunks[]: streamed telemetry chunks
        - artifacts[]: optional supplementary files

    Response: 202 Accepted
      { session_id, ingest_job_id, status_stream: "/api/v1/jobs/:id/events" }

T041 ships the typed surface only (class + result dataclass + method
signature). Behavior lands in follow-up sprint tasks:

* T042 — ``upload(manifest, artifacts)`` returns ``ingest_job_id``
* T043 — ``Idempotency-Key`` = session UUIDv7 in headers
* T044 — chunk streaming: telemetry uploaded in 5MB chunks
* T045 — resume-on-interrupt: persisted chunk cursor
* T048 — retry with exponential backoff on network failure
* T054 — unit coverage: 2xx / 4xx / 5xx / network error paths

``IngestClient`` replaces the legacy ``sync.bundle_uploader.BundleUploader``
as the desktop's canonical outbound entry point for session ingestion.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_INGEST_ENDPOINT = "/api/v1/sessions/ingest"
_MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class IngestResult:
    """Typed outcome of an ``IngestClient.upload`` call.

    Mirrors the ADR-012 202-response payload plus a transport-level
    ``success`` flag and optional error metadata for non-2xx paths.
    The ``status_stream_url`` is the relative SSE path that callers
    hand to the progress consumer (T046).
    """

    success: bool
    session_id: str | None = None
    ingest_job_id: str | None = None
    status_stream_url: str | None = None
    http_status: int | None = None
    error_code: str = ""
    error_message: str = ""


class IngestClient:
    """Typed HTTP client for the unified ingestion endpoint (ADR-012)."""

    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str,
        timeout_s: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout_s = timeout_s

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout_s(self) -> float:
        return self._timeout_s

    def upload(self, *, bundle_dir: Path) -> IngestResult:
        """Upload a finalized bundle to ``/api/v1/sessions/ingest`` (T042).

        Sends a single multipart POST with the manifest.json field plus
        every other bundle file as a ``chunks[]`` part. Returns a typed
        ``IngestResult`` whose ``ingest_job_id`` is populated from the
        ADR-012 202 response.

        Later sprint tasks refine this: T043 (Idempotency-Key),
        T044 (5MB chunk streaming), T045 (resume-on-interrupt),
        T048 (retry with backoff), T054 (explicit 4xx/5xx coverage).
        """
        manifest_path = bundle_dir / _MANIFEST_FILENAME
        if not manifest_path.exists():
            return IngestResult(
                success=False,
                error_code="no_manifest",
                error_message=f"{_MANIFEST_FILENAME} not found in {bundle_dir}",
            )

        manifest_bytes = manifest_path.read_bytes()
        boundary = uuid.uuid4().hex
        body = _build_multipart_body(bundle_dir, manifest_bytes, boundary)

        url = f"{self._base_url}{_INGEST_ENDPOINT}"
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Length": str(len(body)),
        }

        # T043: Idempotency-Key = session UUIDv7 so the backend can
        # short-circuit duplicate uploads of the same session.
        idempotency_key = _session_idempotency_key(manifest_bytes)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            req = Request(url, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=self._timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                payload = json.loads(raw) if raw else {}
                return IngestResult(
                    success=True,
                    session_id=payload.get("session_id"),
                    ingest_job_id=payload.get("ingest_job_id"),
                    status_stream_url=payload.get("status_stream"),
                    http_status=resp.status,
                )
        except HTTPError as exc:
            return IngestResult(
                success=False,
                http_status=exc.code,
                error_code=f"http_{exc.code}",
                error_message=str(exc),
            )
        except (URLError, OSError) as exc:
            return IngestResult(
                success=False,
                error_code="connection_error",
                error_message=str(exc),
            )


def _build_multipart_body(
    bundle_dir: Path, manifest_bytes: bytes, boundary: str
) -> bytes:
    """Build a multipart/form-data body carrying the manifest + chunks.

    Manifest is always field ``manifest`` (JSON). Every other regular
    file in ``bundle_dir`` is appended as a ``chunks[]`` part with the
    file's name preserved; directories and the manifest itself are
    skipped.
    """
    parts: list[bytes] = []
    parts.append(
        _form_part(
            boundary,
            field_name="manifest",
            filename=_MANIFEST_FILENAME,
            content_type="application/json",
            data=manifest_bytes,
        )
    )
    for path in sorted(bundle_dir.iterdir()):
        if not path.is_file() or path.name == _MANIFEST_FILENAME:
            continue
        parts.append(
            _form_part(
                boundary,
                field_name="chunks[]",
                filename=path.name,
                content_type="application/octet-stream",
                data=path.read_bytes(),
            )
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"\r\n".join(parts)


def _session_idempotency_key(manifest_bytes: bytes) -> str | None:
    """Return the manifest's ``session_id`` for use as Idempotency-Key.

    The Bundle v2 contract guarantees ``session_id`` is a UUID7; we
    return it as-is without re-validating so the client stays a thin
    transport. Returns ``None`` only if the manifest can't be parsed
    or omits the field — in which case the header is dropped and the
    server will fall back to request-scoped idempotency.
    """
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    session_id = manifest.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    return session_id


def _form_part(
    boundary: str,
    *,
    field_name: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> bytes:
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; '
        f'filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8")
    return header + data


__all__ = ["IngestClient", "IngestResult"]
