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

from dataclasses import dataclass
from pathlib import Path


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
        """Upload a finalized bundle to ``/api/v1/sessions/ingest``.

        Behavior lands in T042. This skeleton exists so dependent
        sprint tasks can take a typed dependency on the interface
        without blocking on the full implementation.
        """
        raise NotImplementedError(
            "IngestClient.upload arrives in T042 (behavior + mock-server test)"
        )


__all__ = ["IngestClient", "IngestResult"]
