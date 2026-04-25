"""T052: ``PairingViewModel`` exposes the "Not paired" empty state to QML.

The Finalize/Upload screen — and any other surface that needs the
user authenticated — binds to this VM. When the keychain has no
refresh token for the configured account, the VM reports
``is_paired = False`` and the QML renders the empty state with a
CTA that calls ``open_pairing_page()`` to open the webapp pairing
page (where the QR is shown). A scanned/typed code reaches the VM
via ``submit_payload()`` which delegates to ``PairingClient`` (T051)
and on success transitions the VM to ``is_paired = True``.

Tests use the real ``PairingClient`` (against a ThreadingHTTPServer
mock) and the real ``TokenStore`` (against an in-memory fake
keyring) so the redemption→keychain→VM-state chain is exercised
end-to-end without touching the network or the OS keychain.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Iterator

import pytest


_PAIRING_URL = "https://lapcoach.app/desktop/pair"


class _PairingHandler(BaseHTTPRequestHandler):
    valid_code: str = "ABC-123"
    response_body: dict[str, str] = {}
    fail_status: int | None = None

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        body = json.loads(raw.decode("utf-8")) if raw else {}
        if type(self).fail_status is not None:
            self.send_response(type(self).fail_status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
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
    _PairingHandler.valid_code = "ABC-123"
    _PairingHandler.fail_status = None
    _PairingHandler.response_body = {
        "account": "theos.eleve@gmail.com",
        "refresh_token": "rt_pair_zzz",
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


def _build_vm(
    pairing_server,
    *,
    fake_keyring: _FakeKeyringModule | None = None,
    known_account: str | None = None,
    url_opener=None,
):
    """Build a real VM wired to a real PairingClient + real TokenStore."""
    from lap_coach_logger.infra.pairing import PairingClient
    from lap_coach_logger.infra.token_store import TokenStore
    from lap_coach_logger.viewmodels.pairing_vm import PairingViewModel

    base_url, _ = pairing_server
    keyring = fake_keyring or _FakeKeyringModule()
    store = TokenStore(keyring_module=keyring)
    client = PairingClient(base_url=base_url, token_store=store)
    vm = PairingViewModel(
        pairing_client=client,
        token_store=store,
        pairing_url=_PAIRING_URL,
        known_account=known_account,
        url_opener=url_opener,
    )
    return vm, store, keyring


# ---------------------------------------------------------------------------
# Empty-state detection
# ---------------------------------------------------------------------------


def test_is_not_paired_when_no_known_account(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server)
    assert vm.is_paired is False
    assert vm.account == ""


def test_is_not_paired_when_known_account_has_no_token(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server, known_account="theos.eleve@gmail.com")
    assert vm.is_paired is False
    assert vm.account == ""


def test_is_paired_when_known_account_already_has_token(pairing_server) -> None:
    """Cold start: cached account name + existing keychain entry → paired."""
    fake_keyring = _FakeKeyringModule()
    fake_keyring.set_password(
        "lap-coach-logger", "theos.eleve@gmail.com", "rt_existing"
    )
    vm, _, _ = _build_vm(
        pairing_server,
        fake_keyring=fake_keyring,
        known_account="theos.eleve@gmail.com",
    )
    assert vm.is_paired is True
    assert vm.account == "theos.eleve@gmail.com"


# ---------------------------------------------------------------------------
# CTA: open the webapp pairing page
# ---------------------------------------------------------------------------


def test_pairing_url_is_exposed_for_qr_cta(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server)
    assert vm.pairing_url == _PAIRING_URL


def test_open_pairing_page_invokes_injected_url_opener(pairing_server) -> None:
    opened: list[str] = []
    vm, _, _ = _build_vm(pairing_server, url_opener=opened.append)
    vm.open_pairing_page()
    assert opened == [_PAIRING_URL]


# ---------------------------------------------------------------------------
# submit_payload: redeem a code from manual entry / scanned QR
# ---------------------------------------------------------------------------


def test_submit_payload_success_transitions_to_paired(pairing_server) -> None:
    vm, store, _ = _build_vm(pairing_server)
    transitions: list[bool] = []
    vm.paired_changed.connect(lambda: transitions.append(vm.is_paired))

    ok = vm.submit_payload("ABC-123")

    assert ok is True
    assert vm.is_paired is True
    assert vm.account == "theos.eleve@gmail.com"
    assert transitions == [True]
    # PairingClient persisted via the same TokenStore; confirm the
    # token landed where the VM later reads from.
    assert store.load_refresh_token("theos.eleve@gmail.com") == "rt_pair_zzz"


def test_submit_payload_failure_keeps_unpaired_and_emits_error(
    pairing_server,
) -> None:
    vm, _, _ = _build_vm(pairing_server)
    failures: list[str] = []
    vm.redemption_failed.connect(failures.append)
    transitions: list[bool] = []
    vm.paired_changed.connect(lambda: transitions.append(vm.is_paired))

    ok = vm.submit_payload("WRONG-CODE")

    assert ok is False
    assert vm.is_paired is False
    assert vm.account == ""
    assert failures == ["not_found"]
    assert transitions == [], "no paired_changed on failure"


def test_submit_payload_invalid_input_emits_invalid_payload(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server)
    failures: list[str] = []
    vm.redemption_failed.connect(failures.append)

    ok = vm.submit_payload("   ")

    assert ok is False
    assert failures == ["invalid_payload"]


def test_submit_payload_accepts_deep_link(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server)
    ok = vm.submit_payload("lapcoach://pair?code=ABC-123")
    assert ok is True
    assert vm.is_paired is True


# ---------------------------------------------------------------------------
# refresh(): re-query the keychain (e.g. after sign-out elsewhere)
# ---------------------------------------------------------------------------


def test_refresh_picks_up_freshly_stored_token(pairing_server) -> None:
    """Pairing might happen out-of-band (e.g. via a tray-menu flow)."""
    fake_keyring = _FakeKeyringModule()
    vm, _, _ = _build_vm(
        pairing_server,
        fake_keyring=fake_keyring,
        known_account="theos.eleve@gmail.com",
    )
    assert vm.is_paired is False

    fake_keyring.set_password(
        "lap-coach-logger", "theos.eleve@gmail.com", "rt_new"
    )
    transitions: list[bool] = []
    vm.paired_changed.connect(lambda: transitions.append(vm.is_paired))

    vm.refresh()

    assert vm.is_paired is True
    assert transitions == [True]


def test_refresh_does_not_emit_when_state_unchanged(pairing_server) -> None:
    vm, _, _ = _build_vm(pairing_server)
    transitions: list[bool] = []
    vm.paired_changed.connect(lambda: transitions.append(vm.is_paired))

    vm.refresh()
    vm.refresh()

    assert transitions == [], "no spurious paired_changed when nothing changed"


def test_refresh_detects_token_cleared_externally(pairing_server) -> None:
    """If another component clears the token, the VM must regress to unpaired."""
    fake_keyring = _FakeKeyringModule()
    fake_keyring.set_password(
        "lap-coach-logger", "theos.eleve@gmail.com", "rt_existing"
    )
    vm, _, _ = _build_vm(
        pairing_server,
        fake_keyring=fake_keyring,
        known_account="theos.eleve@gmail.com",
    )
    assert vm.is_paired is True

    del fake_keyring.store[("lap-coach-logger", "theos.eleve@gmail.com")]
    transitions: list[bool] = []
    vm.paired_changed.connect(lambda: transitions.append(vm.is_paired))

    vm.refresh()

    assert vm.is_paired is False
    assert transitions == [False]
