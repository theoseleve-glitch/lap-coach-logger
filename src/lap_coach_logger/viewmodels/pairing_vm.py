"""Pairing view model — drives the "Not paired" empty state in QML.

The Finalize/Upload screen (and any other surface that needs an
authenticated user) binds to this VM. When the keychain has no
refresh token for the configured account, ``is_paired`` is False
and QML renders the empty state with a CTA that calls
``open_pairing_page()`` to open the webapp pairing page (where the
QR is shown). A scanned/typed code reaches the VM via
``submit_payload()`` which delegates to ``PairingClient`` (T051);
on success the VM transitions to ``is_paired = True``.

Design notes
------------
* ``known_account`` is supplied by the wiring layer at construction
  time. It's the user's last-known account name (typically email).
  When None, the VM is in pristine "never paired" state.
* ``url_opener`` is injected so tests can spy on the CTA without
  pulling in ``QDesktopServices`` (which would also need a
  ``QApplication`` event loop). Defaults to ``webbrowser.open``.
* Plain ``@property`` + ``Signal`` (no ``@Property(notify=...)``)
  matches the existing ``IngestProgressViewModel`` pattern, which
  keeps the VM unit-testable without a ``QApplication``. QML
  consumers connect to the change signals to refresh bindings.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from lap_coach_logger.infra.pairing import PairingClient
from lap_coach_logger.infra.token_store import TokenStore


class PairingViewModel(QObject):
    """Pair-state VM bridging ``TokenStore`` + ``PairingClient`` to QML."""

    # Fires whenever ``is_paired`` flips. UI rebinds is_paired+account.
    paired_changed = Signal()
    # ``error_code`` from PairingResult (e.g. "not_found",
    # "already_redeemed", "invalid_or_expired", "invalid_payload",
    # "connection_error"). UI maps to a user-facing message.
    redemption_failed = Signal(str)
    # Fired on a successful redemption — useful for toasts/analytics.
    redemption_succeeded = Signal()

    def __init__(
        self,
        *,
        pairing_client: PairingClient,
        token_store: TokenStore,
        pairing_url: str,
        known_account: str | None = None,
        url_opener: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._pairing_client = pairing_client
        self._token_store = token_store
        self._pairing_url = pairing_url
        self._account: str = known_account or ""
        self._url_opener = url_opener if url_opener is not None else webbrowser.open
        self._is_paired = self._compute_paired()

    # ------------------------------------------------------------------
    # QML-bindable properties
    # ------------------------------------------------------------------

    @property
    def is_paired(self) -> bool:
        """True iff a refresh token exists for the current account."""
        return self._is_paired

    @property
    def account(self) -> str:
        """The paired account identifier, or "" when not paired."""
        return self._account if self._is_paired else ""

    @property
    def pairing_url(self) -> str:
        """The webapp page that shows the pairing QR (CTA target)."""
        return self._pairing_url

    # ------------------------------------------------------------------
    # Slots / actions
    # ------------------------------------------------------------------

    def open_pairing_page(self) -> None:
        """Invoke the injected URL opener with the pairing URL."""
        self._url_opener(self._pairing_url)

    def submit_payload(self, payload: str) -> bool:
        """Redeem a pairing code (raw or deep link). Returns success."""
        result = self._pairing_client.redeem(payload)
        if result.success and result.account:
            self._account = result.account
            self._update_paired_state()
            self.redemption_succeeded.emit()
            return True
        self.redemption_failed.emit(result.error_code or "unknown_error")
        return False

    def refresh(self) -> None:
        """Re-query the keychain. Use after out-of-band token changes."""
        self._update_paired_state()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _compute_paired(self) -> bool:
        if not self._account:
            return False
        return self._token_store.load_refresh_token(self._account) is not None

    def _update_paired_state(self) -> None:
        new_paired = self._compute_paired()
        if new_paired != self._is_paired:
            self._is_paired = new_paired
            self.paired_changed.emit()


__all__ = ["PairingViewModel"]
