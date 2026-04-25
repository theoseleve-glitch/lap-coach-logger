"""T051: Pairing flow — webapp→desktop magic-link redemption.

Per ADR-011, the desktop pairs with a Clerk account via a one-time
pairing code shown as a QR on the webapp. The desktop either scans
the QR (camera) or accepts a manually-typed code; either path
funnels into ``PairingClient.redeem(payload)`` which:

1. Parses the payload (accepts raw code or ``lapcoach://pair?code=..``).
2. POSTs ``{"pairing_code": "..."}`` to ``/api/v1/auth/pairing/redeem``
   *without* an Authorization header (the pairing code IS the auth).
3. On 200, returns the ``account`` + ``refresh_token`` and — if a
   ``TokenStore`` was injected — persists the refresh token via
   ``TokenStore.save_refresh_token`` so subsequent uploads use it.
4. On 4xx, surfaces a typed error code so the UI can render the
   right "expired" / "already redeemed" / "not found" message.

Tests use a ``ThreadingHTTPServer`` mock for the redemption endpoint
and an in-memory fake keyring for the token-store side. No real
HTTP server, no real keychain.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Iterator

import pytest


_PAIRING_ENDPOINT = "/api/v1/auth/pairing/redeem"


class _PairingHandler(BaseHTTPRequestHandler):
    """Mock that returns canned responses keyed by pairing_code."""

    valid_code: str = "ABC-123-XYZ"
    response_body: dict[str, str] = {}
    fail_status: int | None = None
    last_path: str | None = None
    last_body: dict | None = None
    last_auth_header: str | None = None
    post_count: int = 0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        type(self).post_count += 1
        type(self).last_path = self.path
        type(self).last_auth_header = self.headers.get("Authorization")
        try:
            type(self).last_body = json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            type(self).last_body = None

        if type(self).fail_status is not None:
            self.send_response(type(self).fail_status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        body = type(self).last_body or {}
        if body.get("pairing_code") != type(self).valid_code:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        payload = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def pairing_server() -> Iterator[tuple[str, type[_PairingHandler]]]:
    _PairingHandler.valid_code = "ABC-123-XYZ"
    _PairingHandler.fail_status = None
    _PairingHandler.last_path = None
    _PairingHandler.last_body = None
    _PairingHandler.last_auth_header = None
    _PairingHandler.post_count = 0
    _PairingHandler.response_body = {
        "account": "theos.eleve@gmail.com",
        "refresh_token": "rt_pair_aBcDeF",
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PairingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _PairingHandler
    finally:
        server.shutdown()
        server.server_close()


class _PasswordDeleteError(Exception):
    pass


class _FakeKeyringModule:
    """Mirrors the keyring module-level surface used by TokenStore."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}
        self.errors = SimpleNamespace(PasswordDeleteError=_PasswordDeleteError)

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise _PasswordDeleteError
        del self.store[(service, username)]


# ---------------------------------------------------------------------------
# parse_pairing_payload — accepts raw code or deep link
# ---------------------------------------------------------------------------


def test_parse_payload_accepts_raw_code() -> None:
    from lap_coach_logger.infra.pairing import parse_pairing_payload

    assert parse_pairing_payload("ABC-123-XYZ") == "ABC-123-XYZ"


def test_parse_payload_strips_whitespace() -> None:
    """Manual entry frequently carries trailing newlines / spaces."""
    from lap_coach_logger.infra.pairing import parse_pairing_payload

    assert parse_pairing_payload("  ABC-123-XYZ \n") == "ABC-123-XYZ"


def test_parse_payload_extracts_code_from_deep_link() -> None:
    from lap_coach_logger.infra.pairing import parse_pairing_payload

    assert (
        parse_pairing_payload("lapcoach://pair?code=XYZ-789-QQQ") == "XYZ-789-QQQ"
    )


def test_parse_payload_rejects_empty_input() -> None:
    from lap_coach_logger.infra.pairing import parse_pairing_payload

    with pytest.raises(ValueError):
        parse_pairing_payload("")
    with pytest.raises(ValueError):
        parse_pairing_payload("   ")


def test_parse_payload_rejects_deep_link_without_code() -> None:
    from lap_coach_logger.infra.pairing import parse_pairing_payload

    with pytest.raises(ValueError):
        parse_pairing_payload("lapcoach://pair")


