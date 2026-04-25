"""Pairing client — webapp→desktop magic-link redemption.

Per ADR-011, the desktop pairs with a Clerk identity by redeeming a
one-time pairing code shown as a QR on the webapp::

    webapp ─ shows QR ──► user scans / types ──► desktop
                                                    │
                                                    ▼
              POST /api/v1/auth/pairing/redeem  (no Authorization)
              { "pairing_code": "ABC-123-XYZ" }
                                                    │
                                                    ▼
              200 { "account": "...", "refresh_token": "rt_..." }
              ── persisted via TokenStore (T050) ──┘

The pairing code IS the authentication: there's no Bearer token to
send (the user has none yet — that's what redemption gets them).

Two payload shapes are accepted by ``parse_pairing_payload`` so the
same ``redeem(payload)`` method handles camera-decoded deep links
*and* manually-typed codes:

  * raw code:   ``"ABC-123-XYZ"``
  * deep link:  ``"lapcoach://pair?code=ABC-123-XYZ"``

Server error shape mapping:

  * 404 → ``not_found``        (unknown / invalid code)
  * 410 → ``already_redeemed`` (one-time use violated)
  * 400 → ``invalid_or_expired``
  * other → ``http_<code>``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from lap_coach_logger.infra.token_store import TokenStore

_PAIRING_ENDPOINT = "/api/v1/auth/pairing/redeem"
_DEEP_LINK_SCHEME = "lapcoach"
_DEEP_LINK_HOST = "pair"

_HTTP_STATUS_TO_ERROR_CODE = {
    400: "invalid_or_expired",
    404: "not_found",
    410: "already_redeemed",
}


@dataclass(frozen=True)
class PairingResult:
    """Typed outcome of a ``PairingClient.redeem`` call."""

    success: bool
    account: str | None = None
    refresh_token: str | None = None
    http_status: int | None = None
    error_code: str = ""
    error_message: str = ""


def parse_pairing_payload(payload: str) -> str:
    """Normalize a pairing payload (raw code or deep link) to a code.

    Raises ``ValueError`` on empty / whitespace-only input or on a
    deep link missing the ``code`` query param.
    """
    if payload is None or not payload.strip():
        raise ValueError("pairing payload is empty")
    text = payload.strip()
    if text.lower().startswith(f"{_DEEP_LINK_SCHEME}://"):
        parts = urlsplit(text)
        codes = parse_qs(parts.query).get("code", [])
        if not codes or not codes[0].strip():
            raise ValueError("deep link is missing 'code' query param")
        return codes[0].strip()
    return text


class PairingClient:
    """Typed HTTP client for the ADR-011 pairing redemption endpoint.

    Parameters
    ----------
    base_url:
        Backend root, e.g. ``"https://api.lapcoach.app"``.
    token_store:
        Optional. When supplied, a successful redemption persists the
        returned ``refresh_token`` via
        ``TokenStore.save_refresh_token`` so subsequent uploads use
        it without a second round trip.
    timeout_s:
        urllib request timeout. Defaults to 30s — the pairing call
        should be fast; a longer timeout just hides server problems.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token_store: TokenStore | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_store = token_store
        self._timeout_s = timeout_s

    def redeem(self, payload: str) -> PairingResult:
        """Exchange a pairing code (or deep link) for a refresh token."""
        try:
            code = parse_pairing_payload(payload)
        except ValueError as exc:
            return PairingResult(
                success=False,
                error_code="invalid_payload",
                error_message=str(exc),
            )

        body = json.dumps({"pairing_code": code}).encode("utf-8")
        url = f"{self._base_url}{_PAIRING_ENDPOINT}"
        req = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=self._timeout_s) as resp:
                status = resp.status
                raw = resp.read()
        except HTTPError as exc:
            return PairingResult(
                success=False,
                http_status=exc.code,
                error_code=_HTTP_STATUS_TO_ERROR_CODE.get(
                    exc.code, f"http_{exc.code}"
                ),
                error_message=str(exc),
            )
        except (URLError, OSError) as exc:
            return PairingResult(
                success=False,
                error_code="connection_error",
                error_message=str(exc),
            )

        if status != 200:
            return PairingResult(
                success=False,
                http_status=status,
                error_code=_HTTP_STATUS_TO_ERROR_CODE.get(
                    status, f"http_{status}"
                ),
            )

        try:
            payload_json = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return PairingResult(
                success=False,
                http_status=status,
                error_code="malformed_response",
                error_message=str(exc),
            )

        account = payload_json.get("account")
        refresh_token = payload_json.get("refresh_token")
        if not account or not refresh_token:
            return PairingResult(
                success=False,
                http_status=status,
                error_code="malformed_response",
                error_message="missing 'account' or 'refresh_token'",
            )

        if self._token_store is not None:
            self._token_store.save_refresh_token(
                account=account, refresh_token=refresh_token
            )

        return PairingResult(
            success=True,
            account=account,
            refresh_token=refresh_token,
            http_status=status,
        )


__all__ = ["PairingClient", "PairingResult", "parse_pairing_payload"]
