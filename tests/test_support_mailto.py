"""T234: Support email mailto: link builder.

Pins the helper that produces the ``mailto:`` URL the Help menu
opens. Putting this in a pure helper means we can pin the
contract (URL shape, prefilled diagnostic fields, encoding)
without spinning up the Qt menu, AND we can re-use the same URL
in the AboutDialog or first-run consent screen later.

  - ``SUPPORT_EMAIL`` is the canonical address the app sends to.
  - ``build_support_mailto(...)`` returns a string starting with
    ``mailto:<SUPPORT_EMAIL>?...``.
  - The query string carries an informative ``subject`` and a
    ``body`` that already includes the user's app version + OS
    summary so the support reply is useful from the first message.
  - Special characters in those fields are URL-encoded so they
    don't break the mailto handler on Windows.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from lap_coach_logger.diagnostics import support_links as sl


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_support_email_is_lap_coach_racing() -> None:
    """The support inbox is at lap-coach.racing — pinning this
    so a typo in the constant doesn't silently route mail to a
    nonexistent address."""
    assert sl.SUPPORT_EMAIL == "support@lap-coach.racing"


# ---------------------------------------------------------------------------
# build_support_mailto: shape + prefilled fields
# ---------------------------------------------------------------------------


def test_mailto_url_starts_with_mailto_scheme() -> None:
    url = sl.build_support_mailto(app_version="1.2.3", os_summary="Windows 11")
    assert url.startswith("mailto:")


def test_mailto_url_targets_support_address() -> None:
    """The path component (between ``mailto:`` and ``?``) must
    be the canonical support address."""
    url = sl.build_support_mailto(app_version="1.2.3", os_summary="Windows 11")
    parsed = urlsplit(url)
    assert parsed.scheme == "mailto"
    assert parsed.path == sl.SUPPORT_EMAIL


def test_mailto_includes_subject_query_param() -> None:
    """A subject is mandatory — without one, support inboxes
    file the mail under "(no subject)" and triage gets harder."""
    url = sl.build_support_mailto(app_version="1.2.3", os_summary="Windows 11")
    qs = parse_qs(urlsplit(url).query)
    assert "subject" in qs
    assert qs["subject"][0]  # non-empty


def test_mailto_subject_mentions_app_name() -> None:
    """Subject should make it obvious to support staff that
    this is a Lap Coach Logger ticket — they may handle other
    products."""
    url = sl.build_support_mailto(app_version="1.2.3", os_summary="Windows 11")
    qs = parse_qs(urlsplit(url).query)
    assert "Lap Coach Logger" in qs["subject"][0]


def test_mailto_body_includes_app_version() -> None:
    """Prefill app version so the user doesn't have to copy-
    paste from About; support gets a usable repro context
    from the first message."""
    url = sl.build_support_mailto(app_version="2.0.5-beta", os_summary="Windows 11")
    qs = parse_qs(urlsplit(url).query)
    assert "2.0.5-beta" in qs["body"][0]


def test_mailto_body_includes_os_summary() -> None:
    """Prefill OS context for the same reason."""
    url = sl.build_support_mailto(
        app_version="1.0.0", os_summary="Windows 11 (10.0.22631)"
    )
    qs = parse_qs(urlsplit(url).query)
    assert "Windows 11 (10.0.22631)" in qs["body"][0]


def test_mailto_body_has_describe_your_issue_placeholder() -> None:
    """The body should also contain a clear "tell us what
    happened" placeholder so the user knows where to type."""
    url = sl.build_support_mailto(app_version="1.0.0", os_summary="Windows 11")
    qs = parse_qs(urlsplit(url).query)
    body = qs["body"][0].lower()
    assert "describe" in body or "what happened" in body or "issue" in body


# ---------------------------------------------------------------------------
# Encoding: special characters survive
# ---------------------------------------------------------------------------


def test_mailto_encodes_spaces_and_special_chars_in_body() -> None:
    """A version string with a space, an OS summary with parens
    and brackets — everything must round-trip through URL
    encoding so the user's mail client doesn't see a malformed
    URL."""
    url = sl.build_support_mailto(
        app_version="1.0.0 (build 42)",
        os_summary="Windows 11 [10.0.22631.4317]",
    )
    parsed = urlsplit(url)
    qs = parse_qs(parsed.query)
    assert "1.0.0 (build 42)" in qs["body"][0]
    assert "Windows 11 [10.0.22631.4317]" in qs["body"][0]


def test_mailto_does_not_contain_unescaped_newlines_in_query() -> None:
    """Raw \\n in a mailto query breaks the URL on some Windows
    handlers. Body line-breaks must be encoded (the parsed
    body still gets line breaks back)."""
    url = sl.build_support_mailto(
        app_version="1.0.0",
        os_summary="Windows 11",
    )
    # Query portion (after the '?') must not contain a literal
    # newline character.
    query = urlsplit(url).query
    assert "\n" not in query
    assert "\r" not in query


# ---------------------------------------------------------------------------
# Convenience overload: build with auto-detected current context
# ---------------------------------------------------------------------------


def test_build_default_support_mailto_works_without_args() -> None:
    """The Help-menu call site doesn't need to know what to
    pass — there's a zero-arg variant that auto-fills app
    version and OS from the current process."""
    url = sl.build_default_support_mailto()
    assert url.startswith(f"mailto:{sl.SUPPORT_EMAIL}")
    qs = parse_qs(urlsplit(url).query)
    assert "subject" in qs
    assert "body" in qs
