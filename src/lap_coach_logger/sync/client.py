"""Sync client — sends envelopes to the webapp API.

Non-blocking. Runs sync attempts in a background thread.
No direct coupling to specific API endpoints — just POST JSON.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from lap_coach_logger.sync.queue import SyncQueue

log = logging.getLogger(__name__)


class SyncClient:
    """Background sync client with retry logic."""

    def __init__(self, queue: SyncQueue, api_url: str, device_token: str = "") -> None:
        self._queue = queue
        self._api_url = api_url.rstrip("/")
        self._device_token = device_token
        self._running = False
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_depth(self) -> int:
        return self._queue.depth

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="sync-client", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while self._running:
            envelope = self._queue.peek()
            if envelope is None:
                time.sleep(5.0)
                continue
            success = self._send(envelope)
            if success:
                self._queue.ack(envelope.envelope_id)
            else:
                self._queue.nack(envelope.envelope_id)
                time.sleep(min(30.0, 2 ** envelope.attempt_count))

    def _send(self, envelope: Any) -> bool:
        if not self._api_url:
            return False
        try:
            url = f"{self._api_url}/api/sync"
            headers = {"Content-Type": "application/json"}
            if self._device_token:
                headers["Authorization"] = f"Bearer {self._device_token}"
            body = json.dumps(envelope.to_dict()).encode("utf-8")
            req = Request(url, data=body, headers=headers, method="POST")
            with urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except HTTPError as e:
            log.warning("Sync HTTP error: %d", e.code)
            return e.code >= 500  # retry server errors
        except (URLError, OSError):
            log.debug("Sync connection error", exc_info=True)
            return False
