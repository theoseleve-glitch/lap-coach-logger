"""T077: Rules engine — fetch from server, cache to disk.

T076 shipped the parser only. T077 layers on:

- ``RuleBundleHttpClient`` — fetches the compiled bundle from the
  server (Bearer auth, JSON body, hermetic-testable transport).
- ``RuleBundleCache`` — persists the **raw** server payload to disk
  so T078 can sig-verify it later, and re-parses on load.

T077 stops at the building blocks; T078 layers TTL + signature
verification, T090 wires ``fetch_and_cache`` into the app-start
update check. Per the loop directive ("minimal diffs — no scope
creep") none of those land here.

Hermetic HTTP testing pattern mirrors ``test_ingest_client_paths``
so future readers see one consistent shape across the infra
clients.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest

from lap_coach_logger.coaching.rules_engine import (
    RuleBundle,
    RuleBundleCache,
    RuleBundleFetchError,
    RuleBundleHttpClient,
)


# ---------------------------------------------------------------------------
# Hermetic mock server
# ---------------------------------------------------------------------------


class _BundleHandler(BaseHTTPRequestHandler):
    """Mock that returns ``status`` with ``body`` for every GET.

    Records the last request's headers so tests can assert
    Authorization wiring without test-specific hooks.
    """

    status: int = 200
    body: bytes = b"{}"
    content_type: str = "application/json"
    last_auth_header: str | None = None
    get_count: int = 0

    def do_GET(self) -> None:  # noqa: N802
        type(self).get_count += 1
        type(self).last_auth_header = self.headers.get("Authorization")
        self.send_response(type(self).status)
        if type(self).body:
            self.send_header("Content-Type", type(self).content_type)
            self.send_header("Content-Length", str(len(type(self).body)))
            self.end_headers()
            self.wfile.write(type(self).body)
        else:
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


def _minimal_bundle_payload(bundle_id: str = "rules-2026-q1-v1") -> bytes:
    return json.dumps(
        {
            "schema_version": "1.0",
            "bundle_id": bundle_id,
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [
                {
                    "id": "br.late_braking",
                    "category": "braking",
                    "condition": {"type": "feature_threshold"},
                    "insight": {"title": "Brake later"},
                }
            ],
        }
    ).encode("utf-8")


@pytest.fixture
def bundle_server() -> Iterator[tuple[str, type[_BundleHandler]]]:
    _BundleHandler.status = 200
    _BundleHandler.body = _minimal_bundle_payload()
    _BundleHandler.content_type = "application/json"
    _BundleHandler.last_auth_header = None
    _BundleHandler.get_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _BundleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _BundleHandler
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# RuleBundleHttpClient — happy path
# ---------------------------------------------------------------------------


def test_http_client_fetch_returns_parsed_bundle(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    base_url, _ = bundle_server
    client = RuleBundleHttpClient(base_url=base_url)

    bundle, raw_payload = client.fetch(auth_token="t-12345")

    assert isinstance(bundle, RuleBundle)
    assert bundle.bundle_id == "rules-2026-q1-v1"
    assert len(bundle.rules) == 1
    assert isinstance(raw_payload, str)
    assert "rules-2026-q1-v1" in raw_payload  # raw, not the parsed dict


def test_http_client_sends_bearer_authorization_header(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    """T078 sig-verification still requires the Authorization
    header on the fetch — it's how the server scopes the bundle
    to the caller's claims set per ADR-011."""
    base_url, handler = bundle_server
    client = RuleBundleHttpClient(base_url=base_url)

    client.fetch(auth_token="my-access-token")

    assert handler.last_auth_header == "Bearer my-access-token"