# ---------------------------------------------------------------------------
# PairingClient.redeem — happy path + error mapping
# ---------------------------------------------------------------------------


def test_redeem_returns_account_and_refresh_token_on_200(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, _ = pairing_server
    client = PairingClient(base_url=base_url)

    result = client.redeem("ABC-123-XYZ")

    assert result.success is True, result.error_message
    assert result.account == "theos.eleve@gmail.com"
    assert result.refresh_token == "rt_pair_aBcDeF"
    assert result.error_code == ""


def test_redeem_posts_to_adr_011_pairing_endpoint(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, handler = pairing_server
    client = PairingClient(base_url=base_url)

    client.redeem("ABC-123-XYZ")

    assert handler.last_path == _PAIRING_ENDPOINT
    assert handler.last_body == {"pairing_code": "ABC-123-XYZ"}


def test_redeem_does_not_send_authorization_header(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    """Pairing IS the auth — no bearer token needed (or available yet)."""
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, handler = pairing_server
    client = PairingClient(base_url=base_url)

    client.redeem("ABC-123-XYZ")

    assert handler.last_auth_header is None


def test_redeem_accepts_deep_link_payload(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    """Camera-decoded QR will hand us a deep link, not a raw code."""
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, handler = pairing_server
    client = PairingClient(base_url=base_url)

    result = client.redeem("lapcoach://pair?code=ABC-123-XYZ")

    assert result.success is True
    assert handler.last_body == {"pairing_code": "ABC-123-XYZ"}


def test_redeem_persists_refresh_token_when_token_store_injected(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient
    from lap_coach_logger.infra.token_store import TokenStore

    base_url, _ = pairing_server
    fake_keyring = _FakeKeyringModule()
    store = TokenStore(keyring_module=fake_keyring)
    client = PairingClient(base_url=base_url, token_store=store)

    result = client.redeem("ABC-123-XYZ")

    assert result.success is True
    assert (
        store.load_refresh_token("theos.eleve@gmail.com") == "rt_pair_aBcDeF"
    )


def test_redeem_unknown_code_returns_not_found_error(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, _ = pairing_server
    client = PairingClient(base_url=base_url)

    result = client.redeem("BOGUS-CODE")

    assert result.success is False
    assert result.http_status == 404
    assert result.error_code == "not_found"


def test_redeem_already_redeemed_returns_typed_error(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, handler = pairing_server
    handler.fail_status = 410

    client = PairingClient(base_url=base_url)
    result = client.redeem("ABC-123-XYZ")

    assert result.success is False
    assert result.http_status == 410
    assert result.error_code == "already_redeemed"


def test_redeem_expired_returns_typed_error(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    base_url, handler = pairing_server
    handler.fail_status = 400

    client = PairingClient(base_url=base_url)
    result = client.redeem("ABC-123-XYZ")

    assert result.success is False
    assert result.http_status == 400
    assert result.error_code == "invalid_or_expired"


def test_redeem_does_not_persist_token_on_failure(
    pairing_server: tuple[str, type[_PairingHandler]],
) -> None:
    from lap_coach_logger.infra.pairing import PairingClient
    from lap_coach_logger.infra.token_store import TokenStore

    base_url, handler = pairing_server
    handler.fail_status = 410

    fake_keyring = _FakeKeyringModule()
    store = TokenStore(keyring_module=fake_keyring)
    client = PairingClient(base_url=base_url, token_store=store)

    client.redeem("ABC-123-XYZ")

    assert fake_keyring.store == {}, "no token must be saved on failure"


def test_redeem_connection_error_surfaces_typed_error() -> None:
    from lap_coach_logger.infra.pairing import PairingClient

    client = PairingClient(base_url="http://127.0.0.1:1")  # tcpmux — refused

    result = client.redeem("ABC-123-XYZ")

    assert result.success is False
    assert result.error_code == "connection_error"


def test_redeem_rejects_empty_payload_before_network_call() -> None:
    """Bad input shouldn't waste a round trip."""
    from lap_coach_logger.infra.pairing import PairingClient

    client = PairingClient(base_url="http://127.0.0.1:1")
    result = client.redeem("   ")

    assert result.success is False
    assert result.error_code == "invalid_payload"
    assert result.http_status is None
