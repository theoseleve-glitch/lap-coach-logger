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
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_INGEST_ENDPOINT = "/api/v1/sessions/ingest"
_MANIFEST_FILENAME = "manifest.json"
_DEFAULT_CHUNK_SIZE_BYTES = 5 * 1024 * 1024  # T044: 5 MiB per ADR-012
_CURSOR_FILENAME = ".ingest_cursor.json"  # T045: session-completion marker
# T048: HTTP statuses we treat as transient (retry-eligible).
_TRANSIENT_HTTP_STATUSES = frozenset({502, 503, 504})


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
        chunk_size_bytes: int = _DEFAULT_CHUNK_SIZE_BYTES,
        max_retries: int = 3,
        base_backoff_s: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
        auth_refresh: Callable[[], str] | None = None,
    ) -> None:
        if chunk_size_bytes <= 0:
            raise ValueError("chunk_size_bytes must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        self._base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout_s = timeout_s
        self._chunk_size_bytes = chunk_size_bytes
        self._max_retries = max_retries
        self._base_backoff_s = base_backoff_s
        self._sleep = sleep
        self._auth_refresh = auth_refresh

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout_s(self) -> float:
        return self._timeout_s

    @property
    def chunk_size_bytes(self) -> int:
        return self._chunk_size_bytes

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

        # T045: skip the whole upload if the bundle has a cursor for the
        # same session_id (previous successful call). Any mismatch or
        # malformed cursor falls through to a fresh upload attempt.
        cached = _load_completion_cursor(bundle_dir, manifest_bytes)
        if cached is not None:
            return cached

        boundary = uuid.uuid4().hex
        body = _build_multipart_body(
            bundle_dir, manifest_bytes, boundary, self._chunk_size_bytes
        )

        url = f"{self._base_url}{_INGEST_ENDPOINT}"
        # T043: Idempotency-Key = session UUIDv7 so the backend can
        # short-circuit duplicate uploads of the same session.
        idempotency_key = _session_idempotency_key(manifest_bytes)

        last_failure: IngestResult | None = None
        refreshed = False  # T049: refresh runs at most once per upload call.
        # T048: total attempts = 1 initial + max_retries. Sleep between
        # attempts only — never after the final attempt.
        for attempt in range(self._max_retries + 1):
            while True:  # T049 inner loop: 401 refresh-retry is free.
                headers = {
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Authorization": f"Bearer {self._auth_token}",
                    "Content-Length": str(len(body)),
                }
                if idempotency_key:
                    headers["Idempotency-Key"] = idempotency_key
                try:
                    req = Request(url, data=body, headers=headers, method="POST")
                    with urlopen(req, timeout=self._timeout_s) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                        # T054: a 2xx with a garbled body must return a typed
                        # failure rather than letting JSONDecodeError escape.
                        # Empty body is valid (no payload metadata, but the
                        # upload itself succeeded).
                        if raw:
                            try:
                                payload = json.loads(raw)
                            except json.JSONDecodeError as exc:
                                return IngestResult(
                                    success=False,
                                    http_status=resp.status,
                                    error_code="malformed_response",
                                    error_message=str(exc),
                                )
                        else:
                            payload = {}
                        result = IngestResult(
                            success=True,
                            session_id=payload.get("session_id"),
                            ingest_job_id=payload.get("ingest_job_id"),
                            status_stream_url=payload.get("status_stream"),
                            http_status=resp.status,
                        )
                        _persist_completion_cursor(bundle_dir, result)
                        return result
                except HTTPError as exc:
                    # T049: silent token refresh on 401. Run at most once
                    # per upload — if the refreshed token is also rejected,
                    # surface the second 401 instead of looping.
                    if (
                        exc.code == 401
                        and self._auth_refresh is not None
                        and not refreshed
                    ):
                        refreshed = True
                        try:
                            self._auth_token = self._auth_refresh()
                        except Exception:
                            return IngestResult(
                                success=False,
                                http_status=exc.code,
                                error_code=f"http_{exc.code}",
                                error_message=str(exc),
                            )
                        continue  # inner while: re-issue with the new token.
                    last_failure = IngestResult(
                        success=False,
                        http_status=exc.code,
                        error_code=f"http_{exc.code}",
                        error_message=str(exc),
                    )
                    if exc.code not in _TRANSIENT_HTTP_STATUSES:
                        return last_failure
                    break  # outer for: count this attempt against the budget.
                except (URLError, OSError) as exc:
                    last_failure = IngestResult(
                        success=False,
                        error_code="connection_error",
                        error_message=str(exc),
                    )
                    break  # outer for: transient connection failure.

            if attempt < self._max_retries:
                self._sleep(self._base_backoff_s * (2 ** attempt))

        # ``last_failure`` is always set when the loop exits without returning.
        assert last_failure is not None
        return last_failure


def _build_multipart_body(
    bundle_dir: Path,
    manifest_bytes: bytes,
    boundary: str,
    chunk_size_bytes: int,
) -> bytes:
    """Build a multipart/form-data body carrying the manifest + chunks.

    Manifest is always field ``manifest`` (JSON). Every other regular
    file in ``bundle_dir`` is appended as one or more ``chunks[]``
    parts; files larger than ``chunk_size_bytes`` are split into
    ``<name>.part<i>of<N>`` slices so the backend can reassemble.
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
        for filename, data in _chunked_parts(path, chunk_size_bytes):
            parts.append(
                _form_part(
                    boundary,
                    field_name="chunks[]",
                    filename=filename,
                    content_type="application/octet-stream",
                    data=data,
                )
            )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"\r\n".join(parts)


def _chunked_parts(
    path: Path, chunk_size_bytes: int
) -> list[tuple[str, bytes]]:
    """Slice *path* into ``<=chunk_size_bytes`` pieces with ordered names.

    Files at or below ``chunk_size_bytes`` stay as a single
    ``(path.name, <bytes>)`` tuple so small bundles keep their wire
    shape unchanged. Larger files split into ``part<i>of<N>``
    filenames so the server can reassemble in order.
    """
    data = path.read_bytes()
    if len(data) <= chunk_size_bytes:
        return [(path.name, data)]
    total = (len(data) + chunk_size_bytes - 1) // chunk_size_bytes
    pieces: list[tuple[str, bytes]] = []
    for idx in range(total):
        start = idx * chunk_size_bytes
        end = start + chunk_size_bytes
        pieces.append((f"{path.name}.part{idx}of{total}", data[start:end]))
    return pieces


def _load_completion_cursor(
    bundle_dir: Path, manifest_bytes: bytes
) -> IngestResult | None:
    """Return a cached ``IngestResult`` iff the cursor matches this session.

    Mismatched / malformed / absent cursors fall through to a fresh
    upload so stale or partial state can't silently skip work.
    """
    cursor_path = bundle_dir / _CURSOR_FILENAME
    if not cursor_path.exists():
        return None
    try:
        cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(cursor, dict) or not isinstance(manifest, dict):
        return None
    if cursor.get("session_id") != manifest.get("session_id"):
        return None
    return IngestResult(
        success=True,
        session_id=cursor.get("session_id"),
        ingest_job_id=cursor.get("ingest_job_id"),
        status_stream_url=cursor.get("status_stream_url"),
        http_status=cursor.get("http_status"),
    )


def _persist_completion_cursor(bundle_dir: Path, result: IngestResult) -> None:
    """Write the 202-response fields so the next upload can short-circuit."""
    payload = {
        "session_id": result.session_id,
        "ingest_job_id": result.ingest_job_id,
        "status_stream_url": result.status_stream_url,
        "http_status": result.http_status,
    }
    try:
        (bundle_dir / _CURSOR_FILENAME).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except OSError:
        # Persistence is best-effort; upload already succeeded.
        pass


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