def test_http_client_strips_trailing_slash_from_base_url(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    """Otherwise ``base_url + path`` produces ``//api`` and the
    server returns 404. Mirrors the same normalisation IngestClient
    does."""
    base_url, _ = bundle_server
    client = RuleBundleHttpClient(base_url=base_url + "/")

    bundle, _ = client.fetch(auth_token="t")

    assert bundle.bundle_id == "rules-2026-q1-v1"


# ---------------------------------------------------------------------------
# RuleBundleHttpClient — error handling
# ---------------------------------------------------------------------------


def test_http_client_raises_fetch_error_on_4xx(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    """Permanent failure (auth missing/bad, no bundle for tier).
    Caller falls back to cache; that's T089's job, not T077's."""
    base_url, handler = bundle_server
    handler.status = 403
    handler.body = b'{"error": "forbidden"}'
    client = RuleBundleHttpClient(base_url=base_url)

    with pytest.raises(RuleBundleFetchError):
        client.fetch(auth_token="t")


def test_http_client_raises_fetch_error_on_5xx(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    """Server error — we don't retry at this layer (T077 is the
    raw fetch). T089 handles cache fallback. T090 retries on next
    app start."""
    base_url, handler = bundle_server
    handler.status = 503
    handler.body = b'{"error": "service unavailable"}'
    client = RuleBundleHttpClient(base_url=base_url)

    with pytest.raises(RuleBundleFetchError):
        client.fetch(auth_token="t")


def test_http_client_raises_fetch_error_on_malformed_json(
    bundle_server: tuple[str, type[_BundleHandler]],
) -> None:
    """A 200 with bad JSON is a server bug — fail loudly so the
    caller knows not to write the cache. Without this, T078's
    sig-verify would write garbage to disk."""
    base_url, handler = bundle_server
    handler.status = 200
    handler.body = b"{not valid json"
    client = RuleBundleHttpClient(base_url=base_url)

    with pytest.raises(RuleBundleFetchError):
        client.fetch(auth_token="t")


# ---------------------------------------------------------------------------
# RuleBundleCache — round-trip
# ---------------------------------------------------------------------------


def test_cache_save_and_load_round_trip(tmp_path: Path) -> None:
    """The cache stores the *raw* server payload verbatim so T078
    can sig-verify against it byte-for-byte. Round-tripping returns
    a parsed RuleBundle plus the raw payload for downstream use."""
    cache = RuleBundleCache(path=tmp_path / "rules_cache.json")

    raw = _minimal_bundle_payload().decode("utf-8")
    cache.save(raw)

    loaded = cache.load()

    assert loaded is not None
    assert isinstance(loaded.bundle, RuleBundle)
    assert loaded.bundle.bundle_id == "rules-2026-q1-v1"
    assert loaded.raw_payload == raw  # byte-for-byte preserved


def test_cache_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    """First-run / never-fetched-yet — return None so the caller
    can decide between "fetch from server" and "show empty state"."""
    cache = RuleBundleCache(path=tmp_path / "missing.json")

    assert cache.load() is None


def test_cache_load_returns_none_on_corrupt_file(tmp_path: Path) -> None:
    """Disk corruption / partial write → cold start. The caller's
    next move is "fetch from server" — same as a missing file.
    Raising would mean the user can't recover without manually
    deleting the cache file, which is bad UX for an opaque
    in-app cache."""
    cache_path = tmp_path / "corrupt.json"
    cache_path.write_text("{garbage", encoding="utf-8")

    cache = RuleBundleCache(path=cache_path)

    assert cache.load() is None


def test_cache_load_returns_none_when_payload_field_missing(
    tmp_path: Path,
) -> None:
    """Old cache shape (e.g., from a prior version) — treat as
    cold start rather than crashing."""
    cache_path = tmp_path / "old.json"
    cache_path.write_text(json.dumps({"cached_at": "..."}), encoding="utf-8")

    cache = RuleBundleCache(path=cache_path)

    assert cache.load() is None


def test_cache_save_creates_parent_directory(tmp_path: Path) -> None:
    """First-run app-data directory may not exist yet; the cache
    must create it rather than crashing."""
    deeply_nested = tmp_path / "config" / "lap-coach" / "rules" / "cache.json"
    cache = RuleBundleCache(path=deeply_nested)

    cache.save(_minimal_bundle_payload().decode("utf-8"))

    assert deeply_nested.exists()


def test_cache_save_overwrites_existing_file(tmp_path: Path) -> None:
    """A second save (e.g., after server returns a newer bundle)
    must replace the old cache, not append or refuse."""
    cache_path = tmp_path / "rules_cache.json"
    cache = RuleBundleCache(path=cache_path)

    cache.save(_minimal_bundle_payload(bundle_id="old").decode("utf-8"))
    cache.save(_minimal_bundle_payload(bundle_id="new").decode("utf-8"))

    loaded = cache.load()
    assert loaded is not None
    assert loaded.bundle.bundle_id == "new"
