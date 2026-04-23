"""HTTP transport with retry, backoff, auth, and response validation.

Isolated from client.py so retry policy is testable without a running
queue. Never raises — every outcome is a TransportResult.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)


class TransportOutcome(Enum):
    SUCCESS = "success"
    RETRY = "retry"              # transient error, retry later
    PERMANENT_FAILURE = "permanent_failure"  # 4xx (client), bad payload, etc.
    AUTH_FAILURE = "auth_failure"  # 401/403 — needs user intervention


@dataclass(frozen=True)
class TransportResult:
    outcome: TransportOutcome
    http_status: int | None
    response_body: str
    error_message: str
    attempt_count: int


@dataclass(frozen=True)
class TransportConfig:
    base_url: str
    device_token: str = ""
    api_key: str = ""          # Supabase anon key or similar
    timeout_s: float = 10.0
    max_attempts: int = 5
    initial_backoff_s: float = 1.0
    max_backoff_s: float = 30.0


class HttpTransport:
    """Encapsulates HTTP POST + retry/backoff/auth."""

    def __init__(self, config: TransportConfig) -> None:
        self._config = config

    def post(
        self,
        path: str,
        body: dict[str, Any],
        idempotency_key: str,
        idempotency_header: str = "Idempotency-Key",
    ) -> TransportResult:
        """POST with retry. Blocks until success or permanent failure."""
        url = self._build_url(path)
        headers = self._build_headers(idempotency_key, idempotency_header)
        body_bytes = json.dumps(body).encode("utf-8")

        last_error = ""
        last_status: int | None = None
        last_body = ""

        for attempt in range(1, self._config.max_attempts + 1):
            try:
                req = Request(url, data=body_bytes, headers=headers, method="POST")
                with urlopen(req, timeout=self._config.timeout_s) as resp:
                    status = resp.status
                    response_body = resp.read().decode("utf-8", errors="replace")
                    if 200 <= status < 300:
                        return TransportResult(
                            outcome=TransportOutcome.SUCCESS,
                            http_status=status,
                            response_body=response_body,
                            error_message="",
                            attempt_count=attempt,
                        )
                    # Non-2xx with no exception is unusual — treat as permanent
                    return TransportResult(
                        outcome=TransportOutcome.PERMANENT_FAILURE,
                        http_status=status,
                        response_body=response_body,
                        error_message=f"Unexpected status {status}",
                        attempt_count=attempt,
                    )
            except HTTPError as e:
                last_status = e.code
                try:
                    last_body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    last_body = ""
                last_error = f"HTTP {e.code}: {e.reason}"
                # 401/403 → auth failure (no retry, user must fix token)
                if e.code in (401, 403):
                    return TransportResult(
                        outcome=TransportOutcome.AUTH_FAILURE,
                        http_status=e.code,
                        response_body=last_body,
                        error_message=last_error,
                        attempt_count=attempt,
                    )
                # 4xx (including 409) → permanent failure. Dedup is signalled
                # at the backend via HTTP 200 + {"already_seen": true}, so we
                # no longer treat 409 as success. 409 means "precondition
                # failed" (e.g. laps arrived before their parent session);
                # surfacing it to sync_failures is the correct audit path.
                if 400 <= e.code < 500:
                    return TransportResult(
                        outcome=TransportOutcome.PERMANENT_FAILURE,
                        http_status=e.code,
                        response_body=last_body,
                        error_message=last_error,
                        attempt_count=attempt,
                    )
                # 5xx → retry
            except (URLError, OSError) as e:
                last_error = f"Connection error: {e}"
                last_status = None

            if attempt < self._config.max_attempts:
                sleep_s = min(
                    self._config.max_backoff_s,
                    self._config.initial_backoff_s * (2 ** (attempt - 1)),
                )
                time.sleep(sleep_s)

        # Exhausted retries — return RETRY so caller can decide to queue for later
        return TransportResult(
            outcome=TransportOutcome.RETRY,
            http_status=last_status,
            response_body=last_body,
            error_message=last_error or "Max retries exhausted",
            attempt_count=self._config.max_attempts,
        )

    def _build_url(self, path: str) -> str:
        base = self._config.base_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    def _build_headers(self, idempotency_key: str, idempotency_header: str) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers[idempotency_header] = idempotency_key
        if self._config.device_token:
            headers["Authorization"] = f"Bearer {self._config.device_token}"
        if self._config.api_key:
            headers["apikey"] = self._config.api_key
        return headers
